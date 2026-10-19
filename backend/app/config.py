from datetime import date
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://explorer:explorer@localhost:5432/explorer"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me"
    ADMIN_EMAIL: str = "admin@example.com"
    BETA_DAYS: int = 10
    LAUNCH_DATE: str = ""
    VERIFY_TIMEOUT: float = 8.0
    GOOGLE_SAFE_BROWSING_KEY: str = ""
    BETA_CANDIDATES: int = 50
    REVERIFY_DAYS: int = 30

settings = Settings()

def launch_date() -> date:
    if settings.LAUNCH_DATE:
        return date.fromisoformat(settings.LAUNCH_DATE)
    from .database import SessionLocal
    from .models import Meta
    with SessionLocal() as db:
        m = db.get(Meta, "launch_date")
        if not m:
            m = Meta(key="launch_date", value=date.today().isoformat()); db.add(m); db.commit()
        return date.fromisoformat(m.value)

def in_beta() -> bool:
    return (date.today() - launch_date()).days < settings.BETA_DAYS
