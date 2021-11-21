from typing import Optional

from requests import post
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlmodel import SQLModel, create_engine, Session, Field, select, func, and_
from time import time
from os import rename, mkdir, path
from uuid import uuid4 as uuid

API_SERVER = "http://example.com"
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


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int
    sex: str
    count_records: int = Field(default=0, primary_key=False)
    count_proofed: int = Field(default=0, primary_key=False)


class Learning(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(default=None, foreign_key="user.telegram_id")
    date: int
    voice_uuid: str
    emotion: str
    emotion_feedback: str = Field(default=None)
    emotion_moderate: str = Field(default=None)


def download_voice(message):
    file_info = bot.get_file(message.voice.file_id)

    downloaded_file = bot.download_file(file_info.file_path)

    filename = f'{message.from_user.id}.ogg'

    if not path.isdir(path.join(path.dirname(__file__), "voices")):
        mkdir(path.join(path.dirname(__file__), "voices"))

    with open(path.join(path.dirname(__file__), "voices", filename), 'wb') as new_file:
        new_file.write(downloaded_file)

    return filename


def menu_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    buttons = [
        InlineKeyboardButton(text="⚡ Быстрое распознование", callback_data="fast_recog"),
        InlineKeyboardButton(text="🗣️ Длительное распознавание", callback_data="long_recog"),
        InlineKeyboardButton(text="🧠 Режим обучения модели", callback_data="model_train"),
        InlineKeyboardButton(text="📑 Режим проверки обучения", callback_data="model_checking")
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


def emotions_keyboard(key_command, file_uuid):
    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton(text="😡 Злость", callback_data=f"{key_command} anger {file_uuid}"),
        InlineKeyboardButton(text="🙂 Счастье", callback_data=f"{key_command} happiness {file_uuid}"),
        InlineKeyboardButton(text="😭 Грусть", callback_data=f"{key_command} sadness {file_uuid}"),
        InlineKeyboardButton(text="😄 Энтузиазм", callback_data=f"{key_command} enthusiasm {file_uuid}"),
        InlineKeyboardButton(text="😩 Усталость", callback_data=f"{key_command} tiredness {file_uuid}")
    ]

    keyboard.add(*buttons)

    return keyboard


def sex_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(text="🙎‍♂️ Мужчина", callback_data="sex male"),
        InlineKeyboardButton(text="🙎‍♀️ Женщина", callback_data="sex female"),

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
    bot.answer_callback_query(call.id, show_alert=False)

    session = Session(engine)
    find_user = select(User).where(User.telegram_id == call.from_user.id)
    find_user = session.exec(find_user).one_or_none()
    session.close()

    if find_user is None:
        bot.send_message(
            call.message.chat.id,
            "Прежде чем начать моё обучение, пожалуйста, укажи, ты парень или девушка?"
            "Это единоразовый вопрос, чтобы понять, на чьём голосе я буду обучаться :)",
            reply_markup=sex_keyboard()
        )

    else:
        file_uuid = str(uuid())
        bot.send_message(
            call.message.chat.id,
            "Выбери, какую эмоцию хочешь запечатлить в своем голосе",
            reply_markup=emotions_keyboard("em_train", file_uuid)
        )


@bot.callback_query_handler(func=lambda call: call.data == "model_checking")
def model_checking(call):
    bot.answer_callback_query(call.id, show_alert=False)

    session = Session(engine)
    find_proof = select(Learning).where(and_(Learning.telegram_id != call.message.from_user.id,
                                             Learning.emotion_feedback == None)).order_by(func.random()).limit(1)
    find_proof = session.exec(find_proof).one_or_none()

    if find_proof:
        voice = open(path.join(path.dirname(__file__), "voices", f"{find_proof.voice_uuid}.ogg"), "rb")
        bot.send_voice(call.message.chat.id, voice)
        voice.close()

        bot.send_message(
            call.message.chat.id,
            "Мне нужна твоя помощь! Можешь, пожалуйста, указать, какая эмоция прослеживается "
            "в этом голосовом сообщении?",
            reply_markup=emotions_keyboard("em_proof_ns", find_proof.voice_uuid)
        )

    else:
        bot.send_message(
            call.message.chat.id,
            "Пока нет новых записей голоса для обучения, которые остались неразмеченными! "
            "Возвращайся сюда почаще вновь, чтобы помочь мне обучиться)",
        )

    session.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith("sex"))
def setup_sex(call):
    bot.answer_callback_query(call.id, show_alert=False)
    sex = call.data.split(" ")[1]

    user = User(telegram_id=call.from_user.id, sex=sex)
    session = Session(engine)
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()

    bot.edit_message_text(message_id=call.message.id, chat_id=call.message.chat.id,
                          text=call.message.text)

    file_uuid = str(uuid())
    bot.send_message(
        call.message.chat.id,
        "Выбери, какую эмоцию хочешь запечатлить в своем голосе",
        reply_markup=emotions_keyboard("em_train", file_uuid)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("em_train"))
def pick_emotion_for_train(call):
    bot.answer_callback_query(call.id, show_alert=False)
    emotion, file_uuid = call.data.split(" ")[1:]

    emoji = {"anger": "😡", "happiness": "🙂", "sadness": "😭", "tiredness": "😩", "enthusiasm": "😄"}[emotion]

    bot.edit_message_text(message_id=call.message.id, chat_id=call.message.chat.id,
                          text=f"({emoji}) " + str(call.message.text))

    message = bot.send_message(call.message.chat.id, "Хорошо! А теперь запиши свое голосовое. Постарайся соблюдать "
                                                     "несколько правил:\n\n"
                                                     "* Не молчи) Говори, что-нибудь. А если не знаешь "
                                                     "что говорить, попробуй сказать: `Белый стул стоит в углу`.\n"
                                                     "* Постарайся имеено голосом передать свою эмоцию, которую "
                                                     "ты хочешь записать\n"
                                                     "* Уложись в 3 секунды) Попробуй проверсти это время максимально "
                                                     "содержательно :))")

    bot.register_next_step_handler(message, train_voice_handler, file_uuid=file_uuid, emotion=emotion)


@bot.callback_query_handler(func=lambda call: call.data.startswith("em_proof"))
def proof_emotion_in_voice(call):
    bot.answer_callback_query(call.id, show_alert=False)
    emotion, file_uuid = call.data.split(" ")[1:]

    emoji = {"anger": "😡", "happiness": "🙂", "sadness": "😭", "tiredness": "😩", "enthusiasm": "😄"}[emotion]

    bot.edit_message_text(message_id=call.message.id, chat_id=call.message.chat.id,
                          text=f"({emoji}) " + str(call.message.text))

    session = Session(engine)
    find_voice = select(Learning).where(Learning.voice_uuid == file_uuid)
    find_voice = session.exec(find_voice).one_or_none()

    if find_voice.emotion_feedback is None:
        find_voice.emotion_feedback = emotion
        session.add(find_voice)
        session.commit()

    if emotion == find_voice.emotion:
        find_user = select(User).where(User.telegram_id == call.from_user.id)
        find_user = session.exec(find_user).one_or_none()
        session.add(find_user)
        session.commit()

    session.close()

    if not call.data.startswith("em_proof_ns"):

        bot.send_message(call.message.chat.id, "Спасибо за твоё мнение!")

        file_uuid = str(uuid())
        bot.send_message(
            call.message.chat.id,
            "Выбери, какую эмоцию хочешь запечатлить в своем голосе",
            reply_markup=emotions_keyboard("em_train", file_uuid)
        )

    else:
        session = Session(engine)
        find_proof = select(Learning).where(and_(Learning.telegram_id != call.message.from_user.id,
                                                 Learning.emotion_feedback == None)).order_by(func.random()).limit(1)
        find_proof = session.exec(find_proof).one_or_none()

        if find_proof:
            voice = open(path.join(path.dirname(__file__), "voices", f"{find_proof.voice_uuid}.ogg"), "rb")
            bot.send_voice(call.message.chat.id, voice)
            voice.close()

            bot.send_message(call.message.chat.id, "Спасибо за твоё мнение!")

            bot.send_message(
                call.message.chat.id,
                "Мне нужна твоя помощь! Можешь, пожалуйста, указать, какая эмоция прослеживается "
                "в этом голосовом сообщении?",
                reply_markup=emotions_keyboard("em_proof_ns", find_proof.voice_uuid)
            )

        else:
            bot.send_message(call.message.chat.id,
                         "Пока нет новых записей голоса для обучения, которые остались неразмеченными! "
                         "Возвращайся сюда почаще вновь, чтобы помочь мне обучиться)\n"
                         "Чтобы вернуться к выбору режима - нажми на /start"
                         )


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
                          text=f"(👍) " + str(call.message.text))

    bot.send_message(call.message.chat.id, "Вот и славно! Спасибо за помощь в усовершенствовании)\n"
                     "Если снова захочешь распознать, напиши в чате /start")


@bot.callback_query_handler(func=lambda call: call.data.startswith("dislike"))
def decline_recognition(call):
    bot.answer_callback_query(call.id, show_alert=False)
    file_uuid = call.data.split("_")[1]

    bot.edit_message_text(message_id=call.message.id, chat_id=call.message.chat.id,
                          text=f"(👎) " + str(call.message.text))

    bot.send_message(call.message.chat.id, "Не получилось? Хорошо, что у меня есть ты :)\n"
                     "Если тебе не сложно, укажи, какую эмоцию ты испытывал в момент записи голоса, нажав на "
                     "соответствующую кнопку", reply_markup=emotions_keyboard("em_recognize", file_uuid))


@bot.callback_query_handler(func=lambda call: call.data.startswith("em_recognize"))
def pick_emotion(call):
    bot.answer_callback_query(call.id, show_alert=False)
    emotion, file_uuid = call.data.split(" ")[1:]

    emoji = {"anger": "😡", "happiness": "🙂", "sadness": "😭", "tiredness": "😩", "enthusiasm": "😄"}[emotion]

    session = Session(engine)
    find_voice = select(Training).where(Training.voice_uuid == file_uuid)
    find_voice = session.exec(find_voice).one_or_none()

    if find_voice:
        find_voice.user_result = emotion
        session.add(find_voice)
        session.commit()
        session.close()

    bot.edit_message_text(message_id=call.message.id, chat_id=call.message.chat.id,
                          text=f"({emoji}) " + str(call.message.text))

    bot.send_message(call.message.chat.id, "Вот и славно! Спасибо за помощь в усовершенствовании)\n"
                                           "Если снова захочешь распознать, напиши в чате /start")


def long_voice_processing(message):
    if getattr(message, "voice", None) is None:
        return True

    filename = download_voice(message)

    response = post(API_SERVER + "/get_emotion_timeline", files={"audio.ogg": open(path.join(path.dirname(__file__), "voices", filename), "rb").read()})

    try:
        r_json = response.json()
    except Exception as e:
        bot.send_message(message.chat.id, "Произошла внутренняя ошибка сервера: **500**\nПожалуйста, повторите запрос",
                         parse_mode="MARKDOWN")
        return False

    filename_new = r_json["response"]["file_id"] + ".ogg"
    rename(path.join(path.dirname(__file__), "voices", filename), path.join(path.dirname(__file__), "voices", filename_new))

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


def short_voice_processing(message):
    if getattr(message, "voice", None) is None:
        return True

    filename = download_voice(message)

    response = post(API_SERVER + "/get_emotion", files={"audio.ogg": open(path.join(path.dirname(__file__), "voices", filename), "rb").read()})

    try:
        r_json = response.json()
    except Exception as e:
        bot.send_message(message.chat.id, "Произошла внутренняя ошибка сервера: **500**\nПожалуйста, повторите запрос",
                         parse_mode="MARKDOWN")
        return False

    filename_new = r_json["response"]["file_id"] + ".ogg"
    rename(path.join(path.dirname(__file__), "voices", filename), path.join(path.dirname(__file__), "voices", filename_new))

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


def train_voice_handler(message, file_uuid, emotion):
    if getattr(message, "voice", None) is None:
        return True

    filename = download_voice(message)
    filename_new = file_uuid + ".ogg"

    bot.send_message(message.chat.id, "Окей, спасибо!")
    rename(path.join(path.dirname(__file__), "voices", filename), path.join(path.dirname(__file__), "voices", filename_new))

    session = Session(engine)
    voice_train = Learning(
        telegram_id=message.from_user.id,
        date=time(),
        voice_uuid=file_uuid,
        emotion=emotion
    )
    session.add(voice_train)
    session.commit()
    session.refresh(voice_train)

    find_user = select(User).where(User.telegram_id == message.from_user.id)
    find_user = session.exec(find_user).one_or_none()

    find_user.count_records += 1
    session.add(find_user)
    session.commit()
    session.refresh(find_user)

    find_proof = select(Learning).where(and_(Learning.telegram_id != message.from_user.id,
                                             Learning.emotion_feedback == None)).order_by(func.random()).limit(1)
    find_proof = session.exec(find_proof).one_or_none()

    if find_proof:
        voice = open(path.join(path.dirname(__file__), "voices", f"{find_proof.voice_uuid}.ogg"), "rb")
        bot.send_voice(message.chat.id, voice)
        voice.close()

        bot.send_message(
            message.chat.id,
            "Мне нужна твоя помощь! Можешь, пожалуйста, указать, какая эмоция прослеживается "
            "в этом голосовом сообщении?",
            reply_markup=emotions_keyboard("em_proof", find_proof.voice_uuid)
        )

    else:
        bot.send_message(message.chat.id,
            "Пока нет новых записей голоса для обучения, которые остались неразмеченными! "
            "Возвращайся сюда почаще вновь, чтобы помочь мне обучиться)\n"
            "Чтобы вернуться к выбору режима - нажми на /start"
             )

        file_uuid = str(uuid())
        bot.send_message(
            message.chat.id,
            "Выбери, какую эмоцию хочешь запечатлить в своем голосе",
            reply_markup=emotions_keyboard("em_train", file_uuid)
        )

    session.close()


SQLModel.metadata.create_all(engine)
bot.infinity_polling()
