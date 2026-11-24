# MatchGrid

### Tournament Management Platform for Sports & eSports

MatchGrid is a web-based tournament management platform designed to simplify the organization and management of sports and eSports tournaments.

It provides a centralized platform for tournament registration, team and player management, fixture generation, live scores, result verification, standings, and public match information.

## Key Features

- Tournament creation and management
- Team and player registration
- Registration approval
- Fixture and bracket generation
- Match scheduling and conflict detection
- Scorer assignment
- Live score submission
- Score verification
- Standings and rankings
- Dispute and result review
- Public spectator view
- Real-time tournament updates

## User Roles

- **Organizer** — creates tournaments, approves registrations, publishes fixtures, picks the scorers for each tournament, verifies scores and finalizes results
- **Scorer** — starts the matches of tournaments they are assigned to and records the score
- **Team Captain / Player** — registers and participates in tournaments
- **Spectator** — views fixtures, verified scores, standings, and match history

## System Architecture

MatchGrid follows a **Layered Modular Monolith Architecture**.

The system is organized into three main functional modules:

- **Organiser Management**
- **Player & Team Management**
- **Spectator**

Each module follows a layered structure consisting of:

- Presentation Layer
- API Layer
- Service Layer
- Data Access Layer

The system uses a shared relational database, with Redis for caching and WebSockets (Socket.IO) for real-time updates.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React.js, Tailwind CSS |
| Backend | FastAPI, Python |
| Database | PostgreSQL |
| Cache | Redis |
| Real-Time Communication | WebSockets / Socket.IO |

## Run Locally

You need PostgreSQL, Redis and Node.js. Each part runs in its own terminal.

1. **Redis**, with Docker Desktop running: `docker run -d --name matchgrid-redis -p 6379:6379 redis:7-alpine` (next time: `docker start matchgrid-redis`).
2. **Backend**, from the project root, with `DATABASE_URL`, `SECRET_KEY` and `REDIS_URL` set in `.env` (see `.env.example`):
   ```
   python -m venv venv
   venv\Scripts\pip install -r requirements.txt
   venv\Scripts\python -m alembic upgrade head
   venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
   ```
3. **Frontend**, from `frontend/`: `npm install`, then `npm run dev`, and open http://localhost:5173.

### Demo data

With the backend running, this creates a finished four-team football league (squads, fixtures, scores, standings and leaderboard) and prints demo logins:

```
venv\Scripts\python scripts\seed_demo_tournament.py
```

### Tests

The test suite only runs against a database whose name ends in `_test`. Create one, run `alembic upgrade head` against it, set `TEST_DATABASE_URL`, then run `pytest`.

## Project Status

Core features are implemented: registration and approvals, round-robin and single-elimination fixtures, live scoring, score verification, results, disputes, standings, leaderboards and real-time updates.

## Project Structure

```text
MatchGrid/
├── app/
│   └── main.py
├── README.md
├── requirements.txt
└── .gitignore
