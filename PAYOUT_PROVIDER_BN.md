# LibraAI payout adapter — integration contract (বাংলা)

## এই release-এ যা আছে

- `payout_provider.py`-তে idempotent HTTP disbursement adapter, strict HTTPS production endpoint validation, bounded timeout/response size এবং secret-free errors.
- Admin-only `POST /api/admin/royalty-payouts/<id>/submit-transfer` endpoint. Creator request নিজে থেকে টাকা পাঠায় না; admin explicit action দিলে gateway-তে পাঠায়.
- Stable idempotency key: `libraai-payout-<payout_id>`. Gateway অবশ্যই একই key-এর repeated request-এ দ্বিতীয়বার transfer করবে না.
- `POST /api/admin/royalty-payouts/<id>/reconcile` provider-এর GET `<endpoint>/<idempotency-key>` response দিয়ে ambiguous/failed request যাচাই করে.
- `POST /api/payouts/webhook/generic` signed webhook গ্রহণ করে. `X-LibraAI-Signature: sha256=<hex-hmac>` header-এর HMAC-SHA256 raw request body-তে গণনা হয়; replayed `event_id` duplicate হিসেবে নিরাপদে handle হয়.
- Initiation response-এ `paid` থাকলেও সরাসরি payout paid হয় না. Final signed webhook অথবা authenticated provider reconciliation reference লাগবে.

## Required environment variables

```env
LIBRAAI_PAYOUT_PROVIDER=generic_http
LIBRAAI_PAYOUT_API_URL=https://merchant-approved-gateway.example/transfers
LIBRAAI_PAYOUT_API_KEY=replace-with-private-api-key
LIBRAAI_PAYOUT_WEBHOOK_SECRET=replace-with-random-webhook-secret
LIBRAAI_PAYOUT_TIMEOUT_SECONDS=8
LIBRAAI_PAYOUT_LIVE_E2E_VERIFIED=no
```

এই endpoint generic LibraAI adapter contract; এটি bKash/Nagad-এর certified native integration নয়. Gateway/provider-এর লিখিত approval ও exact contract না থাকলে live transfers enable কোরো না.

## Gateway contract

`POST <endpoint>` JSON body:

```json
{"merchant_reference":"libraai-payout-42","payout_id":42,"amount_minor":25000,"currency":"BDT","method":"bkash","destination":"01712345678"}
```

Headers: `Authorization: Bearer <key>`, `Idempotency-Key`, `Content-Type: application/json`. Success JSON must contain `{ "status": "accepted|processing|paid", "reference": "provider-transaction-id" }`. Provider must persist idempotency before initiating money movement.

Reconciliation endpoint: `GET <endpoint>/libraai-payout-42`, JSON `{ "status": "accepted|processing|paid|failed", "reference": "..." }`. `paid` requires a non-empty reference. Provider must protect both endpoints with authentication, TLS and authorization.

Webhook JSON: `{ "event_id":"unique-provider-event", "payout_id":42, "idempotency_key":"libraai-payout-42", "status":"paid|failed|processing", "reference":"provider-transaction-id" }`. HMAC signs the exact raw bytes. Configure the gateway to send only verified final states. Provider-specific payload mapping may be needed before connecting a real provider.

## Before production

1. Provider must approve the merchant/account and this contract.
2. Test success, rejection, timeout-after-acceptance, duplicate idempotency key, webhook replay, wrong signature, delayed webhook, reconciliation and recovery in sandbox.
3. Have finance reconcile payout ledger against provider statements.
4. Keep `LIBRAAI_PAYOUT_LIVE_E2E_VERIFIED=no` until evidence is reviewed. Configuration alone never proves transfers work.
