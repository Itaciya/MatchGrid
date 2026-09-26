from fastapi import Request, status
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import AppException


async def app_exception_handler(
    request: Request,
    exc: AppException,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "type": "application_error",
                "message": exc.detail,
            },
        },
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "type": "validation_error",
                "message": "Invalid request data",
                "details": [
                    {
                        "type": error.get("type"),
                        "loc": error.get("loc"),
                        "message": error.get("msg"),
                    }
                    for error in exc.errors()
                ],
            },
        },
    )


async def database_exception_handler(
    request: Request,
    exc: SQLAlchemyError,
):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "type": "database_error",
                "message": "A database error occurred",
            },
        },
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "type": "http_error",
                "message": str(exc.detail),
            },
        },
    )


async def general_exception_handler(
    request: Request,
    exc: Exception,
):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "type": "internal_server_error",
                "message": "An unexpected error occurred",
            },
        },
    )