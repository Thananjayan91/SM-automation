"""Application configuration classes.

Load settings from environment variables. Never hardcode secrets here.
"""
import os
from datetime import timedelta


def _normalize_database_url(url: str | None) -> str:
    """Ensure database URL uses postgresql:// dialect required by SQLAlchemy 2.0."""
    if not url:
        return "postgresql://postgres:postgres@localhost:5432/ai_social_publisher"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class BaseConfig:
    """Shared configuration across all environments."""

    # Flask core
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: int = 3600

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI: str = _normalize_database_url(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Redis (general)
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Celery / Redis
    CELERY_BROKER_URL: str = os.environ.get("CELERY_BROKER_URL") or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.environ.get("CELERY_RESULT_BACKEND") or os.environ.get("REDIS_URL", "redis://localhost:6379/1")

    # Flask-Limiter
    RATELIMIT_STORAGE_URL: str = os.environ.get("RATELIMIT_STORAGE_URL") or os.environ.get("REDIS_URL", "memory://")
    RATELIMIT_DEFAULT: str = "200 per day;50 per hour"

    # Session / cookies
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"
    REMEMBER_COOKIE_HTTPONLY: bool = True
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # S3 / object storage
    S3_BUCKET: str = os.environ.get("S3_BUCKET", "ai-social-publisher-media")
    S3_REGION: str = os.environ.get("S3_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: str = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    S3_ENDPOINT_URL: str = os.environ.get("S3_ENDPOINT_URL", "")

    # Encryption
    CREDENTIAL_ENCRYPTION_KEY: str = os.environ.get("CREDENTIAL_ENCRYPTION_KEY", "")

    # Meta / Facebook
    META_APP_ID: str = os.environ.get("META_APP_ID", "")
    META_APP_SECRET: str = os.environ.get("META_APP_SECRET", "")
    META_REDIRECT_URI: str = os.environ.get("META_REDIRECT_URI", "")

    # Platform admin
    PLATFORM_ADMIN_SECRET: str = os.environ.get("PLATFORM_ADMIN_SECRET", "")

    # File uploads
    MAX_CONTENT_LENGTH: int = 20 * 1024 * 1024  # 20 MB
    ALLOWED_IMAGE_EXTENSIONS: set = {"jpg", "jpeg", "png", "gif", "webp"}
    MAX_IMAGE_WIDTH: int = 8000
    MAX_IMAGE_HEIGHT: int = 8000


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True
    SESSION_COOKIE_SECURE: bool = False
    REMEMBER_COOKIE_SECURE: bool = False


class ProductionConfig(BaseConfig):
    DEBUG: bool = False
    SESSION_COOKIE_SECURE: bool = True
    REMEMBER_COOKIE_SECURE: bool = True
    WTF_CSRF_SSL_STRICT: bool = False


class TestingConfig(BaseConfig):
    TESTING: bool = True
    WTF_CSRF_ENABLED: bool = False
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "TEST_DATABASE_URL", "sqlite:///:memory:"
    )
    RATELIMIT_ENABLED: bool = False
    SERVER_NAME: str = "localhost"


config_map: dict = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
