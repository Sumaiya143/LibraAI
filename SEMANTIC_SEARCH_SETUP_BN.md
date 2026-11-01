# LibraAI Semantic Search Setup (বাংলা)

## কী যোগ হয়েছে
- `POST /api/search/semantic` API; Next.js থেকে `/backend/api/search/semantic` দিয়ে ব্যবহার হবে।
- Catalog-এর title, author, genre, description, language, format ও ISBN-কে search evidence হিসেবে ব্যবহার করে ranking।
- External embedding provider configured থাকলে OpenAI-compatible `/embeddings` API দিয়ে semantic similarity ranking।
- Book embedding cache SQLite-তে রাখা হয়; বইয়ের metadata বদলালে fingerprint বদলে embedding পুনরায় তৈরি হয়।
- Provider key অনুপস্থিত, timeout বা provider/cache error হলে local concept-aware ranking fallback হয়।
- Chatbot-এর catalog recommendation-ও একই ranker ব্যবহার করে; catalog-এর বাইরের বই বানিয়ে দেখায় না।
- Public search endpoint-এর প্রতি client IP-তে 60 সেকেন্ডে 30 request limit; raw IP নয়, keyed digest সংরক্ষণ হয়।

## External semantic mode চালু করা
`.env` / deployment environment-এ server-side variables দিন:

```dotenv
LIBRAAI_EMBEDDINGS_API_KEY=your_provider_key
LIBRAAI_EMBEDDINGS_BASE_URL=https://api.openai.com/v1
LIBRAAI_EMBEDDINGS_MODEL=text-embedding-3-small
LIBRAAI_SEMANTIC_MAX_BOOKS=150
```

`OPENAI_API_KEY`-ও key fallback হিসেবে পড়া হয়। Key কখনো frontend environment variable (`NEXT_PUBLIC_*`) হিসেবে দেবেন না। Backend restart করুন। সফল external ranking response-এ `mode: external_embeddings`; fallback-এ `mode: local_semantic_fallback` থাকবে। প্রথমবার catalog embedding তৈরির জন্য provider usage/cost হতে পারে। Catalog limit configurable, default 150 books.

## পরীক্ষা

```bash
python -m unittest -v test_semantic_search.py
python -m py_compile app.py semantic_search.py
cd frontend && node scripts/verify-live-integration-contracts.mjs
```

## Payment gateway status
Checkout UI ও existing provider integration code রাখা হয়েছে, কিন্তু live bKash/Nagad/SSLCommerz/card transactions চালু/verify করা হয়নি: merchant account credentials, provider callback URLs এবং live/sandbox transaction approval প্রয়োজন। Credentials ছাড়া production payment enable করা নিরাপদ নয়।
