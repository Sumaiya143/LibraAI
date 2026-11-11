# LibraAI Admin Account Setup (বাংলা)

এই রিলিজে কোনো hard-coded/default admin username বা password রাখা হয়নি। নিরাপত্তার জন্য প্রথম administrator নিজে bootstrap করতে হবে; password database-এ salted PBKDF2 hash হিসেবে সংরক্ষিত হয়।

1. Python backend-এর virtual environment সক্রিয় করুন এবং প্রয়োজনীয় dependencies install করুন।
2. Database schema initialize/migrate করুন।
3. Database-এর absolute path দিয়ে `LIBRAAI_DB_PATH` সেট করুন।
4. প্রজেক্ট root থেকে চালান:

   ```bash
   # Windows PowerShell
   $env:LIBRAAI_DB_PATH = "C:\absolute\path\to\libraai.db"
   python bootstrap_admin.py

   # Linux / macOS
   export LIBRAAI_DB_PATH="/absolute/path/to/libraai.db"
   python bootstrap_admin.py
   ```

5. Prompt-এ administrator name, username, email এবং অন্তত 12 অক্ষরের password দিন। Password terminal-এ echo হবে না।
6. এরপর `/login` থেকে সেই username/email ও password দিয়ে sign in করুন।

একটি admin account আগে থেকেই থাকলে bootstrap script দ্বিতীয় admin তৈরি করতে অস্বীকার করবে। Password ভুলে গেলে production-approved password reset workflow ব্যবহার করুন; source code বা ZIP-এ কোনো shared credential রাখা হয়নি।

## Manga seller upload

Seller Workspace → Upload & Edit Products → Upload New Product থেকে `Manga` অথবা `Comics` category নির্বাচন করে title, description, cover image, price, stock ও প্রয়োজনীয় metadata দিন। Listing review/publish policy অনুযায়ী catalog-এ আসবে। Manga browse page-এ live catalog খালি থাকলে দেখানো 10টি starter title কেবল sample/demo metadata; এগুলো বিক্রয়যোগ্য licensed inventory নয়।
