from fastapi import FastAPI

from app.core.config import settings
from app.data_access.database import test_database_connection


app = FastAPI()


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