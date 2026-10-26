from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://servisai:servisai@localhost:5432/servisai"
    secret_key: str = "change-me"
    access_token_expire_days: int = 30
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"

    google_client_id: str = ""

    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    telegram_admin_chat_id: str = ""
    # Telegram orqali kirish havolasi necha soniya amal qiladi
    telegram_login_ttl: int = 300

    admin_emails: str = ""
    admin_telegram_ids: str = ""

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return _split(self.cors_origins)

    @cached_property
    def admin_email_list(self) -> set[str]:
        return {e.lower() for e in _split(self.admin_emails)}

    @cached_property
    def admin_telegram_id_list(self) -> set[int]:
        return {int(i) for i in _split(self.admin_telegram_ids)}


settings = Settings()
