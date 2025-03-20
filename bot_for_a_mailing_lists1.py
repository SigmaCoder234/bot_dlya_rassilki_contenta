import json
import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties
import os

# Токен бота
API_TOKEN = 'ТОКЕН ВАШЕГО БОТА'

# Список админов
ADMIN_IDS = [1020290414]

# Инициализация бота
bot = Bot(
    token=API_TOKEN,
    session=AiohttpSession(),
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

router = Router()
dp.include_router(router)

# если файлов нет, то они создаются автоматически при первом запуске
SUBSCRIBERS_FILE = "subscribers.json"
USER_DATA_FILE = "user_data.json"
LAST_MESSAGES_FILE = "last_messages.json"

if not os.path.exists(LAST_MESSAGES_FILE):
    with open(LAST_MESSAGES_FILE, "w", encoding="utf-8") as file:
        json.dump({}, file)

def load_json(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(file_name, data):
    with open(file_name, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def load_subscribers():
    return set(load_json(SUBSCRIBERS_FILE))

def save_subscribers(subscribers):
    save_json(SUBSCRIBERS_FILE, list(subscribers))

video_subscribers = load_subscribers()
last_messages = load_json(LAST_MESSAGES_FILE)

def is_admin(user_id):
    return user_id in ADMIN_IDS

@router.message(Command("start"))
async def send_welcome(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться на рассылку", callback_data="subscribe_video")]
        ]
    )
    user = message.from_user
    all_users = load_json(USER_DATA_FILE)

    if str(user.id) not in all_users:
        all_users[str(user.id)] = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name or "Без фамилии",
            "username": user.username or "Без ника"
        }
        save_json(USER_DATA_FILE, all_users)

    await message.answer("Привет! Нажми на кнопку, чтобы подписаться на рассылку.", reply_markup=keyboard)

@router.callback_query(lambda c: c.data == "subscribe_video")
async def process_video_subscription(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in video_subscribers:
        video_subscribers.add(user_id)
        save_subscribers(video_subscribers)
        await callback_query.answer("Вы подписались на рассылку!")
    else:
        await callback_query.answer("Вы уже подписаны на рассылку!")

@router.message(Command("stop"))
async def stop_handler(message: Message):
    user_id = message.from_user.id
    if user_id in video_subscribers:
        video_subscribers.remove(user_id)
        save_subscribers(video_subscribers)
        await message.answer("Вы отписались от рассылки!")
    else:
        await message.answer("Вы не были подписаны на рассылку.")

@router.message(Command("send_video"))
async def send_video_to_subscribers(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("У вас нет прав на использование этой команды.")
        return

    if not video_subscribers:
        await message.reply("Нет подписчиков для рассылки.")
        return

    if message.reply_to_message:
        content = message.reply_to_message
        for user_id in video_subscribers:
            try:
                sent_message = None
                if content.video:
                    sent_message = await bot.send_video(chat_id=user_id, video=content.video.file_id, caption=content.html_text or None)
                elif content.photo:
                    sent_message = await bot.send_photo(chat_id=user_id, photo=content.photo[-1].file_id, caption=content.html_text or None)
                elif content.text:
                    sent_message = await bot.send_message(chat_id=user_id, text=content.html_text or None)
                else:
                    await message.reply("Сообщение не содержит поддерживаемого контента.")
                    return
                if sent_message:
                    last_messages[str(user_id)] = sent_message.message_id
                    save_json(LAST_MESSAGES_FILE, last_messages)
            except Exception as e:
                print(f"Ошибка при отправке пользователю {user_id}: {e}")
    else:
        await message.reply("Ответьте на сообщение с медиа или текстом для рассылки.")

@router.message(Command("del_last"))
async def delete_last_message(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("У вас нет прав на использование этой команды.")
        return

    if not last_messages:
        await message.reply("Нет данных о последнем отправленном сообщении.")
        return

    for user_id, message_id in list(last_messages.items()):
        try:
            await bot.delete_message(chat_id=user_id, message_id=message_id)
            del last_messages[user_id]
        except Exception as e:
            print(f"Ошибка при удалении сообщения для пользователя {user_id}: {e}")

    save_json(LAST_MESSAGES_FILE, last_messages)
    await message.reply("Последнее отправленное сообщение удалено у всех подписчиков.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())