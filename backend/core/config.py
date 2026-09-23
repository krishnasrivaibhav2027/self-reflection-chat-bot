from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    ENVIRONMENT: str
    DEBUG: bool
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ALLOWED_ORIGINS: List[str]
    OPENROUTER_API_KEY: str
    XKIRO_API_KEY: str
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file= "backend/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()