from fastapi import APIRouter


router = APIRouter(
    prefix="/scorer",
    tags=["Scorer / Referee"]
)


@router.get("/")
def scorer_home():
    return {
        "message": "Scorer / Referee router is working"
    }
