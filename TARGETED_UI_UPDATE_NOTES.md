# LibraAI targeted UI update

This update is intentionally limited to the requested resource/community/help/about/footer areas.

- Added `/manga`, connected to the existing live `/backend/api/books` catalog. It shows 15 series initially and reveals more in batches of 15. The Library > Manga & Comics category now opens this page.
- Refined the existing audiobook catalog with search and 20-item progressive display. Playback still uses the existing rights-aware `/backend/api/audiobooks` API and private stream endpoint; no fake audio records or unlicensed media were introduced.
- Replaced the generic Community information page with 12 interest-based community cards that explain practical use cases and route access requests through the existing support portal.
- Replaced Help Center cards with interactive troubleshooting accordions and a support-ticket route. Existing SQLite-backed support tickets, user ownership checks and admin replies remain the backend source of truth.
- Kept About LibraAI content in English and aligned its typography; refined the Need a hand icon animation and glassmorphism footer styling.

## Verification
- Python compilation passed for the existing audiobook and support backend modules.
- `test_audiobook_library.py` and `test_audiobook_entitlements.py`: 6 tests passed.
- TypeScript/TSX syntax transpilation passed for all modified TSX files.
- Full Next.js build could not be run because `npm ci` timed out in this environment and the local `node_modules` installation remained incomplete (`next` and React/Node type definitions unavailable). Run `npm ci` and `npm run build` in an environment with npm registry access before deployment.

## Existing backend upload workflows
- Audiobook assets are uploaded and licensed through the existing admin audiobook hosting workspace (`/admin/audiobook-library`); playback checks license state and entitlement.
- Manga entries are read from the existing books catalog. Admins can add catalog metadata through `/admin/catalog/new`. This project version does not contain a chapter-file ingestion API, so this UI does not pretend that metadata creation uploads or hosts manga chapter files.
- Community join/member persistence is not present in the current backend; the cards therefore link to the authenticated support workflow instead of faking a successful join.
