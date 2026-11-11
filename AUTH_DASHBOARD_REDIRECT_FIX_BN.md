# LibraAI Authentication Dashboard Redirect Fix

তারিখ: 2026-11-11

## সমস্যা
Sign up / Sign in API সফল হওয়ার পর Reader/Customer account-এর redirect `/` ছিল। Next.js authentication component-এর fallback-ও `/` ছিল। ফলে সফল authentication-এর পর ব্যবহারকারী unified `/dashboard` workspace-এ পৌঁছাতেন না।

## পরিবর্তন
- Flask `_workspace_for_role()` এখন সব authenticated role-এর জন্য `/dashboard` ফেরত দেয়।
- Next.js sign-in ও sign-up response-এ redirect অনুপস্থিত/অগ্রহণযোগ্য হলে fallback `/dashboard`।
- Role-based dashboard navigation অপরিবর্তিত; dashboard নিজেই Reader, Merchant, Admin ও Librarian workspace নির্ধারণ করে।
- Auth API contract regression test-এ signup/login redirect `/dashboard` assert যোগ করা হয়েছে।

## যাচাই
- `python -m py_compile app.py`: Passed
- Auth source-contract tests: 4/4 Passed
- Full Flask auth integration test: এই build environment-এ Flask dependency অনুপস্থিত থাকায় চালানো যায়নি।
- Next.js production build: এই patch-এ চালানো হয়নি।

## Deploy
এই ZIP দিয়ে existing project replace/merge করার আগে database ও `.env` backup নিন। Production `.env` ফাইল overwrite করবেন না। Frontend এবং Flask backend—দুটিই নতুন code দিয়ে rebuild/restart করতে হবে। Browser cache refresh করে sign up/sign in পরীক্ষা করুন।
