# LibraAI v60 — Final Client Handover Status (বাংলা)

## সিদ্ধান্ত
এই ZIP হলো source-code/client-handover candidate; এটি 100% production-certified বা live-commercially-verified release নয়। Hosting/domain কেনা ছাড়াই local setup, source review এবং CI verification সম্ভব। কিন্তু client-এর environment, provider credentials, staging database ও externally reachable HTTPS callback ছাড়া বাস্তব integration/production behavior certify করা যায় না।

## এই build-এ পুনরায় চালানো checks
- `test_extended_verification.py`, `test_backup_restore.py`, `test_backup_safety.py`, `test_payment_callbacks_integration.py`: 15টি test discovery; 10 pass, 5 skip (Flask অনুপস্থিতির কারণে payment callback route integration)।
- `verify_full_test_suite.py`: শুরু হয়নি; `flask` ও `werkzeug` runtime dependency অনুপস্থিত। pip install চেষ্টা করা হয়েছে, কিন্তু environment-এর DNS/network access না থাকায় package registry পাওয়া যায়নি।
- v59 ZIP-এর CRC/integrity check: pass; archive-এ 535টি পূর্ববর্তী entry ছিল।

## এখনো client/staging-এ বাধ্যতামূলক
1. Python requirements install করে `VERIFY_PROJECT.bat` সম্পূর্ণ green করা; skipped test শূন্য হতে হবে।
2. Frontend-এর lockfile/dependencies প্রস্তুত করে `npm ci` ও `npm run build` সফল করা।
3. Client-এর নির্বাচিত DB engine-এ migration, backup, isolated restore, schema/row-count ও application-level read/write validation। SQLite drill PostgreSQL/MySQL production recovery-র বিকল্প নয়।
4. bKash/SSLCommerz বা নির্বাচিত payment provider-এর sandbox credentials দিয়ে create→callback/IPN→signature/server validation→amount/currency→idempotency→refund/entitlement lifecycle পরীক্ষা। Live charge নয়।
5. AI/storage/email/other external API sandbox বা test credentials দিয়ে success, timeout, retry, rate-limit, invalid credential ও failure-path test।
6. Staging HTTPS/TLS, secure cookies, CORS/CSRF, headers, secrets, authorization/IDOR, upload validation, rate limits, dependency vulnerability review এবং manual penetration test।
7. Independent security auditor-এর লিখিত report, findings remediation এবং retest। Automated `security_review.py` independent audit নয়।
8. GitHub Actions-এ required workflows green এবং client acceptance sign-off।

## Commercial release gate
উপরের সব item evidence (CI logs, test reports, DB restore log, provider sandbox transaction IDs, TLS scan, auditor report) সহ pass না হওয়া পর্যন্ত product-টিকে “100% production verified” বলা যাবে না। Production secrets কখনো GitHub repository-তে commit করবেন না; client-এর secret manager/environment-এ দিন।

## Local commands
```bash
python -m pip install -r requirements.txt
python verify_full_test_suite.py
cd frontend
npm ci
npm run build
```
Windows-এ project root থেকে `VERIFY_PROJECT.bat` চালান। প্রথমবার frontend lockfile না থাকলে project-এর `START_FRONTEND.bat` নির্দেশনা অনুসরণ করে lockfile তৈরি ও commit করুন।
