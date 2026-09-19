import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "bot.db")))

DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/Moscow")
DEFAULT_MORNING_TIME = os.getenv("DEFAULT_MORNING_TIME", "09:30")
DEFAULT_EVENING_TIME = os.getenv("DEFAULT_EVENING_TIME", "22:30")

REMINDER_DELAYS_MIN = [10, 15, 20, 180]

QUIET_START = os.getenv("QUIET_START", "00:00")
QUIET_END = os.getenv("QUIET_END", "09:00")

PROBABILITY_SOURCE = "prob-list4-25f"
PROBABILITY_SOURCE_URL = (
    "https://mccme.ru/media/filer_public/92/90/"
    "929062a6-024d-486c-bb24-3b5b7e7fbf0c/prob-list4-25f.pdf"
)
