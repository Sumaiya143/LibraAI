# LibraAI v57 — Backend Verification & GitHub Portability (বাংলা)

## উদ্দেশ্য

v56-এর সব ফাইল ও ফিচার অক্ষুণ্ণ রেখে স্থানীয় Windows verification এবং GitHub Actions-এর frontend bootstrap আরও নির্ভরযোগ্য করা হয়েছে।

## পরিবর্তন

- `.github/workflows/full-release-verification.yml`-এ `frontend/package-lock.json` অনুপস্থিত থাকলেও `setup-node` cache setup যেন missing-file error না দেয়, সেই cache configuration সরানো হয়েছে। Workflow এখন frontend directory-তে lockfile না থাকলে `npm install` দিয়ে bootstrap করে এবং পরেই `npm ci` দিয়ে clean install যাচাই করে।
- `test_release_portability.py` যোগ করা হয়েছে; এটি CI lockfile bootstrap, Windows startup script, required entrypoints ও secret-file hygiene-এর dependency-free regression checks চালায়।
- `VERIFY_PROJECT.bat` যোগ করা হয়েছে; এটি backend dependencies install করে, environment doctor, targeted release tests, strict full Python suite, frontend source verification এবং production build চালায়। কোনো ধাপ ব্যর্থ হলে non-zero exit দেয়।

## Windows-এ যাচাই

1. Python 3.12+ এবং Node.js 20+ ইনস্টল করুন।
2. Project root থেকে `VERIFY_PROJECT.bat` চালান।
3. Frontend dependencies প্রথমবার install করার জন্য internet দরকার; `START_FRONTEND.bat` lockfile bootstrap করে। তৈরি হওয়া `frontend/package-lock.json` GitHub-এ commit করুন, যাতে পরবর্তী install reproducible হয়।
4. যেকোনো test/build ব্যর্থ হলে সেটি ঠিক না করে production deploy করবেন না।

## এই পরিবেশে যাচাইয়ের সীমা

এই build environment-এ network/DNS বন্ধ থাকায় Flask ও frontend npm dependencies download করা যায়নি। তাই full backend test suite ও production Next.js build এখানে সফল বলে দাবি করা হয়নি। Dependency-free Python checks, Python syntax compilation, source-contract checks (যেখানে চালানো যায়), এবং archive integrity আলাদাভাবে রিপোর্ট করতে হবে। GitHub Actions-এ dependencies install হয়ে গেলে পূর্ণ suite চলবে এবং failure হলে workflow লাল হবে।

Live HTTPS/SSL, payment-provider credentials, external AI providers, production database, multi-host Redis/PostgreSQL behaviour এবং independent security review-এর জন্য আলাদা staging verification প্রয়োজন।
