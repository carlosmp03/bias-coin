import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()

DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "bot.db")))

DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/Moscow")
MORNING_TIME = os.getenv("MORNING_TIME", "10:00")
QUIET_START = os.getenv("QUIET_START", "00:30")
QUIET_END = os.getenv("QUIET_END", "09:00")

# После того как человек перестал отвечать.
NAG_DELAYS_MIN = [10, 15, 20, 120]

# Сколько последних событий отдавать модели.
RECENT_EVENTS_LIMIT = 12
