import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError

from app.core.exception_handlers import validation_exception_handler
from app.core.exception_handlers import general_exception_handler


@pytest.mark.anyio
async def test_validation_error_returns_consistent_response():
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
        "http_version": "1.1",
    })

    exc = RequestValidationError([
        {
            "type": "missing",
            "loc": ("body", "name"),
            "msg": "Field required",
            "input": {},
        }
    ])

    response = await validation_exception_handler(request, exc)
    body = response.body.decode()

    assert response.status_code == 422
    assert "validation_error" in body
    assert "Invalid request data" in body
    assert "Field required" in body
    assert "traceback" not in body.lower()

@pytest.mark.anyio
async def test_unexpected_error_does_not_expose_internal_details():
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
        "http_version": "1.1",
    })

    secret = "internal-database-secret"
    exc = RuntimeError(secret)

    response = await general_exception_handler(request, exc)
    body = response.body.decode()

    assert response.status_code == 500
    assert "unexpected error" in body.lower()
    assert secret not in body
