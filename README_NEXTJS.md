# LibraAI — local development and release guide

LibraAI uses a **Next.js App Router / React / TypeScript** frontend and a **Python / Flask** backend. The backend owns authentication, catalog data, sessions, and commerce actions.

## Quick start on Windows

**Requirements:** Python 3.12+, Node.js 20+ (npm included), and internet access for the first dependency installation.

1. Extract the ZIP and open the `LibraAI` folder.
2. Double-click `START_LIBRAAI.bat`. It opens backend and frontend in separate terminal windows. Alternatively, start `START_BACKEND.bat` and `START_FRONTEND.bat` separately.
3. Open `http://localhost:3000`. The backend normally listens on `http://127.0.0.1:5000`.
4. Keep both terminal windows running while using the app. Close them to stop the local servers.

The startup scripts create a local `.venv` if needed and install dependencies. `START_FRONTEND.bat` (Windows) or `./SETUP_FRONTEND.sh` (macOS/Linux) generates the initial authentic `frontend/package-lock.json` when missing, installs via `npm ci`, and validates the lockfile. The first generation requires internet access. Keep the generated lockfile with the project and commit it to source control so later installs are deterministic.

## Manual start

Backend terminal (from the project root):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python project_doctor.py
python app.py
```

Frontend terminal (Windows PowerShell):

```powershell
cd frontend
npm install --package-lock-only --ignore-scripts
npm ci
node scripts/verify-lockfile.mjs
npm run verify:shell
npm run verify:security-headers
npm run dev
```

On macOS/Linux, run `./SETUP_FRONTEND.sh` from the project root.

## Complete local verification (Windows)

Run `VERIFY_PROJECT.bat` from the project root after installing Python 3.12+ and Node.js 20+. It installs backend requirements, checks environment prerequisites, runs release/configuration tests, requires the strict Python suite to pass with zero skips, runs frontend source-contract checks, and builds the production frontend. A non-zero exit means verification failed or is incomplete; do not deploy.

The first frontend setup needs internet access to generate `frontend/package-lock.json`. Commit that generated lockfile to GitHub so clean installs are reproducible. The root `package-lock.json` is for Playwright tests and is not a substitute for the frontend lockfile.

## Diagnostics, tests, and build

```powershell
python project_doctor.py
python -B verify_full_test_suite.py
python buyer_preflight.py
python verify_handover.py
```

`project_doctor.py` checks required local prerequisites and reports warnings without exposing environment variable values. `verify_handover.py` deliberately exits non-zero when live-provider, browser, hardware, or independent security sign-off is missing; this is not the same as a failed local startup.

For frontend production compilation:

```powershell
cd frontend
npm install
npm run build
```

Do not deploy until the build succeeds and the strict production preflight and live staging checks have been completed.

## Frontend and catalog behavior

- The public homepage and discovery/library UI include preview data for visual development.
- `/library/[slug]` tries to resolve titles against `/backend/api/books`; when a preview title is absent from the live backend catalog, it is labelled as sample content and purchase actions are disabled.
- Live catalog purchase actions require a signed-in user and configured backend/CSRF flow.
- The legacy Flask routes remain available behind `/backend/*` where linked from the Next.js UI.

## Environment and deployment boundary

- `.env.example` is for local development only. Never use its development secret in production.
- `.env.production.example` is a checklist with placeholders. Supply secrets through the deployment environment; do not commit `.env` or credentials.
- The main application database remains SQLite. Redis sessions and distributed rate limiting do not, by themselves, make the whole app safe for multiple application hosts. Complete PostgreSQL migration and concurrency/backup/restore tests first.
- Run `python production_preflight.py --strict` before deployment. It checks configuration; it does not prove provider approval or successful live operations.
- Keep real payment credentials, customer data, databases, and backups out of the source ZIP.

## Useful documentation

- `IMPLEMENTATION_V42_BN.md` — latest verification and developer workflow changes.
- `IMPLEMENTATION_V41_BN.md` — prior cleanup and startup changes.
- `PRODUCTION_PREFLIGHT_BN.md` and `SECURITY_DEPLOYMENT_CHECKLIST.md` — deployment gates.
- `PAYOUT_PROVIDER_BN.md` — payout adapter boundary and staging requirements.
- `SCALABILITY_REDIS_BN.md` — shared sessions and rate-limiter requirements.
- `FRONTEND_LOCKFILE_BN.md` — frontend dependency lockfile status.
- `AUDIOBOOK_HOSTING_SETUP_BN.md` and `SEMANTIC_SEARCH_SETUP_BN.md` — optional integrations.
