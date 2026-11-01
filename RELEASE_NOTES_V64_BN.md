# LibraAI v64 — Role-aware workspace update

## What changed

- Hides the public marketing header on `/dashboard`; the authenticated workspace now owns its top toolbar.
- Removes the fake preview-role switcher. The active workspace is determined from the signed-in backend session (`reader`, `creator`/`merchant`, `admin`, or `librarian`).
- Keeps a dedicated AI Assistant workspace available to every authenticated role.
- Adds an account menu with Profile, Settings, and Sign out, plus notification and EN/বাংলা controls.
- Adds authenticated dashboard APIs for profile/reading summary, reading-goal posts, guild discovery and membership, wallet/order/refund records, and quiz/memory-game coin rewards.
- My Library shows only titles with saved reading progress and their percentage/page position.
- Bookstore opens `/library`; Audiobooks and Manga & Comics open the library with the corresponding filter.
- Adds community search, levels 1–10, community creation/joining, top communities and latest guild cards.
- Adds a Knowledge Vault quiz and memory game. Coin rewards are calculated on the server and capped at 20 quiz attempts per user per day.
- Adds account-backed reading analytics, order/cart/wishlist views, spending and verified refund totals.
- Extends the library filters to support Manga & Comics.

## Data and honesty notes

- Reading minutes and genre-by-week charts are not fabricated. The existing reader progress API does not persist reliable daily reading-duration events, so the dashboard labels reading-time analytics as not yet tracked.
- Community rankings use recorded guild membership counts. A new guild starts at level 1; no artificial rank or member count is shown.
- Wallet refund totals include only refund requests whose backend state is `refunded`.
- The AI Assistant requires the existing AI provider configuration. A missing provider returns a safe error rather than a fabricated answer.

## Verification performed

- Python syntax compilation: `app.py`, `dashboard_workspace.py`.
- TSX syntax transpilation: dashboard, header, library page.
- Page-shell verification: passed.
- Dashboard workspace contract checks: 14/14 passed.
- Live integration contracts: passed (static contract tests, not live-provider acceptance).
- Security-header contracts: passed.
- Client enhancement contracts: passed.
- Language bridge contracts: passed.
- Homepage v63 regression checks: passed.

## Verification not performed

- Full Next.js production build and browser-based end-to-end testing were not run because the frontend dependencies were not installed in this environment. Offline package installation was blocked by a missing npm cache entry and network access is unavailable.
- Flask route-level integration tests, live database migration, payment-provider acceptance, and deployed SSL/TLS verification were not run because the Python Flask runtime and production services are not available in this environment.
