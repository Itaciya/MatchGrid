# Running the backend tests

The suite runs against a separate PostgreSQL database whose name must end in
`_test`. `tests/conftest.py` aborts the run otherwise, so the tests can never
write to the development database.

## One-time local setup

1. Create a database named `<your database>_test`.
2. Add its URL to `.env` as `TEST_DATABASE_URL`.
3. Build its schema (PowerShell):

       $env:DATABASE_URL = $env:TEST_DATABASE_URL   # or paste the URL
       alembic upgrade head
       Remove-Item Env:DATABASE_URL

## Running

    pytest -q                         # everything
    pytest tests\test_user_login.py   # one file

Redis is replaced by an in-memory fake (`fake_redis` fixture), so no Redis
server is needed.

## CI

`.github/workflows/backend-tests.yml` starts PostgreSQL, applies the migrations
to a `matchgrid_test` database and runs `pytest -q` on every pull request.