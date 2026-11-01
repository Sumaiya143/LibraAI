# LibraAI v51 — Audiobook Position Sync

## এই সংস্করণে যোগ করা হয়েছে
- MP3/M4A/OGG audiobook-এর playback position (`audio_seconds`) ডাটাবেসে সংরক্ষণ।
- বইয়ের আগের saved file audiobook হলে সেটি খুলে saved timestamp-এ ফেরত যাওয়া।
- playback চলার সময় প্রায় প্রতি ৫ সেকেন্ডে progress autosave; pause ও playback শেষ হলেও save।
- audio progress percentage হিসাব করে আগের reading progress API-তেই সংরক্ষণ, আলাদা endpoint ছাড়াই।
- পুরোনো ডাটাবেসে নতুন কলাম যোগ করার backward-compatible migration।
- audio position-এর numeric bounds এবং আগের book/file ownership checks বজায় রাখা।

## যাচাই
- `python -m compileall -q .`
- `python -m unittest test_audiobook_position_sync test_reader_position_sync test_reader_progress_sync_contract test_study_tools test_saved_study_sets_contract test_upload_security -v`
- `node --check` দিয়ে reader inline JavaScript syntax যাচাই।
- ZIP integrity check।

## সীমাবদ্ধতা
- browser/codec এবং media server support-এর ওপর audio seek নির্ভরশীল; বাস্তব production media deployment-এ end-to-end পরীক্ষা প্রয়োজন।
- PDF browser-native viewer-এর internal page index এখনো reliably sync হয় না। EPUB-এর জন্য পূর্ণ CFI/spine-based navigation এখনো যোগ হয়নি।
- Full production Next.js build, full Flask runtime এবং browser E2E suite এই পরিবেশে চালানো হয়নি।
