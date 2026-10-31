from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role, verify_tournament_owner
from app.data_access.database import get_db
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.schemas.tournament import (
    TournamentCreate,
    TournamentResponse,
    TournamentUpdate,
)
from app.modules.tournament.services.tournament_service import (
    archive_tournament,
    create_tournament,
    invalidate_public_tournament_cache,
    update_tournament,
)
from app.modules.user.models import User


router = APIRouter(
    prefix="/organiser",
    tags=["Organiser"],
)


@router.get("/")
def organiser_home():
    return {
        "message": "Organiser router is working"
    }


@router.post(
    "/tournaments",
    response_model=TournamentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_tournament_route(
    data: TournamentCreate,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    return create_tournament(db, current_user.id, data)


@router.patch(
    "/tournaments/{tournament_id}",
    response_model=TournamentResponse,
)
def update_tournament_route(
    data: TournamentUpdate,
    tournament: Tournament = Depends(verify_tournament_owner),
    db: Session = Depends(get_db),
):
    return update_tournament(db, tournament, data)
@router.patch(
    "/tournaments/{tournament_id}/archive",
    response_model=TournamentResponse,
)
def archive_tournament_route(
    tournament: Tournament = Depends(verify_tournament_owner),
    db: Session = Depends(get_db),
):
    return archive_tournament(db, tournament)

MAX_IMAGE_SIZE = 5 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}


@router.post(
    "/tournaments/{tournament_id}/image",
    response_model=TournamentResponse,
)
async def upload_tournament_image(
    file: UploadFile = File(...),
    tournament: Tournament = Depends(verify_tournament_owner),
    db: Session = Depends(get_db),
):
    """Upload or replace a tournament picture."""

    content_type = file.content_type

    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, and WebP images are allowed.",
        )

    image_data = await file.read(MAX_IMAGE_SIZE + 1)

    if not image_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded image is empty.",
        )

    if len(image_data) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Image size must not exceed 5 MB.",
        )

    valid_signature = any(
        image_data.startswith(signature)
        for signature in ALLOWED_IMAGE_TYPES[content_type]
    )

    if content_type == "image/webp":
        valid_signature = (
            image_data.startswith(b"RIFF")
            and image_data[8:12] == b"WEBP"
        )

    if not valid_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid image.",
        )

    tournament.image_data = image_data
    tournament.image_content_type = content_type

    db.commit()
    db.refresh(tournament)

    invalidate_public_tournament_cache()

    return tournament
