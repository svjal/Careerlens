# CareerLens portfolio copy

These drafts describe the repository as it exists. Keep the Ollama statement conditional until a local model has been installed and exercised in a real demo. Do not add personal performance metrics unless you measured them.

## Resume bullets

- Built CareerLens, a local-first career analysis web app with a React and TypeScript frontend, FastAPI backend, and PostgreSQL persistence.
- Implemented PDF/DOCX text extraction, resume section and likely experience/education/project entry detection, skill overlap and gap analysis, an explainable match score, and an application tracker.
- Added account registration, salted PBKDF2 password hashes, signed bearer tokens, per-user data filtering, and versioned PostgreSQL migrations.
- Added an optional Ollama integration that validates structured career-plan output and restricts the model endpoint to loopback; kept transparent rules as the default analysis mode.
- Packaged local development with Docker Compose, documented setup and API usage, and added Python service tests, PostgreSQL migration checks in CI, and Playwright user-flow tests.

## LinkedIn project description

**CareerLens — local-first career intelligence**

CareerLens helps a user explore how a resume aligns with a target job description. The app extracts text and skills from PDF or DOCX resumes, detects common resume sections, calculates a transparent keyword-overlap score, highlights missing skills, and saves career plans and application activity to PostgreSQL.

I built the interface with React and TypeScript and the API with FastAPI and SQLAlchemy. Account access is scoped to each user, schema changes are tracked with Alembic, and Docker Compose provides an optional local setup. Career plans use transparent local rules by default, with an optional loopback-only Ollama integration for on-device language-model analysis.

This is a learning project. Its curated keyword vocabulary, explicit spelling aliases, and overlap score are not a hiring prediction or a measure of a person's overall qualifications.

## LinkedIn post draft

I’ve been building CareerLens, a local-first project that helps explain how a resume lines up with a target role.

The current app can read PDF and DOCX resumes, find common sections and skills, compare those skills with a job description, and save a career plan and application status. I used React and TypeScript for the interface, FastAPI for the API, and PostgreSQL for persistence.

One design choice I focused on is making the match score understandable: it shows the overlap in a curated list of recognized skills, normalizing a few common spelling aliases, rather than presenting itself as a hiring judgment. Career advice uses transparent local rules by default; an optional local Ollama adapter is available for structured on-device analysis.

I’m using the project to learn how a complete app fits together—from migrations and account access to the frontend flow and local development setup. My next step is to review account recovery, login throttling, and session handling before deciding whether the app is ready for public deployment.

#CareerLens #FullStackDevelopment #FastAPI #React #PostgreSQL #LearningInPublic
