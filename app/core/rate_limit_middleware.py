
import logging

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.rate_limiter import check_rate_limit
from app.core.security import decode_token

logger = logging.getLogger(__name__)

EXCLUDED_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health/database",
}


async def rate_limit_middleware(request: Request, call_next):
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)

    if request.method == "OPTIONS" or request.url.path in EXCLUDED_PATHS:
        return await call_next(request)

    # Identify authenticated users by verified access-token subject.
    authenticated = False
    client_key = None

    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        try:
            payload = decode_token(token)
            if payload.get("type") == "access" and payload.get("sub"):
                client_key = f"user:{payload['sub']}"
                authenticated = True
        except (jwt.PyJWTError, ValueError, TypeError):
            pass

    # Requests without a valid access token are tracked by client IP.
    if client_key is None:
        client_host = request.client.host if request.client else "unknown"
        client_key = f"ip:{client_host}"

    result = await run_in_threadpool(
        check_rate_limit,
        client_key,
        authenticated=authenticated,
    )

    headers = {
        "X-RateLimit-Limit": str(result.limit),
        "X-RateLimit-Remaining": str(result.remaining),
    }

    if not result.allowed:
        headers["Retry-After"] = str(result.retry_after)

        return JSONResponse(
            status_code=429,
            headers=headers,
            content={
                "success": False,
                "error": {
                    "type": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                },
            },
        )

    response = await call_next(request)

    response.headers.update(headers)
    return response
