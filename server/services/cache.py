import time
import threading
import functools

_MISS = object()  # sentinel: distinct from None so cached None is handled correctly


class TTLCache:
    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._store.get(key, _MISS)
            if entry is _MISS:
                return _MISS
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                return _MISS
            return value

    def set(self, key, value, ttl):
        with self._lock:
            self._store[key] = (value, time.time() + ttl)

    def invalidate(self, key):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()


_cache = TTLCache()


def cached(ttl):
    """Decorator: cache the return value of a function for `ttl` seconds."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (fn.__module__, fn.__name__, args, tuple(sorted(kwargs.items())))
            hit = _cache.get(key)
            if hit is not _MISS:
                return hit
            result = fn(*args, **kwargs)
            _cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator
