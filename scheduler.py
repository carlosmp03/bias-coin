from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram.ext import ContextTypes

import database as db
from config import MORNING_TIME, NAG_DELAYS_MIN
from keyboards import checkin_keyboard, nag_keyboard, proposed_keyboard


def now_utc():
    return datetime.now(timezone.utc)


def parse_iso(value):
    return datetime.fromisoformat(value)


def zone(name):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def hhmm_after(now_local, hhmm):
    h, m = map(int, hhmm.split(":"))
    target = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
    return now_local >= target


def quiet(now_local, start_text, end_text):
    sh, sm = map(int, start_text.split(":"))
    eh, em = map(int, end_text.split(":"))
    current = now_local.hour * 60 + now_local.minute
    start = sh * 60 + sm
    end = eh * 60 + em
    if start < end:
        return start <= current < end
    return current >= start or current < end


async def safe_send(context, chat_id, text, **kwargs):
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        return True
    except Exception as exc:
        print(f"send failed chat={chat_id}: {exc}")
        return False


async def process_reminders(context):
    now = now_utc()
    for r in db.due_reminders(now.isoformat()):
        local = now.astimezone(zone(r["timezone"]))
        if quiet(local, r["quiet_start"], r["quiet_end"]):
            continue

        text = r["commitment_text"] or "то, что ты собирался сделать"
        ok = await safe_send(
            context,
            r["chat_id"],
            f"⏰ Время. Ты собирался: {text}\n\nНачал?",
            reply_markup=proposed_keyboard(),
        )
        if ok:
            db.mark_reminder_sent(r["id"])
            db.log_event(r["user_id"], "assistant", "reminder",
                         f"Напомнил начать: {text}")


async def process_sessions(context):
    now = now_utc()

    for s in db.all_active_sessions():
        local = now.astimezone(zone(s["timezone"]))
        if quiet(local, s["quiet_start"], s["quiet_end"]):
            continue

        if s["status"] == "working" and parse_iso(s["due_at"]) <= now:
            ok = await safe_send(
                context,
                s["chat_id"],
                f"⏰ Блок закончился.\n\n"
                f"Ты собирался: {s['commitment_text']}\n\nЧто по факту?",
                reply_markup=checkin_keyboard(),
            )
            if ok:
                next_ping = now + timedelta(minutes=NAG_DELAYS_MIN[0])
                db.set_session_waiting(
                    s["id"], next_ping.isoformat(), nag_stage=0
                )
                db.log_event(
                    s["user_id"], "assistant", "checkin",
                    f"Спросил результат: {s['commitment_text']}"
                )
            continue

        if s["status"] != "waiting":
            continue
        if not s["next_ping_at"] or parse_iso(s["next_ping_at"]) > now:
            continue

        stage = int(s["nag_stage"])
        if stage == 0:
            text = (
                f"👀 Ты пропал. «{s['commitment_text']}» всё ещё висит.\n\n"
                "Сделал, делаешь или опять откладываем?"
            )
        elif stage == 1:
            text = (
                f"Так, возвращаю тебя сюда.\n\n"
                f"«{s['commitment_text']}».\n"
                "Не нужен идеальный настрой. Нужны 10 минут."
            )
        elif stage == 2:
            text = (
                f"⚡ Минимальный контракт: 10 минут на "
                f"«{s['commitment_text']}» прямо сейчас."
            )
        else:
            text = (
                f"🔁 Я всё ещё помню про «{s['commitment_text']}».\n\n"
                "Либо делаем 10 минут, либо честно отменяем."
            )

        ok = await safe_send(
            context, s["chat_id"], text, reply_markup=nag_keyboard()
        )
        if ok:
            new_stage = min(stage + 1, 3)
            delay = NAG_DELAYS_MIN[min(
                new_stage, len(NAG_DELAYS_MIN) - 1
            )]
            db.advance_nag(
                s["id"], new_stage,
                (now + timedelta(minutes=delay)).isoformat()
            )
            db.log_event(
                s["user_id"], "assistant", "nag",
                f"Напоминание stage={new_stage}: {s['commitment_text']}"
            )


async def morning_prompt(context):
    now = now_utc()

    for user in db.all_users():
        local = now.astimezone(zone(user["timezone"]))
        date = local.date().isoformat()

        if quiet(local, user["quiet_start"], user["quiet_end"]):
            continue

        if not hhmm_after(local, MORNING_TIME):
            continue

        if db.morning_ping_sent(user["user_id"], date):
            continue

        c = db.active_commitment(user["user_id"])
        if c:
            text = (
                f"🌅 У тебя со вчера/раньше висит:\n\n"
                f"«{c['text']}»\n\n"
                "Что делаем с этим сегодня?"
            )
        else:
            text = (
                "🌅 Что тебе сегодня реально надо сделать?\n\n"
                "Напиши как есть. Я выберу, с чего начать, и потом вернусь "
                "проверить, сделал ли ты это."
            )

        if await safe_send(context, user["chat_id"], text):
            db.mark_morning_ping(user["user_id"], date)
            db.log_event(user["user_id"], "assistant", "morning", text)


async def watchdog(context: ContextTypes.DEFAULT_TYPE):
    await process_reminders(context)
    await process_sessions(context)
    await morning_prompt(context)
