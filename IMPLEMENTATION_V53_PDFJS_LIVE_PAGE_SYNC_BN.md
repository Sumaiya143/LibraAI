# LibraAI v53 — PDF.js Live Page Sync (বাংলা)

## কী যোগ হয়েছে
- PDF-এর browser-native iframe-only view-এর বদলে PDF.js canvas reader ব্যবহার করা হয়েছে; PDF.js CDN অনুপলব্ধ হলে browser-native fallback থাকে।
- PDF পৃষ্ঠা সংখ্যা ডকুমেন্ট থেকে পড়া হয় এবং input-এর সর্বোচ্চ সীমা প্রকৃত page count দিয়ে নিয়ন্ত্রিত হয়।
- Previous/Next, নির্দিষ্ট পৃষ্ঠায় যাওয়া এবং Zoom controls যোগ করা হয়েছে।
- প্রতিটি PDF page render সফল হলে account-scoped progress API-তে file ID, zero-based page index, percentage ও location সংরক্ষণ করা হয়।
- Saved progress-এ PDF থাকলে সেটি স্বয়ংক্রিয়ভাবে restore করার ব্যবস্থা যোগ হয়েছে।
- আগের EPUB/CBZ page-index sync, audiobook timestamp sync, study tools ও upload security অক্ষুণ্ণ রাখা হয়েছে।

## যাচাই
- Python compileall সফল।
- নির্বাচিত 29টি Python test সফল (reader/PDF sync, study tools, saved study sets, upload security অন্তর্ভুক্ত)।
- Reader inline JavaScript `node --check` সফল।
- Frontend client enhancement, page-shell, live integration contract, security header ও language bridge static checks সফল।
- এগুলো static/contract checks; live browser, real PDF files, CDN availability এবং production deployment-এ end-to-end acceptance test চালানো হয়নি।

## সীমাবদ্ধতা
- PDF.js client CDN-এ নির্ভরশীল; CDN লোড না হলে native viewer fallback চালু হয়, কিন্তু fallback-এ page changes auto-detect হয় না। Production-এ PDF.js library/worker self-host করা উত্তম।
- EPUB এখনও full EPUB.js/CFI spine location নয়; বর্তমান simplified page-index behaviour বহাল।
- Full Next.js production build, Flask live runtime, full browser E2E, complete Bangla localization, distributed caching এবং backup/restore-এর production acceptance বাকি।
