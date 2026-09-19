from datetime import timedelta
from telegram import Update
from telegram.ext import ContextTypes
import database as db
from config import PROBABILITY_SOURCE_URL
from keyboards import focus_keyboard, continue_keyboard, minimum_keyboard
from utils import utc_now

def task_text(t):
    return f"📚 Листок 4 — задача {t['task_no']}\n{t['title']}\nРаздел: {t['topic']}"

async def study(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    t = db.next_task(uid)
    if not t:
        await update.message.reply_text("🎉 Нерешённых задач не осталось.")
        return
    if db.active_session(uid):
        await update.message.reply_text(task_text(t) + "\n\nСессия уже активна. /status")
        return
    await update.message.reply_text(
        task_text(t) +
        "\n\nВыбирай блок. После него я потребую отчёт; если исчезнешь — вернусь сам.",
        reply_markup=focus_keyboard()
    )

async def study_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    db.ensure_user(uid, q.message.chat_id)
    t = db.next_task(uid)
    if not t:
        await q.message.reply_text("Нерешённых задач нет.")
        return
    await q.message.reply_text(task_text(t) + "\n\nВыбирай блок:", reply_markup=focus_keyboard())

async def focus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    db.ensure_user(uid, q.message.chat_id)
    minutes = int(q.data.split(":")[1])
    t = db.next_task(uid)
    if not t:
        await q.message.reply_text("Нерешённых задач нет.")
        return
    due = utc_now() + timedelta(minutes=minutes)
    db.create_session(uid, t["id"], minutes, due.isoformat())
    await q.message.reply_text(
        f"▶️ Старт: задача {t['task_no']}, {minutes} мин.\n\n"
        "Не переключайся. Если упёрся — выпиши, во что именно."
    )

async def task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    t = db.next_task(uid)
    if not t:
        await update.message.reply_text("Нерешённых задач нет.")
        return
    await update.message.reply_text(task_text(t) + f"\n\nИсточник:\n{PROBABILITY_SOURCE_URL}")

async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    rows = db.all_tasks(uid)
    symbols = {"todo":"⬜","done":"✅","skipped":"⏭"}
    lines = ["📋 Листок 4"]
    topic = None
    for r in rows:
        if r["topic"] != topic:
            topic = r["topic"]
            lines.append(f"\n{topic}")
        lines.append(f"{symbols.get(r['status'],'•')} {r['task_no']}. {r['title']}")
    await update.message.reply_text("\n".join(lines))

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    credited = db.credit_session(uid)
    t = db.complete_task(uid)
    if not t:
        await update.message.reply_text("Активной задачи нет.")
        return
    extra = f" Зачтено: +{credited} мин." if credited else ""
    await update.message.reply_text(
        f"✅ Задача {t['task_no']} закрыта. +1 Action Token.{extra}\n\n"
        "Когда готов к следующей: /study"
    )

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    db.ensure_user(uid, q.message.chat_id)
    action = q.data.split(":")[1]

    if action == "done":
        credited = db.credit_session(uid)
        t = db.complete_task(uid)
        if t:
            await q.message.reply_text(
                f"✅ Задача {t['task_no']} закрыта. +1 токен. +{credited} мин."
            )
        return

    if action == "progress":
        credited = db.credit_session(uid)
        await q.message.reply_text(
            f"Хорошо. +{credited} мин зачтено. Продолжаем ту же задачу.",
            reply_markup=continue_keyboard()
        )
        return

    if action == "stuck":
        credited = db.credit_session(uid)
        db.set_state(uid, "awaiting_attempt")
        await q.message.reply_text(
            f"+{credited} мин зачтено.\n\n"
            "Напиши ОДНИМ сообщением:\n"
            "1) что уже сделал;\n"
            "2) точное место, где перестал понимать.\n\n"
            "Без попытки новую задачу не открываю."
        )
        return

    if action == "not_worked":
        s = db.active_session(uid)
        if s:
            db.session_snoozed(s["id"], (utc_now()+timedelta(minutes=10)).isoformat())
        await q.message.reply_text(
            "Не засчитываю блок. Не спасаем весь день — только вход в работу.",
            reply_markup=minimum_keyboard()
        )

async def continue_focus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    db.ensure_user(uid, q.message.chat_id)
    minutes = int(q.data.split(":")[1])
    t = db.current_task(uid)
    if not t:
        await q.message.reply_text("Активной задачи нет. /study")
        return
    due = utc_now()+timedelta(minutes=minutes)
    s = db.active_session(uid)
    if s:
        db.session_working(s["id"], due.isoformat(), minutes)
    else:
        db.create_session(uid, t["id"], minutes, due.isoformat())
    await q.message.reply_text(f"▶️ Ещё {minutes} мин на задачу {t['task_no']}.")

async def pause_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    minutes = int(q.data.split(":")[1])
    s = db.active_session(uid)
    if not s:
        await q.message.reply_text("Активной сессии нет.")
        return
    db.session_snoozed(s["id"], (utc_now()+timedelta(minutes=minutes)).isoformat())
    await q.message.reply_text(f"☕ Пауза {minutes} мин. Я сам вернусь.")

async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    minutes = 15
    if context.args:
        try:
            minutes = max(1, min(180, int(context.args[0])))
        except ValueError:
            await update.message.reply_text("Формат: /pause 15")
            return
    s = db.active_session(uid)
    if not s:
        await update.message.reply_text("Активной сессии нет.")
        return
    db.session_snoozed(s["id"], (utc_now()+timedelta(minutes=minutes)).isoformat())
    await update.message.reply_text(f"☕ Пауза {minutes} мин. Я вернусь сам.")

async def stuck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    if not db.current_task(uid):
        await update.message.reply_text("Сначала /study")
        return
    db.credit_session(uid)
    db.set_state(uid, "awaiting_attempt")
    await update.message.reply_text(
        "Пиши попытку одним сообщением: что сделано и где конкретно тупик. "
        "«Ничего не понимаю» не считается."
    )

async def attempt_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = db.get_user(uid)
    if not u or u["state"] != "awaiting_attempt":
        return
    text = update.message.text.strip()
    if len(text) < 15:
        await update.message.reply_text(
            "Слишком мало. Нужна формула/идея и конкретная точка тупика."
        )
        return
    if not db.save_attempt(uid, text):
        await update.message.reply_text("Активная задача потерялась. /study")
        return
    await update.message.reply_text(
        "🧱 Попытка сохранена.\n\n"
        "Теперь сделай ещё один минимальный ход: выпиши определение, известные "
        "величины или точное утверждение, которое нужно доказать.",
        reply_markup=continue_keyboard()
    )

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    reason = " ".join(context.args).strip()
    if len(reason) < 5:
        await update.message.reply_text(
            "Формат: /skip причина\nНапример: /skip нужна теорема, которую ещё не проходил"
        )
        return
    t = db.skip_task(uid)
    if not t:
        await update.message.reply_text("Активной задачи нет.")
        return
    await update.message.reply_text(
        f"⏭ Задача {t['task_no']} пропущена, но не решена.\nПричина: {reason}"
    )

async def reopen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db.ensure_user(uid, update.effective_chat.id)
    await update.message.reply_text(
        f"Вернул пропущенных задач: {db.reopen_skipped(uid)}."
    )
