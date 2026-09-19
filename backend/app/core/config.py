from pydantic_settings import BaseSettings
from pathlib import Path
import secrets


class Settings(BaseSettings):
    APP_NAME: str = "Recorded World"
    APP_VERSION: str = "0.4.0"
    DEBUG: bool = True

    # Database — supports SQLite (dev) and PostgreSQL (prod)
    DATABASE_URL: str = "sqlite:///./recorded_world.db"
    DATABASE_ECHO: bool = False

    # PostgreSQL specific (used when DATABASE_URL starts with postgresql)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "recorded_world"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""

    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB

    WS_HOST: str = "0.0.0.0"
    WS_PORT: int = 8765

    CORS_ORIGINS: list[str] = ["*"]

    # JWT Authentication
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # API Key Management
    API_KEY_PREFIX: str = "rw_"
    API_KEY_LENGTH: int = 32

    # Rate Limiting
    RATE_LIMIT_API_REQUESTS: int = 100
    RATE_LIMIT_UPLOAD_REQUESTS: int = 10
    RATE_LIMIT_WS_MESSAGES: int = 30
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Security
    ALLOWED_UPLOAD_EXTENSIONS: list[str] = [".mp4", ".mov", ".avi", ".webm", ".jpg", ".jpeg", ".png"]
    MAX_FILE_SIZE_MB: int = 500
    SIGNED_URL_EXPIRY_SECONDS: int = 3600

    # Logging
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    @property
    def is_postgres(self) -> bool:
        """Check if using PostgreSQL."""
        return self.DATABASE_URL.startswith("postgresql")

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite."""
        return self.DATABASE_URL.startswith("sqlite")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
