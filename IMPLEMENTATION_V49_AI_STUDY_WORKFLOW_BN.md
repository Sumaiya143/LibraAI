# LibraAI v49 — AI Study Workflow (বাংলা নোট)

## কী যোগ হয়েছে
- Study Tools এখন optional OpenAI-compatible chat-completions provider ব্যবহার করে summary, keywords, quiz এবং flashcards তৈরি করতে পারে।
- Provider configuration পাওয়া গেলে `LIBRAAI_LLM_*` variables ব্যবহার করা হয়; `OPENAI_API_KEY`/`OPENAI_MODEL` fallback-ও সমর্থিত।
- Provider output JSON হিসেবে parse এবং schema/field-size/count সীমা দিয়ে validate করা হয়। Invalid response, timeout বা provider error হলে local extractive generator চালু থাকে।
- Result-এর `mode` field (`ai-assisted` অথবা `local-extractive`) ও notice UI-তে দেখানো হয়, যাতে local heuristic output-কে AI-generated বলে ভুল না হয়।
- Bengali এবং English source text workflow আগের মতোই সমর্থিত; saved study library-র API/UX অপরিবর্তিত রাখা হয়েছে।
- Provider call কেবল server-side configuration থাকলেই হয়; API key browser-এ পাঠানো হয় না।

## Configuration
Production environment-এ `.env.example`-এর বিদ্যমান values configure করুন:

```env
LIBRAAI_LLM_API_KEY=your-server-side-provider-key
LIBRAAI_LLM_BASE_URL=https://api.openai.com/v1
LIBRAAI_LLM_MODEL=gpt-4o-mini
```

Provider configured থাকলে submitted chapter text ওই provider-এ পাঠানো হবে। ব্যবহারকারীর অনুমোদিত text-ই submit করুন। Key কখনো frontend environment variable বা client bundle-এ রাখবেন না। HTTPS endpoint ছাড়া production provider call চালু হয় না।

## Verification
- `python -m py_compile study_tools.py app.py`
- `python -m compileall -q .`
- Targeted suite: 21 tests passed (AI study workflow, existing study tools, saved study library, upload security, reader progress contracts)
- Frontend static checks passed: language bridge, client enhancements, page shell, live-integration contracts, security headers.

## সীমাবদ্ধতা
- এটি optional AI provider integration; provider credentials/billing/configuration ছাড়া local heuristic fallback চলবে।
- Tests mock provider response; live external-provider acceptance test চালানো হয়নি।
- Full Next.js production build এবং Flask runtime integration এই environment-এ যাচাই করা হয়নি।
