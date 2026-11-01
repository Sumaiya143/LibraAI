# LibraAI Audiobook Hosting & Licensing (বাংলা)

## যা যোগ হয়েছে
- Admin UI: `/admin/audiobook-library` — catalog title নির্বাচন, audio upload, rights holder, agreement reference, optional expiry এবং `licensed` / `sample` access policy।
- Private storage adapter: local persistent storage by default; S3/MinIO support via existing `cloud_storage.py` when credentials and `boto3` are configured.
- Audio formats: MP3, M4A, AAC, OGG/OGA, OPUS, WAV, FLAC, WEBM. Configurable upload cap via `LIBRAAI_MAX_AUDIO_UPLOAD_MB` (1–200 MB).
- `GET /api/audiobooks/<book_id>` reports availability without revealing private storage keys.
- `GET /api/audiobooks/<book_id>/stream` checks active license, expiry and paid digital entitlement; explicitly marked short samples are public. HTTP byte ranges support player seeking.
- SHA-256 integrity verification, private/no-store responses, safe storage keys and license revocation controls.
- Payment entitlement grants recognize audiobook format records when the audiobook license is active.

## Local development
`LIBRAAI_STORAGE_BACKEND=local` and `LIBRAAI_LOCAL_STORAGE_DIR` should point to persistent private storage outside `static/`. Never commit real audio or publisher files to the repository.

## S3 / MinIO production storage
Set `LIBRAAI_STORAGE_BACKEND=s3` or `minio`, `LIBRAAI_STORAGE_BUCKET`, `LIBRAAI_STORAGE_REGION`, `LIBRAAI_STORAGE_ENDPOINT` (if needed), `LIBRAAI_STORAGE_KEY`, and `LIBRAAI_STORAGE_SECRET`. Install `requirements-production.txt`. Use private buckets; do not enable public object access.

## Rights and licensing limits
- The app records rights holder, agreement reference, expiry and active/revoked status; it cannot validate the underlying contract or acquire distribution rights for you.
- Only upload audio that LibraAI is legally allowed to host and stream. `sample` must be a separately supplied short preview, not a full audiobook.
- This version reads audio objects into memory before byte-range responses. It is suitable for prototype/small launch tests, not high-volume streaming. For production scale, use a streaming S3 proxy or short-lived signed URLs gated by a backend entitlement check, CDN protection, monitoring, backups and load tests.
- No audio files, publisher licenses, royalties, DRM or commercial audiobook catalog are bundled.

## External semantic search status
External embedding search exists in `semantic_search.py` using a server-side OpenAI-compatible embeddings endpoint. Catalog and repeated query vectors are cached in SQLite; provider errors fall back to transparent local concept/lexical ranking. External mode requires `LIBRAAI_EMBEDDINGS_API_KEY` (or `OPENAI_API_KEY`) and was not live-tested without a provider credential. This is exact cosine ranking over a bounded SQLite catalog, not a managed vector database; default cap is 150 books.
