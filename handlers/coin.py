import random
from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def flip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    action = random.random() < 0.8
    db.coin(uid, action)
    if action:
        await update.message.reply_text(
            "⚡ ACTION\n\nНе обсуждаем. Сделай следующий физически возможный шаг."
        )
    else:
        await update.message.reply_text(
            "☕ PAUSE\n\nПауза разрешена. Потом возвращаемся к активной задаче."
        )
