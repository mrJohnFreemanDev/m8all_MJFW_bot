import logging
import random
import os
import time
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from gtts import gTTS

# Load token
load_dotenv("all.env")
TOKEN = os.getenv("BOT_TOKEN")

# Logging config
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
for noisy_logger in ["httpx", "apscheduler", "telegram", "telegram.ext", "telegram.request"]:
    logging.getLogger(noisy_logger).setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

# Ответы
RESPONSES_EN = [
    "😊 It is certain.", "✨ It is decidedly so.", "👍 Without a doubt.",
    "✅ Yes – definitely.", "👍 You may rely on it.", "😊 As I see it, yes.",
    "✅ Most likely.", "✨ Outlook good.", "😊 Yes.", "🔮 Signs point to yes.",
    "🤔 Reply hazy, try again.", "🕰️ Ask again later.", "🤐 Better not tell you now.",
    "🌀 Cannot predict now.", "🔄 Concentrate and ask again.",
    "🚫 Don’t count on it.", "🙅 My reply is no.", "😞 My sources say no.",
    "❌ Outlook not so good.", "😐 Very doubtful."
]

RESPONSES_RU = [
    "😊 Без сомнений.", "✨ Определённо да.", "👍 Несомненно.",
    "✅ Да – абсолютно.", "👍 Можешь на это положиться.", "😊 Как я вижу — да.",
    "✅ Скорее всего.", "✨ Перспективы хорошие.", "😊 Да.", "🔮 Знаки говорят — да.",
    "🤔 Ответ туманен, попробуй снова.", "🕰️ Спроси позже.", "🤐 Лучше не говорить сейчас.",
    "🌀 Сейчас не могу предсказать.", "🔄 Сконцентрируйся и спроси снова.",
    "🚫 Не рассчитывай на это.", "🙅 Мой ответ — нет.", "😞 По моим данным — нет.",
    "❌ Перспективы не очень.", "😐 Очень сомнительно."
]

user_timestamps = {}

def get_language(update: Update) -> str:
    lang_code = (update.effective_user.language_code or "en").lower()
    return "ru" if lang_code.startswith("ru") else "en"

def get_keyboard(lang: str):
    if lang == "ru":
        buttons = [["🔮 Спросить Шар Судьбы", "ℹ️ О Боте", "❔ Как использовать"]]
    else:
        buttons = [["🔮 Ask the Magic Ball", "ℹ️ About", "❔ How It Works"]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_language(update)
    keyboard = get_keyboard(lang)
    text = (
        "🎱 Добро пожаловать в *Magic 8 Ball by MJFW*!\n"
        "Задай вопрос с ответом «да» или «нет», и я предскажу твою судьбу."
        if lang == "ru" else
        "🎱 Welcome to *Magic 8 Ball by MJFW*!\n"
        "Ask me a yes-or-no question, and I will reveal your fate."
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_language(update)
    text = (
        "🔮 Этот бот имитирует классический шар судьбы — Magic 8 Ball.\n"
        "Создан с заботой: *Ivan Mudriakov / MJFW*"
        if lang == "ru" else
        "🔮 This bot simulates the classic fortune-telling toy — Magic 8 Ball.\n"
        "Created with care by *Ivan Mudriakov / MJFW*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def how_to_use(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_language(update)
    text = (
        "❔ Просто задай вопрос, который требует ответа «да» или «нет».\n"
        "Например: *Сегодня пойдет дождь?*"
        if lang == "ru" else
        "❔ Just ask a yes-or-no question.\n"
        "Example: *Will it rain today?*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        lang = get_language(update)
        message = update.message.text.strip()
        user_id = update.effective_user.id
        username = update.effective_user.first_name

        if message in ["🔮 Спросить Шар Судьбы", "🔮 Ask the Magic Ball"]:
            await start(update, context)
            return
        elif message in ["ℹ️ О Боте", "ℹ️ About"]:
            await about(update, context)
            return
        elif message in ["❔ Как использовать", "❔ How It Works"]:
            await how_to_use(update, context)
            return

        now = time.time()
        if now - user_timestamps.get(user_id, 0) < 10:
            await update.message.reply_text(
                "⏱ Подожди немного перед следующим вопросом." if lang == "ru"
                else "⏱ Please wait a bit before asking again.")
            return
        user_timestamps[user_id] = now

        if "?" not in message:
            await update.message.reply_text(
                "❓ Пожалуйста, задай вопрос с вопросительным знаком." if lang == "ru"
                else "❓ Please ask a *yes or no* question ending with a question mark.",
                parse_mode="Markdown")
            return

        answer = random.choice(RESPONSES_RU if lang == "ru" else RESPONSES_EN)
        logger.info(f"[{username} | {user_id}] asked: {message} → Answer: {answer}")

        # Папка голосов
        voice_dir = Path("voices")
        voice_dir.mkdir(exist_ok=True)

        # Пути к файлам
        mp3_path = voice_dir / f"voice_{user_id}.mp3"
        ogg_path = voice_dir / f"voice_{user_id}.ogg"

        # Генерация TTS без эмодзи
        tts_text = ''.join(char for char in answer if char.isalnum() or char.isspace())
        tts = gTTS(text=tts_text, lang=lang)
        tts.save(str(mp3_path))

        # Конвертация
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(mp3_path),
            "-ar", "24000",
            "-ac", "1",
            "-c:a", "libopus",
            str(ogg_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Отправка и удаление
        with open(ogg_path, "rb") as voice:
            await update.message.reply_voice(voice)

        await update.message.reply_text(f"🎱 {answer}")

        # Удаляем оба файла
        mp3_path.unlink(missing_ok=True)
        ogg_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Error: {e}")

async def ignore_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Only text questions are supported.")

def main():
    if not TOKEN:
        logger.error("BOT_TOKEN missing!")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("howtouse", how_to_use))

    app.add_handler(MessageHandler(
        filters.ATTACHMENT |
        filters.VIDEO |
        filters.PHOTO |
        filters.AUDIO |
        filters.VOICE |
        filters.VIDEO_NOTE |
        filters.Sticker.ALL |
        filters.Document.ALL,
        ignore_content
    ))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
