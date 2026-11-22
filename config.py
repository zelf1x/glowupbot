import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    bot_token: str = Field(default="", description="Telegram Bot API Token from @BotFather")
    default_timezone: str = Field(default="Europe/Moscow", description="Default timezone for users")
    database_path: str = Field(
        default=str(BASE_DIR / "reminders.db"),
        description="Path to SQLite database file",
    )

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
