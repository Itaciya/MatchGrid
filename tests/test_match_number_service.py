from datetime import datetime, timezone
from uuid import uuid4

from app.modules.match.models.match import Match
from app.modules.match.services.match_number_service import (
    generate_match_number,
    get_next_match_number,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


def create_test_tournament(db, name: str) -> Tournament:
    user = User(
        email=f"{name.lower()}_{uuid4()}@example.com",
        password_hash="test-password-hash",
        role="organizer",
        is_active=True,
    )

    db.add(user)
    db.flush()

    tournament = Tournament(
        name=f"{name} {uuid4()}",
        format="single_elimination",
        start_date=datetime(
            2026,
            10,
            10,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        end_date=datetime(
            2026,
            10,
            20,
            18,
            0,
            tzinfo=timezone.utc,
        ),
        status="upcoming",
        organizer_id=user.id,
    )

    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    return tournament


def test_get_next_match_number_returns_one_for_new_tournament(db):
    tournament = create_test_tournament(
        db,
        "New Match Number Tournament",
    )

    next_number = get_next_match_number(
        db,
        tournament_id=tournament.id,
    )

    assert next_number == 1


def test_get_next_match_number_increments_with_existing_matches(db):
    tournament = create_test_tournament(
        db,
        "Increment Match Number Tournament",
    )

    first_match = Match(
        tournament_id=tournament.id,
        match_number=1,
        scheduled_at=datetime.now(timezone.utc),
        status="scheduled",
    )

    second_match = Match(
        tournament_id=tournament.id,
        match_number=2,
        scheduled_at=datetime.now(timezone.utc),
        status="scheduled",
    )

    db.add_all(
        [
            first_match,
            second_match,
        ]
    )
    db.commit()

    next_number = get_next_match_number(
        db,
        tournament_id=tournament.id,
    )

    assert next_number == 3


def test_generate_match_number_returns_next_available_number(db):
    tournament = create_test_tournament(
        db,
        "Generate Match Number Tournament",
    )

    existing_match = Match(
        tournament_id=tournament.id,
        match_number=1,
        scheduled_at=datetime.now(timezone.utc),
        status="scheduled",
    )

    db.add(existing_match)
    db.commit()

    generated_number = generate_match_number(
        db,
        tournament_id=tournament.id,
    )

    assert generated_number == 2


def test_match_numbers_are_independent_between_tournaments(db):
    first_tournament = create_test_tournament(
        db,
        "First Match Number Tournament",
    )

    second_tournament = create_test_tournament(
        db,
        "Second Match Number Tournament",
    )

    first_tournament_match = Match(
        tournament_id=first_tournament.id,
        match_number=1,
        scheduled_at=datetime.now(timezone.utc),
        status="scheduled",
    )

    second_tournament_match = Match(
        tournament_id=second_tournament.id,
        match_number=1,
        scheduled_at=datetime.now(timezone.utc),
        status="scheduled",
    )

    db.add_all(
        [
            first_tournament_match,
            second_tournament_match,
        ]
    )
    db.commit()

    first_next_number = get_next_match_number(
        db,
        tournament_id=first_tournament.id,
    )

    second_next_number = get_next_match_number(
        db,
        tournament_id=second_tournament.id,
    )

    assert first_next_number == 2
    assert second_next_number == 2