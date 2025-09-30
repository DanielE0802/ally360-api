from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pydantic import field_validator

class Settings(BaseSettings):
    # Database settings
    POSTGRES_USER: str = 'ally_user'
    POSTGRES_PASSWORD: str = 'ally_pass'
    POSTGRES_DB: str = 'ally_db'
    POSTGRES_HOST: str = 'postgres'
    POSTGRES_PORT: int = 5432
    
    # Redis settings
    REDIS_HOST: str = 'redis'
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # MinIO settings
    MINIO_HOST: str = 'minio'
    MINIO_PORT: int = 9000
    MINIO_PUBLIC_HOST: str = 'localhost'  # Hostname público para presigned URLs
    MINIO_PUBLIC_PORT: int = 9000
    MINIO_ACCESS_KEY: str = 'minioadmin'
    MINIO_SECRET_KEY: str = 'minioadmin'
    MINIO_BUCKET_NAME: str = 'ally360'
    MINIO_USE_SSL: bool = False
    
    # JWT settings
    APP_SECRET_STRING: str = 'your-super-secret-key-here-change-in-production-2024'
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60
    
    # File upload limits
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_FILE_TYPES: list = ["image/jpeg", "image/png", "application/pdf", "text/csv", "application/excel"]
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # Email settings
    EMAIL_SMTP_SERVER: str = 'smtp.gmail.com'
    EMAIL_SMTP_PORT: int = 587
    EMAIL_USE_TLS: bool = True
    EMAIL_USERNAME: str = ''
    EMAIL_PASSWORD: str = ''
    EMAIL_FROM: str = ''
    EMAIL_FROM_NAME: str = 'Ally360'
    FRONTEND_URL: str = 'http://localhost:3000'
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def minio_endpoint(self) -> str:
        return f"{self.MINIO_HOST}:{self.MINIO_PORT}"
    
    @property
    def minio_public_endpoint(self) -> str:
        return f"{self.MINIO_PUBLIC_HOST}:{self.MINIO_PUBLIC_PORT}"

    model_config = SettingsConfigDict(
        extra="allow",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower().strip('"').strip("'") in ("true", "1", "yes", "on")
        return bool(v)
    
    @field_validator("MINIO_USE_SSL", mode="before")
    @classmethod
    def parse_ssl(cls, v):
        if isinstance(v, str):
            return v.lower().strip('"').strip("'") in ("true", "1", "yes", "on")
        return bool(v)
    
    @field_validator("EMAIL_USE_TLS", mode="before")
    @classmethod
    def parse_email_tls(cls, v):
        if isinstance(v, str):
            return v.lower().strip('"').strip("'") in ("true", "1", "yes", "on")
        return bool(v)

settings = Settings()