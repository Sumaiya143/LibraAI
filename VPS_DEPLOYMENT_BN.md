# LibraAI VPS Deployment (single VPS)

## Recommended topology

- Nginx + Let's Encrypt terminates public HTTPS on ports 80/443.
- Next.js frontend runs on `127.0.0.1:3000`.
- Flask/Gunicorn API runs on `127.0.0.1:8000`.
- SQLite is stored on the persistent Docker volume `libraai_data`.
- This is a **single-VPS / single-writer** deployment. Do not scale the Flask service to multiple hosts or replicas while the primary database is SQLite.

## Deploy

1. Install Docker Engine + Docker Compose plugin, Nginx, and Certbot on Ubuntu.
2. Point your domain's DNS A/AAAA records to the VPS.
3. In the extracted project root, run `cp .env.production.example .env`.
4. Generate a secret: `openssl rand -hex 48`; put it in `SECRET_KEY`.
5. Set `LIBRAAI_PUBLIC_URL=https://your-real-domain`, `LIBRAAI_TRUSTED_HOSTS=your-real-domain,www.your-real-domain`, `LIBRAAI_ENV=production`, and keep debug disabled.
6. Review payment/storage/rights flags. Sandbox credentials are not live payment credentials.
7. Run `./deploy-vps.sh`.
8. Copy `nginx/libraai.conf.example` to `/etc/nginx/sites-available/libraai`, replace the example domain, obtain certificates with Certbot, then enable the Nginx site and run `nginx -t && systemctl reload nginx`.
9. Verify `https://your-domain/api/ready` through the frontend proxy and test sign-in, CSRF, borrow, return, fine payment review, and restore from backup.

## Operational notes

- Never commit `.env`, database files, uploads, payment secrets, or private keys to GitHub.
- Use `docker compose logs -f libraai frontend` for logs.
- The backend is intentionally bound to loopback; expose only Nginx publicly.
- Take regular SQLite-consistent backups using the application's supported backup tooling and test restores to a separate database before relying on them.
- A PostgreSQL migration and multi-host readiness are not included in this single-VPS release.
- Live SSLCommerz/bKash settlement, private object storage, restore drills, and independent security review require real provider credentials and external infrastructure.

## Local development

Backend: create a Python 3.12 virtual environment, install `requirements-dev.txt`, then run `python app.py` in development mode.

Frontend: `cd frontend && npm ci && npm run dev`.

Full verification: run `python -m compileall -q .`, `python -B verify_full_test_suite.py`, then in `frontend/` run `npm ci`, all `scripts/verify-*.mjs`, and `npm run build`.
