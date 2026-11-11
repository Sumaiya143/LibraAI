# LibraAI — স্থানীয় যাচাই প্রতিবেদন

এই ZIP প্রস্তুতের সময় যেসব যাচাই বাস্তবে চালানো হয়েছে:

- Python source compilation: সফল
- Backend-independent portability, environment-template ও production-preflight tests: ৩৭/৩৭ সফল
- Frontend source-contract scripts: সবগুলো সফল
- Frontend lockfile/package manifest consistency: সফল
- Release ZIP hygiene (`buyer_preflight.py`): সফল
- Bash launcher syntax: যাচাই করা হয়েছে

## এই পরিবেশে যেগুলো সম্পূর্ণ চালানো যায়নি

এই build environment-এ নেটওয়ার্ক/DNS বন্ধ থাকায় Flask/Werkzeug dependencies `pip` দিয়ে ইনস্টল করা যায়নি এবং npm cache-এ সব package ছিল না। তাই পূর্ণ Flask integration/unit suite, Next.js production build, live HTTP/API smoke test এবং browser E2E test চালানো সম্ভব হয়নি। এগুলোকে সফল বলে দাবি করা হচ্ছে না।

## নিজের PC বা GitHub Actions-এ সম্পূর্ণ যাচাই

প্রয়োজন: Python 3.12+, Node.js 20+, npm এবং প্রথমবার dependency install-এর জন্য internet access।

- Windows: `VERIFY_PROJECT.bat`
- macOS/Linux: `./VERIFY_PROJECT.sh`
- Local app start (macOS/Linux): `./start-dev-unix.sh`
- Local app start (Windows): `START_LIBRAAI.bat`

সম্পূর্ণ verification/build ব্যর্থ হলে সেটি ঠিক না করা পর্যন্ত deploy করবেন না। Production SSL certificate, database backup/restore, live payment provider, content licensing ও independent security review আলাদা production sign-off-এর বিষয়।
