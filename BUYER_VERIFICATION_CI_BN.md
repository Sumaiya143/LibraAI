# LibraAI — Buyer Verification CI-এর সীমা

**CI green মানে live-market certification নয়।** এটি source-level checks, automated tests এবং CI environment-এ চালানো acceptance checks সফল হওয়ার প্রমাণ মাত্র।

Production launch-এর আগে আলাদাভাবে যাচাই করতে হবে:

- বাস্তব deployment environment-এ database, persistent session store, backup এবং restore drill;
- অনুমোদিত AI provider credentials দিয়ে end-to-end RAG/AI request এবং failure handling;
- payment gateway-এর sandbox transaction, signature validation, idempotency, refund/void এবং webhook replay;
- প্রতিটি বই, eBook, audiobook, manga/comic, cover ও excerpt-এর প্রয়োজনীয় distribution/licensing rights;
- বাস্তব domain-এ HTTPS, secure cookies, secret management, monitoring, rate limits এবং security review;
- mobile/desktop browser QA, accessibility checks এবং regression tests;
- কোনো required test skip হলে তার কারণ সমাধান করে supported environment-এ পুনরায় চালানো। Platform-specific symlink tests unsupported OS-এ skip হতে পারে; এগুলোকে passing test হিসেবে গণ্য করা যাবে না।

Live provider credentials, domain/DNS access, licensing documents এবং production infrastructure ছাড়া এই items-কে verified বা production-ready বলা যাবে না।
