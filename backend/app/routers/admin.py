from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..auth import admin_user
from ..config import in_beta
from ..database import get_db
from ..models import Website, User, Visit, Vote, Submission
from ..schemas import WebsiteOut
from .. import cache

router = APIRouter(prefix="/api", tags=["admin"])

def count(db, *where, model=Website):
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

@router.get("/stats")
def public_stats(db: Session = Depends(get_db)):
    """Discovery statistics (public)."""
    cached = cache.get_json("public_stats")
    if cached: return cached
    day = datetime.utcnow() - timedelta(days=1)
    s = {"total_websites": count(db, Website.status == "alive"),
         "discovered_today": count(db, Website.date_discovered >= day),
         "total_visits": db.scalar(select(func.coalesce(func.sum(Website.times_visited), 0))),
         "by_category": dict(db.execute(select(Website.category, func.count()).where(Website.status == "alive").group_by(Website.category)).all()),
         "beta": in_beta()}
    cache.set_json("public_stats", s, 30)
    return s

@router.get("/admin/stats")
def admin_stats(db: Session = Depends(get_db), _=Depends(admin_user)):
    week = datetime.utcnow() - timedelta(days=7)
    stale = datetime.utcnow() - timedelta(days=30)
    return {
        "total_websites": count(db),
        "alive": count(db, Website.status == "alive"),
        "new_websites_7d": count(db, Website.date_discovered >= week),
        "dead_websites": count(db, Website.status == "dead"),
        "pending_reverification": count(db, Website.status == "alive", Website.last_verified < stale),
        "verified_last_7d": count(db, Website.last_verified >= week),
        "pending_submissions": count(db, Submission.status == "pending", model=Submission),
        "users": count(db, model=User),
        "new_users_7d": count(db, User.created_at >= week, model=User),
        "visits_7d": count(db, Visit.created_at >= week, model=Visit),
        "votes_total": count(db, model=Vote),
        "by_category": dict(db.execute(select(Website.category, func.count()).group_by(Website.category)).all()),
        "by_source": dict(db.execute(select(Website.source, func.count()).group_by(Website.source)).all()),
        "beta": in_beta(),
    }

@router.get("/admin/websites", response_model=list[WebsiteOut])
def admin_websites(status: str | None = None, db: Session = Depends(get_db), _=Depends(admin_user)):
    q = select(Website)
    if status: q = q.where(Website.status == status)
    return db.scalars(q.order_by(Website.date_discovered.desc()).limit(200)).all()

@router.post("/admin/websites/{wid}/status")
def set_status(wid: int, status: str, db: Session = Depends(get_db), _=Depends(admin_user)):
    w = db.get(Website, wid); w.status = status; db.commit()
    return {"ok": True}

@router.post("/admin/discover")
def trigger_discover(_=Depends(admin_user)):
    from ..tasks import discover_batch
    discover_batch.delay(50); return {"queued": True}

@router.post("/admin/reverify")
def trigger_reverify(_=Depends(admin_user)):
    from ..tasks import reverify_stale
    reverify_stale.delay(); return {"queued": True}
