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

- **Organizer** — manages tournaments, fixtures, registrations, scores, and results
- **Referee / Scorer** — submits and manages match scores
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

## Project Status

**Initial Project Setup**

The repository and initial FastAPI backend structure have been established. Core MatchGrid modules and features will be developed incrementally.

## Project Structure

```text
MatchGrid/
├── app/
│   └── main.py
├── README.md
├── requirements.txt
└── .gitignore
