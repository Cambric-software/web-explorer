from datetime import datetime
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

CATEGORIES = ["Developer","Games","Art","Retro","Education","Business","Technology","Communities","Personal","Tools","Random"]

class Meta(Base):
    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))

class Website(Base):
    __tablename__ = "websites"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="Random", index=True)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    date_discovered: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_verified: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    times_visited: Mapped[int] = mapped_column(Integer, default=0)
    times_liked: Mapped[int] = mapped_column(Integer, default=0)
    times_disliked: Mapped[int] = mapped_column(Integer, default=0)
    hidden_gem_score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(16), default="alive", index=True)  # alive|dead|pending|blocked
    source: Mapped[str] = mapped_column(String(32), default="seed")
    discovered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Visit(Base):
    __tablename__ = "visits"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    website_id: Mapped[int] = mapped_column(ForeignKey("websites.id"))
    discovered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    website = relationship("Website")

class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (UniqueConstraint("user_id", "website_id", "kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    website_id: Mapped[int] = mapped_column(ForeignKey("websites.id"))
    kind: Mapped[str] = mapped_column(String(16))  # like|gem|dislike|favorite
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    website = relationship("Website")

class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    items = relationship("CollectionItem", cascade="all, delete-orphan")

class CollectionItem(Base):
    __tablename__ = "collection_items"
    __table_args__ = (UniqueConstraint("collection_id", "website_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"))
    website_id: Mapped[int] = mapped_column(ForeignKey("websites.id"))
    website = relationship("Website")

class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2048))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
