@echo off
chcp 65001 > nul
echo ========================================================
echo   Запуск Telegram-бота напоминаний об учебе и занятиях
echo ========================================================
echo.

if not exist .env (
    if exist .env.example (
        copy .env.example .env
        echo [!] Создан файл .env. Пожалуйста, откройте его и вставьте ваш BOT_TOKEN.
        pause
        exit /b
    )
)

python main.py
pause
