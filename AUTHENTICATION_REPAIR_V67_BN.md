# LibraAI Authentication Repair v67

## কী ঠিক করা হয়েছে

- Production Flask app-এ `/api/signup`, `/api/login`, `/api/me`, `/api/logout` এবং `/api/csrf` JSON endpoints যোগ করা হয়েছে; `/api/auth/*` aliases-ও রয়েছে।
- JSON POST-এর আগে same-origin CSRF token বাধ্যতামূলক। Account page প্রথমে `/api/csrf` নেয় এবং প্রতিটি POST-এ `X-CSRF-Token` পাঠায়।
- Sign in-এ username, email অথবা username/email field-এর accepted aliases দিয়ে login করা যায়। Email lookup case-insensitive।
- Public signup-এ customer/reader এবং merchant/seller role গ্রহণ করা হয়; public admin signup প্রত্যাখ্যান করা হয়।
- Signup-এর পর নতুন account-এ authenticated server-side session তৈরি হয়। Role অনুযায়ী reader `/`, seller `/creator`, admin `/admin/dashboard`, librarian `/librarian`-এ যায়।
- Username optional; না দিলে নাম বা email local-part থেকে username তৈরি হয়। একই নামের account-এর username collision হলে numeric suffix দেওয়া হয়।
- Email ও username duplicate check, case-insensitive email unique index (legacy duplicate থাকলে account data না মুছে index skip), password length/type validation, generic credential errors এবং existing login/signup throttling বজায় রাখা হয়েছে।
- Login/signup-এর পর session rotate হয়; credential fingerprint, idle timeout, absolute timeout এবং server-side session storage বজায় থাকে।
- `/account`, `/account.html`, `/account.js`, `/account.css` compatibility routes যোগ করা হয়েছে।

## Password ও account policy

- New password: 12–128 characters.
- Public account roles: Customer/Reader এবং Seller/Merchant.
- Admin account কেবল existing administrator provisioning flow বা bootstrap procedure দিয়ে তৈরি করতে হবে।
- Login: username অথবা email + password.

## Local run

Windows: `START_BACKEND.bat` চালাও। এটি `.venv` তৈরি করে `requirements.txt` install করে, diagnostics চালায় এবং Flask app শুরু করে।

Manual:

```bash
python -m pip install -r requirements.txt
python app.py
```

## Production deployment requirements

- `LIBRAAI_ENV=production`
- Unique random `SECRET_KEY` (কমপক্ষে 32 characters; source control-এ রাখবে না)
- Absolute persistent `LIBRAAI_DB_PATH`
- HTTPS reverse proxy এবং `SESSION_COOKIE_SECURE` production setting
- Production preflight, database backup এবং restore rehearsal
- Multi-instance deployment-এর আগে SQLite application database PostgreSQL-এ migrate করতে হবে; শুধু Redis sessions সেট করলেই multi-host database safety নিশ্চিত হয় না।

## Verification status in this build environment

Python syntax checks, browser JavaScript syntax check, pure account-registration tests, login-throttle tests এবং session-lifecycle tests run করা হয়েছে। Flask runtime dependency এই environment-এ অনুপস্থিত এবং package index/DNS access blocked ছিল; তাই নতুন Flask test-client end-to-end tests এখানে execute করা যায়নি। Production browser/API test-কে passed বলা হয়নি।
