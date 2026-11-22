import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Coroutine
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from database import Database

logger = logging.getLogger(__name__)

# Фиксированное ежедневное расписание
FIXED_DAILY_SCHEDULE = [
    ("07:00", ["🔔 <b>ОБЩЕЕ</b>: белки, правильное питание и обязательно кола зеро 🥤"]),
    ("10:00", ["🔔 <b>УТРО</b>: практика английского в школе 🇬🇧"]),
    ("11:00", ["🔔 <b>УТРО</b>: практика английского в школе 🇬🇧"]),
    ("16:00", [
        "🔔 <b>ВЕЧЕР</b>: минимум 8-10к шагов и турники 💪",
        "🔔 <b>ОБЩЕЕ</b>: белки, правильное питание и обязательно кола зеро 🥤",
    ]),
    ("19:00", ["🔔 <b>ВЕЧЕР</b>: минимум 8-10к шагов и турники 💪"]),
    ("20:00", ["🔔 <b>ОБЩЕЕ</b>: белки, правильное питание и обязательно кола зеро 🥤"]),
    ("22:00", ["🔔 <b>ОБЩЕЕ</b>: белки, правильное питание и обязательно кола зеро 🥤"]),
]


class ReminderScheduler:
    def __init__(
        self,
        db: Database,
        send_message_callback: Callable[[int, str], Coroutine[Any, Any, None]],
    ) -> None:
        self.db = db
        self.send_message = send_message_callback
        self.scheduler = AsyncIOScheduler()
        # Кэш отправленных сообщений: "user_{id}_{time}_{YYYY-MM-DD}"
        self._sent_cache: set[str] = set()

    def start(self) -> None:
        self.scheduler.add_job(
            self._check_reminders,
            trigger="interval",
            seconds=20,
            id="periodic_reminder_checker",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Reminder scheduler started with fixed daily timetable.")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Reminder scheduler stopped.")

    async def _check_reminders(self) -> None:
        try:
            await self._process_fixed_schedule()
        except Exception as e:
            logger.error(f"Error during reminder check: {e}", exc_info=True)

    async def _process_fixed_schedule(self) -> None:
        users = await self.db.get_all_users()
        now_utc = datetime.now(timezone.utc)

        # Очистка старых ключей раз в сутки
        if len(self._sent_cache) > 5000:
            self._sent_cache.clear()

        for user in users:
            user_id = user["user_id"]
            user_tz_name = user.get("timezone", "Asia/Yekaterinburg")
            try:
                user_tz = ZoneInfo(user_tz_name)
            except Exception:
                user_tz = ZoneInfo("Asia/Yekaterinburg")

            now_user = now_utc.astimezone(user_tz)
            current_hh_mm = now_user.strftime("%H:%M")
            today_str = now_user.strftime("%Y-%m-%d")

            for target_time, messages in FIXED_DAILY_SCHEDULE:
                if current_hh_mm == target_time:
                    cache_key = f"user_{user_id}_{target_time}_{today_str}"
                    if cache_key in self._sent_cache:
                        continue

                    for msg in messages:
                        try:
                            await self.send_message(user_id, msg)
                            logger.info(f"Sent reminder '{target_time}' to user {user_id}")
                        except Exception as err:
                            logger.error(f"Failed to send reminder to {user_id}: {err}")

                    self._sent_cache.add(cache_key)
