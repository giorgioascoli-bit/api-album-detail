from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    port: int = 8000
    host: str = "0.0.0.0"
    debug: bool = False

    # Discogs Configuration
    discogs_token: Optional[str] = None
    discogs_user_agent: str = "AlbumDetailAPI/1.0.0"

    # AI Configuration (Gemini API)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"

    # Cache Configuration
    cache_ttl_seconds: int = 86400  # 24 hours

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
