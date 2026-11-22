import json
import logging
from typing import Any, Optional
import aiosqlite

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "reminders.db") -> None:
        self.db_path = db_path

    async def init_db(self) -> None:
        """Инициализация таблиц базы данных."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    time_str TEXT NOT NULL,
                    remind_before TEXT NOT NULL DEFAULT '[60, 15, 0]',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS one_time_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    is_sent INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS activity_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    total_distance_meters REAL DEFAULT 0.0,
                    total_steps INTEGER DEFAULT 0,
                    last_latitude REAL,
                    last_longitude REAL,
                    last_timestamp REAL,
                    status_message_id INTEGER,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS daily_activity (
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    total_steps INTEGER DEFAULT 0,
                    total_distance_km REAL DEFAULT 0.0,
                    total_calories REAL DEFAULT 0.0,
                    PRIMARY KEY (user_id, date)
                );
            """)

            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_active ON activity_sessions (user_id, is_active);"
            )

            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_lessons_user ON lessons (user_id);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminders_pending ON one_time_reminders (is_sent, remind_at);"
            )
            await db.commit()
            logger.info("Database schema initialized successfully.")

    # --- Работа с пользователями ---
    async def get_or_create_user(self, user_id: int, default_tz: str = "Europe/Moscow") -> dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                return dict(row)

            await db.execute(
                "INSERT INTO users (user_id, timezone) VALUES (?, ?)",
                (user_id, default_tz),
            )
            await db.commit()
            return {"user_id": user_id, "timezone": default_tz}

    async def get_all_users(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users")
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def update_user_timezone(self, user_id: int, timezone: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET timezone = ? WHERE user_id = ?",
                (timezone, user_id),
            )
            await db.commit()

    async def get_user_timezone(self, user_id: int, default_tz: str = "Europe/Moscow") -> str:
        user = await self.get_or_create_user(user_id, default_tz)
        return user.get("timezone", default_tz)

    # --- Работа с постоянным расписанием занятий ---
    async def add_lesson(
        self,
        user_id: int,
        title: str,
        day_of_week: int,
        time_str: str,
        remind_before: list[int],
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO lessons (user_id, title, day_of_week, time_str, remind_before)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, title, day_of_week, time_str, json.dumps(remind_before)),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_user_lessons(self, user_id: int) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM lessons 
                WHERE user_id = ? 
                ORDER BY day_of_week ASC, time_str ASC
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                try:
                    item["remind_before"] = json.loads(item["remind_before"])
                except Exception:
                    item["remind_before"] = [60, 15, 0]
                result.append(item)
            return result

    async def get_lesson_by_id(self, lesson_id: int) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            try:
                item["remind_before"] = json.loads(item["remind_before"])
            except Exception:
                item["remind_before"] = [60, 15, 0]
            return item

    async def delete_lesson(self, lesson_id: int, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM lessons WHERE id = ? AND user_id = ?",
                (lesson_id, user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def toggle_lesson_active(self, lesson_id: int, user_id: int) -> Optional[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT is_active FROM lessons WHERE id = ? AND user_id = ?",
                (lesson_id, user_id),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            new_val = 0 if row[0] == 1 else 1
            await db.execute(
                "UPDATE lessons SET is_active = ? WHERE id = ? AND user_id = ?",
                (new_val, lesson_id, user_id),
            )
            await db.commit()
            return new_val

    async def get_all_active_lessons_with_tz(self) -> list[dict[str, Any]]:
        """Возвращает все активные занятия вместе с таймзоной пользователя для шедулера."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT l.id, l.user_id, l.title, l.day_of_week, l.time_str, l.remind_before, u.timezone
                FROM lessons l
                JOIN users u ON l.user_id = u.user_id
                WHERE l.is_active = 1
            """)
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                try:
                    item["remind_before"] = json.loads(item["remind_before"])
                except Exception:
                    item["remind_before"] = [60, 15, 0]
                result.append(item)
            return result

    # --- Работа с разовыми напоминаниями ---
    async def add_one_time_reminder(self, user_id: int, title: str, remind_at_iso: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO one_time_reminders (user_id, title, remind_at, is_sent)
                VALUES (?, ?, ?, 0)
                """,
                (user_id, title, remind_at_iso),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_user_one_time_reminders(self, user_id: int) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM one_time_reminders 
                WHERE user_id = ? AND is_sent = 0
                ORDER BY remind_at ASC
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def delete_one_time_reminder(self, reminder_id: int, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM one_time_reminders WHERE id = ? AND user_id = ?",
                (reminder_id, user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def mark_reminder_sent(self, reminder_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE one_time_reminders SET is_sent = 1 WHERE id = ?",
                (reminder_id,),
            )
            await db.commit()

    async def get_due_one_time_reminders(self, now_iso: str) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM one_time_reminders
                WHERE is_sent = 0 AND remind_at <= ?
                ORDER BY remind_at ASC
                """,
                (now_iso,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # --- Трекинг активности и шагов по геолокации ---
    async def start_activity_session(
        self,
        user_id: int,
        started_at_iso: str,
        lat: float,
        lon: float,
        timestamp: float,
        status_msg_id: Optional[int] = None,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            # Сначала закрываем предыдущие незавершенные сессии этого пользователя
            await db.execute(
                "UPDATE activity_sessions SET is_active = 0 WHERE user_id = ? AND is_active = 1",
                (user_id,),
            )
            cursor = await db.execute(
                """
                INSERT INTO activity_sessions (
                    user_id, started_at, last_latitude, last_longitude,
                    last_timestamp, status_message_id, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (user_id, started_at_iso, lat, lon, timestamp, status_msg_id),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_active_session(self, user_id: int) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM activity_sessions 
                WHERE user_id = ? AND is_active = 1
                ORDER BY id DESC LIMIT 1
                """,
                (user_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_activity_session(
        self,
        session_id: int,
        added_distance_m: float,
        added_steps: int,
        lat: float,
        lon: float,
        timestamp: float,
    ) -> tuple[float, int]:
        """Обновляет сессию и возвращает новые суммарные значения (дистанция, шаги)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE activity_sessions
                SET total_distance_meters = total_distance_meters + ?,
                    total_steps = total_steps + ?,
                    last_latitude = ?,
                    last_longitude = ?,
                    last_timestamp = ?
                WHERE id = ?
                """,
                (added_distance_m, added_steps, lat, lon, timestamp, session_id),
            )
            await db.commit()

            cursor = await db.execute(
                "SELECT total_distance_meters, total_steps FROM activity_sessions WHERE id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            if row:
                return float(row[0]), int(row[1])
            return 0.0, 0

    async def finish_activity_session(
        self, session_id: int, ended_at_iso: str
    ) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM activity_sessions WHERE id = ?", (session_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None

            await db.execute(
                """
                UPDATE activity_sessions 
                SET is_active = 0, ended_at = ?
                WHERE id = ?
                """,
                (ended_at_iso, session_id),
            )
            await db.commit()
            return dict(row)

    async def add_to_daily_activity(
        self, user_id: int, date_str: str, steps: int, distance_km: float, calories: float
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO daily_activity (user_id, date, total_steps, total_distance_km, total_calories)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, date) DO UPDATE SET
                    total_steps = total_steps + excluded.total_steps,
                    total_distance_km = total_distance_km + excluded.total_distance_km,
                    total_calories = total_calories + excluded.total_calories
                """,
                (user_id, date_str, steps, distance_km, calories),
            )
            await db.commit()

    async def get_daily_activity(self, user_id: int, date_str: str) -> dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM daily_activity WHERE user_id = ? AND date = ?",
                (user_id, date_str),
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return {
                "user_id": user_id,
                "date": date_str,
                "total_steps": 0,
                "total_distance_km": 0.0,
                "total_calories": 0.0,
            }
