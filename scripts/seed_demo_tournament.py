"""Create a finished demo football league through the public API.

Plays a whole tournament the way real users would: an organiser creates a
round-robin league, four captains build their squads and register, the
organiser approves them, publishes fixtures and adds a scorer, the scorer
plays every match, and the organiser verifies and finalizes each result.
Standings and the leaderboard are then filled with real data.

Usage (with the backend running):
    python scripts/seed_demo_tournament.py
    python scripts/seed_demo_tournament.py --api http://127.0.0.1:8000

Only the standard library is used. Run it against a local or demo database:
it creates accounts and data.
"""

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

TEAMS = [
    ("Dhaka Dynamos", "Tanvir", "Hasan", [("Rahim", "Uddin"), ("Sabbir", "Rahman"), ("Nayeem", "Islam")]),
    ("Chattogram Chargers", "Arif", "Chowdhury", [("Fahim", "Ahmed"), ("Rakib", "Hossain"), ("Imran", "Kabir")]),
    ("Sylhet Strikers", "Mahin", "Alam", [("Shakil", "Mia"), ("Jubayer", "Khan"), ("Rifat", "Sarker")]),
    ("Khulna Kings", "Sakib", "Molla", [("Tamim", "Biswas"), ("Rony", "Das"), ("Asif", "Karim")]),
]

# Final scores, in the order the fixtures are generated (by match number).
SCORES = [(3, 1), (2, 2), (0, 1), (4, 2), (1, 0), (2, 3)]


class Api:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def call(self, method, path, token=None, body=None, allow_error=False):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, method=method
        )
        request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            if allow_error:
                return None
            sys.exit(f"{method} {path} failed ({error.code}): {detail}")
        except urllib.error.URLError as error:
            sys.exit(f"Could not reach the API at {self.base_url}: {error.reason}")


def make_account(api, tag, label, role, password):
    email = f"{label}.{tag}@matchgrid-demo.com"
    api.call("POST", "/auth/register", body={"email": email, "password": password, "role": role})
    tokens = api.call("POST", "/auth/login", body={"email": email, "password": password})
    return email, tokens["access_token"]


def make_player(api, tag, label, first, last, password):
    email, token = make_account(api, tag, label, "player", password)
    profile = api.call(
        "POST", "/player-team/profile", token, {"first_name": first, "last_name": last}
    )
    return email, token, profile


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="Backend URL")
    args = parser.parse_args()

    api = Api(args.api)
    tag = secrets.token_hex(3)
    password = f"Demo{secrets.token_hex(4)}9"
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    print("Creating organiser and scorer...")
    organiser_email, organiser = make_account(api, tag, "organiser", "organiser", password)
    scorer_email, scorer = make_account(api, tag, "scorer", "scorer", password)
    scorer_id = api.call("GET", "/auth/me", scorer)["id"]

    tournament = api.call("POST", "/organiser/tournaments", organiser, {
        "name": f"MatchGrid Football League {now:%Y}",
        "description": "A four-team round-robin football league. Three points for a win, one for a draw.",
        "category": "sports",
        "participation_type": "team",
        "min_roster_size": 4,
        "max_roster_size": 11,
        "format": "round_robin",
        "format_config": {"number_of_teams": len(TEAMS)},
        "registration_open_at": (now - timedelta(days=1)).isoformat(),
        "registration_close_at": (now + timedelta(minutes=30)).isoformat(),
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=7)).isoformat(),
    })
    tournament_id = tournament["id"]
    print(f"Created tournament: {tournament['name']}")

    for index, (team_name, cap_first, cap_last, squad) in enumerate(TEAMS):
        _, captain, captain_profile = make_player(
            api, tag, f"captain{index + 1}", cap_first, cap_last, password
        )
        # Team names are unique: keep the clean name unless it is taken.
        team = api.call(
            "POST", "/player-team/team", captain, {"name": team_name}, allow_error=True
        ) or api.call("POST", "/player-team/team", captain, {"name": f"{team_name} {tag}"})
        api.call("POST", f"/player-team/team/{team['id']}/players/{captain_profile['id']}", captain)
        for number, (first, last) in enumerate(squad):
            _, _, profile = make_player(
                api, tag, f"player{index + 1}{number + 1}", first, last, password
            )
            api.call("POST", f"/player-team/team/{team['id']}/players/{profile['id']}", captain)

        registration = api.call("POST", "/registrations/", captain, {
            "tournament_id": tournament_id,
            "team_id": team["id"],
            "registration_type": "team",
            "note": f"{team_name} are ready to play.",
        })
        api.call("PATCH", f"/registrations/{registration['id']}/approve", organiser)
        print(f"  {team['name']}: squad of {len(squad) + 1}, registration approved")

    print("Publishing fixtures and adding the scorer...")
    fixtures = api.call(
        "POST", f"/matches/tournaments/{tournament_id}/fixtures/auto-generate", organiser
    )
    api.call(
        "POST",
        f"/official-assignments/tournaments/{tournament_id}/scorers",
        organiser,
        {"scorer_id": scorer_id},
    )

    fixtures.sort(key=lambda fixture: fixture["match_number"])
    for fixture, (score_a, score_b) in zip(fixtures, SCORES):
        match_id = fixture["id"]
        api.call("POST", f"/matches/{match_id}/start", scorer)
        api.call("POST", f"/matches/{match_id}/score", scorer, {
            "match_id": match_id, "team_a_score": score_a, "team_b_score": score_b,
        })
        api.call("POST", f"/matches/{match_id}/complete", scorer)
        api.call("PATCH", f"/matches/{match_id}/score/verification", organiser, {"status": "verified"})
        api.call("POST", f"/matches/{match_id}/result/finalize", organiser)
        print(
            f"  Match {fixture['match_number']}: {fixture.get('team_a_name')} "
            f"{score_a} - {score_b} {fixture.get('team_b_name')}"
        )

    standings = api.call("GET", f"/tournaments/{tournament_id}/standings")
    print("\nFinal table:")
    for row in standings:
        print(f"  {row['rank']}. {row.get('team_name', row['team_id'])}: {row.get('points', '?')} pts")

    status = api.call("GET", f"/tournaments/{tournament_id}")["status"]
    print(f"\nTournament status: {status}")
    print("\nDemo logins (all accounts share this password):")
    print(f"  Organiser: {organiser_email}")
    print(f"  Scorer:    {scorer_email}")
    print(f"  Captain:   captain1.{tag}@matchgrid-demo.com")
    print(f"  Password:  {password}")


if __name__ == "__main__":
    main()
