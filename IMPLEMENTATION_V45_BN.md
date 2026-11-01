# LibraAI v45 — Reader progress sync hardening

এই update-এ v42, v43 ও v44 archive-গুলোর কোনো ফাইল overwrite করা হয়নি। নতুন build আলাদা archive হিসেবে দেওয়া হচ্ছে। Existing routes, visual styling, book sample licensing guardrails, checkout safety policy এবং frontend design বজায় রাখা হয়েছে।

## v45-এ বাস্তবে যোগ করা হয়েছে

- `GET /api/reader/<book_id>/progress`: signed-in account-এর নিজস্ব saved progress ফেরত দেয়।
- `POST /api/reader/<book_id>/progress`: JSON body থেকে page/percent validate করে একই user/book row-তে upsert করে; app-এর session-bound CSRF middleware প্রযোজ্য।
- Reader-এ scroll position থেকে আনুমানিক progress percentage auto-save হয়, visibility change/page hide-এ sync চেষ্টা করে এবং reload-এ server/local progress restore করে।
- Guest/offline অবস্থায় best-effort localStorage fallback থাকে; cross-device sync-এর জন্য sign-in এবং একই backend/database প্রয়োজন।
- Dependency-free static contract tests যোগ হয়েছে: `test_reader_progress_sync_contract.py`.

## যাচাই

Passed in this environment:
- `python -m py_compile app.py`
- `python -m unittest test_reader_progress_sync_contract -v`
- `node frontend/scripts/verify-client-enhancements.mjs`
- `node frontend/scripts/verify-page-shell.mjs`
- `node frontend/scripts/verify-live-integration-contracts.mjs`
- `node frontend/scripts/verify-security-headers.mjs`

Not verified:
- Flask runtime/API integration tests cannot run in this environment because Flask is not installed.
- Next.js production build cannot be confirmed without installing the declared frontend dependencies.
- Scroll-derived percent is an approximation for this sample-reader prototype; accurate page-level progress requires reader-engine page/CFI callbacks and real licensed PDF/EPUB assets.
- Full site-wide Bangla translation, malware scanning, distributed cache, production PDF/EPUB sync, complete test suite, real payment-provider acceptance, publisher licensing and deployment/restore acceptance remain incomplete.

## Production cautions

This release does not claim all 60 features are complete or production-ready. Payment and publisher rights remain fail-closed; no simulated successful payment or invented license is introduced.
