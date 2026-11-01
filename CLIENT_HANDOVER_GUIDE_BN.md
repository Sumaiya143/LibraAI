# LibraAI — Client Handover Guide (বাংলা)

এই package-টি **source-code handover ও local verification**-এর জন্য। এটি live hosting, domain, SSL certificate, payment merchant approval বা third-party API credentials অন্তর্ভুক্ত করে না। এগুলো client-এর deployment phase-এ configure করতে হবে। কোনো check pass করলেই production security certification বোঝায় না।

## ১. Client-এর PC-তে চালানো

### প্রয়োজনীয় সফটওয়্যার
- Windows 10/11 (বা সমতুল্য macOS/Linux environment)
- Python 3.12+, Node.js 20+ এবং npm
- Dependency install-এর সময় internet access

### প্রথমবার চালানো
1. ZIP extract করে `LibraAI` folder খুলুন।
2. `START_LIBRAAI.bat` চালান; backend ও frontend আলাদা terminal-এ চালু হবে।
3. Browser-এ `http://localhost:3000` খুলুন। Backend সাধারণত `http://127.0.0.1:5000`-এ চলে।
4. দুই terminal খোলা রাখুন। বন্ধ করলে server বন্ধ হবে।
5. এরপর `VERIFY_PROJECT.bat` চালিয়ে strict verification শেষ করুন। কোনো ধাপ fail/incomplete হলে সেটিকে success হিসেবে ধরে নেবেন না।

## ২. GitHub-এ handover

1. ZIP extract করে project-এর source files GitHub repository-তে upload/commit করুন।
2. `.env`, database, uploads, backups, API keys, private certificates বা customer data কখনো commit করবেন না। `.env.example` এবং `.env.production.example` কেবল template।
3. প্রথমবার frontend dependency install-এর পর `frontend/package-lock.json` তৈরি হলে সেটি commit করুন; root-এর `package-lock.json` frontend lockfile-এর বিকল্প নয়।
4. GitHub Actions-এর required checks green হওয়া পর্যন্ত merge/release অনুমোদন করবেন না। CI green না হলে বা dependency download না হলে সেটিকে verified বলা যাবে না।
5. Client-কে repo access, required software versions, এই guide এবং verification report handover করুন। Secrets আলাদা secure channel-এ client নিজে সেট করবে।

## ৩. Database, backup ও deployment

- Local default database SQLite; single-host/local handover-এর জন্য। Container ব্যবহার করলে `/data` persistent volume হিসেবে mount করতে হবে, নইলে container recreate করলে data হারানোর ঝুঁকি আছে।
- একাধিক app instance/host চালাতে হলে শুধু Redis যোগ করলেই হবে না: primary database PostgreSQL-এ migrate করে concurrency, migration, backup/restore এবং failover পরীক্ষা করতে হবে।
- Client production-এ যাওয়ার আগে backup তৈরি এবং clean environment-এ restore drill সফলভাবে চালাবে। Backup file source repository-তে রাখা যাবে না।

## ৪. SSL ও security boundary

- `Caddyfile` HTTPS reverse-proxy configuration template; real domain-এর DNS, inbound ports, valid certificate issuance/renewal এবং external TLS scan এখানে live-এ পরীক্ষা করা হয়নি।
- `.env.production.example` কপি করে deployment secrets-এর মাধ্যমে unique `SECRET_KEY`, public HTTPS URL, persistent database path এবং প্রয়োজনীয় provider config দিন। Example placeholder 그대로 ব্যবহার করবেন না।
- Production deployment-এর আগে `python production_preflight.py --strict` চালান। এটি configuration audit; live SSL, API behavior বা security penetration test নয়।
- Upload scanning, storage provider, email/AI, payment, social login বা payout feature-এর জন্য সংশ্লিষ্ট provider credentials ও staging E2E test প্রয়োজন হতে পারে। Credentials না থাকলে সেই integration-কে live-verified বলা যাবে না।
- Payment sandbox থেকে live mode-এ পরিবর্তন করার আগে merchant approval, callback/signature verification, refund/reconciliation এবং বাস্তব low-value transaction test client-এর দায়িত্বে সম্পন্ন করতে হবে।

## ৫. Handover acceptance checklist

- [ ] Clean PC-তে dependency setup সফল
- [ ] `START_LIBRAAI.bat` দিয়ে frontend ও backend চালু
- [ ] Login/registration, session, CSRF এবং authorization flows পরীক্ষা
- [ ] Core API integration tests ও full backend test suite pass; unexplained skips নেই
- [ ] Frontend `npm ci` এবং `npm run build` pass
- [ ] Browser E2E এবং supported browsers/devices পরীক্ষা
- [ ] Database backup/restore drill pass
- [ ] Production secrets, HTTPS, headers, CORS/cookies, rate limits যাচাই
- [ ] AI, storage, email, payment ও payout-এর configured integrations staging-এ E2E pass
- [ ] Independent security review এবং client acceptance sign-off সম্পন্ন

## ৬. বর্তমান যাচাইয়ের সীমা

এই release-এর offline source/configuration checks ও নির্বাচিত automated tests চালানো হয়েছে। এই execution environment-এ dependency registry/network unavailable থাকায় full backend dependency-based suite এবং Next.js production build সফলভাবে চালিয়ে নিশ্চিত করা যায়নি। Real SSL, production database, external API credentials, payment providers, multi-instance deployment এবং independent security audit-ও এখানে যাচাই করা হয়নি। তাই এই deliverable-কে **handover candidate** হিসেবে দেখুন, certified/fully production-verified release হিসেবে নয়। উপরোক্ত acceptance checklist-এর সব প্রাসঙ্গিক item pass না হওয়া পর্যন্ত “100% error-free” বা “production-ready verified” দাবি করবেন না।
