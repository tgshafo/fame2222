import telebot
from telebot import types

TOKEN = "8341879502:AAEO5qaIQ894Q5cziGoRA963b-yOOqlETCk"
CHANNEL_1_LINK = "https://t.me/famIist"
CHANNEL_2_LINK = "https://t.me/+wUJ5LhK53Us0ZmM6"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    # Создаём клавиатуру
    markup = types.InlineKeyboardMarkup()
    
    # Кнопка 1
    btn1 = types.InlineKeyboardButton("📢 Канал", url=CHANNEL_1_LINK)
    # Кнопка 2
    btn2 = types.InlineKeyboardButton("📢 Канал", url=CHANNEL_2_LINK)
    
    markup.add(btn1, btn2)
    
    text = ("Вас приветствует наш совместный проект sn5ser bot!\n\n"
            "Чтобы получить доступ к боту, подпишитесь на спонсоров:")
    
    bot.send_message(message.chat.id, text, reply_markup=markup)

print("Бот запущен и работает!")
bot.infinity_polling()
