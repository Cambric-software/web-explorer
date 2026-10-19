import asyncio
from datetime import datetime, timedelta
from celery import Celery
from sqlalchemy import select
from .config import settings
from .database import SessionLocal
from .discovery import discover
from .models import Website
from .verifier import verify_many

celery = Celery("explorer", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery.conf.beat_schedule = {
    "reverify-stale": {"task": "app.tasks.reverify_stale", "schedule": 3600.0},
    "background-discovery": {"task": "app.tasks.discover_batch", "schedule": 900.0, "args": (50,)},
}

@celery.task
def discover_batch(n: int = 50):
    with SessionLocal() as db:
        return len(asyncio.run(discover(db, n)))

@celery.task
def reverify_stale(batch: int = 200):
    """Automatic cleanup: recheck sites older than REVERIFY_DAYS; dead sites are hidden."""
    cutoff = datetime.utcnow() - timedelta(days=settings.REVERIFY_DAYS)
    with SessionLocal() as db:
        sites = db.scalars(select(Website).where(Website.status.in_(["alive", "dead"]), Website.last_verified < cutoff).limit(batch)).all()
        if not sites: return 0
        results = asyncio.run(verify_many([s.url for s in sites]))
        for s, r in zip(sites, results):
            s.last_verified = datetime.utcnow()
            s.status = "alive" if r.ok else ("blocked" if r.reason == "unsafe" else "dead")
        db.commit()
        return len(sites)
