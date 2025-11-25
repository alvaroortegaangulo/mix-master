# Repository Guidelines

## Project Structure & Module Organization
- Backend lives in `backend/app` using FastAPI for the API (`server.py`) and Celery tasks (`tasks.py`); audio pipeline code sits in `src/` with job artifacts under `temp/` and sample inputs in `media/`.
- Frontend is a Next 16 + TypeScript app in `frontend/src` (App Router: `app/` for pages/layout, `components/` for UI, `lib/` for helpers); static assets live in `public/`.
- Container setup: `backend/app/docker-compose.yaml` wires Redis, API, Celery worker, and the frontend image built from `frontend/Dockerfile`.

## Build, Test, and Development Commands
- Backend local dev: `cd backend/app && python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000` (requires Python deps from `requirements.txt`).
- Celery worker: `celery -A celery_app.celery_app worker --loglevel=info --concurrency=4` from `backend/app` with Redis reachable at `REDIS_URL`.
- Full stack via containers: `cd backend/app && docker compose up --build` (builds API, worker, Redis, and frontend).
- Frontend: `cd frontend && npm install` once, then `npm run dev` for HMR, `npm run build` for production bundles, `npm start` to serve the build, `npm run lint` for ESLint checks.

## Coding Style & Naming Conventions
- Python: 4-space indents, type hints, `snake_case` for functions/vars, `PascalCase` for classes; prefer `pathlib.Path` for filesystem work and keep side effects behind `if __name__ == "__main__":` blocks.
- Frontend: TypeScript + React function components; filename/component names in `PascalCase` (e.g., `MixResultPanel.tsx`); favor hooks and keep UI state close to components. Tailwind 4 is imported in `globals.css`; reuse the defined CSS variables for colors/fonts.
- Linting: ESLint is configured via `eslint.config.mjs` with Next core web vitals rules; fix warnings before pushing.

## Testing Guidelines
- No dedicated automated test suite yet; minimum check is `npm run lint` and a manual smoke: run the API, call `/pipeline/stages`, and upload a small job to verify Celery + Redis flow.
- When adding tests, co-locate frontend specs under `frontend/src/__tests__/` and backend checks with `pytest` under `backend/app/tests/`; prefer deterministic fixtures for audio samples to keep runs reproducible.

## Commit & Pull Request Guidelines
- Commits: present-tense, imperative subjects (`Add Celery retry logic`), keep to one concern, and include a short scope tag when helpful (e.g., `[frontend]`, `[api]`).
- PRs: include a concise summary, linked issue/goal, before/after notes for UX changes, and screenshots or clip links for UI work. List verification steps (e.g., `npm run lint`, curl to `/mix`) and call out config changes (`REDIS_URL`, `NEXT_PUBLIC_BACKEND_URL`).

## Security & Configuration Tips
- Do not commit secrets; rely on environment variables (see `docker-compose.yaml` for `REDIS_URL` and `CELERY_RESULT_BACKEND`).
- Uploaded media and generated mixes live under `backend/app/temp`; clean old job folders when debugging sensitive data. Exposed downloads are served from `/files`—avoid leaving private assets there.
