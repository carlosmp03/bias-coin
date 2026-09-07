import os
import random
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "bot.db"

load_dotenv(BASE_DIR / ".env")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                action_tokens INTEGER NOT NULL DEFAULT 0,
                flips_total INTEGER NOT NULL DEFAULT 0,
                action_flips INTEGER NOT NULL DEFAULT 0,
                pause_flips INTEGER NOT NULL DEFAULT 0,
                done_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()


def ensure_user(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (user_id)
            VALUES (?)
            """,
            (user_id,),
        )
        conn.commit()


def get_user_stats(user_id: int) -> sqlite3.Row:
    ensure_user(user_id)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    return row


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    ensure_user(user_id)

    text = (
        "🪙 Bias Coin Bot\n\n"
        "Монетка специально смещена в сторону действия:\n"
        "80% — ACTION\n"
        "20% — PAUSE\n\n"
        "Команды:\n"
        "/flip — бросить монетку\n"
        "/done — отметить выполненное действие и получить +1 Action Token\n"
        "/balance — баланс Action Tokens\n"
        "/stats — статистика"
    )

    await update.message.reply_text(text)


async def flip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    ensure_user(user_id)

    is_action = random.random() < 0.8

    with get_connection() as conn:
        if is_action:
            conn.execute(
                """
                UPDATE users
                SET flips_total = flips_total + 1,
                    action_flips = action_flips + 1
                WHERE user_id = ?
                """,
                (user_id,),
            )
        else:
            conn.execute(
                """
                UPDATE users
                SET flips_total = flips_total + 1,
                    pause_flips = pause_flips + 1
                WHERE user_id = ?
                """,
                (user_id,),
            )
        conn.commit()

    if is_action:
        await update.message.reply_text("⚡ ACTION")
    else:
        await update.message.reply_text("☕ PAUSE")


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    ensure_user(user_id)

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET action_tokens = action_tokens + 1,
                done_count = done_count + 1
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()

    stats = get_user_stats(user_id)

    await update.message.reply_text(
        f"✅ Засчитано.\n"
        f"+1 Action Token\n"
        f"Баланс: {stats['action_tokens']}"
    )


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    stats = get_user_stats(user_id)

    await update.message.reply_text(
        f"🪙 Action Tokens: {stats['action_tokens']}"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    stats = get_user_stats(user_id)

    flips_total = stats["flips_total"]
    action_flips = stats["action_flips"]
    pause_flips = stats["pause_flips"]

    if flips_total > 0:
        action_rate = action_flips / flips_total * 100
        pause_rate = pause_flips / flips_total * 100
    else:
        action_rate = 0.0
        pause_rate = 0.0

    text = (
        "📊 Stats\n\n"
        f"Flips: {flips_total}\n"
        f"ACTION: {action_flips} ({action_rate:.1f}%)\n"
        f"PAUSE: {pause_flips} ({pause_rate:.1f}%)\n"
        f"Done: {stats['done_count']}\n"
        f"Action Tokens: {stats['action_tokens']}"
    )

    await update.message.reply_text(text)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Create a .env file from .env.example."
        )

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("flip", flip))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("stats", stats))

    print("Bias Coin Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
