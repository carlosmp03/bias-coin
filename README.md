# bias-coin-bot

Минимальный Telegram-бот с намеренно смещённой монеткой:

- `80%` — `ACTION`
- `20%` — `PAUSE`
- `/done` — начисляет `+1 Action Token`
- данные хранятся в SQLite

## Структура

```text
bias-coin-bot/
├── bot.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

`bot.db` создаётся автоматически при первом запуске.

## Запуск

### 1. Создать виртуальное окружение

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

### 3. Создать `.env`

Скопировать `.env.example` в `.env`:

```env
TELEGRAM_BOT_TOKEN=твой_токен_от_BotFather
```

### 4. Запустить

```bash
python bot.py
```

## Команды

- `/start` — описание бота
- `/flip` — бросок: 80% ACTION / 20% PAUSE
- `/done` — +1 Action Token
- `/balance` — текущий баланс
- `/stats` — статистика бросков и выполненных действий
