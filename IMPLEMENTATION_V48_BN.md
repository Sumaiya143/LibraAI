# LibraAI v48 — Persistent Study Library and Bengali Study Tools

এই সংস্করণটি v47 থেকে তৈরি। আগের ডিজাইন, upload-security hardening, global language bridge এবং reader progress sync অক্ষুণ্ণ রেখে Study Tools workflow বাড়ানো হয়েছে।

## নতুন কাজ

- Study Tools থেকে তৈরি summary, quiz ও flashcards signed-in account-এ save করা যায়।
- Saved study set-এর তালিকা দেখা, আগের set খুলে দেখা এবং মুছে ফেলা যায়।
- নতুন `saved_study_sets` SQLite table account foreign key ও per-user query scope ব্যবহার করে। পুরোনো database-এ `init_db()` চালু হলে table তৈরি হয়।
- API routes: `POST /api/study-tools` (optional `save: true`), `GET /api/study-tools/saved`, `GET /api/study-tools/saved/<id>`, `DELETE /api/study-tools/saved/<id>`। Mutation requests-এর জন্য বিদ্যমান CSRF middleware প্রযোজ্য।
- Local extractive study generator এখন বাংলা Unicode শব্দ ও `।` বাক্য-সমাপ্তি চিনতে পারে; ইংরেজি workflow-ও রাখা হয়েছে।
- Input length bounds এবং saved JSON size limit বহাল আছে।

## যাচাই

- `python -m py_compile app.py study_tools.py test_saved_study_sets_contract.py` — passed
- `python -m unittest test_saved_study_sets_contract test_reader_progress_sync_contract -v` — 8 tests passed
- Frontend static checks — language bridge, client enhancements, page shell, live integration contracts, security headers — passed
- Flask runtime integration tests and Next.js production build were not run in this environment: Flask and frontend `node_modules` are not installed. Static checks do not establish live-provider acceptance.

## এখনও বাকি

- প্রকৃত PDF/EPUB engine-এ page/CFI-ভিত্তিক cross-device progress sync
- Connected generative AI provider দিয়ে grounded chapter summary ও quiz generation (বর্তমান study generator extractive heuristic)
- Full unit/integration/browser E2E suite and production Next.js build
- Full human-reviewed Bangla localization of all route content, backend errors and generated content
- Production distributed caching, live scanner verification, and backup/restore acceptance
