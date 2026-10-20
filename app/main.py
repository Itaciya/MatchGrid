
import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress

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
from app.modules.notification.routes import router as notification_router
from app.modules.notification.services.upcoming_match_scheduler import (
    start_reminder_scheduler,
    stop_reminder_scheduler,
)
from app.modules.official_assignment.routes import (
    router as official_assignment_router,
)
from app.modules.organiser.routes import router as organiser_router
from app.modules.player_team.routes import router as player_team_router
from app.modules.registration.routes import router as registration_router
from app.modules.score.routes import router as score_router
from app.modules.scorer.routes import router as scorer_router
from app.modules.spectator.routes import router as spectator_router
from app.modules.tournament.routes import router as tournament_router
from app.modules.user.routes import router as user_router
from app.modules.user.models import User  # noqa: F401
from app.modules.venue.routes import router as venue_router

from app.realtime.redis_pubsub import pubsub_manager
from app.realtime.routes import router as websocket_router


configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background services and clean them up during shutdown."""

    listener_task = None

    try:
        # Start the Redis Pub/Sub listener.
        # It receives events published by any MatchGrid backend instance.
        listener_task = asyncio.create_task(
            pubsub_manager.listen_for_events(),
            name="matchgrid-redis-pubsub-listener",
        )

        # Start scheduled notification reminders.
        start_reminder_scheduler()

        logger.info("MatchGrid background services started")

        yield

    finally:
        # Stop the reminder scheduler even if another cleanup step fails.
        try:
            stop_reminder_scheduler()
        except Exception:
            logger.exception("Failed to stop the reminder scheduler")

        # Cancel and wait for the Redis listener to finish.
        if listener_task is not None:
            listener_task.cancel()

            with suppress(asyncio.CancelledError):
                await listener_task

        # Close the Redis client owned by the shared Pub/Sub manager.
        try:
            await pubsub_manager.close()
        except Exception:
            logger.exception("Failed to close the Redis Pub/Sub client")

        logger.info("MatchGrid background services stopped")


app = FastAPI(lifespan=lifespan)

logger.info("MatchGrid API application initialized")




app.add_exception_handler(
    AppException,
    app_exception_handler,
)

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

app.add_exception_handler(
    Exception,
    general_exception_handler,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    if response.status_code >= 500:
        log_method = logger.error
    elif response.status_code >= 400:
        log_method = logger.warning
    else:
        log_method = logger.info

    log_method(
        "%s %s -> %s (%.3fs)",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    return response


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
app.include_router(official_assignment_router)
app.include_router(notification_router)
app.include_router(websocket_router)

@app.get("/")
def root():
    return {
        "message": "MatchGrid API is running!",
        "environment": "configured",
    }


@app.get("/health/database")
def database_health():
    result = test_database_connection()

    if result == "Database connection successful":
        logger.info("Database health check successful")
    else:
        logger.error("Database health check failed")

    return {"database": result}
