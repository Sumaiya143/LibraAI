# LibraAI v44 — Remaining-work implementation update

The original `LibraAI_v42_Regression_Hardening_Developer_Workflow.zip` and the prior v43 archive are preserved. This update is packaged separately.

## Implemented in v44

- Fixed a malformed literal newline in the Header TypeScript source.
- Removed duplicate AI-chat clear-history controls and duplicate footer copy.
- Added account-scoped AI conversation history endpoints at `GET/POST/DELETE /api/ai/history`. Records are tied to the authenticated user, capped at 100 messages, validated, and protected by the app's CSRF middleware. SQLite stores them durably for the configured app database.
- Updated the floating AI chat to restore authenticated server history, maintain a local browser backup, and queue account-history sync requests. Guest/offline use remains device-local.
- Added `/study-tools`, a premium-styled workspace for summary, fill-in-the-blank quiz, and revision flashcards from user-provided/authorized chapter text.
- Added a reusable, offline/local `study_tools.py` extractive generation module with text-size and sentence validation.
- Added four unit tests for study-set generation and validation.
- Expanded `frontend/scripts/verify-client-enhancements.mjs` to check the language, durable-history and study-tools integration contracts.
- Connected the global AI Tools navigation item to `/study-tools`.

## Verification performed

Passed:
- Python syntax compilation for `app.py`, `study_tools.py`, and `test_study_tools.py`.
- `python -m unittest test_study_tools -v` (4 tests).
- `node scripts/verify-client-enhancements.mjs` from `frontend/`.
- `node scripts/verify-page-shell.mjs`.
- `node scripts/verify-live-integration-contracts.mjs`.
- `node scripts/verify-security-headers.mjs`.
- ZIP archive CRC validation after packaging.

Not verified / still outstanding:
- Full Next.js production build and TypeScript compilation: frontend dependencies and `frontend/package-lock.json` are not present in this environment.
- Full Python suite: 1,153 tests were discovered; the run failed because Flask is not installed in this environment (three import/runtime errors and one subprocess-dependent failure were reported). Most dependency-independent tests passed, but this is not a clean full-suite result.
- End-to-end cross-device history under a real multi-instance deployment. The app currently uses its configured primary database; the existing deployment docs already note that SQLite must be migrated for multi-host production.
- Full site-wide Bangla translation, all reader formats and automatic progress sync, malware scanning service, production distributed cache, real payment provider acceptance, publisher licensing, and production deployment/restore acceptance.

## Important behavior notes

- The study tool is explicitly **local extractive analysis**, not a generative AI model. It creates a short extractive summary and simple keyword-based revision materials; it should not be marketed as advanced AI summarization.
- Real payments remain fail-closed unless a verified provider is configured. No fake payment confirmations or publisher rights are added.
- The original v42 and v43 ZIP files are unchanged.
