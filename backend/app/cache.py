import json
import redis
from .config import settings

r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
FRONTIER = "frontier"

def push_frontier(links: list[str]):
    try:
        if links: r.sadd(FRONTIER, *links[:100])
    except redis.RedisError: pass

def pop_frontier(n: int) -> list[str]:
    try: return r.spop(FRONTIER, n) or []
    except redis.RedisError: return []

def incr(key: str, by: int = 1):
    try: r.incrby(key, by)
    except redis.RedisError: pass

def get_json(key):
    try:
        v = r.get(key); return json.loads(v) if v else None
    except redis.RedisError: return None

def set_json(key, val, ttl=60):
    try: r.setex(key, ttl, json.dumps(val, default=str))
    except redis.RedisError: pass
