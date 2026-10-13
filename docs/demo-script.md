# CareerLens demo video script

Target length: 3–4 minutes. Use the fictional `backend/sample_data/sample_resume.docx` and a made-up job description. Do not record a real person's resume or show passwords, API tokens, or the contents of `.env`.

## Before recording

1. Start PostgreSQL, the FastAPI backend, and the React frontend as described in the root README.
2. Open the app at `http://127.0.0.1:5173` and sign in with a demo account.
3. Decide which analysis mode to show. The default is transparent local rules. To show Ollama, start a local Ollama model and set the backend provider before starting the API.
4. Prepare a fictional job description that mentions skills present and absent from the sample resume.

## Walkthrough

The repository includes a short captioned screen recording at `docs/assets/careerlens-demo.webm`. Recreate it with `npm run demo:record` from `frontend/`; the browser test uses its isolated database and the fictional sample resume.

### 0:00–0:25 — Introduce the problem

“CareerLens is a local-first project for learning how a resume lines up with a target role. It turns a resume and job description into skill overlap, gaps, and practical next steps. The app and its PostgreSQL data run locally.”

Show the signed-in workspace and briefly mention that each account sees only its own records.

### 0:25–1:05 — Parse a resume

Upload the fictional DOCX. Show the extracted sections, skills, and completeness score.

“The parser reads PDF and DOCX text, detects common section headings, groups likely experience, education, and project entries using formatting hints, and looks for skills in a curated vocabulary. Common spellings such as Postgres and PostgreSQL are normalized to one name. The completeness score checks whether useful resume sections and measurable outcomes are present; it is not a rating of the candidate.”

### 1:05–1:45 — Compare a role

Paste the prepared job description, add a title, and compare it. Show matching skills, missing skills, and the score explanation.

“The current match score is explainable: recognized skills shared by the resume and job description divided by recognized job-description skills. It is a transparent baseline, not a hiring prediction.”

### 1:45–2:35 — Create a career plan

Generate a plan and show resume suggestions, skill priorities, roadmap steps, project ideas, and interview questions.

If the UI says “Rule-based starter,” explain that the plan comes from local rules. If it says “Ollama model,” explain that the configured local model receives the extracted resume and job description at the loopback Ollama service. Do not call the rules output an LLM result.

### 2:35–3:15 — Track the application

Add the role to the application tracker. Change its status and show the dashboard metrics, score timeline, application-status bars, and recurring skill coverage.

“CareerLens saves the comparison and tracker entry in PostgreSQL, then refreshes the dashboard from the API. The skill summary counts recognized overlaps and missing keywords across saved roles, so repeated requirements are easier to spot.”

### 3:15–3:45 — Explain the stack

Show the API docs at `http://127.0.0.1:8000/docs` and briefly name the stack: React and TypeScript, FastAPI, SQLAlchemy, PostgreSQL, and Alembic migrations. Mention the local automated checks and Docker Compose option.

## Suggested closing

“This is a learning project, so the keyword vocabulary and score are intentionally simple. The next improvements are broader coverage for error paths, more nuanced matching, and a carefully evaluated local AI model.”
