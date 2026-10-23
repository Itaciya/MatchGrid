# MatchGrid Production Deployment Runbook

## 1. Configuration
- Store production secrets in the deployment environment or protected `.env`.
- Never commit `.env` or real passwords, tokens, or secret keys.
- Set `DATABASE_URL`, `SECRET_KEY`, `REDIS_URL`, `CORS_ORIGINS`,
  `VITE_API_BASE_URL`, and `VITE_WS_URL` for the target environment.
- Use the actual production URLs, not localhost defaults.

## 2. Deploy
1. Confirm the intended release and preserve the previous known-good release.
2. Take and verify a database backup before applying schema migrations.
3. Validate configuration:

   `docker compose config --quiet`

4. Build and start the services:

   `docker compose up -d --build`

5. Check service state:

   `docker compose ps`

6. Confirm that database, Redis, and backend are healthy and that the
   frontend is running before considering deployment successful.

## 3. Rollback
1. Identify the previous known-good release or commit.
2. If application code causes a problem, restore that release and rebuild
   the backend and frontend using its matching configuration.
3. Check service health again after rollback.
4. If a database migration is incompatible with the previous application,
   follow the database recovery procedure and restore the verified
   pre-deployment backup when required.
5. Verify the backup and recovery plan before relying on it.

Do not run `docker compose down -v` as a rollback step; it can delete
persistent database and Redis volumes.

## 4. Security
- Keep production secrets out of source control and deployment logs.
- Restrict access to database backups and production environment files.
- Review health status and application logs after deployment.
