# Skill Assessment System

*Assess Your Skills. Understand Your Potential. Build Your Career.*

A full-stack career-development platform. A learner uploads a resume, reviews and confirms what was extracted, takes timed
skill assessments, sees verified strengths and gaps, gets explainable career matches, and follows a personal roadmap.
The distinguishing idea: **a resume is a claim, an assessment is evidence**. The two are never confused.

**Stack:** React 19 + TypeScript + Vite + Tailwind + Recharts · Flask + SQLAlchemy + Flask-Migrate · SQLite (PostgreSQL-ready schema) · optional LLM provider.

---

## 1. Install and run (Windows PowerShell)

Prerequisites: **Python 3.11+** and **Node.js 20+** on PATH.

```powershell
cd skill-assessment-system
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass     # only if scripts are blocked
.\setup.ps1          # creates .env, Python venv, installs dependencies, migrates and seeds the database, installs npm packages
```

Then start the two servers in **two PowerShell windows**:

```powershell
# window 1: API  -> http://127.0.0.1:5000
cd backend
.\.venv\Scripts\python.exe run.py

# window 2: web app -> http://localhost:5173
cd frontend
npm run dev
```

Open **http://localhost:5173**, register, and start at *Resume Analyzer*. A sample resume you can use is `backend/tests/helpers.py` (`SAMPLE_RESUME`), or upload your own PDF/DOCX.

macOS/Linux equivalent: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && flask db upgrade && flask seed`, then `python run.py` and `npm run dev`.

### Create an admin
```powershell
cd backend
$env:FLASK_APP = "run.py"
.\.venv\Scripts\flask.exe create-admin        # prompts for email, name, password; promotes the account if the email already exists
```
Sign in with that account; an **Administration** item appears in the sidebar (users, question bank, career-role requirements, categories, skills, resources).

### Database
```powershell
cd backend; $env:FLASK_APP = "run.py"
.\.venv\Scripts\flask.exe db upgrade      # apply migrations (backend/migrations)
.\.venv\Scripts\flask.exe seed            # load skills, assessments, 106 questions, 11 roles, resources, projects (idempotent: never overwrites admin edits)
```
The schema is in `backend/app/models/` (29 tables). To move to PostgreSQL later, set `DATABASE_URL=postgresql+psycopg://...` and `pip install "psycopg[binary]"`; constraint names are explicit so migrations are portable.

### Configuration (`.env` in the project root; see `.env.example`)
| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Required in production (the app refuses to start without it). In development a random key is used and sessions reset on restart. |
| `DATABASE_URL` | Defaults to `backend/instance/app.db` (SQLite). |
| `COOKIE_SECURE` | `true` when served over HTTPS. |
| `MAX_UPLOAD_MB` | Resume size limit (default 5). |
| `SMTP_*` | Optional. Without it, password-reset links are printed in the backend console. |
| `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `AI_TIMEOUT_SECONDS` | Optional AI features (below). |

### Optional AI
The app is fully functional with AI **off**. To turn it on, set in `.env`:
```
AI_PROVIDER=anthropic
AI_API_KEY=<your key from console.anthropic.com>
AI_MODEL=claude-sonnet-4-5          # change to any model your key can use
```
and restart the backend. AI then (a) reads resumes (validated and mapped to the skill list; failures fall back to the built-in parser), (b) can suggest a profile summary, explain a career match in words, suggest learning-resource ideas, and write mock-interview feedback. AI output is always a **suggestion**: nothing is saved without the user's action, AI never produces scores or match percentages, and resume text is sent to the provider only when you upload a resume with AI enabled (interview answers only when you finish an interview).

### Deploy to Render (free demo)
The root `render.yaml` and `Dockerfile` deploy the frontend and API as one same-origin web service, with a PostgreSQL database. This keeps session cookies and CSRF requests same-origin. The blueprint generates a production secret and applies migrations/seeds when the service starts.

1. Create a GitHub repository and push this project. Keep `.env`, database files, and uploaded resumes out of Git (the root `.gitignore` already excludes them).
2. In Render, choose **New + → Blueprint**, connect the repository, and apply the `render.yaml` blueprint. It creates the web service and database.
3. Wait for the service health check to pass at `/api/health`, then register an account. To make yourself an administrator, open the service's Shell and run `flask --app run.py create-admin` from `/app/backend`.

This free configuration is for demos only: the web service can spin down while idle, free PostgreSQL expires after 30 days, and uploaded resumes are on ephemeral storage and can disappear on restart or deploy. Do not upload sensitive or real user resumes to this demo. For durable use, choose a paid database and web service, attach persistent storage for uploads, and configure SMTP before enabling password reset for users. AI and email are disabled unless configured.

### Run the tests
```powershell
cd backend;  .\.venv\Scripts\python.exe -m pytest          # 153 tests
cd frontend; npm test                                      # 26 tests
cd frontend; npm run build                                 # type-check + production build
# live end-to-end journey against a running API (20 steps):
cd backend;  .\.venv\Scripts\python.exe tests\e2e_smoke.py http://127.0.0.1:5000
```
(`e2e_smoke.py` reads correct answers straight from `instance/app.db` to answer the quiz; run it against a fresh seeded database.)

---

## 2. What is implemented

| Area | What it does |
|---|---|
| **Auth** | Register, login (remember-me only if ticked), logout, forgot/reset password (hashed one-time token, 30 min), change password. scrypt hashing, HttpOnly SameSite cookies, CSRF header on every write, rate limits, uniform login errors, deactivated users lose existing sessions. |
| **Resume Analyzer** | Drag-and-drop upload with progress; PDF/DOCX validated by extension **and** content (magic bytes, zip structure, page/size limits, encrypted/macro/empty/scanned rejection). Extracts contact info, education, experience, projects, certifications, skills. Every skill has evidence, source section, confidence and an explicit/inferred flag. Analysis report (strengths, gaps, "how we read this"). Files stored under random names, never served. |
| **Confirmation** | Full editable review: tick/untick and edit every item, accept/reject each skill, add skills manually, new vs *differs-from-saved* badges. Nothing is written until an explicit confirm, and only ticked items are saved. Re-upload replaces the file and diffs against your profile (new, changed, missing; "missing" is reported, never auto-deleted). |
| **Profile** | Edit everything: personal info, summary (optional suggestion), skills, education, experience, projects, certifications, interests, work preferences, target career. Completion checklist. |
| **Assessments** | 4 question types, 3 difficulties, random no-repeat selection, server-enforced timer with grace, autosave, resume interrupted attempts, expiry handling, server-side scoring. Answer keys are never sent to the browser. |
| **Results & analytics** | Marks, %, accuracy, category, per-topic and per-difficulty charts, strengths/weaknesses, full review with explanations, history and improvement trend. |
| **Skill analysis & gaps** | Three evidence levels kept visibly separate; per-role gap table with priority. |
| **Career matching** | Ranked, explainable, deterministic (see `docs/ALGORITHMS.md`); pick a target career. |
| **Roadmap** | Generated from gaps (learn, practise, mini-project, assess); you mark progress; flagged out-of-date after new results; rebuild keeps your progress. |
| **Practice** | 13 projects ranked by relevance to your target gaps, with status tracking; mock interviews (bank or AI) with no fake scores. |
| **Admin** | Users (activate/deactivate), question CRUD with validation (retire, never delete), categories, skills, assessments, role requirements (weights/levels), learning resources, stats. Every admin route is server-gated; a test enforces this for all of them. |

Data included: 64 skills · 26 assessments · **106 questions** · 11 career roles · 27 learning resources · 13 projects.

---

## 3. Known limitations (please read)

**Verification gaps**
- **Not run on Windows or in a real browser.** Everything was verified on Linux with automated tests, a production build, and a live end-to-end API run. `setup.ps1` and the UI's visual rendering have not been seen by a human. Expect to find cosmetic issues.
- **AI has never been called against the live provider** (no key was available while building). The request and response handling is tested with mocked responses, including failures; the first real call may need prompt or model-name tweaks.
- No screen-reader or full accessibility audit (labels, roles, focus handling and reduced-motion are implemented).

**Content**
- **Only 10 of the 26 assessments have questions** (Python, SQL, JavaScript, HTML, CSS, Machine Learning, Statistics, Logical Reasoning, Quantitative Aptitude, Excel). The rest are listed as "Questions coming soon" and cannot be started. Add questions in Admin → Questions.
- The 106 starter questions were written for this project and should be reviewed by a subject expert before any high-stakes use. Per-difficulty pools are small (2-5 questions), so tests with many questions borrow from neighbouring difficulties (the UI says so) and repeat attempts will see repeats across attempts.
- Many roles require skills with no assessment yet (Docker, AWS, Linux, Git, Networking...). Those skills can be confirmed but never verified, so they cap at 40 % credit.
- Difficulty weights (0.6/0.85/1.0), performance bands and match adjustments are sensible design choices, **not psychometrically validated**.
- Learning-resource links were chosen from well-known official sources but not link-checked; admins can edit them.
- Interview and project banks are edited in `backend/app/seeds/`, not in the admin UI. Difficulty levels are a fixed set.

**Resume reading**
- The built-in parser is heuristic and English-only. Unusual layouts (multi-column, tables, graphics-heavy designs) can mis-assign fields. The review step exists for exactly this.
- Scanned/image-only PDFs are rejected (no OCR).
- Only the latest resume is kept.

**Operations**
- Local development uses Flask's development server; Render uses Gunicorn in Docker and serves the built frontend from the same origin.
- Rate limiting is in-memory and per-process (use a shared store for multiple workers).
- No email verification at registration; password reset needs SMTP or the console. The free Render demo has ephemeral resume storage and an expiring database; see the deployment notes above.
- PostgreSQL compatibility is by design (explicit constraint names, portable types) but untested.

## 4. Layout
```
backend/app/{models,routes,services,ai,seeds,utils,config}   backend/migrations   backend/tests
frontend/src/{pages,components,layouts,context,hooks,services,types,utils}
docs/API.md   docs/ALGORITHMS.md   .env.example   setup.ps1
```
Security notes: passwords hashed (scrypt); sessions server-side; CSRF on all writes; ORM everywhere (no string-built SQL); uploads validated by content and stored under random names outside any served path; answer keys and other users' data never leave the server; errors return generic messages; secrets only from the environment.
