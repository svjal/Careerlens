# CareerLens learning guide

Work through one small slice at a time. Keep PostgreSQL and the two local servers running while you explore. For the first walkthrough, use the fictional sample resume so you can focus on the code rather than personal data.

## Step 1 — Find the frontend and API

Open `http://127.0.0.1:5173` and create a local account. Then open `http://127.0.0.1:8000/docs` in another tab.

In the API docs, `GET /api/health` is a public check. The route summaries describe each operation, and `backend/app/schemas.py` defines the response shapes shown in the schema panel. The `/api/v1/auth` routes create and verify accounts. The app uses a signed bearer token for the other endpoints; after signing in through the UI, the browser adds that token to requests. Passwords are stored as salted hashes, not reversible text.

**Try:** Find the resume upload and job-match endpoints in `/docs`. Notice the request fields and response examples.

## Step 2 — Follow a resume through the app

Choose `backend/sample_data/sample_resume.docx`, upload it, then expand “View extracted text and sections.” Refresh the browser and notice that the latest resume is reopened from the database. If you have multiple saved resumes, select one from the saved-resume list.

Trace the flow through these files:

1. `frontend/src/App.tsx` builds a `FormData` request and sends it to `POST /api/v1/resumes/parse`.
2. `backend/app/api/routes/resumes.py` enforces the size limit, verifies account ownership context, and calls the parser.
3. `backend/app/services/resume_parser.py` uses `python-docx` for DOCX and `pypdf` for PDF, detects headings, groups likely experience/education/project entries from formatting hints, and matches a curated skill catalog.
4. `backend/app/services/resume_scorer.py` counts completeness evidence. This is a document checklist, not a judgment of a person's ability.
5. `backend/app/models/records.py` defines the PostgreSQL row. Alembic migrations create and evolve the tables.
6. `GET /api/v1/resumes` and `GET /api/v1/resumes/{id}` list and reopen only resumes belonging to the signed-in user. `DELETE /api/v1/resumes/{id}` removes that resume and its comparisons and career plans; applications remain in the tracker with no match attached.

The entry grouping is deliberately conservative and rule-based: common date/separator patterns and a few degree/job-title terms hint at boundaries. Treat the grouped entries as a reading aid, not verified facts, and use “View extracted text and sections” to check the source.

**Try:** Change the sample text in a copy of a DOCX, add a clearly labeled skill, and compare the detected output. Avoid editing the bundled example; keep it as a known-good reference.

## Step 3 — Understand the match score

Paste a job description that mentions a few skills from the sample. The service in `backend/app/services/job_matcher.py` calls the same `extract_skills()` function for both text inputs, so it compares names produced by one shared catalog.

In `backend/app/services/resume_parser.py`, `SKILL_TERMS` contains the canonical names CareerLens stores and displays. `SKILL_ALIASES` maps common spellings to those names—for example, “Postgres” becomes “PostgreSQL,” “K8s” becomes “Kubernetes,” and “Amazon Web Services” becomes “AWS.” The extractor checks each canonical name and its aliases without regard to capitalization, then returns a deduplicated, alphabetized list of canonical names. Its word-boundary checks help prevent accidental matches, such as `Java` inside `JavaScript` or the `JS` alias at the end of `React.js`.

This is still keyword matching: the catalog only recognizes terms listed in the code and their explicit aliases. It does not infer that two different phrases mean the same thing, or understand whether a skill was used professionally.

The current formula is:

```text
match score = recognized job skills also found in resume
              ÷ all recognized job skills × 100
```

The API also saves the matching and missing skills. Explicit aliases are normalized first; the score still does not compare context, seniority, skill depth, or unlisted synonyms.

**Try:** Change `PostgreSQL` to `Postgres` on one side, compare again, and see whether it remains a match. Then add a different catalog skill to the job description that is absent from the resume and observe the denominator and gap list. To add your own alias, edit `SKILL_ALIASES` so both inputs normalize to the same canonical skill name.

## Step 4 — Compare the two career-plan engines

CareerLens uses local rules by default. `backend/app/services/career_analyzer.py` turns the gaps and detected sections into suggestions, a roadmap, project ideas, and interview questions.

The optional Ollama adapter in `backend/app/services/ollama_provider.py` sends the resume text and job description to a local loopback server. It requests a JSON-schema-shaped response and validates it before saving. It rejects non-loopback URLs, disables proxy use, and refuses redirects. The app labels rule-based output and Ollama output separately.

**Try, when Ollama is installed:** Run a model locally, change `CAREER_ANALYSIS_PROVIDER` and `OLLAMA_MODEL` in `backend/.env`, restart the backend, and generate a plan. Check the generated recommendations against the fictional resume. If Ollama is not installed, keep the rules engine and continue.

## Step 5 — Follow saved data into the dashboard

The match and analysis endpoints write through SQLAlchemy models. `GET /api/v1/dashboard/summary` calculates counts, average match score, and the five newest comparisons. It also counts matching and missing skills across all of the signed-in user's saved comparisons, returning each skill's frequency in `skill_coverage`. In `frontend/src/App.tsx`, `MatchScoreChart` reverses newest-first results to draw a chronological SVG line chart; the chart is built into the browser, so it needs no chart package. `ApplicationStatusChart` turns the API's application counts into labeled status bars, while `SkillCoverageChart` draws the recurring skill frequencies. Both bar charts scale each bar to the relevant total. `GET` and `PATCH` on `/api/v1/applications` power the tracker and update its counts.

Each data query includes the authenticated user's ID. That is how account ownership is enforced in addition to requiring a valid token.

**Try:** Save a role, change its status to “applied,” and refresh the dashboard. See how the application count and status summary change.

Compare a few different roles and look at the match-score line. Its vertical axis is a percentage from 0 to 100, and the horizontal order is oldest to newest. Change an application status and watch its bar grow while the other status bars adjust to the new total.

Compare several roles and review “Skill coverage across roles.” A skill's count means how many saved job descriptions include it as overlap or as a gap. This helps find repeated themes, but it is still based on the keyword matcher and does not measure your experience level.

In the resume panel, you can also delete a saved resume after confirming. This is a permanent database deletion for that resume and its match history. The application record remains because it can still be useful as a tracker item after its source comparison is removed.

At the bottom of the dashboard, the account controls can permanently delete the whole local account. The UI asks for the current password and a confirmation checkbox; the API checks the password again before deleting anything. `backend/app/api/routes/auth.py` removes tracker rows first, then comparisons, resumes, and finally the account. Deleting a comparison also removes its saved career plan through the database foreign key. Once the account row is gone, the API rejects its old signed token because protected requests look up the account on each request.

**Try:** Open `/docs`, inspect `DELETE /api/v1/auth/account`, and note the bearer-token requirement and password request body. Use it only with a temporary account: deleting the account is permanent.

## Step 6 — Run the checks

From `backend/`, activate `.venv`, install the development-only client once with `python -m pip install -r requirements-dev.txt`, then run `python -m unittest discover -s tests -v`. The suite includes a full HTTP flow and uses temporary in-memory SQLite databases; it does not alter your PostgreSQL records. From `frontend/`, run `npm run build` to type-check and create a production frontend bundle.

For a real browser journey, install Playwright's browser once with `npx playwright install chromium`, then run `npm run test:e2e`. Locally, the Playwright config starts a separate API and Vite server and creates a disposable SQLite database in the operating system's temporary directory. The tests register unique accounts, upload the fictional DOCX, compare a job, generate the default local career plan, change the application status, reject an unsupported file, delete a resume while checking that its tracker entry remains, verify another account cannot see saved data, check the layout at a 390-pixel viewport, and exercise account deletion. The temporary database is removed after the run, leaving the normal local app data alone. CI runs the same browser journey against its temporary PostgreSQL service after applying migrations.

## Step 7 — Make a small contribution

Choose one improvement and trace it end to end: a new skill, a clearer parser error, a match explanation, or another dashboard metric. Update the relevant unit test, then run the checks above. Keep each change small enough that you can explain the input, transformation, storage, and display.
