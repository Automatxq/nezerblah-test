import asyncio
import logging
import wikipediaapi
from datetime import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --------------------- НАСТРОЙКИ ---------------------
TOKEN = "8234184501:AAEu77D5t2D1FvzxaOpZ4HyyYAaD9qLHmyw"  # токен от BotFather
ADMIN_CHAT_ID = 5868232737  # ← твой chat_id (чтобы бот знал, кому слать по умолчанию)
SEND_HOUR = 19  # во сколько утра слать (0–23)
SEND_MINUTE = 0

# Русская Википедия
wiki = wikipediaapi.Wikipedia(
    user_agent='DailyWikiBot/1.0 (https://github.com/Automatxq/nezerblah-test; b.v.mikhailovich@gmail.com)',
    language='ru',
    extract_format=wikipediaapi.ExtractFormat.WIKI  # или .HTML, если хочешь форматирование
)

# Хранилище chat_id подписчиков (в реальном проекте лучше в базу: sqlite/json/redis)
subscribers = set([ADMIN_CHAT_ID])  # изначально только ты

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# -----------------------------------------------------

async def get_random_article():
    """Возвращает заголовок, краткое описание и ссылку на случайную статью"""
    while True:
        page = wiki.random(1)  # берём одну случайную страницу
        if not page:
            continue

        if page.exists() and len(page.summary) > 100 and "Википедия:" not in page.title:
            # Пытаемся отфильтровать мусор (служебные страницы, очень короткие и т.п.)
            break

    title = page.title
    summary = page.summary[:700]  # обрезаем, чтобы влезло в сообщение
    if len(page.summary) > 700:
        summary += "..."

    url = page.fullurl

    return title, summary, url


async def daily_random_job(context: ContextTypes.DEFAULT_TYPE):
    """Задача, которая выполняется каждый день"""
    title, summary, url = await get_random_article()

    text = f"✦ <b>Статейку?</b>\n\n<b>{title}</b>\n\n{summary}"

    keyboard = [
        [InlineKeyboardButton("Читать полностью →", url=url)]
    ]
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
            subscribers.discard(chat_id)  # чистим мёртвые чаты


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.add(chat_id)
    await update.message.reply_text(
        "Заменяю Лёню, пока он филонит на заводе 🎲\n"
        "Чтобы отписаться — напиши /stop"
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers.discard(chat_id)
    await update.message.reply_text("Ты отписался от ежедневных статей. До встречи! 👋")


async def random_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /random — получить статью прямо сейчас"""
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


def main():
    app = Application.builder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("random", random_now))

    # Ловим всё остальное (можно потом расширить)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None))

    # Ошибки
    app.add_error_handler(error_handler)

    # Ежедневная рассылка в 9:00
    app.job_queue.run_daily(
        daily_random_job,
        time=time(hour=SEND_HOUR, minute=SEND_MINUTE),
        name="daily_wiki"
    )

    print("Бот запущен. Ожидаю сообщений и ежедневной задачи...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()