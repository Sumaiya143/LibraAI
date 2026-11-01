# LibraAI v47 — Global Bangla UI Translation Layer

এই release-এ v46-এর upload security hardening, v45 reader progress sync এবং পূর্ববর্তী UI/layout অপরিবর্তিত রেখে global language bridge যোগ করা হয়েছে।

## কী যোগ হয়েছে
- `frontend/components/LanguageBridge.tsx`: global English ↔ Bangla phrase dictionary এবং UI text/placeholder/title/aria-label translation.
- `frontend/app/layout.tsx`-এ bridge mount করা হয়েছে, তাই বিদ্যমান page shell ও routes অপরিবর্তিত থাকে।
- বিদ্যমান header language toggle (`libraai-language`) ব্যবহার করে অনুবাদ পরিবর্তন; `libraai-language` localStorage preference থেকে initial language restore.
- `MutationObserver` dynamic content-এও dictionary translation প্রয়োগ করে। Script/style/code/input value ইত্যাদি বাদ দেওয়া হয়েছে।
- `frontend/scripts/verify-language-bridge.mjs` এবং `verify:language-bridge` npm script যোগ করা হয়েছে।

## যাচাই
- `node scripts/verify-language-bridge.mjs` — passed.
- Existing frontend contract scripts (client enhancements, page shell, live integration contracts, security headers) — passed.
- Python compile checks — passed.
- Upload security ও reader progress contract tests — 8 passed.

## গুরুত্বপূর্ণ সীমাবদ্ধতা
এটি global phrase-based UI translation layer, সম্পূর্ণ পেশাদার human-reviewed website localization নয়। যেসব unique long-form paragraphs, catalog data, publisher-uploaded content, server-rendered emails/PDFs বা backend validation messages dictionary-তে নেই, সেগুলো ইংরেজিতে থাকতে পারে। সম্পূর্ণ অনুবাদের জন্য প্রতিটি route-এর content ও backend messages-কে explicit locale dictionaries-এ স্থানান্তর, native Bangla proofreading এবং accessibility review প্রয়োজন।

Production Next.js build এবং full browser E2E test এই environment-এ চালানো হয়নি; dependencies/lockfile অনুপস্থিত থাকায় production readiness নিশ্চিত করা যাচ্ছে না।
