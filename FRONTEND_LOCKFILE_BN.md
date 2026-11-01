# Frontend reproducible dependency lock (বাংলা)

`frontend/package-lock.json` এখন repository-তে committed এবং `package.json`-এর root dependency pin-এর সাথে মিলিয়ে `scripts/verify-lockfile.mjs` দিয়ে যাচাই করা হয়। Production build-এ সবসময় `npm ci` ব্যবহার করো — `npm install` নয়।

Frontend stack এখন security-patched line-এ আছে: Next.js 15.5.x (React 19) — পুরনো Next 14.2.x লাইনে প্রকাশিত critical/high advisories (React Server Components RCE/DoS series) এই সংস্করণে patched। PostCSS override (`^8.5.32`) transitive PostCSS advisories বন্ধ করে।

Local steps:

```bash
cd frontend
npm ci --no-audit --no-fund
node scripts/verify-lockfile.mjs
npm run build
```

Dependency update করলে:

```bash
cd frontend
npm install --no-audit --no-fund   # package-lock.json regenerate হয়
node scripts/verify-lockfile.mjs   # root pin মিল যাচাই
npm audit --omit=dev               # 0 vulnerabilities রাখার লক্ষ্য
npm run build
```

পরিবর্তিত `package-lock.json` commit করার আগে diff review করো।
