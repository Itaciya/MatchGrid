from fastapi import APIRouter


router = APIRouter(
    prefix="/spectator",
    tags=["Spectator"]
)


@router.get("/")
def spectator_home():
    return {
        "message": "Spectator router is working"
    }