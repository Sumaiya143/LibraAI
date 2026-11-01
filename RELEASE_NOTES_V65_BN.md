# LibraAI v65 — Seller Commerce Workspace

## Seller dashboard
- Merchant/creator accounts now see a dedicated seller workspace instead of reader-oriented book metrics.
- The seller navigation includes Dashboard, Upload & Edit Products, My Products & Inventory, Orders & Sales, Earnings & Payouts, and Sales Analytics.
- Dashboard cards show the seller's own product listings and inventory, plus order and earnings summaries from recorded commerce data.

## Product management
- Added authenticated seller-owned product records linked to the existing catalog book index.
- Supported product types: physical book, eBook, stationery, audiobook, manga, comics, and other products.
- Product fields include title, subtitle, description, HTTPS image URL, SKU, tags, hashtags, additional key/value details, base price, discount percentage, and stock quantity.
- Sellers can create and edit only their own product records. Editing sends the listing back to review.
- New or edited listings are marked `pending_review` and are not publicly purchasable (`catalog_products.sale_enabled=0`) until an administrator approves them.

## Inventory, orders and earnings
- Inventory view includes single-unit price, two-unit price, discount, stock, recorded sold quantity, and estimated platform commission per product.
- Orders & Sales lists marketplace order lines matched to the seller's catalog records, including order ID, product, quantity, unit price, line value, date and order status.
- Order status counters count unique orders, not line items.
- Earnings and Sales Analytics provide week/month/year filters, recorded completed-order revenue, prior-period comparison when data exists, best-selling products, commission estimates, and payout request history.
- Payout requests are restricted to the seller's calculated available balance and are not represented as automatic transfers.

## Required production configuration and limitations
- Set `LIBRAAI_PLATFORM_COMMISSION_RATE` to the platform's approved commission percentage (0–50) before displaying net earnings or accepting payout requests. It is intentionally not guessed or defaulted. If missing, the UI shows that the rate is not configured and payout requests are disabled.
- Configure and independently verify a real payout provider and seller settlement process before enabling actual payouts. A payout request currently creates an internal review request only.
- Product images are supplied as HTTPS image URLs; binary image upload/storage is not implemented in this release.
- Orders and earnings are attributed when existing `order_items.book_id` values match a seller-owned catalog product. Existing unrelated orders are not fabricated or assigned to sellers.
- The new seller tables are created automatically when seller APIs are first used; back up the production database before deployment.

## Verification
- Seller workspace contract tests: 7 passed.
- Related catalog/inventory/payout health tests: 16 passed (23 combined tests total).
- Frontend verification scripts: 9 passed, including seller workspace and existing dashboard/homepage/security contracts.
- TSX syntax transpilation: both seller component and dashboard passed.
- Python syntax compilation and SQLite seller schema/catalog/order-attribution smoke check passed.
- Full Next.js production build and live Flask HTTP/DB integration tests were not run in this environment because frontend dependencies and Flask runtime are unavailable here.
