from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_, delete
from sqlalchemy.orm import Session
from ..auth import current_user, optional_user
from ..database import get_db
from ..gamification import GEM_POINTS
from ..models import Website, Vote, Submission, User, CATEGORIES
from ..schemas import WebsiteOut, VoteIn, SubmitIn
from ..verifier import normalize

router = APIRouter(prefix="/api", tags=["websites"])
LANG_WORDS = {"japanese":"ja","french":"fr","german":"de","spanish":"es","arabic":"ar","russian":"ru","chinese":"zh","korean":"ko","italian":"it","portuguese":"pt"}

@router.get("/categories")
def categories(): return CATEGORIES

@router.get("/search", response_model=list[WebsiteOut])
def search(q: str = "", category: str | None = None, sort: str = "gem", limit: int = 30, offset: int = 0, db: Session = Depends(get_db)):
    stmt = select(Website).where(Website.status == "alive")
    words = q.lower().split()
    for w in list(words):
        if w in LANG_WORDS:
            stmt = stmt.where(Website.language.ilike(LANG_WORDS[w] + "%")); words.remove(w)
        for c in CATEGORIES:
            if w.rstrip("s") == c.lower().rstrip("s"):
                stmt = stmt.where(Website.category == c); words.remove(w) if w in words else None
    if category: stmt = stmt.where(Website.category == category)
    rest = [w for w in words if w not in ("websites","website","sites","site","projects")]
    for w in rest:
        like = f"%{w}%"
        stmt = stmt.where(or_(Website.title.ilike(like), Website.description.ilike(like), Website.url.ilike(like)))
    order = {"gem": Website.hidden_gem_score.desc(), "new": Website.date_discovered.desc(), "popular": Website.times_visited.desc()}.get(sort)
    return db.scalars(stmt.order_by(order).offset(offset).limit(min(limit, 100))).all()

@router.get("/websites/{wid}", response_model=WebsiteOut)
def get_site(wid: int, db: Session = Depends(get_db)):
    w = db.get(Website, wid)
    if not w: raise HTTPException(404)
    return w

@router.post("/websites/{wid}/vote")
def vote(wid: int, body: VoteIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if body.kind not in GEM_POINTS: raise HTTPException(400, "Invalid vote")
    w = db.get(Website, wid)
    if not w: raise HTTPException(404)
    existing = db.scalar(select(Vote).where(Vote.user_id == user.id, Vote.website_id == wid, Vote.kind == body.kind))
    sign = -1 if existing else 1
    if existing: db.delete(existing)
    else:
        # like and dislike are mutually exclusive
        opposite = {"like": "dislike", "dislike": "like"}.get(body.kind)
        if opposite:
            o = db.scalar(select(Vote).where(Vote.user_id == user.id, Vote.website_id == wid, Vote.kind == opposite))
            if o:
                db.delete(o); w.hidden_gem_score -= GEM_POINTS[opposite]
                if opposite == "like": w.times_liked -= 1
                else: w.times_disliked -= 1
        db.add(Vote(user_id=user.id, website_id=wid, kind=body.kind))
    w.hidden_gem_score += sign * GEM_POINTS[body.kind]
    if body.kind == "like": w.times_liked += sign
    if body.kind == "dislike": w.times_disliked += sign
    db.commit()
    return {"active": not existing, "hidden_gem_score": w.hidden_gem_score}

@router.get("/websites/{wid}/my-votes")
def my_votes(wid: int, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    if not user: return []
    return db.scalars(select(Vote.kind).where(Vote.user_id == user.id, Vote.website_id == wid)).all()

@router.post("/submit")
def submit(body: SubmitIn, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    url = normalize(body.url)
    if db.scalar(select(Website.id).where(Website.url == url)): return {"status": "already known"}
    db.add(Submission(url=url, user_id=user.id if user else None)); db.commit()
    return {"status": "queued"}
