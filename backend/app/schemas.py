from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict

class WebsiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; url: str; title: str; description: str; category: str
    country: str | None; language: str | None
    date_discovered: datetime; last_verified: datetime
    times_visited: int; times_liked: int; times_disliked: int
    hidden_gem_score: float; status: str

class ExploreOut(BaseModel):
    website: WebsiteOut
    mode: str
    newly_discovered: int

class Register(BaseModel):
    email: EmailStr; username: str; password: str

class Login(BaseModel):
    email: EmailStr; password: str

class Token(BaseModel):
    access_token: str; token_type: str = "bearer"

class VoteIn(BaseModel):
    kind: str

class SubmitIn(BaseModel):
    url: str

class CollectionIn(BaseModel):
    name: str; is_public: bool = True
