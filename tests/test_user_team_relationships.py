from app.data_access.database import SessionLocal
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.user.models import User


def test_user_team_player_relationships():
    db = SessionLocal()

    try:
        user = User(
            email="relationship_test@example.com",
            password_hash="test_hash",
            role="player",
        )
        db.add(user)
        db.flush()

        team = Team(
            name="Relationship Test Team",
            captain_id=user.id,
        )
        db.add(team)
        db.flush()

        player = Player(
            user_id=user.id,
            team_id=team.id,
            first_name="Test",
            last_name="Player",
        )
        db.add(player)
        db.commit()

        db.refresh(user)
        db.refresh(team)
        db.refresh(player)

        assert team.captain.id == user.id
        assert player.team.id == team.id
        assert player in team.players

    finally:
        db.rollback()
        db.close()