from fastapi import APIRouter


router = APIRouter(
    prefix="/organiser",
    tags=["Organiser"]
)


@router.get("/")
def organiser_home():
    return {
        "message": "Organiser router is working"
    }
