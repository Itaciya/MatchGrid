from datetime import datetime, timedelta

from app.modules.match.models.match import Match

MATCH_DURATION = timedelta(hours=1)


def has_time_overlap(
    first_start: datetime,
    second_start: datetime,
) -> bool:
    """
    Check whether two matches overlap in time.
    """

    first_end = first_start + MATCH_DURATION
    second_end = second_start + MATCH_DURATION

    return (
        first_start < second_end
        and second_start < first_end
    )

def check_team_conflicts(
    matches: list[Match],
) -> list[dict]:
    """
    Detect overlapping matches for the same team.
    """

    conflicts = []

    for index, first_match in enumerate(matches):
        first_teams = {
            first_match.team_a_id,
            first_match.team_b_id,
        }

        for second_match in matches[index + 1:]:
            second_teams = {
                second_match.team_a_id,
                second_match.team_b_id,
            }

            common_teams = (
                first_teams
                & second_teams
            )

            if not common_teams:
                continue

            if has_time_overlap(
                first_match.scheduled_at,
                second_match.scheduled_at,
            ):
                conflicts.append(
                    {
                        "type": "team_conflict",
                        "team_ids": list(common_teams),
                        "match_ids": [
                            first_match.id,
                            second_match.id,
                        ],
                        "message": (
                            "Team has overlapping matches"
                        ),
                    }
                )

    return conflicts

def check_player_conflicts(
    matches: list[Match],
) -> list[dict]:
    """
    Detect overlapping matches for players.
    """

    conflicts = []

    for index, first_match in enumerate(matches):

        first_players = set()

        if first_match.team_a:
            first_players.update(
                player.id
                for player in first_match.team_a.players
            )

        if first_match.team_b:
            first_players.update(
                player.id
                for player in first_match.team_b.players
            )

        for second_match in matches[index + 1:]:

            second_players = set()

            if second_match.team_a:
                second_players.update(
                    player.id
                    for player in second_match.team_a.players
                )

            if second_match.team_b:
                second_players.update(
                    player.id
                    for player in second_match.team_b.players
                )

            common_players = (
                first_players
                & second_players
            )

            if not common_players:
                continue

            if has_time_overlap(
                first_match.scheduled_at,
                second_match.scheduled_at,
            ):
                conflicts.append(
                    {
                        "type": "player_conflict",
                        "player_ids": list(common_players),
                        "match_ids": [
                            first_match.id,
                            second_match.id,
                        ],
                        "message": (
                            "Player has overlapping matches"
                        ),
                    }
                )

    return conflicts

def check_venue_conflicts(
    matches: list[Match],
) -> list[dict]:
    """
    Detect overlapping matches for the same venue.
    """

    conflicts = []

    for index, first_match in enumerate(matches):

        if first_match.venue_id is None:
            continue

        for second_match in matches[index + 1:]:

            if second_match.venue_id is None:
                continue

            if (
                first_match.venue_id
                != second_match.venue_id
            ):
                continue

            if has_time_overlap(
                first_match.scheduled_at,
                second_match.scheduled_at,
            ):
                conflicts.append(
                    {
                        "type": "venue_conflict",
                        "venue_id": first_match.venue_id,
                        "match_ids": [
                            first_match.id,
                            second_match.id,
                        ],
                        "message": (
                            "Venue has overlapping matches"
                        ),
                    }
                )

    return conflicts

def check_time_slot_conflicts(
    matches: list[Match],
) -> list[dict]:
    """
    Detect overlapping fixture time slots.
    """

    conflicts = []

    for index, first_match in enumerate(matches):

        for second_match in matches[index + 1:]:

            if has_time_overlap(
                first_match.scheduled_at,
                second_match.scheduled_at,
            ):
                conflicts.append(
                    {
                        "type": "time_slot_conflict",
                        "match_ids": [
                            first_match.id,
                            second_match.id,
                        ],
                        "scheduled_times": [
                            first_match.scheduled_at,
                            second_match.scheduled_at,
                        ],
                        "message": (
                            "Fixture time slots are overlapping"
                        ),
                    }
                )

    return conflicts