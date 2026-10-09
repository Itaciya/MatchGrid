
from datetime import datetime, timedelta

from app.modules.match.models.match import Match


MATCH_DURATION = timedelta(hours=1)


def has_time_overlap(
    first_start: datetime,
    second_start: datetime,
) -> bool:
    """Check whether two matches overlap in time."""

    first_end = first_start + MATCH_DURATION
    second_end = second_start + MATCH_DURATION

    return (
        first_start < second_end
        and second_start < first_end
    )


def check_team_conflicts(
    matches: list[Match],
) -> list[dict]:
    """Detect overlapping matches for the same team."""

    conflicts = []

    for index, first_match in enumerate(matches):
        first_teams = {
            team_id
            for team_id in (
                first_match.team_a_id,
                first_match.team_b_id,
            )
            if team_id is not None
        }

        for second_match in matches[index + 1:]:
            second_teams = {
                team_id
                for team_id in (
                    second_match.team_a_id,
                    second_match.team_b_id,
                )
                if team_id is not None
            }

            common_teams = first_teams & second_teams

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
                        "message": "Team has overlapping matches",
                    }
                )

    return conflicts


def check_player_conflicts(
    matches: list[Match],
) -> list[dict]:
    """Detect overlapping matches for players."""

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

            common_players = first_players & second_players

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
                        "message": "Player has overlapping matches",
                    }
                )

    return conflicts


def check_venue_conflicts(
    matches: list[Match],
) -> list[dict]:
    """Detect overlapping matches for the same venue."""

    conflicts = []

    for index, first_match in enumerate(matches):
        if first_match.venue_id is None:
            continue

        for second_match in matches[index + 1:]:
            if second_match.venue_id is None:
                continue

            if first_match.venue_id != second_match.venue_id:
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
                        "message": "Venue has overlapping matches",
                    }
                )

    return conflicts


def check_time_slot_conflicts(
    matches: list[Match],
) -> list[dict]:
    """
    Detect overlapping matches that share the same venue.

    Matches at different venues may run simultaneously.
    Team and player conflicts are checked separately.
    """

    conflicts = []

    for index, first_match in enumerate(matches):
        for second_match in matches[index + 1:]:
            if not has_time_overlap(
                first_match.scheduled_at,
                second_match.scheduled_at,
            ):
                continue

            if (
                first_match.venue_id is None
                or second_match.venue_id is None
            ):
                continue

            if first_match.venue_id != second_match.venue_id:
                continue

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
                        "Overlapping matches cannot use "
                        "the same venue"
                    ),
                }
            )

    return conflicts


def validate_schedule_conflicts(
    candidate_matches: list[Match],
    existing_matches: list[Match] | None = None,
    exclude_match_ids: set[int] | None = None,
) -> list[dict]:
    """
    Validate candidate fixtures against each other and
    against existing scheduled fixtures.
    """

    existing_matches = existing_matches or []
    exclude_match_ids = exclude_match_ids or set()

    candidate_ids = {
        match.id
        for match in candidate_matches
        if match.id is not None
    }

    candidates = [
        match
        for match in candidate_matches
        if match.id not in exclude_match_ids
    ]

    existing = [
        match
        for match in existing_matches
        if match.id not in exclude_match_ids
        and match.id not in candidate_ids
    ]

    conflicts = []

    # Check conflicts among the proposed fixtures.
    conflicts.extend(check_team_conflicts(candidates))
    conflicts.extend(check_player_conflicts(candidates))
    conflicts.extend(check_venue_conflicts(candidates))

    # Check proposed fixtures against existing fixtures.
    for candidate in candidates:
        for current in existing:
            pair = [current, candidate]

            conflicts.extend(check_team_conflicts(pair))
            conflicts.extend(check_player_conflicts(pair))
            conflicts.extend(check_venue_conflicts(pair))

    # Remove duplicate conflict records.
    unique_conflicts = []
    seen = set()

    for conflict in conflicts:
        match_ids = tuple(
            sorted(
                str(match_id)
                for match_id in conflict["match_ids"]
            )
        )

        key = (
            conflict["type"],
            match_ids,
        )

        if key not in seen:
            seen.add(key)
            unique_conflicts.append(conflict)

    return unique_conflicts