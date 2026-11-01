# LibraAI v59 — Extended Verification (বাংলা)

এই প্যাকেজে চারটি আলাদা verification পথ দেওয়া হয়েছে। এগুলো **পরীক্ষা চালানোর ব্যবস্থা**; এগুলো নিজে থেকে production certification নয়।

## 1) Full backend test suite
Windows: `VERIFY_PROJECT.bat` চালান। Linux/macOS: `python -m pip install -r requirements.txt` তারপর `python verify_full_test_suite.py`। Dependency install ব্যর্থ হলে suite শুরু হয়েছে বা pass করেছে—এমন দাবি করবেন না।

## 2) SQLite backup/restore rehearsal
প্রথমে local test database-এ চালান: `python backup_restore_drill.py --db path/to/test.db`। এটি disposable backup/restore করে source অপরিবর্তিত রাখার চেষ্টা যাচাই করে। Production database-এ চালানোর আগে backup policy, encryption, permissions এবং maintenance window review করুন। PostgreSQL/MySQL হলে তাদের নিজস্ব dump/restore এবং staging recovery test আলাদা করে লাগবে।

## 3) External APIs/payment
`python external_integration_preflight.py` provider configuration, endpoint reachability ও required environment variables রিপোর্ট করে; payment নেয় না। Real provider API test করতে sandbox credentials, provider dashboard setup এবং public HTTPS callback URL লাগবে। `RUN_OPENAI_LIVE_TEST=1` দিলে configured AI API-তে একটি ছোট billable request পাঠাতে পারে। কোনো live payment স্বয়ংক্রিয়ভাবে চালানো হয় না।

## 4) Security review
`python security_review.py` repository-র কিছু risky pattern/secret exposure এবং available dependency scanners পরীক্ষা করে। এটি independent penetration test, threat model review, manual code audit বা compliance certification-এর বিকল্প নয়। External auditor-কে আলাদা করে নিয়োগ/অনুমোদন করতে হবে।

## Handover acceptance gate
- `VERIFY_PROJECT.bat` সব ধাপে pass
- GitHub Actions CI green
- staging DB-তে backup → restore → row/schema validation pass
- provider sandbox test successful, callback/signature/amount/idempotency যাচাই
- security review report, findings remediation ও retest complete
- production secrets client-এর নিজস্ব secret manager-এ; GitHub repo-তে নয়

Hosting/domain এখন না কিনলেও local ও CI verification করা যায়; real public callbacks, production TLS, live payment settlement এবং production-scale restore/availability যাচাই করতে staging/public endpoint ও provider credentials লাগতে পারে।
