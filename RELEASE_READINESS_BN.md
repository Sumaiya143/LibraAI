# LibraAI Release Readiness — current handover note

## v40 additions

- Optional Redis sessions and atomic distributed rate limiting are implemented; shared Redis must be configured and tested. Main application data remains SQLite, so full multi-host deployment is still blocked pending PostgreSQL migration.
- Generic merchant-approved payout HTTP adapter, idempotent submission, signed webhook and provider reconciliation workflow are implemented. This is not a certified native bKash/Nagad integration and must remain disabled/manual until provider approval and live evidence.
- CI now runs clean `npm ci` validation and publishes the generated frontend lockfile if one is missing. Because the current build environment has no registry/DNS access, `frontend/package-lock.json` could not be generated and committed in this archive; do not claim fully reproducible frontend installs until the CI artifact is reviewed and committed.
- Full Flask runtime suite and real browser E2E have not been run locally because Flask is missing and dependencies cannot be downloaded here. Focused tests/static checks pass; release CI must go green before production.

# LibraAI Release Readiness — v19

## এই সংস্করণে source-level improvements

- Next.js frontend ও existing application features সংরক্ষিত।
- Backend test runner এখন skipped tests-সহ যেকোনো failure/error-এ non-zero exit দেয়।
- Windows, Unix ও GitHub Actions backend verification একই strict test policy ব্যবহার করে।
- Frontend CI-তে ভুল npm cache lockfile reference সরানো হয়েছে।

## বর্তমান verification status

- Python source compilation: **Pass**
- ZIP integrity: **প্যাকেজ তৈরির পর যাচাই করতে হবে**
- Full Python test suite: **Not green in this environment** — Flask dependency অনুপস্থিত হওয়ায় একটি subprocess test fail করেছে এবং সাতটি Flask-dependent test skip হয়েছে।
- Payment callback integration: **Not run successfully here** — Flask runtime dependency অনুপস্থিত।
- Next.js production build: **Unverified** — npm registry network/DNS access unavailable; `package-lock.json` নেই।
- Live AI/RAG, payment gateway, database restore, production HTTPS and legal content licensing: **Not verified**.

## Release blockers

1. Install `requirements.txt` in a network-enabled environment and run `python -B verify_full_test_suite.py`; expected result is zero failures, errors and skips.
2. Generate and commit `frontend/package-lock.json`; use `npm ci` and `npm run build` in CI.
3. Run end-to-end tests against actual Flask runtime for login/logout, server-side session expiry/rotation, authorization, CSRF, payment callbacks and persistence.
4. Complete provider sandbox tests, database migration/backup/restore, security audit, domain/HTTPS, monitoring and load tests.
5. Confirm content distribution rights for ebooks, audiobooks, manga/comics and other commercial content.

**Release status: NOT production-certified.** Do not treat a successful archive or source compilation as evidence of live production readiness.


## v19 verification note

- `LIBRAAI_SESSION_BACKEND=sqlite` is now required explicitly in production because this release implements SQLite server-side sessions on a single host only. Redis/PostgreSQL session backends are not implemented and are not accepted as configured.
- New integrated GitHub Actions workflow: `.github/workflows/full-release-verification.yml`. It runs the strict Python suite, payment callback checks, route acceptance, Docker validation/build, Next.js production build and Playwright browser tests. This workflow has been added but has **not** run from this local environment.
- Latest local Python suite: 1,061 tests run; 1 failure; 7 skipped. The failure is a subprocess import error because Flask is unavailable; the seven skipped tests depend on Flask runtime. The strict gate remains red.
- 22 focused configuration/deployment tests pass. Full Next.js build, Docker build, and browser E2E remain unverified here due unavailable package registry/network and unavailable Docker runtime.
