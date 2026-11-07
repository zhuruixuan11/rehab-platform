import logging
import threading
import time

from app.config import settings

logger = logging.getLogger("fitness.redis")


class MemoryCache:
    """Redis 不可用时的进程内降级缓存（含 TTL 与有序集合）。"""

    def __init__(self):
        self._data = {}
        self._expiry = {}
        self._zsets = {}
        self._lock = threading.Lock()

    def _alive(self, key):
        exp = self._expiry.get(key)
        if exp is not None and exp < time.time():
            self._data.pop(key, None)
            self._expiry.pop(key, None)
            return False
        return key in self._data

    def get(self, key):
        with self._lock:
            if self._alive(key):
                return self._data[key]
        return None

    def set(self, key, value, ttl=None):
        with self._lock:
            self._data[key] = value
            if ttl:
                self._expiry[key] = time.time() + ttl
            else:
                self._expiry.pop(key, None)
        return True

    def delete(self, *keys):
        with self._lock:
            for key in keys:
                self._data.pop(key, None)
                self._expiry.pop(key, None)
                self._zsets.pop(key, None)

    def incr(self, key, amount=1):
        with self._lock:
            value = int(self._data.get(key, 0)) + amount
            self._data[key] = value
            return value

    def zadd(self, key, mapping):
        with self._lock:
            zset = self._zsets.setdefault(key, {})
            zset.update(mapping)
        return True

    def zincrby(self, key, amount, member):
        with self._lock:
            zset = self._zsets.setdefault(key, {})
            zset[member] = zset.get(member, 0) + amount
            return zset[member]

    def zrevrange(self, key, start, end, withscores=False):
        with self._lock:
            zset = self._zsets.get(key, {})
            items = sorted(zset.items(), key=lambda kv: kv[1], reverse=True)
        if end != -1:
            items = items[start:end + 1]
        else:
            items = items[start:]
        if withscores:
            return [(m, s) for m, s in items]
        return [m for m, _ in items]

    def expire(self, key, ttl):
        with self._lock:
            if key in self._data or key in self._zsets:
                self._expiry[key] = time.time() + ttl
                return True
        return False


class Cache:
    """统一缓存入口：优先 Redis，连接失败自动降级内存缓存。"""

    def __init__(self):
        self._redis = None
        self._fallback = MemoryCache()
        self.available = False
        self._connect()

    def _connect(self):
        try:
            import redis

            client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            self._redis = client
            self.available = True
            logger.info("Redis 连接成功: %s:%s/%s", settings.REDIS_HOST, settings.REDIS_PORT, settings.REDIS_DB)
        except Exception as exc:
            self.available = False
            logger.warning("Redis 不可用(%s)，使用内存缓存降级", exc)

    # ---- 通用 KV ----
    def get(self, key):
        if self.available:
            try:
                return self._redis.get(key)
            except Exception:
                pass
        return self._fallback.get(key)

    def set(self, key, value, ttl=None):
        if self.available:
            try:
                return self._redis.set(key, value, ex=ttl)
            except Exception:
                pass
        return self._fallback.set(key, value, ttl)

    def delete(self, *keys):
        if self.available:
            try:
                return self._redis.delete(*keys)
            except Exception:
                pass
        return self._fallback.delete(*keys)

    def incr(self, key, amount=1):
        if self.available:
            try:
                return self._redis.incr(key, amount)
            except Exception:
                pass
        return self._fallback.incr(key, amount)

    # ---- 有序集合（排行榜） ----
    def zadd(self, key, mapping):
        if self.available:
            try:
                return self._redis.zadd(key, mapping)
            except Exception:
                pass
        return self._fallback.zadd(key, mapping)

    def zincrby(self, key, amount, member):
        if self.available:
            try:
                return self._redis.zincrby(key, amount, member)
            except Exception:
                pass
        return self._fallback.zincrby(key, amount, member)

    def zrevrange(self, key, start=0, end=-1, withscores=False):
        if self.available:
            try:
                return self._redis.zrevrange(key, start, end, withscores)
            except Exception:
                pass
        return self._fallback.zrevrange(key, start, end, withscores)

    def expire(self, key, ttl):
        if self.available:
            try:
                return self._redis.expire(key, ttl)
            except Exception:
                pass
        return self._fallback.expire(key, ttl)


cache = Cache()
