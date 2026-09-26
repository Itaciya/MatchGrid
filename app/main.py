import logging
import time

from fastapi import FastAPI, Request

from app.core.config import settings
from app.core.logging import configure_logging
from app.data_access.database import test_database_connection
from app.api.routes.health import router as health_router
from app.modules.organiser.routes import router as organiser_router
from app.modules.player_team.routes import router as player_team_router
from app.modules.spectator.routes import router as spectator_router
from app.modules.scorer.routes import router as scorer_router
from fastapi.middleware.cors import CORSMiddleware


configure_logging()

app = FastAPI()

logger = logging.getLogger(__name__)

logger.info("MatchGrid API application initialized")


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
        logger.error(
            "%s %s -> %s (%.3fs)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
    elif response.status_code >= 400:
        logger.warning(
            "%s %s -> %s (%.3fs)",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
    else:
        logger.info(
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

    return {
        "database": result
    }