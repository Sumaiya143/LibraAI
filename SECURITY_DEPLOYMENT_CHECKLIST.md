# LibraAI Security & Deployment Checklist

This checklist is intentionally evidence-based. A checked environment flag is not a substitute for an independently verifiable result.

## Before any public production launch

- [ ] Use a unique random `SECRET_KEY` (32+ chars), private environment file, least-privilege service account and secret rotation plan.
- [ ] Set the canonical public URL to HTTPS and verify TLS, HSTS, secure/HttpOnly/SameSite cookies and trusted-proxy configuration.
- [ ] Choose single-host SQLite sessions or configure authenticated TLS Redis sessions and atomic Redis rate limiting. Redis alone does not make the primary SQLite application database multi-host safe.
- [ ] Migrate the primary database to PostgreSQL before horizontal/multi-host deployment; test migrations, rollback, isolation, concurrent writes and recovery.
- [ ] Configure request-size limits, rate limits, CSRF, authentication/authorization, upload validation and malware/content scanning. Verify all write endpoints with negative authorization tests.
- [ ] Configure payment provider callbacks, signature validation, replay/idempotency controls, refund paths and settlement reconciliation. Test in sandbox and document evidence.
- [ ] Keep creator payouts in manual review until a merchant-approved provider contract is connected. Verify idempotency, signed webhooks, timeout ambiguity, duplicate delivery, reconciliation and failed-transfer recovery.
- [ ] Store ebooks/audiobooks in private durable storage; test access policy, encryption, signed URL expiry, retention and restore.
- [ ] Verify actual publisher/author permissions by content, format, territory, term, distribution channel and royalty terms.
- [ ] Run `python -B -m unittest discover -p "test_*.py" -v`, production frontend build, desktop/mobile Playwright E2E and live staging integration tests.
- [ ] Run an independent penetration test; remediate and retest findings. Review dependencies/SBOM and keep patched versions.
- [ ] Configure structured logs with PII redaction, request IDs, metrics, actionable alerts and incident runbooks.
- [ ] Perform encrypted backup and restore drills for the database and private files; document RPO/RTO.
- [ ] Obtain business/legal sign-off for payment processing, content rights, privacy policy, terms, refunds and data retention.

## Current implementation notes

- Redis-backed server-side sessions and distributed rate limiting are optional code paths; this archive has not been tested against a live Redis service.
- The payout module is a generic merchant-approved HTTP contract, not a certified native bKash/Nagad integration.
- Frontend package lock is not embedded because the package registry was unreachable in the build environment. Review and commit the generated `frontend/package-lock.json` artifact from CI before claiming reproducible frontend installs.
- Production acceptance remains blocked until full runtime tests, real browser E2E, provider sandbox/live evidence, primary database scaling migration and independent security sign-off are complete.
