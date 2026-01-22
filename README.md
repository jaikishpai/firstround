# QA Assessment Platform

Production-ready, dockerized QA screening platform with secure test sessions, admin tooling, and violation tracking.

## System Architecture
- **Frontend**: React app served via Nginx, communicates with backend over REST.
- **Backend**: FastAPI with async SQLAlchemy, JWT auth, and background session sweeper.
- **Database**: PostgreSQL with normalized tables and indexed foreign keys.
- **Security**: Password hashing (bcrypt), JWT-based RBAC, server-side session timer enforcement.
- **Integrity**: Fullscreen enforcement, visibility/blur/devtools detection, violations stored server-side.

## Database Schema (Core Tables)
- `roles`: `id`, `name`
- `users`: `id`, `username`, `password_hash`, `is_active`, `role_id`, timestamps
- `test_types`: `id`, `name`, `description`, `created_at`
- `question_sets`: `id`, `name`, `description`, `test_type_id`, timestamps
- `questions`: `id`, `title`, `body`, `sections`, `answer_type`, `allow_multiple`, timestamps
- `question_set_questions`: `id`, `question_set_id`, `question_id`, `order` (unique per question)
- `question_options`: `id`, `question_id`, `option_text`, `is_correct`, `order`
- `tests`: `id`, `title`, `test_type_id`, `question_set_id`, `duration_minutes`, `warning_minutes`, `is_active`, timestamps
- `test_assignments`: `id`, `test_id`, `user_id`, `assigned_at`, `is_active`
- `test_sessions`: `id`, `test_id`, `user_id`, `assignment_id`, `status`, `start_time`, `end_time`, `submitted_at`, `violation_token`, timestamps
- `answers`: `id`, `session_id`, `question_id`, `answer_text`, `is_final`, timestamps
- `answer_options`: `id`, `answer_id`, `option_id`
- `violations`: `id`, `session_id`, `event_type`, `metadata`, `created_at`

## Backend Structure
```
backend/
  app/
    main.py
    routes.py
    models.py
    database.py
    config.py
```

## Frontend Structure
```
frontend/
  src/
    App.jsx
    api.js
    main.jsx
    styles.css
```

## Environment Variables
Set these in your shell or an `.env` file before running docker-compose:
- `SECRET_KEY` (JWT signing key)
- `ADMIN_SEED_USERNAME` (optional admin seed)
- `ADMIN_SEED_PASSWORD` (optional admin seed)
- `ALLOW_ORIGINS` (comma-separated, e.g. `http://localhost:3000`)
- `VITE_API_BASE` (e.g. `http://localhost:8000`)

Defaults are provided in `docker-compose.yml` for local runs.

## Running Locally
```
docker-compose up --build
```

Services:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

## Admin Flow
1. Login with `ADMIN_SEED_USERNAME` / `ADMIN_SEED_PASSWORD`.
2. Create question sets, tests, and users.
3. Add questions inside each question set (ordering supported).
4. Assign question sets to candidates (tests optional for reporting).
5. Use the dashboard to filter by status/type and review violations.

## Candidate Flow
1. Login with assigned credentials.
2. Start assigned test; fullscreen is required.
3. Answers autosave; server enforces timeout and auto-submits.

## Notes
- The backend runs a background sweeper to auto-submit expired sessions.
- Violations are logged via signed session tokens stored server-side.
- On startup, lightweight SQL migrations add missing columns/tables for new features.

