# Shared sessions ও rate limiting (বাংলা)

## Single-host default

`LIBRAAI_SESSION_BACKEND=sqlite` এবং `LIBRAAI_RATE_LIMIT_BACKEND=memory` single-host development/local use-এর জন্য. In-memory limiter process-local; একাধিক worker-এ shared quota দেয় না.

## Shared Redis configuration

```env
REDIS_URL=rediss://username:password@private-redis-host:6379/0
LIBRAAI_SESSION_BACKEND=redis
LIBRAAI_RATE_LIMIT_BACKEND=redis
LIBRAAI_RATE_LIMIT_HMAC_KEY=use-the-same-random-secret-on-all-workers
LIBRAAI_MULTI_INSTANCE=yes
```

Redis-কে public internet-এ expose কোরো না; managed/private network, authentication, TLS, ACL, monitoring এবং appropriate eviction/backup policy ব্যবহার করো. সব worker-এ একই application `SECRET_KEY` ও rate-limit HMAC key থাকতে হবে. Redis অনুপলব্ধ হলে shared limiter protected write routes-এ fail-closed 503 দেয়; silent in-memory fallback করে না.

## গুরুত্বপূর্ণ architecture blocker

এই release-এর main application database এখনও SQLite. Redis session এবং rate limiter multi-worker state share করে, কিন্তু SQLite-ভিত্তিক main database-কে multi-host write-safe করে না. `LIBRAAI_MULTI_INSTANCE=yes` দিলে production preflight primary database migration-কে blocker দেখায়. Multi-instance launch-এর আগে PostgreSQL migration, SQL dialect/transaction review, migration/rollback, backup restore এবং concurrency tests দরকার. এই release-এ PostgreSQL primary database adapter সম্পন্ন হয়নি.

## Verification

- `python -B -m unittest -v test_api_resilience_redis.py test_payout_provider.py test_redis_sessions.py test_production_preflight.py`
- `python -B production_preflight.py --strict`
- Redis test environment-এ concurrent requests, session rotation across two app workers, Redis outage/failover এবং webhook replay পরীক্ষা করো.
