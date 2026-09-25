from fastapi import APIRouter


router = APIRouter(
    prefix="/player-team",
    tags=["Player & Team"]
)


@router.get("/")
def player_team_home():
    return {
        "message": "Player & Team router is working"
    }
