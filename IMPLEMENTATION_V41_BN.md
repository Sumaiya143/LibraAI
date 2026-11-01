# LibraAI v41 — project cleanup and local developer experience

## এই release-এ কী বদলেছে

- `START_LIBRAAI.bat` দুইটি আলাদা terminal-এ backend ও frontend চালু করে; চাইলে `START_BACKEND.bat` এবং `START_FRONTEND.bat` আলাদাভাবে চালানো যায়।
- Backend startup script isolated `.venv` তৈরি করে, `requirements.txt` থেকে dependencies install করে এবং app চালুর আগে diagnostics চালায়।
- Frontend startup script Node/npm যাচাই করে; lockfile থাকলে `npm ci`, না থাকলে স্পষ্ট warning দিয়ে `npm install` ব্যবহার করে।
- `project_doctor.py` প্রয়োজনীয় source files, Python packages, Node/npm ও frontend lockfile status যাচাই করে। এটি secret values print করে না।
- `verify_handover.py` এখন default-এ শুধু stdout-এ report দেখায়; generated JSON file release ZIP-এ রাখা হয় না। `--output path.json` দিলে report আলাদাভাবে সংরক্ষণ করা যায়।
- পুরোনো version changelog, stale handover reports, duplicate readiness notes এবং একটি empty temporary file সরানো হয়েছে। বর্তমান operational docs ও feature implementation code রাখা হয়েছে।
- `.gitignore`-এ Next.js build output, `node_modules`, Playwright results এবং coverage artifact যোগ করা হয়েছে।

## যাচাই

- `project_doctor.py`-এর unit tests যোগ করা হয়েছে।
- সব Python source-এর AST syntax check ও focused tests চালানো হবে release package তৈরির সময়।
- ZIP-এ `.env`, database, credentials, `.venv`, `node_modules`, `.next`, cache বা generated browser reports রাখা উচিত নয়; `buyer_preflight.py` handover safety gate হিসেবে রয়ে গেছে।

## জানা সীমাবদ্ধতা

- `frontend/package-lock.json` এখনো নেই, কারণ package registry access ছাড়া authentic transitive dependency lockfile তৈরি করা যায়নি। Frontend install সম্পূর্ণ reproducible নয়।
- এই environment-এ Flask/Werkzeug/Redis dependencies অনুপস্থিত এবং internet access সীমিত থাকায় সম্পূর্ণ backend runtime suite, Next.js build এবং real Playwright browser tests পুনরায় চালানো যায়নি।
- `project_doctor.py` prerequisite diagnostic; এটি live payments, provider credentials, content rights, deployment security বা production readiness certify করে না।
