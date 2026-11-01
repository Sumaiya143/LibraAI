# LibraAI v46 — Upload Security Hardening

এই আপডেটে v45-এর reader progress sync এবং আগের design/feature অপরিবর্তিত রেখে upload security-তে একটি configurable malware-scanning layer যোগ করা হয়েছে।

## কী যুক্ত হয়েছে

- `upload_security.py`: dependency-free upload inspection helper.
- ClamAV daemon-এর `INSTREAM` protocol দিয়ে file bytes scan করার সমর্থন।
- PDF, EPUB/CBZ, PNG/JPEG/WebP এবং সমর্থিত audio format-এর জন্য extension/content signature mismatch rejection.
- EICAR antivirus test signature সবসময় reject করা হয়।
- Audiobook upload, publisher content upload এবং admin catalog CSV import-এর আগে validation/scanning hook।
- API response-এ `scan_status` (`clean`, `not_scanned` ইত্যাদি) দেওয়া হয়; scanner না থাকলে ফাইলকে ভুলভাবে “clean” বলা হয় না।
- Scanner unavailable হলে বাধ্যতামূলক fail-closed production mode।

## Production configuration

Private network-এ ClamAV daemon চালিয়ে environment variables সেট করুন:

```env
LIBRAAI_CLAMAV_HOST=clamav
LIBRAAI_CLAMAV_PORT=3310
LIBRAAI_CLAMAV_TIMEOUT=3
LIBRAAI_REQUIRE_MALWARE_SCAN=1
```

`LIBRAAI_REQUIRE_MALWARE_SCAN=1` সেট থাকলে scanner unreachable/response invalid হলে upload reject হবে। Local development-এ scanner configure না থাকলে upload-এ `scan_status=not_scanned` হবে; এটি malware-free হওয়ার নিশ্চয়তা নয়। Production-এ fail-closed mode এবং private network-এ scanner ব্যবহার করুন।

## Verification

- `python -m unittest test_upload_security -v`
- `python -m py_compile upload_security.py audiobook_library.py advanced.py catalog_routes.py`

## সীমাবদ্ধতা

- এই helper antivirus engine-এর বিকল্প নয়; ClamAV configured থাকলেই পূর্ণ signature-based scanning হয়।
- File-type magic checks একটি অতিরিক্ত validation, malware detection নয়।
- Upload storage এবং metadata save-এর মধ্যে distributed transaction নেই; storage cleanup/reconciliation এখনও operational কাজ।
