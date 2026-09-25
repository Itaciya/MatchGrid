from fastapi import FastAPI

from app.core.config import settings
from app.data_access.database import test_database_connection

from app.api.routes.health import router as health_router

app = FastAPI()
app.include_router(health_router)

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