from telegram import Update
from telegram.ext import ContextTypes
import database as db
from config import PROBABILITY_SOURCE_URL
from utils import format_minutes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    await update.message.reply_text(
        "🧭 Bias Coin v2 — учебный диспетчер\n\n"
        "Я веду одну активную задачу, запускаю фокус-блок и сам возвращаюсь, "
        "если ты пропал.\n\n"
        "/study — начать\n"
        "/task — текущая задача\n"
        "/tasks — весь листок\n"
        "/done — задача решена\n"
        "/stuck — зафиксировать тупик\n"
        "/pause 15 — пауза\n"
        "/plan — план дня\n"
        "/today — план сегодня\n"
        "/status — состояние\n"
        "/stats — статистика\n"
        "/schedule 09:30 22:30 — утро/вечер\n"
        "/timezone Europe/Moscow — часовой пояс\n"
        "/flip — старая монетка 80/20\n\n"
        f"Листок №4:\n{PROBABILITY_SOURCE_URL}"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    t = db.current_task(uid)
    s = db.active_session(uid)
    if not t:
        await update.message.reply_text("Активной задачи нет. /study")
        return
    text = f"🎯 Задача {t['task_no']}: {t['title']}\nРаздел: {t['topic']}"
    if s:
        text += f"\n\nСессия: {s['status']}, блок {s['duration_minutes']} мин."
        if s["status"] == "waiting":
            text += f"\nСтупень контроля: {s['reminder_stage'] + 1}"
    else:
        text += "\n\nТаймер не запущен."
    await update.message.reply_text(text)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    s = db.stats(uid)
    rate = s["action_flips"]/s["flips_total"]*100 if s["flips_total"] else 0
    await update.message.reply_text(
        "📊 Статистика\n\n"
        f"Листок: {s['done']}/{s['total']} решено\n"
        f"Пропущено: {s['skipped']}\n"
        f"Учебное время: {format_minutes(s['study_minutes'])}\n"
        f"Action Tokens: {s['action_tokens']}\n"
        f"Броски: {s['flips_total']}\n"
        f"ACTION: {s['action_flips']} ({rate:.1f}%)\n"
        f"PAUSE: {s['pause_flips']}"
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    await update.message.reply_text(
        f"🪙 Action Tokens: {db.stats(uid)['action_tokens']}"
    )
