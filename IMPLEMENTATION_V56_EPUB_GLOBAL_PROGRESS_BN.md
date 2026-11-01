# LibraAI v56 — EPUB Global Progress Accuracy

## এই সংস্করণে
- v55-এর সব ফাইল ও পূর্ববর্তী ফিচার ধরে রাখা হয়েছে।
- EPUB.js-এর `locations.generate(1000)` দিয়ে বইজুড়ে CFI location index তৈরির ব্যবস্থা যোগ করা হয়েছে।
- index প্রস্তুত থাকলে current CFI থেকে `percentageFromCfi()` ব্যবহার করে book-wide reading percentage হিসাব করা হয়।
- index তৈরি না হওয়া পর্যন্ত current section-এর displayed page ratio fallback হিসেবে থাকে; UI-তে এটিকে section page হিসেবে label করা হয়েছে, পুরো বইয়ের page count হিসেবে নয়।
- EPUB পরিবর্তন হলে পুরোনো location index readiness state reset হয়।
- `test_epub_global_progress_v56.py`-এ global percentage, fallback ও state reset-এর contract tests যোগ হয়েছে।

## যাচাই
- Python compile check এবং নির্বাচিত reader/progress tests চালাতে হবে।
- এই পরিবেশে বাহ্যিক CDN-এ network access নেই; তাই বাস্তব EPUB ফাইল দিয়ে browser E2E এবং EPUB.js CDN availability যাচাই করা যায়নি।

## সীমাবদ্ধতা
- PDF.js ও EPUB.js এখনও CDN থেকে আসে; self-hosted vendor assets পরবর্তী কাজ।
- CFI position sync কার্যকর করতে EPUB.js script লোড হওয়া এবং API endpoint-এ access থাকা প্রয়োজন।
- Full production Next.js build/Flask runtime ও multi-device acceptance test এখনও প্রয়োজন।
