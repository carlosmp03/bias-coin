# bias-coin-bot v2

Личный Telegram-диспетчер для работы и теории вероятностей.

## Механика

- `/study` выбирает одну нерешённую задачу.
- Фокус-блок: 10 / 25 / 45 / 60 минут.
- После блока бот сам пишет.
- Если ты не отвечаешь, бот напоминает снова и постепенно уменьшает требование до 10 минут.
- `/stuck` требует зафиксировать попытку текстом.
- Утром бот просит план дня; вечером присылает контрольный итог.
- `/flip` остаётся: 80% ACTION / 20% PAUSE.

## Railway

Variables:

```text
TELEGRAM_BOT_TOKEN=...
DEFAULT_TIMEZONE=Europe/Moscow
DEFAULT_MORNING_TIME=09:30
DEFAULT_EVENING_TIME=22:30
DB_PATH=/data/bot.db
```

Добавь Railway Volume с mount path:

```text
/data
```

Это важно: иначе SQLite может исчезнуть после redeploy.

Start Command:

```text
python bot.py
```

После деплоя в Telegram выполни:

```text
/timezone Europe/Moscow
/schedule 09:30 22:30
/start
```

Потом тест:

```text
/study
```
