import logging
from datetime import timedelta

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import database as db
from agent import decide
from config import TELEGRAM_BOT_TOKEN
from keyboards import checkin_keyboard, nag_keyboard, proposed_keyboard
from scheduler import watchdog
from database import utc_now

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


def _focus_minutes(value):
    return max(5, min(180, int(value or 25)))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, update.effective_chat.id)

    text = (
        "Привет. Я теперь не меню с командами.\n\n"
        "Напиши мне обычным текстом, что тебе надо сделать. Например:\n"
        "«Сегодня надо теорвер и GRE, но я ничего не начал».\n\n"
        "Я выберу ближайшее действие, зафиксирую его и вернусь проверить, "
        "сделал ли ты его."
    )
    db.log_event(user.id, "assistant", "start", text)
    await update.message.reply_text(text)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    db.reset_agent(uid)
    await update.message.reply_text(
        "Контекст агента очищен. Что сейчас надо сделать?"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message.text.strip()

    db.ensure_user(uid, chat_id)
    db.log_event(uid, "user", "message", message)

    try:
        decision = decide(uid, message)
    except Exception as exc:
        log.exception("Agent call failed")
        await update.message.reply_text(
            "Нейронка сейчас не ответила. Сам бот жив.\n\n"
            "Напиши ещё раз через минуту. Если повторится — посмотрим Railway logs."
        )
        return

    if decision.memory_to_save:
        db.save_memory(uid, decision.memory_to_save)

    action = decision.action
    task = (decision.task or "").strip()

    if action == "done":
        finished = db.complete_commitment(uid)
        if finished:
            reply = decision.reply or (
                f"Готово. «{finished['text']}» закрыто. Что дальше?"
            )
        else:
            reply = decision.reply or "Активной задачи не было. Что делаем сейчас?"
        db.log_event(uid, "assistant", "done", reply)
        await update.message.reply_text(reply)
        return

    if action == "cancel":
        cancelled = db.cancel_current(uid)
        reply = decision.reply or (
            "Окей, снимаю эту задачу. Что тогда реально делаем?"
        )
        db.log_event(uid, "assistant", "cancel", reply)
        await update.message.reply_text(reply)
        return

    if action == "status":
        c = db.active_commitment(uid)
        s = db.active_session(uid)
        if c:
            reply = decision.reply or f"Сейчас висит: {c['text']}"
            if s:
                reply += f"\nБлок: {s['focus_minutes']} мин, статус {s['status']}."
        else:
            reply = decision.reply or "Сейчас ничего не зафиксировано."
        db.log_event(uid, "assistant", "status", reply)
        await update.message.reply_text(reply)
        return

    if action == "snooze":
        c = db.active_commitment(uid)
        if not c and task:
            cid = db.create_commitment(uid, task, status="proposed")
            c = db.active_commitment(uid)
        if c:
            delay = max(1, min(1440, int(decision.delay_minutes or 15)))
            due = utc_now() + timedelta(minutes=delay)
            db.add_reminder(uid, c["id"], due.isoformat(), kind="start")
            reply = decision.reply or (
                f"Окей. Вернусь через {delay} минут к «{c['text']}»."
            )
            db.log_event(uid, "assistant", "snooze", reply)
            await update.message.reply_text(reply)
        else:
            reply = decision.reply or "Что именно мне напомнить?"
            db.log_event(uid, "assistant", "reply", reply)
            await update.message.reply_text(reply)
        return

    if action == "start":
        c = db.active_commitment(uid)
        if task and (not c or c["text"].strip().lower() != task.lower()):
            cid = db.create_commitment(uid, task, status="active")
            c = db.active_commitment(uid)
        elif c:
            cid = c["id"]
            db.activate_commitment(cid)
        else:
            # Model asked to start but gave no task.
            reply = decision.reply or "Что именно начинаем?"
            db.log_event(uid, "assistant", "reply", reply)
            await update.message.reply_text(reply)
            return

        minutes = _focus_minutes(decision.focus_minutes)
        due = utc_now() + timedelta(minutes=minutes)
        db.start_session(uid, c["id"], minutes, due.isoformat())

        reply = decision.reply or (
            f"Начали: «{c['text']}».\n\n"
            f"{minutes} минут. Потом я сам вернусь."
        )
        db.log_event(uid, "assistant", "start_focus", reply)
        await update.message.reply_text(reply)
        return

    if action == "propose":
        if not task:
            reply = decision.reply or "Сформулируй одно дело, которое надо сделать."
            db.log_event(uid, "assistant", "reply", reply)
            await update.message.reply_text(reply)
            return

        db.create_commitment(uid, task, status="proposed")
        reply = decision.reply or f"Первое действие: «{task}». Начинаем?"
        db.log_event(uid, "assistant", "propose", reply)
        await update.message.reply_text(reply, reply_markup=proposed_keyboard())
        return

    # Pure conversation.
    reply = decision.reply
    db.log_event(uid, "assistant", "reply", reply)
    await update.message.reply_text(reply)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    db.ensure_user(uid, q.message.chat_id)
    action = q.data.split(":", 1)[1]
    c = db.active_commitment(uid)
    s = db.active_session(uid)

    if action == "start":
        if not c:
            await q.message.reply_text("Задача потерялась. Напиши, что надо сделать.")
            return
        minutes = 25
        due = utc_now() + timedelta(minutes=minutes)
        db.start_session(uid, c["id"], minutes, due.isoformat())
        text = f"▶️ Поехали. «{c['text']}» — {minutes} минут. Я сам вернусь."
        db.log_event(uid, "assistant", "start_focus", text)
        await q.message.reply_text(text)
        return

    if action == "start10":
        if not c:
            await q.message.reply_text("Что делаем? Напиши одним сообщением.")
            return
        minutes = 10
        due = utc_now() + timedelta(minutes=minutes)
        if s:
            db.set_session_working(s["id"], minutes, due.isoformat())
        else:
            db.start_session(uid, c["id"], minutes, due.isoformat())
        text = f"⚡ Только 10 минут на «{c['text']}». Начали."
        db.log_event(uid, "assistant", "start_focus", text)
        await q.message.reply_text(text)
        return

    if action in ("later15", "later20"):
        if not c:
            await q.message.reply_text("Нечего откладывать. Что надо сделать?")
            return
        delay = 15 if action == "later15" else 20
        due = utc_now() + timedelta(minutes=delay)
        db.add_reminder(uid, c["id"], due.isoformat(), kind="start")
        text = f"Окей. Через {delay} минут вернусь к «{c['text']}»."
        db.log_event(uid, "assistant", "snooze", text)
        await q.message.reply_text(text)
        return

    if action == "done":
        finished = db.complete_commitment(uid)
        if finished:
            text = f"✅ «{finished['text']}» закрыто. Что следующее?"
        else:
            text = "Активной задачи уже нет. Что делаем дальше?"
        db.log_event(uid, "assistant", "done", text)
        await q.message.reply_text(text)
        return

    if action == "more15":
        if not c:
            await q.message.reply_text("Активной задачи нет.")
            return
        due = utc_now() + timedelta(minutes=15)
        if s:
            db.set_session_working(s["id"], 15, due.isoformat())
        else:
            db.start_session(uid, c["id"], 15, due.isoformat())
        text = f"➕ Ещё 15 минут на «{c['text']}». Потом проверю."
        db.log_event(uid, "assistant", "continue", text)
        await q.message.reply_text(text)
        return

    if action == "notdone":
        if not c:
            await q.message.reply_text("Окей. Что тогда надо сделать?")
            return
        text = (
            f"Тогда не считаем это провалом. Задача всё ещё одна:\n\n"
            f"«{c['text']}»\n\nБерём 10 минут?"
        )
        if s:
            db.set_session_waiting(
                s["id"],
                (utc_now() + timedelta(minutes=10)).isoformat(),
                nag_stage=0,
            )
        db.log_event(uid, "assistant", "not_done", text)
        await q.message.reply_text(text, reply_markup=nag_keyboard())
        return

    if action == "cancel":
        cancelled = db.cancel_current(uid)
        text = (
            f"Снял «{cancelled['text']}». Что реально делаем вместо этого?"
            if cancelled else
            "Окей. Что тогда реально надо сделать?"
        )
        db.log_event(uid, "assistant", "cancel", text)
        await q.message.reply_text(text)


async def post_init(app: Application):
    # Menu intentionally tiny.
    await app.bot.set_my_commands([
        BotCommand("start", "начать разговор"),
        BotCommand("reset", "сбросить контекст агента"),
    ])

    if app.job_queue is None:
        raise RuntimeError(
            "JobQueue unavailable. Install python-telegram-bot[job-queue]."
        )
    app.job_queue.run_repeating(watchdog, interval=30, first=5)


async def error_handler(update, context):
    log.exception("Unhandled exception", exc_info=context.error)


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")

    db.init_db()

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CallbackQueryHandler(button, pattern=r"^do:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    print("Bias Coin v4 simple agent is running...")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
