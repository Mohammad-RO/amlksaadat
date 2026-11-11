from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{(DATA_DIR / 'amlak.db').as_posix()}"
    secret_key: str = "change-this-secret"
    admin_username: str = "admin"
    admin_password: str = "admin123"
    telegram_bot_token: str = ""
    telegram_archive_chat_id: str = ""
    llm_base_url: str = "https://api.gapgpt.app/v1"
    llm_api_key: str = "aaa"
    llm_model: str = "gapgpt/deepseek-v4.1-flash"
    divar_proxy: str = ""
    telegram_proxy: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
