"""
Small in-process TTL cache for slow, rarely-changing market-data calls.

Caches only plain values (dicts, lists, scalars). DataFrames are not cached, because callers
may mutate them. Each process keeps its own cache; that is sufficient for a single instance.
"""
import functools
import threading
import time
from typing import Any, Callable

_store: dict = {}
_lock = threading.Lock()


def ttl_cache(ttl_seconds: int) -> Callable:
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> Any:
            # 'db' only controls where results are persisted, so it is not part of the cache key
            key = (fn.__module__, fn.__qualname__, args, tuple(sorted((k, v) for k, v in kwargs.items() if k != "db")))
            now = time.time()
            with _lock:
                hit = _store.get(key)
                if hit and now - hit[0] < ttl_seconds:
                    return hit[1]
            value = fn(*args, **kwargs)
            if value:
                with _lock:
                    _store[key] = (now, value)
            return value
        return wrapper
    return decorator
