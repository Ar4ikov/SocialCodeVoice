from requests import post
import telebot

API_SERVER = "http://example.org"

'''/загружаем бота/'''
bot = telebot.TeleBot('token', threaded=True)
'''//находим нашего бота по токену'''

# keyboard1 = telebot.types.ReplyKeyboardMarkup(True, True)
# keyboard1.row('hi', 'bye')
'''//подгружаем клавиатуру. Ответы на выбор. Правда правда - для адаптации размера и скрытия при ответе'''


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, WELCOME_TEXT)


'''//бот отвечает на команды'''
WELCOME_TEXT = """Привет! Я учусь лучше распознавать  эмоции! Нажимай кнопку с микрофоном и запиши мне голосовое сообщение!"""
BYE_TEXT = """Увидимся вновь :)"""

ENTHUSIASM = """По твоим голосовым могу сказать, что у тебя хороший настрой, энтузиазм в тебе кипит!"""
HAPPINESS = """Пока слушал твои голосовые, понял, что ты испытываешь радость! Это прекрасно! Я тоже рад за тебя!"""
SADNESS = """Ох, по твоим голосовым сообщениям слышу, что ты грустишь. Иногда такое бывает и можно погрустить, главное, не задерживайся в этом состоянии. Если что, вспоминай полезные техники управления эмоциями!"""
TIREDNESS = """Ой, слышу твой голос и там звучит усталость. Сделай паузу хотя бы на минуту, сделай несколько глубоких вдохов и выдохов, а потом вспомни хотя бы один способ, как можно зарядить себя энергией в ближайшее время!"""
ANGER = """По твоему голосу могу сказать, что ты злился, когда записывал мне голосовое. Подумай, с чем может быть связана эта эмоция?"""

# @bot.message_handler(content_types=['text'])
# def send_text(message):
#     if message.text.lower() == 'hi':
#         bot.send_message(message.chat.id, WELCOME_TEXT)
#     elif message.text.lower() == 'bye':
#         bot.send_message(message.chat.id, BYE_TEXT)


'''//бот отвечает на сообщения'''


@bot.message_handler(content_types=['voice'])
def voice_processing(message):
    file_info = bot.get_file(message.voice.file_id)

    downloaded_file = bot.download_file(file_info.file_path)
    with open('new_file.ogg', 'wb') as new_file:
        new_file.write(downloaded_file)

    response = post(API_SERVER + "/get_emotion_timeline", files={"audio.ogg": open("new_file.ogg", "rb").read()})

    try:
        r_json = response.json()
    except Exception as e:
        bot.send_message(message.chat.id, "Произошла внутренняя ошибка сервера: **500**\nПожалуйста, повторите запрос")
        return False

    int_to_time = lambda x: f"{str(x // 60).zfill(2)}:{str(x % 60).zfill(2)}"
    emotions = r_json["response"]["emotions"]
    e_response = [f"{int_to_time(int(x['time_rate'] // int(22050 * 2.5) * 2.5))} -- {x['emotion']}" for x in emotions]
    bot.send_message(message.chat.id, "\n".join(e_response))

    # emotions_switch = {
    #     "happiness": HAPPINESS,
    #     "anger": ANGER,
    #     "tiredness": TIREDNESS,
    #     "sadness": SADNESS,
    #     "enthusiasm": ENTHUSIASM
    # }
    # bot.send_message(message.chat.id, emotions_switch[r_json["response"]["emotion"].split("_")[1]])


bot.polling(none_stop=True)
'''//это проверка нового сообщения'''
