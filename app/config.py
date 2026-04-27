from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    app_name: str = "AutoTasker"
    debug: bool = True
    secret_key: str = Field(default="autotasker-dev-secret-key-for-local-jwt-32b", min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    database_url: str = Field(
        default=f"sqlite:///{(DATA_DIR / 'autotasker.db').as_posix()}",
        description="Use mysql+pymysql://user:pass@host:3306/autotasker for the course-style deployment.",
    )
    mysql_host: Optional[str] = None
    mysql_port: int = 3306
    mysql_user: Optional[str] = None
    mysql_password: Optional[str] = None
    mysql_database: Optional[str] = None
    auto_create_schema: bool = False

    openai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    qwen_api_key: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    zhipu_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_version: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_database_url(self) -> str:
        if self.mysql_host and self.mysql_user and self.mysql_database:
            password = quote_plus(self.mysql_password or "")
            return (
                f"mysql+pymysql://{self.mysql_user}:{password}"
                f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
            )
        return self.database_url


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
