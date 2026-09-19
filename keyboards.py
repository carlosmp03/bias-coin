from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def focus_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("25 мин", callback_data="focus:25"),
            InlineKeyboardButton("45 мин", callback_data="focus:45"),
            InlineKeyboardButton("60 мин", callback_data="focus:60"),
        ],
        [InlineKeyboardButton("10 мин — просто начать", callback_data="focus:10")],
    ])

def checkin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Решил", callback_data="checkin:done"),
            InlineKeyboardButton("➡️ Есть прогресс", callback_data="checkin:progress"),
        ],
        [
            InlineKeyboardButton("🧱 Застрял", callback_data="checkin:stuck"),
            InlineKeyboardButton("😐 Не занимался", callback_data="checkin:not_worked"),
        ],
    ])

def continue_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("+15 мин", callback_data="continue:15"),
            InlineKeyboardButton("+25 мин", callback_data="continue:25"),
            InlineKeyboardButton("+45 мин", callback_data="continue:45"),
        ],
        [InlineKeyboardButton("☕ Пауза 15 мин", callback_data="pause:15")],
    ])

def minimum_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ 10 минут", callback_data="continue:10"),
            InlineKeyboardButton("☕ Пауза 15", callback_data="pause:15"),
        ],
        [
            InlineKeyboardButton("🧱 Застрял", callback_data="checkin:stuck"),
            InlineKeyboardButton("✅ Уже решил", callback_data="checkin:done"),
        ],
    ])

def morning_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Составить план", callback_data="plan:start")],
        [InlineKeyboardButton("📚 Сразу теорвер", callback_data="study:start")],
    ])
