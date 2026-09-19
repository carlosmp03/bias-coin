from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler, CommandHandler, ContextTypes, ConversationHandler,
    MessageHandler, filters,
)
import database as db
from utils import local_now, valid_hhmm

MAIN, SECONDARY, STUDY = range(3)

def today_date(uid):
    return local_now(db.get_user(uid)["timezone"]).date().isoformat()

async def plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("Главное дело дня — одно. Напиши:")
    else:
        await update.message.reply_text("Главное дело дня — одно. Напиши:")
    return MAIN

async def got_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["main"] = update.message.text.strip()
    await update.message.reply_text("Второстепенное дело:")
    return SECONDARY

async def got_secondary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["secondary"] = update.message.text.strip()
    await update.message.reply_text(
        "Учебная цель. Лучше измеримая: «решить задачи 1–3 листка 4»."
    )
    return STUDY

async def got_study(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    study = update.message.text.strip()
    db.upsert_plan(uid, today_date(uid), context.user_data["main"],
                   context.user_data["secondary"], study)
    await update.message.reply_text(
        "План сохранён.\n\n"
        f"1. {context.user_data['main']}\n"
        f"2. {context.user_data['secondary']}\n"
        f"📚 {study}\n\n"
        "Теперь не улучшаем план. Выполняем. /study"
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    date = today_date(uid)
    p = db.plan(uid, date)
    if not p:
        await update.message.reply_text("Плана на сегодня нет. /plan")
        return
    await update.message.reply_text(
        f"🗓 {date}\n\n1. {p['main_goal']}\n2. {p['secondary_goal']}\n📚 {p['study_goal']}"
    )

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    if len(context.args) != 2:
        u = db.get_user(uid)
        await update.message.reply_text(
            f"Формат: /schedule 09:30 22:30\nСейчас: {u['morning_time']} / {u['evening_time']}"
        )
        return
    m, e = context.args
    if not valid_hhmm(m) or not valid_hhmm(e):
        await update.message.reply_text("Нужен формат HH:MM.")
        return
    db.set_schedule(uid, m, e)
    await update.message.reply_text(f"Утро: {m}. Вечер: {e}.")

async def timezone_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    if len(context.args) != 1:
        await update.message.reply_text(
            f"Формат: /timezone Europe/Moscow\nСейчас: {db.get_user(uid)['timezone']}"
        )
        return
    name = context.args[0]
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError:
        await update.message.reply_text("Такой часовой пояс не найден.")
        return
    db.set_timezone(uid, name)
    await update.message.reply_text(f"Часовой пояс: {name}")

def conversation():
    return ConversationHandler(
        entry_points=[
            CommandHandler("plan", plan_start),
            CallbackQueryHandler(plan_start, pattern=r"^plan:start$")
        ],
        states={
            MAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_main)],
            SECONDARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_secondary)],
            STUDY: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_study)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
