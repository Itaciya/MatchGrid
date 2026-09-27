from datetime import datetime, timezone
from uuid import uuid4

from app.data_access.database import SessionLocal
from app.modules.registration.models.registration import Registration
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


def test_registration_team_relationship():
    db = SessionLocal()

    try:
        user = User(
            email=f"registration_team_{uuid4()}@example.com",
            password_hash="test_hash",
            role="player",
        )
        db.add(user)
        db.flush()

        team = Team(
            name=f"Registration Test Team {uuid4()}",
            captain_id=user.id,
        )
        db.add(team)
        db.flush()

        tournament = Tournament(
            name=f"Registration Team Tournament {uuid4()}",
            description="Registration relationship test",
            format="league",
            start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 10, 30, tzinfo=timezone.utc),
            status="upcoming",
            organizer_id=user.id,
        )
        db.add(tournament)
        db.flush()

        registration = Registration(
            tournament_id=tournament.id,
            team_id=team.id,
            registration_type="team",
            status="pending",
        )
        db.add(registration)
        db.commit()

        assert registration.id is not None
        assert registration.tournament.id == tournament.id
        assert registration.team.id == team.id
        assert registration.player is None

    finally:
        db.rollback()
        db.close()


def test_registration_player_relationship():
    db = SessionLocal()

    try:
        user = User(
            email=f"registration_player_{uuid4()}@example.com",
            password_hash="test_hash",
            role="player",
        )
        db.add(user)
        db.flush()

        team = Team(
            name=f"Registration Player Team {uuid4()}",
            captain_id=user.id,
        )
        db.add(team)
        db.flush()

        player = Player(
            user_id=user.id,
            team_id=team.id,
            first_name="Registration",
            last_name="Player",
            is_active=True,
        )
        db.add(player)
        db.flush()

        tournament = Tournament(
            name=f"Registration Player Tournament {uuid4()}",
            description="Registration player relationship test",
            format="league",
            start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 11, 30, tzinfo=timezone.utc),
            status="upcoming",
            organizer_id=user.id,
        )
        db.add(tournament)
        db.flush()

        registration = Registration(
            tournament_id=tournament.id,
            player_id=player.id,
            registration_type="player",
            status="pending",
        )
        db.add(registration)
        db.commit()

        assert registration.id is not None
        assert registration.tournament.id == tournament.id
        assert registration.player.id == player.id
        assert registration.team is None

    finally:
        db.rollback()
        db.close()