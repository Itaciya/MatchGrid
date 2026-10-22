
import pytest

from app.core import rate_limiter
from app.core.rate_limiter import check_rate_limit
from redis.exceptions import RedisError
from starlette.requests import Request
from starlette.responses import Response

from app.core import rate_limit_middleware as middleware
from app.core.rate_limiter import RateLimitResult

class FakeRedis:
    """Small fake Redis client for deterministic rate-limit tests."""

    def __init__(self):
        self.counts = {}

    def eval(self, script, numkeys, key, window):
        count = self.counts.get(key, 0) + 1
        self.counts[key] = count
        return [count, int(window)]


@pytest.fixture
def fake_redis(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(rate_limiter, "get_redis", lambda: client)
    monkeypatch.setattr(rate_limiter.settings, "RATE_LIMIT_PUBLIC_REQUESTS", 2)
    monkeypatch.setattr(
        rate_limiter.settings,
        "RATE_LIMIT_AUTHENTICATED_REQUESTS",
        3,
    )
    monkeypatch.setattr(rate_limiter.settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    return client


def test_public_requests_within_limit_are_allowed(fake_redis):
    first = check_rate_limit("ip:127.0.0.1", authenticated=False)
    second = check_rate_limit("ip:127.0.0.1", authenticated=False)

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0


def test_excessive_public_requests_are_blocked(fake_redis):
    check_rate_limit("ip:127.0.0.1", authenticated=False)
    check_rate_limit("ip:127.0.0.1", authenticated=False)

    third = check_rate_limit("ip:127.0.0.1", authenticated=False)

    assert third.allowed is False
    assert third.remaining == 0
    assert third.retry_after >= 1


def test_authenticated_user_has_separate_limit(fake_redis):
    public = check_rate_limit("ip:127.0.0.1", authenticated=False)
    authenticated = check_rate_limit("user:42", authenticated=True)

    assert public.limit == 2
    assert authenticated.limit == 3
    assert authenticated.allowed is True


def test_different_clients_have_separate_counters(fake_redis):
    first = check_rate_limit("ip:127.0.0.1", authenticated=False)
    second = check_rate_limit("ip:127.0.0.2", authenticated=False)

    assert first.remaining == 1
    assert second.remaining == 1
def make_request(path="/test", client_host="127.0.0.1"):
    return Request({
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": (client_host, 12345),
        "scheme": "http",
        "http_version": "1.1",
    })


@pytest.mark.anyio
async def test_middleware_blocks_excessive_requests(monkeypatch):
    monkeypatch.setattr(
        middleware.settings, "RATE_LIMIT_ENABLED", True
    )
    monkeypatch.setattr(
        middleware,
        "check_rate_limit",
        lambda *args, **kwargs: RateLimitResult(
            allowed=False,
            limit=2,
            remaining=0,
            retry_after=30,
        ),
    )

    async def call_next(request):
        return Response("should not be reached")

    response = await middleware.rate_limit_middleware(
        make_request(), call_next
    )

    assert response.status_code == 429
    assert response.headers["X-RateLimit-Limit"] == "2"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert response.headers["Retry-After"] == "30"

    body = response.body.decode()
    assert "rate_limit_exceeded" in body
    assert "Too many requests" in body


@pytest.mark.anyio
async def test_middleware_allows_requests_within_limit(monkeypatch):
    monkeypatch.setattr(
        middleware.settings, "RATE_LIMIT_ENABLED", True
    )
    monkeypatch.setattr(
        middleware,
        "check_rate_limit",
        lambda *args, **kwargs: RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            retry_after=0,
        ),
    )

    async def call_next(request):
        return Response("OK", status_code=200)

    response = await middleware.rate_limit_middleware(
        make_request(), call_next
    )

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "100"
    assert response.headers["X-RateLimit-Remaining"] == "99"

def test_redis_failure_fails_open(monkeypatch):
    def raise_redis_error():
        raise RedisError("Redis unavailable")

    monkeypatch.setattr(rate_limiter, "get_redis", raise_redis_error)

    result = check_rate_limit("ip:127.0.0.1", authenticated=False)

    assert result.allowed is True
    assert result.remaining == result.limit
    assert result.retry_after == 0


@pytest.mark.anyio
async def test_middleware_skips_when_rate_limiting_disabled(monkeypatch):
    monkeypatch.setattr(
        middleware.settings, "RATE_LIMIT_ENABLED", False
    )

    async def call_next(request):
        return Response("OK", status_code=200)

    response = await middleware.rate_limit_middleware(
        make_request(), call_next
    )

    assert response.status_code == 200
    assert response.body == b"OK"


@pytest.mark.anyio
async def test_middleware_skips_excluded_health_path(monkeypatch):
    def unexpected_rate_check(*args, **kwargs):
        raise AssertionError("Rate limiter should not be called")

    monkeypatch.setattr(
        middleware.settings, "RATE_LIMIT_ENABLED", True
    )
    monkeypatch.setattr(
        middleware, "check_rate_limit", unexpected_rate_check
    )

    async def call_next(request):
        return Response("OK", status_code=200)

    response = await middleware.rate_limit_middleware(
        make_request("/health/database"), call_next
    )

    assert response.status_code == 200
