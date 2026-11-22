from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

DAYS_RU = [
    ("Понедельник", 0),
    ("Вторник", 1),
    ("Среда", 2),
    ("Четверг", 3),
    ("Пятница", 4),
    ("Суббота", 5),
    ("Воскресенье", 6),
]

DAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню бота."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Мое расписание"), KeyboardButton(text="➕ Добавить занятие")],
            [KeyboardButton(text="📌 Разовое напоминание"), KeyboardButton(text="🚶 Прогулка и шаги")],
            [KeyboardButton(text="⚙️ Часовой пояс"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def get_tracking_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления активной прогулкой."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Обновить статус", callback_data="refresh_tracking"),
                InlineKeyboardButton(text="🛑 Завершить прогулку", callback_data="stop_tracking"),
            ]
        ]
    )


def get_days_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора дня недели."""
    keyboard = []
    row = []
    for day_name, day_idx in DAYS_RU:
        row.append(InlineKeyboardButton(text=day_name, callback_data=f"day_{day_idx}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_intervals_keyboard(selected_intervals: list[int]) -> InlineKeyboardMarkup:
    """Клавиатура выбора интервалов напоминаний."""
    available_intervals = [
        (1440, "За 1 день"),
        (120, "За 2 часа"),
        (60, "За 1 час"),
        (30, "За 30 мин"),
        (15, "За 15 мин"),
        (0, "В момент начала"),
    ]
    keyboard = []
    for minutes, label in available_intervals:
        mark = "✅" if minutes in selected_intervals else "◻️"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{mark} {label}",
                callback_data=f"toggle_int_{minutes}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(text="💾 Сохранить и завершить", callback_data="save_intervals"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_timezones_keyboard() -> InlineKeyboardMarkup:
    """Популярные часовые пояса для быстрого выбора."""
    timezones = [
        ("Калининград (UTC+2)", "Europe/Kaliningrad"),
        ("Москва / СПб (UTC+3)", "Europe/Moscow"),
        ("Самара (UTC+4)", "Europe/Samara"),
        ("Екатеринбург (UTC+5)", "Asia/Yekaterinburg"),
        ("Омск (UTC+6)", "Asia/Omsk"),
        ("Красноярск / Новосибирск (UTC+7)", "Asia/Krasnoyarsk"),
        ("Иркутск (UTC+8)", "Asia/Irkutsk"),
        ("Владивосток (UTC+10)", "Asia/Vladivostok"),
        ("Алматы / Астана (UTC+5)", "Asia/Almaty"),
        ("Ташкент (UTC+5)", "Asia/Tashkent"),
    ]
    keyboard = []
    for label, tz in timezones:
        keyboard.append([InlineKeyboardButton(text=label, callback_data=f"set_tz_{tz}")])

    keyboard.append([
        InlineKeyboardButton(text="✍️ Ввести название пояса вручную", callback_data="set_tz_custom"),
        InlineKeyboardButton(text="❌ Закрыть", callback_data="cancel_action"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lesson_action_keyboard(lesson_id: int, is_active: int) -> InlineKeyboardMarkup:
    """Кнопки управления конкретным занятием."""
    toggle_text = "⏸ Приостановить" if is_active == 1 else "▶️ Активировать"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_lesson_{lesson_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_lesson_{lesson_id}"),
            ],
            [InlineKeyboardButton(text="🔙 Назад к расписанию", callback_data="back_to_schedule")],
        ]
    )


def get_cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены любого текущего шага."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_action")]
        ]
    )
