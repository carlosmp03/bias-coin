from telegram import BotCommand
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, filters,
)
import database as db
from config import BOT_TOKEN
from handlers.coin import flip
from handlers.common import start, status, stats, balance
from handlers.planning import conversation, today, schedule, timezone_cmd
from handlers.study import (
    study, study_button, focus, task, tasks, done, checkin,
    continue_focus, pause_button, pause_cmd, stuck, attempt_text,
    skip, reopen,
)
from scheduler import watchdog

async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("study", "начать учебный блок"),
        BotCommand("task", "текущая задача"),
        BotCommand("tasks", "прогресс по листку"),
        BotCommand("done", "закрыть текущую задачу"),
        BotCommand("stuck", "зафиксировать тупик"),
        BotCommand("pause", "пауза, например /pause 15"),
        BotCommand("plan", "план дня"),
        BotCommand("today", "план на сегодня"),
        BotCommand("status", "текущее состояние"),
        BotCommand("stats", "статистика"),
        BotCommand("flip", "монетка 80/20"),
        BotCommand("balance", "Action Tokens"),
        BotCommand("schedule", "утро и вечер"),
        BotCommand("timezone", "часовой пояс"),
    ])
    if app.job_queue is None:
        raise RuntimeError("Нужен python-telegram-bot[job-queue].")
    app.job_queue.run_repeating(watchdog, interval=30, first=5)

def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(conversation())
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("study", study))
    app.add_handler(CommandHandler("task", task))
    app.add_handler(CommandHandler("tasks", tasks))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("stuck", stuck))
    app.add_handler(CommandHandler("pause", pause_cmd))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CommandHandler("reopen", reopen))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("flip", flip))
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(CommandHandler("timezone", timezone_cmd))

    app.add_handler(CallbackQueryHandler(study_button, pattern=r"^study:start$"))
    app.add_handler(CallbackQueryHandler(focus, pattern=r"^focus:\d+$"))
    app.add_handler(CallbackQueryHandler(checkin, pattern=r"^checkin:"))
    app.add_handler(CallbackQueryHandler(continue_focus, pattern=r"^continue:\d+$"))
    app.add_handler(CallbackQueryHandler(pause_button, pattern=r"^pause:\d+$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, attempt_text))

    print("Bias Coin Bot v2 is running...")
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()
