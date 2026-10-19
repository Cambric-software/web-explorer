from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

def hash_pw(p): return pwd.hash(p)
def check_pw(p, h): return pwd.verify(p, h)

def make_token(uid: int) -> str:
    return jwt.encode({"sub": str(uid), "exp": datetime.utcnow() + timedelta(days=30)}, settings.SECRET_KEY, "HS256")

def optional_user(token: str | None = Depends(oauth2), db: Session = Depends(get_db)) -> User | None:
    if not token: return None
    try:
        uid = int(jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])["sub"])
    except (JWTError, KeyError, ValueError):
        return None
    return db.get(User, uid)

def current_user(u: User | None = Depends(optional_user)) -> User:
    if not u: raise HTTPException(401, "Login required")
    return u

def admin_user(u: User = Depends(current_user)) -> User:
    if not u.is_admin: raise HTTPException(403, "Admins only")
    return u
