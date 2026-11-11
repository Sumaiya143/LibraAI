# LibraAI stability merge — 2026-11-11

Base: LibraAI_Professional_Final_2026-11-11(2).zip
Stability fixes selectively merged from: LibraAI_fixed(2).zip

Applied:
- Explicit SQLite connection closure in backup/restore and restore-drill paths (Windows file-lock safety).
- Cursor-scoped `lastrowid` retrieval for manga seed inserts.
- Release SHA-256 manifest regenerated after the merge.

Preserved:
- Professional base features, UI pages, AI Assistant, voice-related frontend, circulation, borrowing, reader policy, inventory and VPS deployment configuration.
- Professional circulation and production guard logic was intentionally retained; the older `LibraAI_fixed` `app.py` was NOT wholesale copied because it removes/weakens newer circulation routes and production protections.

Verification scope:
- Archive integrity and manifest hashes are checked.
- Python compilation and selected tests are checked where dependencies are available.
- A successful static/test run does not certify live payment credentials, cloud storage, external security audit, or production infrastructure.
