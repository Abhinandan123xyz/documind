from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "DocuMind AI"
    DEBUG: bool = True
    SECRET_KEY: str = "documind-secret-key-2024"
    DATABASE_URL: str = "sqlite+aiosqlite:///./documind.db"
    GOOGLE_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    TAVILY_API_KEY: str = ""
    JWT_SECRET: str = "documind-jwt-secret-2024"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()