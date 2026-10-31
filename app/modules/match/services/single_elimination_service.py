from datetime import timedelta, time
from sqlalchemy.orm import Session

from app.modules.match.models.match import Match
from app.modules.match.models.tournament_round import TournamentRound
from app.modules.match.models.match_result import MatchResult
from app.modules.registration.models.registration import Registration
from app.modules.player_team.models.team import Team
from app.modules.notification.models.notification import Notification


def _notify_team(db: Session, team_id: int, kind: str, message: str):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return

    recipients = {team.captain_id}
    recipients.update(
        p.user_id for p in team.players if p.user_id is not None
    )

    for user_id in recipients:
        if user_id:
            db.add(Notification(
                user_id=user_id,
                notification_type=kind,
                content=message,
            ))


def create_single_elimination_bracket(
    db: Session,
    tournament,
):
    if tournament.format != "single_elimination":
        raise ValueError("Tournament is not Single Elimination")

    if db.query(Match).filter(
        Match.tournament_id == tournament.id
    ).first():
        raise ValueError("Fixtures already exist for this tournament")

    registrations = (
        db.query(Registration)
        .filter(
            Registration.tournament_id == tournament.id,
            Registration.status == "approved",
            Registration.registration_type == "team",
            Registration.team_id.isnot(None),
        )
        .order_by(Registration.registered_at.asc())
        .all()
    )

    team_ids = list(dict.fromkeys(r.team_id for r in registrations))
    if len(team_ids) < 2:
        raise ValueError("At least two approved teams are required")

    bracket_size = 1
    while bracket_size < len(team_ids):
        bracket_size *= 2

    total_rounds = bracket_size.bit_length() - 1
    start = tournament.start_date
    if start.tzinfo is None:
        from datetime import timezone
        start = start.replace(tzinfo=timezone.utc)

    rounds = []
    for number in range(1, total_rounds + 1):
        remaining = total_rounds - number
        name = (
            "Final" if remaining == 0 else
            "Semi Final" if remaining == 1 else
            "Quarter Final" if remaining == 2 else
            f"Round of {bracket_size // (2 ** (number - 1))}"
        )
        round_row = TournamentRound(
            tournament_id=tournament.id,
            round_number=number,
            name=name,
            bracket_type="main",
        )
        db.add(round_row)
        rounds.append(round_row)

    db.flush()

    matches_by_round = []
    match_number = 1

    for index, round_row in enumerate(rounds):
        count = bracket_size // (2 ** index) // 2
        round_matches = []

        for slot in range(count):
            match = Match(
                tournament_id=tournament.id,
                match_number=match_number,
                round_id=round_row.id,
                team_a_id=None,
                team_b_id=None,
                venue_id=None,
                scheduled_at=start + timedelta(days=index, hours=10 + slot),
                status="scheduled",
            )
            db.add(match)
            round_matches.append(match)
            match_number += 1

        matches_by_round.append(round_matches)

    db.flush()

    # Connect every match to the match its winner will enter.
    for round_index in range(len(matches_by_round) - 1):
        current = matches_by_round[round_index]
        following = matches_by_round[round_index + 1]
        for match_index, match in enumerate(current):
            match.winner_next_match_id = following[match_index // 2].id

    # Seed teams into the first round.
    first_round = matches_by_round[0]
    # Standard bracket seed order: 1 vs N, 2 vs N-1, etc.
    seed_order = [1, 2]
    size = 2
    while size < bracket_size:
        seed_order = [
            seed
            for current_seed in seed_order
            for seed in (current_seed, size * 2 + 1 - current_seed)
        ]
        size *= 2

    seeded_teams = {
        seed: team_ids[seed - 1] if seed <= len(team_ids) else None
        for seed in range(1, bracket_size + 1)
    }
    padded = [seeded_teams[seed] for seed in seed_order]

    for index, match in enumerate(first_round):
        match.team_a_id = padded[index * 2]
        match.team_b_id = padded[index * 2 + 1]

        # A bye advances the available team automatically.
        if match.team_a_id is None or match.team_b_id is None:
            advancing_team = match.team_a_id or match.team_b_id
            if advancing_team and match.winner_next_match_id:
                next_match = db.query(Match).filter(
                    Match.id == match.winner_next_match_id
                ).first()
                if next_match:
                    if index % 2 == 0:
                        next_match.team_a_id = advancing_team
                    else:
                        next_match.team_b_id = advancing_team

    tournament.fixtures_published = True

    for team_id in team_ids:
        _notify_team(
            db,
            team_id,
            "fixture_published",
            f"Single Elimination fixtures for {tournament.name} have been published.",
        )

    db.commit()

    return (
        db.query(Match)
        .filter(Match.tournament_id == tournament.id)
        .order_by(Match.match_number.asc())
        .all()
    )


def advance_single_elimination_winner(
    db: Session,
    match_id: int,
    result: MatchResult,
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match or match.tournament.format != "single_elimination":
        return

    if result.outcome == "draw" or not result.winner_team_id:
        return

    winner_id = result.winner_team_id
    loser_id = result.loser_team_id

    if match.winner_next_match_id:
        next_match = (
            db.query(Match)
            .filter(Match.id == match.winner_next_match_id)
            .with_for_update()
            .first()
        )
        if next_match:
            if next_match.team_a_id is None:
                next_match.team_a_id = winner_id
            elif next_match.team_b_id is None:
                next_match.team_b_id = winner_id
            elif winner_id not in (next_match.team_a_id, next_match.team_b_id):
                raise ValueError("Next-round fixture already has two teams")

            _notify_team(
                db,
                winner_id,
                "team_advanced",
                f"Your team has advanced to the next round of {match.tournament.name}.",
            )
    else:
        _notify_team(
            db,
            winner_id,
            "tournament_final",
            f"Congratulations! Your team has won {match.tournament.name}.",
        )

    if loser_id:
        _notify_team(
            db,
            loser_id,
            "team_eliminated",
            f"Your team has been eliminated from {match.tournament.name}.",
        )

    db.commit()
