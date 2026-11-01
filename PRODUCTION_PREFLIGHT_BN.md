# LibraAI v37 — Production preflight ও launch blocker audit

## কী যোগ হয়েছে

- `production_preflight.py`: production configuration-এর জন্য secret-free, repeatable audit report।
- `test_production_preflight.py`: ১৮টি focused policy test—weak/placeholder secret, debug mode, HTTP URL, relative database path, payment credential/flag mismatch, private storage, rights attestation, security review, backup/restore, AI optionality এবং creator payout dependency।
- Full release GitHub Actions workflow-এ preflight report ও focused tests যুক্ত হয়েছে।

## চালানোর নিয়ম

```bash
python production_preflight.py
python production_preflight.py --strict
python -m unittest -v test_production_preflight.py
```

- সাধারণ report command findings দেখাবে এবং external setup blocker থাকলেও report তৈরি করবে।
- `--strict` blocker বা external dependency থাকলে non-zero exit code দেবে।
- `--production-only` দিলে `LIBRAAI_ENV=production` না হলে fail করবে।
- রিপোর্টে credential values প্রকাশ করা হয় না।

## Preflight কী পরীক্ষা করে

1. `SECRET_KEY`-এর ন্যূনতম দৈর্ঘ্য ও placeholder pattern।
2. Debug mode বন্ধ কি না।
3. Canonical public HTTPS URL।
4. Absolute database path—persistent volume সত্যিই durable কি না, সেটি আলাদা করে যাচাই করতে হবে।
5. Payment credentials, sandbox flags এবং operator-verified E2E flags একসাথে আছে কি না।
6. Private S3/MinIO object storage-এর configuration।
7. Publisher/content-rights attestation flags।
8. Independent security review এবং backup-restore drill-এর attestation flags।
9. Creator payout provider configuration আছে কি না; না থাকলে external dependency দেখায়।
10. External AI key configured কি না; না থাকলে optional হিসেবে দেখায়।

## গুরুত্বপূর্ণ নিরাপত্তা ও সত্যতা সীমা

এই স্ক্রিপ্ট **configuration-only audit**। কোনো environment variable, এমনকি `..._VERIFIED=yes`, নিজে থেকে প্রমাণ করে না যে live transaction সফল, legal licence বৈধ, backup restore হয়েছে বা penetration test পাস হয়েছে। Operator-কে evidence, provider dashboard references, test logs, contracts ও independent report আলাদা করে সংরক্ষণ করতে হবে।

Creator payout-এর জন্য approved disbursement provider, credentials, signed webhook validation, idempotency, reconciliation, failure/retry handling এবং বাস্তব sandbox/live transfer test এখনো প্রয়োজন। Payment provider-এর অনুমোদন ও credentials ছাড়া এই অংশ বাস্তবে সম্পন্ন করা যায় না।

## এখনো বাহ্যিকভাবে করতে হবে

- Merchant/provider approval ও sandbox/live transaction verification.
- Publisher/author agreements-এর legal review.
- Production hosting, durable DB/object storage, monitoring ও restore drill.
- Independent penetration test এবং remediation evidence.
- Full browser E2E, accessibility, performance/load এবং disaster-recovery acceptance.

**Release সিদ্ধান্ত:** preflight report-কে launch approval হিসেবে ব্যবহার করা যাবে না। CI-তে test সফল হওয়া এবং live operational evidence—দুটিই দরকার।


## v38 environment-template correction

- `.env.example` এখন শুধু local development-এর জন্য; duplicate/conflicting environment key সরানো হয়েছে।
- `.env.production.example` আলাদা production-shaped template। এটিও সরাসরি ব্যবহারযোগ্য production secret নয়—সব placeholder বদলাতে হবে।
- Single-host deployment-এর জন্য SQLite sessions default. Shared Redis sessions ও atomic rate limiting optional ভাবে implemented; multi-instance চালানোর আগে `REDIS_URL=rediss://...`, `LIBRAAI_SESSION_BACKEND=redis`, `LIBRAAI_RATE_LIMIT_BACKEND=redis` এবং `LIBRAAI_MULTI_INSTANCE=yes` configure করতে হবে. Main app database এখনও SQLite, তাই PostgreSQL migration না হওয়া পর্যন্ত multi-host production blocked থাকবে.
- Preflight এখন malformed HTTPS origin, canonical/legacy URL mismatch এবং missing/unsupported session backend-ও block করে।
