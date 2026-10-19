from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import Base, engine
from .routers import explore, websites, users, admin

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Website Explorer API", description="Discover the Internet Again. — Cambric Software & Hardware Studios")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (explore, websites, users, admin):
    app.include_router(r.router)

@app.get("/api/health")
def health(): return {"ok": True}
