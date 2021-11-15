from typing import Optional

from requests import post
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlmodel import SQLModel, create_engine, Session, Field, select
from time import time
from os import rename

API_SERVER = "http://example.org"
bot = telebot.TeleBot('token', threaded=False)
engine = create_engine("sqlite:///socialcode_voice.sqlite")

ENTHUSIASM = """По твоим голосовым могу сказать, что у тебя хороший настрой, энтузиазм в тебе кипит!"""
HAPPINESS = """Пока слушал твои голосовые, понял, что ты испытываешь радость! Это прекрасно! Я тоже рад за тебя!"""
SADNESS = """Ох, по твоим голосовым сообщениям слышу, что ты грустишь. Иногда такое бывает и можно погрустить, главное, не задерживайся в этом состоянии. Если что, вспоминай полезные техники управления эмоциями!"""
TIREDNESS = """Ой, слышу твой голос и там звучит усталость. Сделай паузу хотя бы на минуту, сделай несколько глубоких вдохов и выдохов, а потом вспомни хотя бы один способ, как можно зарядить себя энергией в ближайшее время!"""
ANGER = """По твоему голосу могу сказать, что ты злился, когда записывал мне голосовое. Подумай, с чем может быть связана эта эмоция?"""

WELCOME_TEXT = """Привет! Я учусь лучше распознавать эмоции! Выбери режим, в котором хочешь распознать свою эмоцию :)"""


class Training(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int
    date: int
    voice_uuid: str
    model_result: str
    user_result: Optional[str] = Field(default=None)


def menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(text="Быстрое распознование", callback_data="fast_recog"),
        InlineKeyboardButton(text="Длительное распознавание", callback_data="long_recog"),
        InlineKeyboardButton(text="Режим обучения модели", callback_data="model_train")
    ]

    keyboard.add(*buttons)

    return keyboard


def feedback_keyboard(file_uuid):
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(text="👍", callback_data=f"like_{file_uuid}"),
        InlineKeyboardButton(text="👎", callback_data=f"dislike_{file_uuid}"),
    ]

    keyboard.add(*buttons)

    return keyboard


def correct_answer_keyboard(file_uuid):
    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton(text="😡", callback_data=f"em anger {file_uuid}"),
        InlineKeyboardButton(text="🙂", callback_data=f"em happiness {file_uuid}"),
        InlineKeyboardButton(text="😭", callback_data=f"em sadness {file_uuid}"),
        InlineKeyboardButton(text="😄", callback_data=f"em enthusiasm {file_uuid}"),
        InlineKeyboardButton(text="😩", callback_data=f"em tiredness {file_uuid}")
    ]

    keyboard.add(*buttons)

    return keyboard


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, WELCOME_TEXT, reply_markup=menu_keyboard())


@bot.callback_query_handler(func=lambda call: call.data == "fast_recog")
def fast_recognition(call):
    bot.answer_callback_query(call.id, show_alert=False)

    message = bot.send_message(call.message.chat.id, "Пришли мне фрагмент своего голосового сообщения\n"
                                   "Распознавание в этом режиме будет более точным, если сообщение "
                                   "будет длится не более 3 секунд.")

    bot.register_next_step_handler(message, short_voice_processing)


@bot.callback_query_handler(func=lambda call: call.data == "long_recog")
def long_recognition(call):
    bot.answer_callback_query(call.id, show_alert=False)

    message = bot.send_message(call.message.chat.id, "Пришли мне фрагмент своего голосового сообщения\n"
                                                     "После распознания эмоций я отправлю тебе сообщение, "
                                                     "в котором по таймкодам я размечу, какие эмоции смог уловить "
                                                     "в твоём голосе)")

    bot.register_next_step_handler(message, long_voice_processing)


@bot.callback_query_handler(func=lambda call: call.data == "model_train")
def model_training(call):
    bot.answer_callback_query(call.id, text="Скоро станет доступно!...")


@bot.callback_query_handler(func=lambda call: call.data.startswith("like"))
def accept_recognition(call):
    bot.answer_callback_query(call.id, show_alert=False)
    file_uuid = call.data.split("_")[1]

    session = Session(engine)
    find_voice = select(Training).where(Training.voice_uuid == file_uuid)
    find_voice = session.exec(find_voice).one_or_none()

    if find_voice:
        find_voice.user_result = find_voice.model_result
        session.add(find_voice)
        session.commit()
        session.close()

    bot.edit_message_text(message_id=call.message.id, chat_id=call.message.chat.id,
                          text=call.message.text)

    bot.send_message(call.message.chat.id, "Вот и славно! Спасибо за помощь в усовершенствовании)\n"
                     "Если снова захочешь распознать, напиши в чате /start")


@bot.callback_query_handler(func=lambda call: call.data.startswith("dislike"))
def decline_recognition(call):
    bot.answer_callback_query(call.id, show_alert=False)
    file_uuid = call.data.split("_")[1]

    bot.edit_message_text(message_id=call.message.id, chat_id=call.message.chat.id,
                          text=call.message.text)

    bot.send_message(call.message.chat.id, "Не получилось? Хорошо, что у меня есть ты :)\n"
                     "Если тебе не сложно, укажи, какую эмоцию ты испытывал в момент записи голоса, нажав на "
                     "соответствующую кнопку", reply_markup=correct_answer_keyboard(file_uuid))


@bot.callback_query_handler(func=lambda call: call.data.startswith("em"))
def pick_emotion(call):
    bot.answer_callback_query(call.id, show_alert=False)
    emotion, file_uuid = call.data.split(" ")[1:]

    session = Session(engine)
    find_voice = select(Training).where(Training.voice_uuid == file_uuid)
    find_voice = session.exec(find_voice).one_or_none()

    if find_voice:
        find_voice.user_result = emotion
        session.add(find_voice)
        session.commit()
        session.close()

    bot.edit_message_text(message_id=call.message.id, chat_id=call.message.chat.id,
                          text=call.message.text)

    bot.send_message(call.message.chat.id, "Вот и славно! Спасибо за помощь в усовершенствовании)\n"
                                           "Если снова захочешь распознать, напиши в чате /start")


@bot.message_handler(content_types=["voice"])
def long_voice_processing(message):
    file_info = bot.get_file(message.voice.file_id)

    downloaded_file = bot.download_file(file_info.file_path)

    filename = f'{message.from_user.id}.ogg'
    with open(filename, 'wb') as new_file:
        new_file.write(downloaded_file)

    response = post(API_SERVER + "/get_emotion_timeline", files={"audio.ogg": open(filename, "rb").read()})

    try:
        r_json = response.json()
    except Exception as e:
        bot.send_message(message.chat.id, "Произошла внутренняя ошибка сервера: **500**\nПожалуйста, повторите запрос",
                         parse_mode="MARKDOWN")
        return False

    filename_new = r_json["response"]["file_id"] + ".ogg"
    rename(filename, filename_new)

    emotion_switch = {
        "anger": "ЗЛОСТЬ",
        "happiness": "СЧАСТЬЕ",
        "tiredness": "УСТАЛОСТЬ",
        "enthusiasm": "ЭНТУЗИАЗМ",
        "sadness": "ГРУСТЬ"
    }

    int_to_time = lambda x: f"{str(x // 60).zfill(2)}:{str(x % 60).zfill(2)}"
    emotions = r_json["response"]["emotions"]
    e_response = [f"{int_to_time(int(x['time_rate'] // int(22050 * 2.5) * 2.5))} -- {emotion_switch[x['emotion']]}" for x in emotions]

    bot.send_message(message.chat.id, "\n".join(e_response), parse_mode="MARKDOWN")


@bot.message_handler(content_types=["voice"])
def short_voice_processing(message):
    file_info = bot.get_file(message.voice.file_id)

    downloaded_file = bot.download_file(file_info.file_path)

    filename = f'{message.from_user.id}.ogg'
    with open(filename, 'wb') as new_file:
        new_file.write(downloaded_file)

    response = post(API_SERVER + "/get_emotion", files={"audio.ogg": open(filename, "rb").read()})

    try:
        r_json = response.json()
    except Exception as e:
        bot.send_message(message.chat.id, "Произошла внутренняя ошибка сервера: **500**\nПожалуйста, повторите запрос",
                         parse_mode="MARKDOWN")
        return False

    filename_new = r_json["response"]["file_id"] + ".ogg"
    rename(filename, filename_new)

    emotion = r_json["response"]["emotion"]

    emotion_switch = {
        "anger": ("ЗЛОСТЬ", ANGER),
        "happiness": ("СЧАСТЬЕ", HAPPINESS),
        "tiredness": ("УСТАЛОСТЬ", TIREDNESS),
        "enthusiasm": ("ЭНТУЗИАЗМ", ENTHUSIASM),
        "sadness": ("ГРУСТЬ", SADNESS)
    }[emotion]

    bot.send_message(message.chat.id, f"{emotion_switch[0]}\n\n{emotion_switch[1]}", reply_markup=feedback_keyboard(
        file_uuid=r_json["response"]["file_id"]
    ))

    session = Session(engine)
    voice = Training(
        telegram_id=message.from_user.id,
        date=time(),
        voice_uuid=r_json["response"]["file_id"],
        model_result=emotion
    )
    session.add(voice)
    session.commit()
    session.close()


SQLModel.metadata.create_all(engine)
bot.infinity_polling()
