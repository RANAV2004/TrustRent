import time
from collections import deque
from fastapi import Request

class RateLimiter:

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def _recent(self, key: str) -> deque[float]:
        q = self._hits.setdefault(key, deque())
        cutoff = time.monotonic() - self.window
        while q and q[0] < cutoff:
            q.popleft()
        if not q:
            self._hits.pop(key, None)
            q = self._hits.setdefault(key, deque())
        return q

    def blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self.limit

    def hit(self, key: str) -> None:
        self._recent(key).append(time.monotonic())

    def allow(self, key: str) -> bool:
        if self.blocked(key):
            return False
        self.hit(key)
        return True

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._hits.clear()
        else:
            self._hits.pop(key, None)

def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

LOGIN_FAILURES_PER_ACCOUNT = RateLimiter(10, 15 * 60)
LOGIN_FAILURES_PER_IP = RateLimiter(50, 15 * 60)
EMAILS_PER_IP = RateLimiter(10, 60 * 60)
LAWYER_APPLICATIONS_PER_IP = RateLimiter(5, 60 * 60)
SIGNUP_CODES_PER_EMAIL = RateLimiter(5, 24 * 60 * 60)
RESET_CODES_PER_EMAIL = RateLimiter(5, 24 * 60 * 60)
CLIENT_ERRORS_PER_IP = RateLimiter(20, 60 * 60)
ALERTS_PER_KIND = RateLimiter(1, 30 * 60)
ALERTS_TOTAL = RateLimiter(10, 60 * 60)
TICKETS_PER_USER = RateLimiter(10, 24 * 60 * 60)
TWO_FACTOR_FAILURES = RateLimiter(5, 15 * 60)
NOTIFY_PER_THREAD = RateLimiter(1, 15 * 60)
NOTIFY_ADMINS = RateLimiter(1, 60 * 60)
ALL_LIMITERS = (LOGIN_FAILURES_PER_ACCOUNT, LOGIN_FAILURES_PER_IP, EMAILS_PER_IP, LAWYER_APPLICATIONS_PER_IP,
                SIGNUP_CODES_PER_EMAIL, RESET_CODES_PER_EMAIL, CLIENT_ERRORS_PER_IP, ALERTS_PER_KIND, ALERTS_TOTAL,
                NOTIFY_PER_THREAD, NOTIFY_ADMINS, TWO_FACTOR_FAILURES, TICKETS_PER_USER)
