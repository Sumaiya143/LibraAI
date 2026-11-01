"""Non-destructive preflight for configured third-party integrations.

No payments are initiated. Set RUN_OPENAI_LIVE_TEST=1 only to send a small,
potentially billable AI request using the configured API key.
"""
import json, os, urllib.request, urllib.error


def probe(url, timeout=5):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LibraAI-Integration-Preflight/1.0"}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {"reachable": True, "status": response.status}
    except urllib.error.HTTPError as exc:
        # An HTTP response proves DNS/TLS/network reachability; 401/404 may be expected for API roots.
        return {"reachable": True, "status": exc.code, "note": "HTTP response received; endpoint may require authentication/path."}
    except Exception as exc:
        return {"reachable": False, "error_type": type(exc).__name__}


def main():
    checks = {}
    ai_key = os.getenv("LIBRAAI_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    ai_base = os.getenv("LIBRAAI_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    checks["ai"] = {"configured": bool(ai_key), "base_url_https": ai_base.startswith("https://")}
    if ai_key:
        checks["ai"]["network"] = probe(ai_base + "/models")
    payment = {
        "sslcommerz": bool(os.getenv("SSLCZ_STORE_ID") and os.getenv("SSLCZ_STORE_PASSWORD")),
        "bkash": bool(os.getenv("BKASH_USERNAME") and os.getenv("BKASH_PASSWORD") and os.getenv("BKASH_APP_KEY") and os.getenv("BKASH_APP_SECRET")),
        "public_https_url": (os.getenv("PUBLIC_BASE_URL", "").startswith("https://")),
    }
    checks["payments"] = {"credentials_configured": payment, "live_payment_attempted": False,
                           "note": "Credentials are presence-checked only; provider sandbox authentication must be tested separately."}
    storage = os.getenv("LIBRAAI_STORAGE_BACKEND", "local").lower()
    checks["storage"] = {"backend": storage, "cloud_credentials_present": bool(os.getenv("LIBRAAI_STORAGE_BUCKET") and os.getenv("LIBRAAI_STORAGE_KEY") and os.getenv("LIBRAAI_STORAGE_SECRET")) if storage == "cloud" else None}
    if os.getenv("RUN_OPENAI_LIVE_TEST") == "1":
        if not ai_key:
            checks["ai"]["live_test"] = {"passed": False, "reason": "No AI API key configured"}
        else:
            body = json.dumps({"model": os.getenv("LIBRAAI_LLM_MODEL", "gpt-4o-mini"), "messages": [{"role": "user", "content": "Reply with exactly: LibraAI integration check."}], "max_tokens": 12}).encode()
            req = urllib.request.Request(ai_base + "/chat/completions", data=body, headers={"Authorization": "Bearer " + ai_key, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    data = json.load(response)
                checks["ai"]["live_test"] = {"passed": bool(data.get("choices")), "http_status": response.status}
            except Exception as exc:
                checks["ai"]["live_test"] = {"passed": False, "error_type": type(exc).__name__}
    print(json.dumps(checks, indent=2))
    # Preflight reports readiness, not full provider certification. Only fail on explicitly requested live AI test failure.
    return 1 if os.getenv("RUN_OPENAI_LIVE_TEST") == "1" and not checks.get("ai", {}).get("live_test", {}).get("passed", False) else 0

if __name__ == "__main__":
    raise SystemExit(main())
