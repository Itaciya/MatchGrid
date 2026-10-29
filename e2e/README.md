# MatchGrid End-to-End (Selenium) Tests

Browser-level UI tests. Backend logic is covered separately by `pytest tests`.

## What is covered
| File | Scenarios |
|---|---|
| `test_smoke.py` | Frontend loads, API docs load |
| `test_auth.py` | Register, login, logout, wrong password, unknown email, protected nav hidden when signed out |
| `test_tournaments.py` | Organiser sees and uses Create tournament, spectator does not, tournament appears in list and search, invalid dates blocked by form validation |

Tests create their own users through the UI (unique email per run), so no pre-seeded accounts are needed.

## Prerequisites
- Google Chrome (Selenium 4.6+ downloads the driver automatically)
- Backend running against a **test database**, never real data
- Frontend running: `npm run dev` inside `frontend/`

## Setup
    pip install -r e2e/requirements-e2e.txt

## Run (PowerShell, from the project root)
Terminal 1, backend (venv active):

    $env:TEST_DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@localhost:5432/matchgrid_test"
    $env:DATABASE_URL = $env:TEST_DATABASE_URL
    uvicorn app.main:app --reload

Terminal 2, frontend:

    cd frontend
    npm run dev

Terminal 3, tests (venv active):

    pytest e2e -v

`e2e/pytest.ini` sets `--confcutdir=e2e`, so the backend `tests/conftest.py`
(which requires `TEST_DATABASE_URL`) is not loaded for E2E runs.
Run `pytest tests` and `pytest e2e` separately.

## Environment variables
| Variable | Default | Purpose |
|---|---|---|
| `E2E_FRONTEND_URL` | `http://localhost:5173` | Frontend base URL (Vite default) |
| `E2E_API_URL` | `http://127.0.0.1:8000` | Backend base URL |
| `E2E_HEADLESS` | unset | Set to `1` to run Chrome headless (CI) |

The frontend must be opened on `localhost:5173`: the backend CORS config only allows that origin.

## Conventions
- Page Object pattern in `e2e/pages/`
- Locators use stable element `id`s from the React forms; prefer `data-testid` for new components
- Explicit waits (`WebDriverWait`) only, never `time.sleep()`
- Each test starts with a fresh browser profile
- No credentials in the repo

## Known limitations
- The app has no URL routing (page state lives in React), so tests navigate by clicking sidebar buttons.
- The auth form keeps field values when switching between Register and Sign in, so page objects clear fields before typing.
- Test users and tournaments accumulate in the test database. Reset it when needed.
- The frontend logs WebSocket errors to the console when the realtime server (`ws://localhost:8090`) is not running. Harmless for current tests.
- Scorer, verification, dispute, standings and registration flows need seeded data and are not covered yet.

## Structure
    e2e/
      pytest.ini
      conftest.py             driver, URL and make_user fixtures
      pages/auth_page.py      auth page object and helpers
      pages/tournament_page.py
      test_smoke.py
      test_auth.py
      test_tournaments.py