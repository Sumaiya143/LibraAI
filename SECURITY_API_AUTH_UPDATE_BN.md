# LibraAI Backend API, Authentication & Security Update

## Implemented in this archive

- Updated the Next.js login form to use the JSON `/backend/api/login` endpoint.
- Updated the Next.js signup form to use the JSON `/backend/api/signup` endpoint.
- Both flows obtain a session-bound CSRF token from `/backend/api/csrf` and send it in `X-CSRF-Token`.
- Login now follows the server-provided role-specific redirect instead of a hard-coded dashboard route.
- Signup allows the server to generate a username when the optional username field is blank, and follows the server-provided workspace redirect.
- Added client-side input bounds for identifiers, email, and passwords; backend validation remains authoritative.
- Added explicit write-rate limits for `/api/login`, `/api/auth/login`, `/api/signup`, and `/api/auth/signup`.
- Added `Cross-Origin-Opener-Policy: same-origin` and disabled the legacy XSS auditor header on Flask and Next.js responses.
- Added production-only HSTS to Next.js responses and disabled DNS prefetching.
- Expanded the frontend security-header verification contract.
- Kept the existing visual authentication layout and existing application pages/features intact.

## Verification performed

- Python syntax compilation: passed for the edited backend modules.
- API resilience, authentication throttle, account security core, and persistent throttle unit tests: 26 passed.
- Frontend security-header contract: passed.
- Full Flask API endpoint integration tests and production Next.js build were not run in this environment because Flask runtime dependencies and frontend `node_modules` are not installed.
- The existing page-shell and live-integration verification scripts expect an `app/` directory at the project root, while this archive places the Next.js App Router under `frontend/app/`; those scripts therefore cannot run from the documented project root without correcting their path assumptions.

## Production deployment requirements

Before public deployment, install dependencies, run the complete test suite and production frontend build, verify HTTPS and environment secrets, and run browser/API integration tests against staging. Use a shared Redis rate-limit/session backend only with TLS and migrate the primary SQLite application database before multi-host deployment. Password recovery remains an administrator/support-assisted process until an email delivery provider and verified reset-token workflow are configured.
