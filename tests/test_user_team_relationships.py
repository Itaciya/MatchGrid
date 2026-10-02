from uuid import uuid4

from app.data_access.database import SessionLocal
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.user.models import User


def test_user_team_player_relationships():
    db = SessionLocal()

    try:
        user = User(
            email=f"relationship_test_{uuid4()}@example.com",
            password_hash="test_hash",
            role="player",
        )
        db.add(user)
        db.flush()

        team = Team(
            name=f"Relationship Test Team {uuid4()}",
            captain_id=user.id,
        )
        db.add(team)
        db.flush()

        player = Player(
            user_id=user.id,
            team_id=team.id,
            first_name="Test",
            last_name="Player",
            status="active",
        )
        db.add(player)
        db.commit()

        db.refresh(user)
        db.refresh(team)
        db.refresh(player)

        assert player.user.id == user.id
        assert player in user.player
        assert player.team.id == team.id
        assert player in team.players
        assert team.captain.id == user.id

    finally:
        db.rollback()
        db.close()