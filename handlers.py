import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardRemove

from config import settings
from database import Database
from geo_tracker import calculate_steps_and_calories, haversine_distance

logger = logging.getLogger(__name__)
router = Router()


MONTHS_RU = [
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]


def format_date_ru(dt: datetime) -> str:
    """Форматирует дату на русском языке: '23 ноября 2026'."""
    return f"{dt.day} {MONTHS_RU[dt.month]} {dt.year}"


def setup_handlers(db: Database) -> Router:
    """Регистрирует минималистичные хэндлеры без лишних кнопок."""

    @router.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        user_id = message.from_user.id
        await db.get_or_create_user(user_id, settings.default_timezone)
        user_tz = await db.get_user_timezone(user_id, settings.default_timezone)

        welcome_text = (
            f"👋 <b>Бот настроен и работает!</b>\n\n"
            f"🌍 Твой часовой пояс: <code>{user_tz}</code>\n\n"
            f"📋 <b>Твое постоянное расписание:</b>\n"
            f"• <b>10:00 и 11:00</b> — УТРО: практика английского в школе\n"
            f"• <b>16:00 и 19:00</b> — ВЕЧЕР: минимум 8-10к шагов и турники\n"
            f"• <b>07:00, 16:00, 20:00, 22:00</b> — ОБЩЕЕ: белки, правильное питание и обязательно кола зеро\n\n"
            f"🚶 <b>Подсчет шагов:</b>\n"
            f"Просто нажми скрепку 📎 -> <b>Геопозиция</b> -> <b>Транслировать геопозицию</b>.\n"
            f"Бот будет сразу конвертировать пройденные км в шаги и показывать сожженные калории!"
        )
        await message.answer(welcome_text, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")

    @router.message(Command("test"))
    @router.message(F.text.lower() == "тест")
    async def cmd_test(message: Message) -> None:
        user_id = message.from_user.id
        await db.get_or_create_user(user_id, settings.default_timezone)
        test_message = (
            "🔔 <b>Тестовое напоминание:</b>\n\n"
            "🇬🇧 <b>УТРО</b>: практика английского в школе\n"
            "🥤 <b>ОБЩЕЕ</b>: белки, правильное питание и обязательно кола зеро\n"
            "💪 <b>ВЕЧЕР</b>: минимум 8-10к шагов и турники\n\n"
            "✅ Все системы и таймеры работают исправно!"
        )
        await message.answer(test_message, parse_mode="HTML")

    @router.message(Command("schedule"))
    @router.message(F.text.lower() == "расписание")
    async def cmd_schedule(message: Message) -> None:
        text = (
            "📋 <b>Ежедневные постоянные напоминания:</b>\n\n"
            "⏰ <b>07:00</b> — ОБЩЕЕ: белки, правильное питание и обязательно кола зеро 🥤\n"
            "⏰ <b>10:00</b> — УТРО: практика английского в школе 🇬🇧\n"
            "⏰ <b>11:00</b> — УТРО: практика английского в школе 🇬🇧\n"
            "⏰ <b>16:00</b> — ВЕЧЕР: минимум 8-10к шагов и турники 💪\n"
            "⏰ <b>16:00</b> — ОБЩЕЕ: белки, правильное питание и обязательно кола зеро 🥤\n"
            "⏰ <b>19:00</b> — ВЕЧЕР: минимум 8-10к шагов и турники 💪\n"
            "⏰ <b>20:00</b> — ОБЩЕЕ: белки, правильное питание и обязательно кола зеро 🥤\n"
            "⏰ <b>22:00</b> — ОБЩЕЕ: белки, правильное питание и обязательно кола зеро 🥤"
        )
        await message.answer(text, parse_mode="HTML")

    # --- Обработка первой входящей геопозиции ---
    @router.message(F.location)
    async def handle_initial_location(message: Message) -> None:
        user_id = message.from_user.id
        loc = message.location
        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        await db.start_activity_session(
            user_id=user_id,
            started_at_iso=now_iso,
            lat=loc.latitude,
            lon=loc.longitude,
            timestamp=now_ts,
            status_msg_id=message.message_id,
        )

        resp = (
            "📍 <b>Геопозиция принята. Шагомер включен!</b>\n\n"
            "Двигайтесь — бот в реальном времени конвертирует расстояние в шаги и калории.\n"
            "Чтобы узнать текущий результат, напишите <code>шаги</code> или команду /steps.\n"
            "Чтобы завершить прогулку, напишите <code>стоп</code> или /stop."
        )
        await message.answer(resp, parse_mode="HTML")

    # --- Поток обновлений Live Location ---
    @router.edited_message(F.location)
    async def handle_live_location_update(message: Message) -> None:
        user_id = message.from_user.id
        loc = message.location
        new_lat = loc.latitude
        new_lon = loc.longitude
        now_ts = time.time()

        active_sess = await db.get_active_session(user_id)
        if not active_sess:
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.start_activity_session(
                user_id=user_id,
                started_at_iso=now_iso,
                lat=new_lat,
                lon=new_lon,
                timestamp=now_ts,
                status_msg_id=message.message_id,
            )
            logger.info(f"Auto-started activity session for user {user_id} from live stream.")
            return

        last_lat = active_sess["last_latitude"]
        last_lon = active_sess["last_longitude"]
        last_ts = active_sess["last_timestamp"] or now_ts

        dist_m = haversine_distance(last_lat, last_lon, new_lat, new_lon)
        dt = max(now_ts - last_ts, 1.0)
        speed_mps = dist_m / dt

        # Фильтр шума (< 8м) и скорости (> 20 км/ч = машина/автобус)
        if dist_m >= 8.0 and speed_mps <= 5.5:
            steps, _ = calculate_steps_and_calories(dist_m)
            tot_dist_m, tot_steps = await db.update_activity_session(
                session_id=active_sess["id"],
                added_distance_m=dist_m,
                added_steps=steps,
                lat=new_lat,
                lon=new_lon,
                timestamp=now_ts,
            )

            # Каждые ~150-200 метров или ~200 шагов отправляем краткий апдейт
            old_steps = active_sess["total_steps"]
            if (tot_steps // 200) > (old_steps // 200) or (int(tot_dist_m) // 150 > int(active_sess["total_distance_meters"]) // 150):
                dist_km = round(tot_dist_m / 1000.0, 2)
                _, kcal = calculate_steps_and_calories(tot_dist_m)
                try:
                    await message.answer(
                        f"🚶 <b>Пройдено</b>: {dist_km} км | ~<b>{tot_steps:,}</b> шагов | ~<b>{kcal}</b> ккал".replace(",", " "),
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.error(f"Failed to send step update: {e}")

    # --- Проверка шагов вручную ---
    @router.message(Command("steps"))
    @router.message(F.text.lower().in_(["шаги", "шаг", "прогресс", "км"]))
    async def cmd_steps(message: Message) -> None:
        user_id = message.from_user.id
        user_tz = await db.get_user_timezone(user_id, settings.default_timezone)
        try:
            tz = ZoneInfo(user_tz)
        except Exception:
            tz = ZoneInfo("Asia/Yekaterinburg")

        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        today_display = format_date_ru(datetime.now(tz))
        daily = await db.get_daily_activity(user_id, today_str)
        active_sess = await db.get_active_session(user_id)

        active_text = ""
        if active_sess:
            cur_dist_km = round(active_sess["total_distance_meters"] / 1000.0, 2)
            cur_steps = active_sess["total_steps"]
            _, cur_kcal = calculate_steps_and_calories(active_sess["total_distance_meters"])
            active_text = (
                f"🟢 <b>Текущая прогулка:</b>\n"
                f"📏 Дистанция: <b>{cur_dist_km} км</b>\n"
                f"👟 Шагов: ~<b>{cur_steps:,}</b>\n"
                f"🔥 Сожжено: ~<b>{cur_kcal} ккал</b>\n\n"
            ).replace(",", " ")

        total_steps = daily["total_steps"] + (active_sess["total_steps"] if active_sess else 0)
        total_km = round(daily["total_distance_km"] + ((active_sess["total_distance_meters"] / 1000.0) if active_sess else 0), 2)
        total_kcal = round(daily["total_calories"] + (calculate_steps_and_calories(active_sess["total_distance_meters"])[1] if active_sess else 0), 1)

        progress_msg = (
            f"📊 <b>Ваша активность за сегодня:</b>\n\n"
            f"{active_text}"
            f"🏁 <b>Всего за день ({today_display}):</b>\n"
            f"• Дистанция: <b>{total_km} км</b>\n"
            f"• Шагов: ~<b>{total_steps:,}</b> (цель: 8 000 - 10 000)\n"
            f"• Сожжено: ~<b>{total_kcal} ккал</b>\n\n"
            f"<i>Цель 8-10к шагов: {'✅ Выполнено!' if total_steps >= 8000 else f'осталось ~{max(0, 8000 - total_steps):,} шагов'}</i>"
        ).replace(",", " ")

        await message.answer(progress_msg, parse_mode="HTML")

    # --- Остановка трекинга ---
    @router.message(Command("stop"))
    @router.message(F.text.lower().in_(["стоп", "хватит", "конец"]))
    async def cmd_stop(message: Message) -> None:
        user_id = message.from_user.id
        active_sess = await db.get_active_session(user_id)

        if not active_sess:
            await message.answer("Сейчас нет активной прогулки. Отправьте геопозицию, чтобы начать!")
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        finished = await db.finish_activity_session(active_sess["id"], now_iso)

        dist_meters = finished["total_distance_meters"] if finished else 0.0
        steps = finished["total_steps"] if finished else 0
        dist_km = round(dist_meters / 1000.0, 2)
        _, kcal = calculate_steps_and_calories(dist_meters)

        # Сохраняем в дневную статистику
        user_tz = await db.get_user_timezone(user_id, settings.default_timezone)
        try:
            tz = ZoneInfo(user_tz)
        except Exception:
            tz = ZoneInfo("Asia/Yekaterinburg")
        today_str = datetime.now(tz).strftime("%Y-%m-%d")

        await db.add_to_daily_activity(
            user_id=user_id,
            date_str=today_str,
            steps=steps,
            distance_km=dist_km,
            calories=kcal,
        )

        res_msg = (
            f"🏁 <b>Прогулка завершена!</b>\n\n"
            f"📏 Дистанция: <b>{dist_km} км</b>\n"
            f"👟 Шагов: ~<b>{steps:,}</b>\n"
            f"🔥 Сожжено: ~<b>{kcal} ккал</b>\n\n"
            f"Результат сохранен в дневную статистику. 💪"
        ).replace(",", " ")
        await message.answer(res_msg, parse_mode="HTML")

    # --- Обработка любых других текстовых сообщений ---
    @router.message()
    async def handle_any_message(message: Message) -> None:
        user_id = message.from_user.id
        await db.get_or_create_user(user_id, settings.default_timezone)
        text = (
            "👋 <b>Бот на связи и готов к работе!</b>\n\n"
            "• Напишите <code>тест</code> — бот сразу пришлет тестовое напоминание\n"
            "• Напишите <code>шаги</code> — покажет шаги, км и калории за сегодня\n"
            "• Напишите <code>расписание</code> — покажет время всех напоминаний\n"
            "• Отправьте трансляцию геопозиции 📎 — для включения шагомера на прогулке"
        )
        await message.answer(text, parse_mode="HTML")

    return router
