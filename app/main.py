from fastapi import FastAPI

from app.core.config import settings
from app.data_access.database import test_database_connection
from app.api.routes.health import router as health_router
from app.modules.organiser.routes import router as organiser_router
from app.modules.player_team.routes import router as player_team_router
from app.modules.spectator.routes import router as spectator_router
from app.modules.scorer.routes import router as scorer_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    return {
        "database": test_database_connection()
    }