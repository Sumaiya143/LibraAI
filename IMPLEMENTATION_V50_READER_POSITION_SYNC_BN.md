# LibraAI v50 — Reader Position Sync (বাংলা নোট)

## কী যোগ হয়েছে
- Legacy `reading_progress` table-এর জন্য non-destructive schema migration: `page`, `location`, `file_id` column অনুপস্থিত থাকলে যোগ হয়; বিদ্যমান `percent` data অক্ষত থাকে।
- `/api/extra/progress?book_id=...` এখন signed-in ব্যবহারকারীর নিজের bookshelf-এর নির্দিষ্ট বইয়ের progress ফেরত দেয়; পুরনো endpoint-এর list response অপরিবর্তিত আছে যখন `book_id` দেওয়া হয় না।
- Progress POST এখন `percent`, `page`, `location`, `file_id` validate ও account/library ownership check করে; file ID অবশ্যই একই বইয়ের হতে হবে।
- Reader-এর simplified EPUB/CBZ page navigation প্রতিটি page render-এ page index ও percent account database-এ save করে এবং পরেরবার একই account থেকে বই খুললে শেষ saved page restore করে।
- আগের design, saved study sets, upload security ও AI study workflow অপরিবর্তিত রাখা হয়েছে।

## গুরুত্বপূর্ণ সীমাবদ্ধতা
- EPUB implementation এখনও archive entries-এর simplified page model ব্যবহার করে; পূর্ণ EPUB spine/CFI/navigation implementation নয়।
- PDF browser-native iframe-এর internal page number cross-origin/embedded viewer constraints-এর কারণে নির্ভরযোগ্যভাবে পড়া যায় না; এই আপডেটে PDF-এর প্রকৃত page-level auto-sync দাবি করা হচ্ছে না।
- Cross-device sync কাজ করতে একই account/database-backed deployment এবং session login প্রয়োজন। Local browser fallback নয়, এই custom server endpoint ব্যবহার হয়।
- Audio playback timestamp, full EPUB CFI, and real PDF.js integration ভবিষ্যৎ কাজ।

## Verification
- `python -m py_compile advanced.py`
- `python -m unittest test_reader_position_sync test_reader_progress_sync_contract -v`
- Frontend static verification scripts
- Inline JavaScript syntax check
- ZIP integrity check
