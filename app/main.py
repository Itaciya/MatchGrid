from fastapi import FastAPI

from app.core.config import settings


app = FastAPI()


@app.get("/")
def root():
    return {
        "message": "MatchGrid API is running!",
        "environment": "configured",
    }
