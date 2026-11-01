"""Offline production configuration check. Does not claim live readiness."""
import argparse
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


def read_env(path):
    values = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def check_config(env):
    issues = []
    domain = env.get("LIBRAAI_DOMAIN", "")
    url = env.get("LIBRAAI_PUBLIC_URL", "")
    if not re.fullmatch(r"(?=.{4,253}$)(?!-)[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+", domain) or domain.lower().endswith((".local", ".test", ".example", ".invalid")):
        issues.append("Set LIBRAAI_DOMAIN to your real public domain")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != domain or parsed.username or parsed.password or parsed.port or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        issues.append("LIBRAAI_PUBLIC_URL must equal https://LIBRAAI_DOMAIN")
    if len(env.get("SECRET_KEY", "")) < 32 or "REPLACE" in env.get("SECRET_KEY", ""):
        issues.append("Generate a strong unique SECRET_KEY")
    if env.get("LIBRAAI_ENV") != "production":
        issues.append("Set LIBRAAI_ENV=production")
    if env.get("LIBRAAI_DB_PATH") != "/data/libraai.db":
        issues.append("Use persistent database path /data/libraai.db")
    for name in ("SSLCOMMERZ_STORE_ID", "SSLCOMMERZ_STORE_PASSWORD", "BKASH_APP_KEY", "BKASH_APP_SECRET", "BKASH_USERNAME", "BKASH_PASSWORD"):
        if not env.get(name) or env[name] == "REPLACE_ME":
            issues.append(f"Merchant onboarding incomplete: {name}")
    for flag in ("LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED", "LIBRAAI_LICENSE_RIGHTS_VERIFIED", "LIBRAAI_SECURITY_REVIEW_PASSED"):
        if env.get(flag) != "yes":
            issues.append(f"Not verified: {flag}")
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    args = parser.parse_args()
    if not os.path.isfile(args.env):
        print("Missing .env: copy .env.market.example and configure it")
        return 1
    issues = check_config(read_env(args.env))
    if issues:
        print("NOT READY — " + str(len(issues)) + " unmet requirements:")
        for issue in issues:
            print("- " + issue)
        return 1
    print("Local configuration checks passed; live gateway and deployment verification still required")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
