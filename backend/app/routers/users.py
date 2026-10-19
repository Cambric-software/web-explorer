from collections import Counter
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..auth import hash_pw, check_pw, make_token, current_user
from ..config import settings
from ..database import get_db
from ..gamification import rank_for, badges
from ..models import User, Visit, Vote, Website, Collection, CollectionItem
from ..schemas import Register, Login, Token, WebsiteOut, CollectionIn

router = APIRouter(prefix="/api", tags=["users"])

@router.post("/auth/register", response_model=Token)
def register(body: Register, db: Session = Depends(get_db)):
    if db.scalar(select(User).where((User.email == body.email) | (User.username == body.username))):
        raise HTTPException(400, "Email or username taken")
    if len(body.password) < 8: raise HTTPException(400, "Password must be at least 8 characters")
    u = User(email=body.email, username=body.username, password_hash=hash_pw(body.password),
             is_admin=body.email.lower() == settings.ADMIN_EMAIL.lower())
    db.add(u); db.commit()
    return Token(access_token=make_token(u.id))

@router.post("/auth/login", response_model=Token)
def login(body: Login, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email))
    if not u or not check_pw(body.password, u.password_hash): raise HTTPException(401, "Invalid credentials")
    return Token(access_token=make_token(u.id))

@router.post("/auth/token", response_model=Token)
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return login(Login(email=form.username, password=form.password), db)

def user_stats(db: Session, u: User) -> dict:
    visits = db.scalars(select(Visit).where(Visit.user_id == u.id)).all()
    cats = Counter(v.website.category for v in visits)
    s = {"sites_visited": len(visits),
         "sites_discovered": sum(1 for v in visits if v.discovered),
         "hidden_gems_found": db.scalar(select(func.count()).select_from(Vote).where(Vote.user_id == u.id, Vote.kind == "gem")),
         "category_counts": dict(cats),
         "favorite_categories": [c for c, _ in cats.most_common(3)]}
    s["rank"] = rank_for(s["sites_visited"]); s["badges"] = badges(s)
    return s

@router.get("/me")
def me(db: Session = Depends(get_db), u: User = Depends(current_user)):
    return {"id": u.id, "email": u.email, "username": u.username, "is_admin": u.is_admin, "stats": user_stats(db, u)}

@router.get("/me/favorites", response_model=list[WebsiteOut])
def favorites(db: Session = Depends(get_db), u: User = Depends(current_user)):
    return db.scalars(select(Website).join(Vote, Vote.website_id == Website.id)
                      .where(Vote.user_id == u.id, Vote.kind == "favorite").order_by(Vote.created_at.desc())).all()

@router.get("/me/history", response_model=list[WebsiteOut])
def history(db: Session = Depends(get_db), u: User = Depends(current_user)):
    return db.scalars(select(Website).join(Visit, Visit.website_id == Website.id)
                      .where(Visit.user_id == u.id).order_by(Visit.created_at.desc()).limit(100)).all()

@router.get("/collections")
def list_collections(db: Session = Depends(get_db), u: User = Depends(current_user)):
    return [{"id": c.id, "name": c.name, "is_public": c.is_public,
             "websites": [WebsiteOut.model_validate(i.website) for i in c.items]}
            for c in db.scalars(select(Collection).where(Collection.user_id == u.id)).all()]

@router.get("/collections/public")
def public_collections(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "websites": [WebsiteOut.model_validate(i.website) for i in c.items]}
            for c in db.scalars(select(Collection).where(Collection.is_public).limit(50)).all()]

@router.post("/collections")
def create_collection(body: CollectionIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    c = Collection(user_id=u.id, name=body.name[:128], is_public=body.is_public); db.add(c); db.commit()
    return {"id": c.id}

def _own(db, cid, u):
    c = db.get(Collection, cid)
    if not c or c.user_id != u.id: raise HTTPException(404)
    return c

@router.post("/collections/{cid}/items/{wid}")
def add_item(cid: int, wid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    _own(db, cid, u)
    if not db.scalar(select(CollectionItem).where(CollectionItem.collection_id == cid, CollectionItem.website_id == wid)):
        db.add(CollectionItem(collection_id=cid, website_id=wid)); db.commit()
    return {"ok": True}

@router.delete("/collections/{cid}/items/{wid}")
def remove_item(cid: int, wid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    _own(db, cid, u)
    db.query(CollectionItem).filter_by(collection_id=cid, website_id=wid).delete(); db.commit()
    return {"ok": True}

@router.delete("/collections/{cid}")
def delete_collection(cid: int, db: Session = Depends(get_db), u: User = Depends(current_user)):
    db.delete(_own(db, cid, u)); db.commit()
    return {"ok": True}
