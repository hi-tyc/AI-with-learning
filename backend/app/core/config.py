from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    SECRET_KEY: str = "study-buddy-secret-key-2024"
    BACKEND_PORT: int = 6003
    UPLOAD_DIR: str = "uploads"
    DATA_DIR: str = "../AI伴学数据"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
