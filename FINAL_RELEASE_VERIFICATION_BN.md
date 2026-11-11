# LibraAI VPS Release Verification — 11 November 2026

## What this ZIP contains
- Consolidated from the full-stack `final(1).zip` project; AI Assistant page added from `vor_merged_final_auth_fixed(2).zip`.
- Reader Borrowing workflow: borrow, renew, return, branch inventory and authenticated route protection.
- Fine workflow: 14-day loan, default BDT 10 per overdue day from the day after due date, account fine ledger, payment-reference submission, admin verification, borrowing lock while unpaid, and Library No-Dues Clearance.
- Existing UI/auth design preserved with additive dashboard shortcuts.
- One authoritative project root; the duplicate nested `LibraAI/` copy and generated caches are excluded.
- VPS files: Docker Compose, backend/frontend Dockerfiles, deployment script, Nginx TLS example, environment templates, GitHub Actions verification workflow.

## Verified in this build environment
- ZIP CRC/integrity: PASS.
- Python compile (`python -m compileall -q .`): PASS.
- Focused backend tests: 34/34 PASS.
- Release/configuration/preflight unit tests: 37/37 PASS.
- Frontend static checks: 12/12 PASS.
- Fine workflow regression checks include exact 14-day due date, BDT fine calculation, unpaid-balance borrowing block, verified-payment release, and legacy returned-loan safety.

## Not verified here — do not claim production-ready
- Full backend suite was not run: this build environment lacks Flask/Werkzeug. `requirements-dev.txt`, `VERIFY_RELEASE.sh`, and the existing GitHub Actions workflow are included to run the full suite in a clean Python 3.12 environment.
- Next.js production build was not completed: clean `npm ci` could not complete in this network-restricted environment. The partial `node_modules` directory was removed from the ZIP. Run `cd frontend && npm ci && npm run build` with internet access.
- Docker image/Compose startup was not verified because Docker Engine is unavailable in this environment.
- Real SSLCommerz/bKash settlement, private object storage, verified database/file restore, publisher rights attestation and independent security review require real provider accounts, VPS infrastructure and external verification.
- SQLite is intended for one VPS / one writer only. PostgreSQL migration and multi-host scaling are not included.

## Fine / student clearance
The system provides a Library No-Dues Clearance after verified fine payment. It does not withhold an academic graduation certificate; academic credential issuance remains under the institution's rules and applicable law.

## Deploy scope
This is a single-VPS deployment candidate, not a claim of fully verified production readiness. Follow `VPS_DEPLOYMENT_BN.md`, configure `.env`, install Docker/Nginx/Certbot, and complete the outstanding checks before live launch.
