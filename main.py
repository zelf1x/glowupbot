import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from database import Database
from handlers import setup_handlers
from scheduler import ReminderScheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("StudyReminderBot")


async def main() -> None:
    if not settings.bot_token or settings.bot_token.startswith("123456789"):
        logger.error(
            "BOT_TOKEN не задан! Создайте файл .env на основе .env.example и укажите ваш токен от @BotFather."
        )
        print("\n" + "=" * 60)
        print(" ОШИБКА: Не указан BOT_TOKEN в файле .env")
        print(" 1. Получите токен бота в Telegram у @BotFather")
        print(" 2. Создайте файл .env и добавьте: BOT_TOKEN=ваш_токен")
        print("=" * 60 + "\n")
        return

    # Инициализация базы данных
    db = Database(settings.database_path)
    await db.init_db()

    # Инициализация бота и диспетчера
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Подключение хэндлеров
    router = setup_handlers(db)
    dp.include_router(router)

    # Функция отправки сообщений для шедулера
    async def send_notification(user_id: int, text: str) -> None:
        try:
            await bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

    # Запуск планировщика напоминаний
    scheduler = ReminderScheduler(db=db, send_message_callback=send_notification)
    scheduler.start()

    logger.info("Бот успешно запущен и готов к работе!")

    try:
        # Удаляем вебхуки и запускаем Long Polling
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Программа завершена.")
