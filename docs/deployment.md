# Deployment guidance

CareerLens is currently a local development app. It has not been deployed. This guide lists the work required before choosing a hosting provider; it does not deploy anything or assume access to a cloud account.

## Local run versus public deployment

Use the regular Python/npm workflow or Docker Compose for localhost development. The Compose file uses a development password and signing key by default, runs the Vite development server, and is not a production deployment configuration.

Before a public deployment, replace the development setup with:

- A production frontend build served through a static host or production web server, with the API base URL set to the deployed API.
- A managed PostgreSQL database with backups, a private connection, and a separately managed migration step.
- Strong secrets stored in the host's secret manager, never in Git or a frontend environment variable.
- HTTPS, a narrow CORS allowlist, login throttling, account recovery, and a production session design (prefer secure, HttpOnly cookies with CSRF protection).
- A file-storage and retention policy for uploaded resumes. The current app stores original file bytes and extracted text in PostgreSQL; review encryption, backup, deletion, and retention requirements before using real user data in a hosted environment.
- Monitoring for health, API errors, database connectivity, storage growth, and model availability.

## Database release sequence

1. Back up the target database.
2. Run the reviewed Alembic migration from a one-off release task: `alembic upgrade head`.
3. Start the API and verify `/api/health` and `/docs`.
4. Start the production frontend and verify registration, sign-in, upload, matching, plan generation, and tracker isolation with test accounts.
5. Confirm rollback and restore steps before allowing real users.

Do not point a public deployment at the local development database or the example secrets. Do not put an Ollama host on the public network. The current AI adapter intentionally accepts only a loopback Ollama URL; production AI requires a separate, explicitly reviewed provider and data-handling design.

## Remaining production work

- The Playwright journey covers invalid uploads, resume deletion with tracker retention, account isolation, and a narrow-screen layout. Before a public release, add password reset/email verification and login rate limiting, then review authentication and session handling with a security checklist.
- Choose a hosting provider and database, define budget and retention policies, and configure domains/TLS.
- Test the built frontend against the deployed API, including CORS and migrations.
- Record a demo using only the fictional sample resume.
