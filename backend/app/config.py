from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App
    APP_NAME: str = "DocuMind AI"
    DEBUG: bool = True
    SECRET_KEY: str = "change-this-in-production"
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./documind.db"
    
    # LLM (we'll fill these in Phase 2)
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""        # for embeddings
    
    # Vector store (Phase 2)
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    
    # Web search (Phase 3)
    TAVILY_API_KEY: str = ""
    
    # Auth
    JWT_SECRET: str = "change-this-too"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()