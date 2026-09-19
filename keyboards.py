from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def proposed_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Начал", callback_data="do:start"),
            InlineKeyboardButton("⏰ Через 15 мин", callback_data="do:later15"),
        ],
        [
            InlineKeyboardButton("✋ Не сегодня", callback_data="do:cancel"),
        ],
    ])


def checkin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Сделал", callback_data="do:done"),
            InlineKeyboardButton("➕ Ещё 15 мин", callback_data="do:more15"),
        ],
        [
            InlineKeyboardButton("😐 Не сделал", callback_data="do:notdone"),
        ],
    ])


def nag_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ 10 минут сейчас", callback_data="do:start10"),
            InlineKeyboardButton("⏰ Через 20 мин", callback_data="do:later20"),
        ],
        [
            InlineKeyboardButton("✅ Уже сделал", callback_data="do:done"),
            InlineKeyboardButton("✋ Отменить", callback_data="do:cancel"),
        ],
    ])
