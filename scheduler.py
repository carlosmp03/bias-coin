from datetime import datetime, timedelta, timezone
from telegram.ext import ContextTypes
import database as db
from config import QUIET_END, QUIET_START, REMINDER_DELAYS_MIN
from keyboards import checkin_keyboard, minimum_keyboard, morning_keyboard
from utils import is_after_hhmm, is_quiet_time, local_now

def dt(value):
    return datetime.fromisoformat(value)

async def send(context, chat_id, text, **kwargs):
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        return True
    except Exception as e:
        print(f"send failed chat={chat_id}: {e}")
        return False

async def check_sessions(context):
    now = datetime.now(timezone.utc)
    for s in db.active_sessions():
        if is_quiet_time(local_now(s["timezone"]), QUIET_START, QUIET_END):
            continue

        if s["status"] == "working" and dt(s["due_at"]) <= now:
            if await send(
                context, s["chat_id"],
                f"⏰ Блок по задаче {s['task_no']} закончился.\n\nЧто реально произошло?",
                reply_markup=checkin_keyboard()
            ):
                db.session_waiting(
                    s["id"],
                    (now+timedelta(minutes=REMINDER_DELAYS_MIN[0])).isoformat(),
                    0
                )
            continue

        if s["status"] == "snoozed":
            if s["next_ping_at"] and dt(s["next_ping_at"]) <= now:
                if await send(
                    context, s["chat_id"],
                    f"☕ Пауза закончилась. Задача {s['task_no']} никуда не делась.\n\n"
                    "Нужны только первые 10 минут.",
                    reply_markup=minimum_keyboard()
                ):
                    db.session_waiting(
                        s["id"],
                        (now+timedelta(minutes=REMINDER_DELAYS_MIN[0])).isoformat(),
                        0
                    )
            continue

        if s["status"] != "waiting":
            continue
        if not s["next_ping_at"] or dt(s["next_ping_at"]) > now:
            continue

        stage = int(s["reminder_stage"])
        if stage == 0:
            text = (
                f"👀 Ты не ответил по задаче {s['task_no']}.\n\n"
                "Мне нужен статус, а не идеальный результат."
            )
            kb = checkin_keyboard()
        elif stage == 1:
            text = (
                f"⚠️ Задача {s['task_no']} всё ещё висит.\n\n"
                "Выбери действие сейчас."
            )
            kb = minimum_keyboard()
        elif stage == 2:
            text = (
                f"🧱 Уменьшаю требование: задача {s['task_no']}, "
                "10 минут без переключений."
            )
            kb = minimum_keyboard()
        else:
            text = (
                f"🔁 Возвращаю задачу {s['task_no']}.\n\n"
                "10 минут, /stuck или /done."
            )
            kb = minimum_keyboard()

        if await send(context, s["chat_id"], text, reply_markup=kb):
            new_stage = min(stage+1, 3)
            delay = REMINDER_DELAYS_MIN[min(new_stage, len(REMINDER_DELAYS_MIN)-1)]
            db.advance_reminder(
                s["id"], new_stage, (now+timedelta(minutes=delay)).isoformat()
            )

async def check_daily(context):
    for u in db.users():
        uid, chat_id = u["user_id"], u["chat_id"]
        now_local = local_now(u["timezone"])
        date = now_local.date().isoformat()

        if is_after_hhmm(now_local, u["morning_time"]) and \
           not db.notification_sent(uid, date, "morning"):
            p = db.plan(uid, date)
            if p:
                text = (
                    "🌅 План уже есть:\n\n"
                    f"1. {p['main_goal']}\n"
                    f"2. {p['secondary_goal']}\n"
                    f"📚 {p['study_goal']}\n\n"
                    "Не перепланируем. Начинаем."
                )
            else:
                text = (
                    "🌅 Доброе утро. До начала хаоса зафиксируем день.\n\n"
                    "Одно главное дело, одно второстепенное и одна учебная цель."
                )
            if await send(context, chat_id, text, reply_markup=morning_keyboard()):
                db.mark_notification(uid, date, "morning")

        if is_after_hhmm(now_local, u["evening_time"]) and \
           not db.notification_sent(uid, date, "evening"):
            s = db.stats(uid)
            t = db.current_task(uid)
            text = (
                "🌙 Вечерний контроль.\n\n"
                f"Листок: {s['done']}/{s['total']} решено.\n"
                f"Учебное время: {s['study_minutes']} мин."
            )
            if t:
                text += f"\n\nНезакрытая задача: {t['task_no']} — {t['title']}."
            text += "\n\n/today — сверить план. /study — ещё один блок."
            if await send(context, chat_id, text):
                db.mark_notification(uid, date, "evening")

async def watchdog(context: ContextTypes.DEFAULT_TYPE):
    await check_sessions(context)
    await check_daily(context)
