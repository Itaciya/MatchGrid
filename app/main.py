import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes.health import router as health_router
from app.core.exception_handlers import (
    app_exception_handler,
    database_exception_handler,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.exceptions import AppException
from app.core.logging import configure_logging
from app.data_access.database import test_database_connection
from app.modules.dispute.routes import router as dispute_router
from app.modules.match.routes import router as match_router
from app.modules.organiser.routes import router as organiser_router
from app.modules.player_team.routes import router as player_team_router
from app.modules.registration.routes import router as registration_router
from app.modules.score.routes import router as score_router
from app.modules.scorer.routes import router as scorer_router
from app.modules.spectator.routes import router as spectator_router
from app.modules.tournament.routes import router as tournament_router
from app.modules.user.routes import router as user_router
from app.modules.venue.routes import router as venue_router


configure_logging()

app = FastAPI()
logger = logging.getLogger(__name__)

logger.info("MatchGrid API application initialized")


# Exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)
app.add_exception_handler(
    SQLAlchemyError,
    database_exception_handler,
)
app.add_exception_handler(
    StarletteHTTPException,
    http_exception_handler,
)
app.add_exception_handler(Exception, general_exception_handler)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# HTTP request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration = time.perf_counter() - start_time
        logger.exception(
            "Unhandled exception during %s %s (%.3fs)",
            request.method,
            request.url.path,
            duration,
        )
        raise

    duration = time.perf_counter() - start_time

    log_method = (
        logger.error
        if response.status_code >= 500
        else logger.warning
        if response.status_code >= 400
        else logger.info
    )

    log_method(
        "%s %s -> %s (%.3fs)",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    return response


# Register API routers
app.include_router(health_router)
app.include_router(organiser_router)
app.include_router(player_team_router)
app.include_router(spectator_router)
app.include_router(scorer_router)
app.include_router(user_router)
app.include_router(registration_router)
app.include_router(match_router)
app.include_router(score_router)
app.include_router(venue_router)
app.include_router(tournament_router)
app.include_router(dispute_router)


# Root endpoint
@app.get("/")
def root():
    return {
        "message": "MatchGrid API is running!",
        "environment": "configured",
    }


# Database health endpoint
@app.get("/health/database")
def database_health():
    result = test_database_connection()

    if result == "Database connection successful":
        logger.info("Database health check successful")
    else:
        logger.error("Database health check failed")

    return {"database": result}