# Bias Coin v4 — simple agent

This version intentionally removes the command-heavy interface.

## What the user sees

Almost nothing except conversation.

The bot asks:

> Что тебе сегодня реально надо сделать?

The user can answer naturally:

> Теорвер, GRE и ещё код. Я вообще ничего не начал.

Gemini turns the message into one concrete next action. The Python application
stores that commitment, starts or schedules the work block, and later checks
back automatically.

## Telegram commands

Only two commands are exposed in the menu:

- `/start` — start/restart the conversation;
- `/reset` — clear the agent's own conversational context.

Everything else is ordinary text and contextual buttons.

## Core loop

1. User tells the bot what needs to be done.
2. Agent selects ONE next action.
3. Bot asks to start now or delay briefly.
4. When started, bot waits for the focus block to finish.
5. Bot checks whether it was done.
6. If the user disappears, the bot nags again:
   - after ~10 min;
   - then ~15 min;
   - then ~20 min;
   - afterwards about every 2 hours.
7. Quiet hours stop the nagging at night.
8. Every morning the bot asks what actually needs to be done today.

The model is called only when the user sends natural-language text. Timers and
nagging are ordinary Python/SQLite logic, so they do not consume model calls.

## Upgrade from v3

Copy these v4 files over the existing repository.

The old `handlers/` and `data/` directories are no longer used. Delete them
after copying v4:

Git Bash:

```bash
rm -rf handlers data
```

Do NOT delete:

```text
.git
.env
.venv
```

The existing SQLite database is migrated safely by adding the new v4 tables.

## Install

```bash
pip install -r requirements.txt
```

## Local `.env`

```env
TELEGRAM_BOT_TOKEN=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.8-flash
DEFAULT_TIMEZONE=Europe/Moscow
MORNING_TIME=10:00
QUIET_START=00:30
QUIET_END=09:00
```

## Railway

Keep the Telegram token already configured and add:

```text
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.8-flash
DEFAULT_TIMEZONE=Europe/Moscow
MORNING_TIME=10:00
QUIET_START=00:30
QUIET_END=09:00
```

For persistent SQLite:

```text
DB_PATH=/data/bot.db
```

with a Railway Volume mounted to:

```text
/data
```

Start command:

```text
python bot.py
```

## First test

After Railway redeploys, send:

```text
/start
```

Then write naturally, for example:

```text
Мне сегодня надо решить две задачи по теорверу и позаниматься GRE.
До шести я свободен, но начинать вообще не хочется.
```

There should be no need to remember `/study`, `/plan`, `/done`, etc.
