from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from app.modules.match.models.match import Match
from app.modules.match.services.fixture_service import (
    create_round_robin_fixtures,
)
from app.modules.tournament.models.tournament import Tournament


def regenerate_round_robin_fixtures(
    db: Session,
    tournament_id: int,
    team_ids: list[int],
    fixture_date,
    fixture_time,
    venue_id: int | None = None,
):
    """
    Regenerate round-robin fixtures safely.

    Only scheduled matches can be removed.
    Completed matches protect fixture history.

    The deletion and creation happen inside the same
    database transaction. If fixture generation fails,
    the transaction is rolled back so existing fixtures
    are not lost.
    """

    tournament = (
        db.query(Tournament)
        .filter(
            Tournament.id == tournament_id
        )
        .first()
    )

    if tournament is None:
        raise NotFoundException(
            detail="Tournament not found"
        )

    if tournament.format != "round_robin":
        raise BadRequestException(
            detail=(
                "Fixture regeneration requires "
                "a round_robin tournament"
            )
        )

    existing_matches = (
        db.query(Match)
        .filter(
            Match.tournament_id == tournament_id
        )
        .all()
    )

    completed_matches = [
        match
        for match in existing_matches
        if match.status == "completed"
    ]

    if completed_matches:
        raise BadRequestException(
            detail=(
                "Cannot regenerate fixtures after "
                "completed matches exist"
            )
        )

    try:
        for match in existing_matches:
            if match.status == "scheduled":
                db.delete(match)

        db.flush()

        matches = create_round_robin_fixtures(
            db=db,
            tournament_id=tournament_id,
            team_ids=team_ids,
            fixture_date=fixture_date,
            fixture_time=fixture_time,
            venue_id=venue_id,
            commit=False,
        )

        db.commit()

        return matches

    except Exception:
        db.rollback()
        raise