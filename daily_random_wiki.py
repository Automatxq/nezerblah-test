import asyncio
import logging
import wikipediaapi
from datetime import time
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import requests
import json
import os

SUBSCRIBERS_FILE = "subscribers.json"  # файл в корне проекта

# Функции загрузки/сохранения
def load_subscribers():
    if os.path.exists(SUBSCRIBERS_FILE):
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data)
        except Exception as e:
            print(f"Ошибка загрузки подписчиков: {e}")
    # Если файла нет — стартуем с твоего ADMIN_CHAT_ID
    return set([ADMIN_CHAT_ID])

def save_subscribers():
    try:
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(subscribers), f)
        print(f"Подписчики сохранены: {list(subscribers)}")
    except Exception as e:
        print(f"Ошибка сохранения подписчиков: {e}")

# --------------------- НАСТРОЙКИ ---------------------
TOKEN = "8234184501:AAEu77D5t2D1FvzxaOpZ4HyyYAaD9qLHmyw"  # токен от BotFather
ADMIN_CHAT_ID = -1003753027344                           # группа или личка
SEND_HOUR = 9
SEND_MINUTE = 30

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Русская Википедия
wiki = wikipediaapi.Wikipedia(
    user_agent='DailyRandomWikiBot/1.0 (https://github.com/Automatxq/nezerblah-test; b.v.mikhailovich@gmail.com)',
    language='ru',
    extract_format=wikipediaapi.ExtractFormat.WIKI
)

# Хранилище подписчиков (в продакшене → файл / база)
subscribers = load_subscribers()
print(f"Загружено подписчиков при старте: {list(subscribers)}")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------

async def get_random_article():
    """Возвращает заголовок, краткое описание и ссылку на случайную статью"""
    # Твой User-Agent из wiki (тот же самый, чтобы Wikimedia был счастлив)
    headers = {
        "User-Agent": 'DailyRandomWikiBot/1.0 (https://github.com/Automatxq/nezerblah-test; b.v.mikhailovich@gmail.com)'
    }

    while True:
        api_url = "https://ru.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "list": "random",
            "rnnamespace": 0,      # только основные статьи
            "rnlimit": 1
        }

        response = requests.get(api_url, params=params, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"Ошибка API: статус {response.status_code}, текст: {response.text[:200]}")
            continue  # попробуем заново

        try:
            data = response.json()
        except Exception as e:
            print(f"Не удалось распарсить JSON: {e}, ответ: {response.text[:200]}")
            continue

        if "query" not in data or "random" not in data["query"] or not data["query"]["random"]:
            print("Плохой ответ от API:", data)
            continue

        title = data["query"]["random"][0]["title"]
        page = wiki.page(title)

        if page.exists() and len(page.summary) > 100 and "Википедия:" not in page.title:
            break

    summary = page.summary[:700]
    if len(page.summary) > 700:
        summary += "..."

    url = page.fullurl

    return title, summary, url

async def daily_random_job(context: ContextTypes.DEFAULT_TYPE):
    """Ежедневная задача"""
    title, summary, url = await get_random_article()

    text = f"✦ <b>Статейку?</b>\n\n<b>{title}</b>\n\n{summary}"

    keyboard = [[InlineKeyboardButton("Читать полностью →", url=url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    for chat_id in list(subscribers):
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                disable_web_page_preview=False
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить в {chat_id}: {e}")
            subscribers.discard(chat_id)

            async def daily_random_job(context: ContextTypes.DEFAULT_TYPE):
                """Ежедневная задача"""
                print("=== ДЖОБ СРАБОТАЛ! ===")  # ← добавь
                print("Текущие подписчики:", list(subscribers))  # ← сколько и какие чаты

                title, summary, url = await get_random_article()
                print("Получили статью:", title)  # ← проверим, что статья вообще пришла
                print("Ссылка:", url)

                text = f"✦ <b>Статейку?</b>\n\n<b>{title}</b>\n\n{summary}"

                keyboard = [[InlineKeyboardButton("Читать полностью →", url=url)]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                for chat_id in list(subscribers):
                    print(f"Пытаюсь отправить в чат {chat_id}...")  # ← логируем каждый
                    try:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            parse_mode="HTML",
                            reply_markup=reply_markup,
                            disable_web_page_preview=False
                        )
                        print(f"Успешно отправлено в {chat_id}")
                    except Exception as e:
                        print(f"ОШИБКА отправки в {chat_id}: {e}")  # ← точная ошибка
                        logger.warning(f"Не удалось отправить в {chat_id}: {e}")
                        subscribers.discard(chat_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in subscribers:
        subscribers.add(chat_id)
        save_subscribers()
        await update.message.reply_text(
            "Заменяю Лёню, пока он филонит на заводе 🎲\n"
            "Теперь каждый день в 09:30 прилетит статейка!\n"
            "Отписаться — /stop"
        )
    else:
        await update.message.reply_text("Ты уже в списке 😏")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        subscribers.discard(chat_id)
        save_subscribers()
        await update.message.reply_text("Отписался. Если соскучишься — /start 👋")
    else:
        await update.message.reply_text("Ты и так не подписан 😂")

async def random_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title, summary, url = await get_random_article()

    text = f"<b>{title}</b>\n\n{summary}"
    keyboard = [[InlineKeyboardButton("Читать →", url=url)]]

    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=False
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling an update: {context.error}")

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автоматически подписываем группу, если бота добавили"""
    if update.message and update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:  # это именно наш бот добавлен
                chat_id = update.effective_chat.id
                if chat_id not in subscribers:
                    subscribers.add(chat_id)
                    save_subscribers()
                    await update.message.reply_text(
                        "Всем привет! 😎\n"
                        "Теперь каждый день в 09:30 буду кидать случайную статью из Википедии.\n"
                        "Чтобы отписаться — /stop"
                    )
                break
def main():
    app = Application.builder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("random", random_now))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))

    # Ловим остальное
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None))

    # Ошибки
    app.add_error_handler(error_handler)

    # Ежедневная рассылка
    send_time = time(hour=SEND_HOUR, minute=SEND_MINUTE, tzinfo=MOSCOW_TZ)

    app.job_queue.run_daily(
        daily_random_job,
        time=send_time,
        name="daily_wiki"
    )



    print("Бот запущен. Ожидаю сообщений и ежедневной задачи...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()