import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..auth import optional_user
from ..config import settings, in_beta
from ..database import get_db
from ..discovery import discover, random_alive
from ..models import Visit, User
from ..schemas import ExploreOut, WebsiteOut

router = APIRouter(prefix="/api", tags=["explore"])

@router.get("/explore", response_model=ExploreOut)
async def explore(category: str | None = None, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    new = []
    if in_beta():
        mode = "beta"
        new = await discover(db, settings.BETA_CANDIDATES, user.id if user else None)
    elif random.random() < 0.5:
        mode = "discovery"
        new = await discover(db, 15, user.id if user else None)
    else:
        mode = "database"
    pool = [w for w in new if not category or category == "Random" or w.category == category]
    site = random.choice(pool) if pool else random_alive(db, category) or random_alive(db)
    if not site: raise HTTPException(404, "No websites yet — try again in a moment")
    site.times_visited += 1
    if user:
        db.add(Visit(user_id=user.id, website_id=site.id, discovered=site in new))
    db.commit(); db.refresh(site)
    return ExploreOut(website=WebsiteOut.model_validate(site), mode=mode, newly_discovered=len(new))
