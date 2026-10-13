# CareerLens

CareerLens is a local-first career intelligence app. It extracts text and skills from a resume, compares them with a job description, suggests next steps, and tracks applications. Career advice uses transparent local rules by default, with an optional Ollama integration for on-device language-model analysis.

## What is built

- React + TypeScript frontend
- FastAPI backend
- Interactive OpenAPI documentation with typed request and response contracts
- PostgreSQL persistence with Alembic migrations
- Account registration and sign-in, with user-scoped career data
- Account deletion with password confirmation; it removes the account's resumes, comparisons, plans, and tracker records
- PDF and DOCX resume text extraction, section detection, and skill matching with a curated vocabulary and common spelling aliases
- Experience, education, and project text grouped into likely entries using resume formatting hints
- Saved resumes can be reopened and reused for later role comparisons
- Resume deletion also removes its saved comparisons and career plans while keeping tracker entries
- Resume completeness feedback and a job match score with an explanation
- Saved career plans and a job application tracker
- Dashboard analytics with a five-match score history, application-status distribution, and recurring skill overlaps and gaps
- Optional Ollama analysis with schema-checked suggestions, roadmap, project ideas, and interview questions

## Run it on localhost

The regular development setup uses the local Python and Node.js installations and a running PostgreSQL server. PostgreSQL.app works well on macOS.

### 1. Start PostgreSQL

Start your local PostgreSQL server and create a database named `careerlens` if you have not already done so. The commands below assume your local PostgreSQL role can connect to that database without a password. If yours uses a password or a different role, update `DATABASE_URL` accordingly.

### 2. Configure the backend

Open a terminal in the repository and run:

```sh
cd backend
cp .env.example .env
```

Edit `backend/.env` so `DATABASE_URL` points to your local database. For the default macOS PostgreSQL.app setup, it looks like:

```dotenv
DATABASE_URL=postgresql+psycopg://YOUR_MAC_USERNAME@127.0.0.1:5432/careerlens
```

Set `JWT_SECRET_KEY` in that same file to a fresh random value. You can create one with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Keep the value private and do not commit `.env`.

Create the Python environment and install the pinned dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --reload-dir app --port 8000
```

Keep this terminal open. The API runs at [http://127.0.0.1:8000](http://127.0.0.1:8000), and its interactive API reference is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 3. Start the frontend

Open a second terminal at the repository root:

```sh
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Keep both terminals and PostgreSQL running while you use the app.

The first screen lets you create an account. Each account can read and change only its own resumes, matches, career plans, and application records. Passwords are stored as salted PBKDF2 hashes; the API returns a signed token that the browser keeps in session storage for up to 60 minutes. Signing out clears that browser tab's token and current resume view. The account controls at the bottom of the dashboard can permanently delete the account after you re-enter its password and confirm the deletion.

### Optional on-device AI

The default `CAREER_ANALYSIS_PROVIDER=rules` keeps the app independent of an AI service. To use a local Ollama model, install Ollama, run `ollama run gemma3:1b`, then set `CAREER_ANALYSIS_PROVIDER=ollama` and `OLLAMA_MODEL=gemma3:1b` in `backend/.env`; restart the backend after changing `.env`. The official [Gemma 3 model page](https://ollama.com/library/gemma3) lists this 1B model. Keep `OLLAMA_BASE_URL` on `http://127.0.0.1:11434`; the backend rejects non-loopback hosts and disables redirects and environment proxies so resume text stays on this computer. Ollama's chat endpoint supports non-streaming requests and JSON-schema-constrained responses, which CareerLens uses to validate the returned plan ([Ollama chat API](https://docs.ollama.com/api/chat)).

The prompt sends the extracted resume text, detected sections, job description, match score, and missing skills to the configured local Ollama process. It does not call a cloud AI API. If the local model is unavailable or returns invalid output, the API reports an error instead of silently presenting rule-based advice as AI output. The Docker Compose setup stays in rules mode; the optional Ollama connection currently applies to the native local Python backend.

### Sample resume

Use `backend/sample_data/sample_resume.docx` to try the extraction flow with fictional data. The file contains a built-in sample profile, so you do not need to upload a personal resume to learn the workflow.

## Run with Docker Compose

Docker Compose runs a separate PostgreSQL container and does not use your PostgreSQL.app database. Docker Desktop must be running first. From the repository root:

```sh
docker compose --project-name careerlens-local up --build
```

Then open [http://127.0.0.1:5173](http://127.0.0.1:5173). The compose database is mapped to host port `5433`, so it can coexist with a local PostgreSQL server on port `5432`. Stop the foreground command with `Ctrl+C`, or stop a detached run with `docker compose --project-name careerlens-local down`. The named database volume remains so your saved data survives a normal stop. To erase that container database, use `docker compose --project-name careerlens-local down -v`.

The default Compose database password and token-signing secret are for local development only. Set `CAREERLENS_DB_PASSWORD` and `CAREERLENS_JWT_SECRET` in your shell before starting Compose if you want different local values. Do not reuse this development configuration for a public deployment.

If the native development servers are already using ports `8000` and `5173`, Compose ports can be changed for one run. For example:

```sh
CAREERLENS_DB_PORT=15433 CAREERLENS_API_PORT=18000 CAREERLENS_FRONTEND_PORT=15173 CAREERLENS_API_BASE_URL=http://127.0.0.1:18000 docker compose --project-name careerlens-local up --build
```

The frontend API URL must use the same host API port selected in `CAREERLENS_API_PORT`, because the browser calls the API directly. Compose also passes that frontend port to the backend's local CORS allowlist. For the native setup, `CORS_ALLOWED_ORIGINS` in `backend/.env` defaults to `http://127.0.0.1:5173,http://localhost:5173`.

## Run the current automated checks

The backend tests use Python's built-in `unittest` plus FastAPI's HTTP test client. Install the development requirements once:

```sh
cd backend
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

The backend checks cover PDF and DOCX parsing, section and likely-entry grouping, skill extraction, score calculation, local career-plan rules, password and token behavior, Ollama request/response validation with a mocked response, and a full HTTP flow from signup through resume upload, matching, career plan, tracker, dashboard, account isolation, resume deletion, and password-confirmed account deletion. Those tests use temporary SQLite databases with foreign-key enforcement. The Playwright browser journey exercises the main user flow, invalid upload feedback, resume deletion with tracker retention, account isolation, narrow-screen layout, and account deletion through the UI with the fictional sample resume and a disposable SQLite database. CI also applies migrations to a temporary PostgreSQL service. Deleting a resume removes its comparisons and career plans while leaving tracker entries with their match reference cleared.

The `.github/workflows/ci.yml` workflow runs the backend tests, applies migrations to a temporary PostgreSQL service, builds the frontend, and runs a Playwright browser journey on pushes, pull requests, or a manual workflow dispatch. It needs a GitHub remote before GitHub can run it.

For the same browser journey locally, install the Playwright browser once and run its command from `frontend/`:

```sh
npx playwright install chromium
npm run test:e2e
```

The browser test starts its own API and Vite servers on ports `18001` and `15174`. Locally it creates a disposable SQLite database under the system temporary directory and removes it after the run, so it does not touch the database used by the normal local app. In CI, the same browser journey uses the temporary PostgreSQL service after the migration check.

## Record the demo video

From `frontend/`, run `npm run demo:record` to create a short captioned screen recording at `docs/assets/careerlens-demo.webm`. It uses the fictional sample resume, a disposable SQLite database, and separate test ports; it does not use the normal local database or the browser's saved session.

## How the project is organized

```text
backend/
  app/api/routes/     HTTP endpoints for resumes, jobs, dashboard, and applications
  app/core/           application settings
  app/db/             SQLAlchemy connection and session setup
  app/models/         database tables
  app/services/       resume parsing, matching, scoring, and career-plan providers
  migrations/         versioned PostgreSQL schema changes
  requirements.txt    backend runtime dependencies
  requirements-dev.txt FastAPI HTTP test client dependency for development tests
  sample_data/        fictional resume for local practice
docs/                 demo, portfolio, and deployment guidance
frontend/
  src/                React interface and styles
compose.yaml          optional local Docker setup
```

## Learning path

The step-by-step [learning guide](docs/learning-guide.md) follows the upload, matching, career-plan, authentication, and dashboard code paths. The rule-based plan is clearly labeled when Ollama is not enabled.

The repository also includes a [demo script](docs/demo-script.md), [portfolio drafts](docs/portfolio-copy.md), and [deployment guidance](docs/deployment.md).

## Current limits

- Authentication is a learning-stage implementation: email verification, password reset, rate limiting, and hardened production cookie handling are not included yet.
- Text-based PDFs and DOCX files are supported; image-only scans need OCR, which is not included. Skill extraction is based on an editable keyword catalog and explicit aliases, so it will not recognize every skill or infer unstated equivalents.
- Experience, education, and project entry boundaries are heuristic. The original extracted text remains available to review, and the app does not infer missing titles, dates, or qualifications.
- Ollama is optional and must be installed separately with a model that fits your computer. No cloud AI provider is configured.
- Compose is a local development setup, not a production deployment recipe.
