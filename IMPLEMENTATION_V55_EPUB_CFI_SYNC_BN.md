# LibraAI v55 — EPUB CFI Position Sync

## এই সংস্করণে
- v54-এর উপর ভিত্তি করে আগের feature ও UI files রাখা হয়েছে।
- EPUB-এর জন্য EPUB.js rendering path যোগ করা হয়েছে; EPUB CFI location restore ও relocated-event sync করা হয়।
- EPUB previous/next ও font-size controls যোগ করা হয়েছে।
- EPUB progress location-এর API truncation limit 300 থেকে 2000 characters করা হয়েছে, যাতে দীর্ঘ CFI কেটে না যায়।
- CDN/EPUB.js load ব্যর্থ হলে পুরোনো basic EPUB/CBZ reader path fallback হিসেবে রাখা হয়েছে।
- `test_epub_cfi_sync_v55.py`-এ CFI restore, save, navigation ও location length-এর contract tests যোগ করা হয়েছে।

## যাচাই
- `python -m compileall -q .` সফল।
- ২৩টি নির্বাচিত Python contract tests সফল।
- Reader inline JavaScript syntax check সফল।

## সীমাবদ্ধতা
- EPUB.js এবং PDF.js এখনও CDN থেকে লোড হয়; offline/self-hosted deployment-এর জন্য bundled assets যোগ করা দরকার।
- Testগুলো contract/static-level; বাস্তব EPUB নমুনা নিয়ে browser E2E এবং multi-device live sync এখনও চালানো হয়নি।
- সম্পূর্ণ Next.js production build ও full Flask runtime validation এই পরিবেশে করা হয়নি।
