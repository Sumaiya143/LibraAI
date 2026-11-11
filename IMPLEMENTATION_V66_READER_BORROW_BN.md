# V66 — Premium Reader ও বাস্তব Borrowing System

## Reader
- `/reader/<book_id>` এখন placeholder/sample text দেখায় না; rights-aware `/reader-plus/<book_id>`-এ পাঠায়।
- কেবল active, rights-verified public sample অথবা verified purchase/active library loan-এ অনুমোদিত licensed eBook content দেখা যায়। Expired, suspended, revoked, territory-mismatched বা unsupported-format content fail-closed থাকে।
- Page-turn এবং continuous layout, previous/next, keyboard navigation, font size, comfortable spacing, high contrast, dark paper, auto-scroll speed এবং browser text-to-speech যোগ করা হয়েছে।
- Active licensed audiobook এবং access থাকলে official audio player দেখায়; না থাকলে browser narration থাকে।
- Reader progress server API-তে CSRF token সহ sync হয়; preferences local device-এ persist করে। Signed-in reader-এর private annotation UI বজায় আছে।

## Borrowing
- Retail sales stock থেকে আলাদা `library_inventory` table যোগ হয়েছে; পুরোনো catalog `books.stock` একবার initial library-copy seed হিসেবে ব্যবহৃত হয়।
- Borrow transaction `BEGIN IMMEDIATE`-এ atomic; stock decrement এবং loan creation একই transaction-এ হয়।
- ১৪ দিনের loan, প্রতি user-এ সর্বোচ্চ ৫টি active loan, একই বইয়ের duplicate active loan block, overdue renewal block, সর্বোচ্চ একবার renewal, return-এর সময় inventory restore এবং legacy branch inventory backfill আছে।
- My Library-তে active borrowed বই Read করা যায়। Book Store listing ও detail page থেকে borrow করা যায়।
- Admin Dashboard থেকে Circulation Inventory পেজে branch-wise library copies manage করা যায়; already checked-out copy বাদ দিয়ে total copy কমানো যায় না।
- Borrow/renew/return POST actions login এবং global CSRF validation-এর অধীনে; member loan ownership এবং librarian branch assignment checks বজায় আছে।

## Security ও verification
- Existing CSP/security headers, production HSTS, secure production session-cookie defaults, CSRF, private ebook storage এবং SHA-256 integrity delivery অক্ষত রাখা হয়েছে।
- নতুন lending, rights-policy, reader controls, progress, audiobook, database migration, database lifecycle, payment-integrity, upload-security এবং API-hardening tests চালানো হয়েছে।
- Flask dependency sandbox-এ install করা না থাকায় Flask app-এর live route/browser integration test চালানো যায়নি। বাস্তব production SSL certificate/HTTPS endpoint এই local ZIP environment থেকে যাচাই করা যায় না; deployment domain-এ আলাদা TLS probe প্রয়োজন।
