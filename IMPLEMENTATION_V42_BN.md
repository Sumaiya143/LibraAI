# LibraAI v42 — verification and developer workflow hardening

## এই release-এ কী উন্নত হয়েছে

- v41 cleanup-এ বাদ পড়ে যাওয়া `BUYER_VERIFICATION_CI_BN.md` পুনরুদ্ধার করা হয়েছে; buyer CI contract test এখন required document খুঁজে পায়।
- `project_doctor.py` এখন test-only `sys.modules` stub-এর `__spec__` না থাকলেও crash করে না এবং কোনো secret value প্রকাশ করে না।
- `test_audiobook_library.py`-এর optional Flask fallback শুধু ওই module import করার জন্য scoped; test শেষে stub-টি `sys.modules` থেকে সরিয়ে দেয়। এতে অন্য test ভুল করে fake Flask module ব্যবহার করে না।
- `production_preflight.py`-তে strict `valid_public_url()` যোগ হয়েছে: malformed/invalid numeric IP, private/reserved/local host, non-HTTPS URL, credentials, query/fragment এবং app path reject করে।
- পুরোনো `inspect()` report API-র compatibility adapter যোগ হয়েছে; নতুন code-এর জন্য `audit_environment()`-ই canonical API।
- `verify_full_test_suite.py` suite শুরু করার আগে Flask/Werkzeug availability যাচাই করে। Required dependency না থাকলে noisy cascade না দেখিয়ে actionable message ও exit code 2 দেয়; কোনো test pass হয়েছে এমন দাবি করে না।
- `START_FRONTEND.bat` এবং `SETUP_FRONTEND.sh` প্রথমবার authentic `package-lock.json` তৈরি করার চেষ্টা করে, এরপর `npm ci` ও lockfile validation চালায়। প্রথমবার network access লাগে; generated lockfile project-এর সঙ্গে রেখে/commit করে রাখতে হবে।
- Frontend lockfile check, route-shell, security header ও static integration checks-এর developer workflow documentation আপডেট করা হয়েছে।

## যাচাইয়ের ফল

- Focused regression tests: 54টি পাস (preflight compatibility, URL validation, project doctor, buyer CI contract, audiobook licensing helper এবং suite dependency preflight)।
- Python source AST/syntax checks, JavaScript `node --check`, frontend static route/security/integration checks ও package-safety check আলাদাভাবে চালানো হয়েছে।
- ZIP SHA-256 manifest ও CRC verification করা হয়েছে।

## Environment limitation

এই build environment-এ Flask/Werkzeug install করা নেই এবং package registry access নেই। তাই Flask-নির্ভর full runtime suite, Next.js production build ও Playwright browser E2E এখানে সম্পূর্ণ চালানো যায়নি। `verify_full_test_suite.py` এখন dependency না থাকলে এটি স্পষ্টভাবে জানিয়ে suite শুরু না করেই থামে। Clean environment-এ `python -m pip install -r requirements.txt`, `python -B verify_full_test_suite.py`, `python -B buyer_acceptance.py`, এবং frontend lockfile generation/build/browser tests চালাতে হবে।

## Production boundary

URL syntax validation বা passing unit tests live payment, publisher rights, AI provider, automated payout, Redis connectivity, PostgreSQL migration, backup restoration, independent security review বা production acceptance-এর প্রমাণ নয়।
