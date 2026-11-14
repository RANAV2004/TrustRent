import threading
import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request, status
from app.core.config import settings


class RateLimiter:  # in-memory sliding window; per process (use Redis when running several instances)
    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: float) -> float | None:
        """Record one hit. Returns seconds to wait when the limit is exceeded, else None."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return q[0] + window - now
            q.append(now)
            if len(self._hits) > 50_000:  # drop idle keys so memory stays bounded
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - 3600][:10_000]:
                    self._hits.pop(k, None)
            return None

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce(key: str, limit: int, window: float, message: str = "Too many attempts. Please wait and try again.") -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    wait = limiter.hit(key, limit, window)
    if wait is not None:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail={"message": message, "field": None},
                            headers={"Retry-After": str(max(1, int(wait) + 1))})


def ip_limit(name: str, limit: int, window: float):
    def dependency(request: Request) -> None:
        enforce(f"{name}:ip:{client_ip(request)}", limit, window)
    return dependency
