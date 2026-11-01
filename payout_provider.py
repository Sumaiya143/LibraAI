"""Idempotent generic HTTPS disbursement adapter contract.

This is not a bKash/Nagad-certified integration. It speaks to a merchant-approved
HTTP gateway implementing the documented LibraAI contract in PAYOUT_PROVIDER_BN.md.
No provider response is treated as paid until a signed webhook or independent
reconciliation confirms a final transaction reference.
"""
from __future__ import annotations
import hashlib, hmac, json, os, re, urllib.error, urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

class PayoutProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, uncertain: bool = False):
        super().__init__(message); self.code=code; self.uncertain=uncertain

@dataclass(frozen=True)
class PayoutProviderConfig:
    endpoint: str
    api_key: str
    webhook_secret: str
    timeout_seconds: float = 8.0

def config_from_env(env=None):
    env = os.environ if env is None else env
    provider = str(env.get('LIBRAAI_PAYOUT_PROVIDER','')).strip().lower()
    endpoint = str(env.get('LIBRAAI_PAYOUT_API_URL','')).strip()
    key = str(env.get('LIBRAAI_PAYOUT_API_KEY','')).strip()
    secret = str(env.get('LIBRAAI_PAYOUT_WEBHOOK_SECRET','')).strip()
    if provider != 'generic_http' or not endpoint or not key or not secret:
        raise PayoutProviderError('provider_not_configured','Approved payout provider is not fully configured.')
    if len(secret) < 32:
        raise PayoutProviderError('webhook_secret_weak','Webhook secret must contain at least 32 characters.')
    parsed=urlsplit(endpoint)
    production=str(env.get('LIBRAAI_ENV','')).lower()=='production'
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or (production and parsed.scheme!='https') or parsed.scheme not in ('https','http'):
        raise PayoutProviderError('provider_endpoint_invalid','Payout endpoint must be a valid HTTPS URL in production.')
    if parsed.scheme=='http' and parsed.hostname not in ('localhost','127.0.0.1','::1'):
        raise PayoutProviderError('provider_endpoint_invalid','Unencrypted HTTP is allowed only for local development.')
    try: timeout=max(2.0,min(20.0,float(env.get('LIBRAAI_PAYOUT_TIMEOUT_SECONDS','8'))))
    except (ValueError,TypeError): timeout=8.0
    return PayoutProviderConfig(endpoint,key,secret,timeout)

def sign_webhook(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

def verify_webhook(body: bytes, signature: str, secret: str) -> bool:
    return bool(signature and secret) and hmac.compare_digest(sign_webhook(body,secret),signature.strip().removeprefix('sha256='))

def submit_transfer(config: PayoutProviderConfig, *, payout_id: int, amount_cents: int, currency: str, method: str, destination: str, idempotency_key: str) -> dict:
    if payout_id<=0 or amount_cents<=0 or currency!='BDT' or method not in ('bkash','nagad','bank_transfer'):
        raise PayoutProviderError('transfer_invalid','Payout request fields failed validation.')
    if not re.fullmatch(r'libraai-payout-[1-9][0-9]*',idempotency_key):
        raise PayoutProviderError('idempotency_invalid','Payout idempotency key is invalid.')
    payload={'merchant_reference':idempotency_key,'payout_id':payout_id,'amount_minor':amount_cents,'currency':currency,'method':method,'destination':destination}
    body=json.dumps(payload,separators=(',',':')).encode()
    request=urllib.request.Request(config.endpoint,data=body,method='POST',headers={'Content-Type':'application/json','Accept':'application/json','Authorization':'Bearer '+config.api_key,'Idempotency-Key':idempotency_key,'User-Agent':'LibraAI-PayoutAdapter/1.0'})
    try:
        with urllib.request.urlopen(request,timeout=config.timeout_seconds) as response:
            raw=response.read(64*1024+1)
            if len(raw)>64*1024: raise PayoutProviderError('provider_response_too_large','Payout provider response exceeded the allowed size.',uncertain=True)
            status=response.status
    except urllib.error.HTTPError as exc:
        # A provider may have accepted a transfer even if its response was an error.
        raise PayoutProviderError('provider_http_error',f'Provider returned HTTP {exc.code}; reconcile before retrying.',uncertain=exc.code>=500) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PayoutProviderError('provider_result_uncertain','Provider result is unknown. Reconcile using the same idempotency key before retrying.',uncertain=True) from exc
    if status<200 or status>=300: raise PayoutProviderError('provider_rejected',f'Provider returned HTTP {status}.')
    try: result=json.loads(raw)
    except (ValueError,TypeError) as exc: raise PayoutProviderError('provider_invalid_response','Provider response was not valid JSON; reconcile before retrying.',uncertain=True) from exc
    if not isinstance(result,dict) or not isinstance(result.get('reference'),str) or not result['reference'].strip():
        raise PayoutProviderError('provider_reference_missing','Provider did not return a transaction reference; reconcile before retrying.',uncertain=True)
    provider_status=str(result.get('status','')).lower()
    if provider_status not in ('accepted','processing','paid'):
        raise PayoutProviderError('provider_status_unknown','Provider returned an unknown status; manual reconciliation required.',uncertain=True)
    # Do not mark the payout paid based on the initiation response alone.
    return {'status':'processing' if provider_status=='paid' else provider_status,'reference':result['reference'].strip()[:180],'provider_status':provider_status}


def lookup_transfer(config: PayoutProviderConfig, *, idempotency_key: str) -> dict:
    """Query the provider's GET /<idempotency-key> reconciliation endpoint.

    The merchant gateway must implement this endpoint and return {status,
    reference}. If the endpoint is unavailable or ambiguous, callers must leave
    the payout pending and reconcile manually rather than assume success.
    """
    if not re.fullmatch(r'libraai-payout-[1-9][0-9]*',idempotency_key or ''):
        raise PayoutProviderError('idempotency_invalid','Payout idempotency key is invalid.')
    from urllib.parse import quote
    url=config.endpoint.rstrip('/')+'/'+quote(idempotency_key,safe='')
    request=urllib.request.Request(url,method='GET',headers={'Accept':'application/json','Authorization':'Bearer '+config.api_key,'Idempotency-Key':idempotency_key,'User-Agent':'LibraAI-PayoutAdapter/1.0'})
    try:
        with urllib.request.urlopen(request,timeout=config.timeout_seconds) as response:
            raw=response.read(64*1024+1); status=response.status
            if len(raw)>64*1024: raise PayoutProviderError('provider_response_too_large','Provider reconciliation response exceeded the allowed size.',uncertain=True)
    except urllib.error.HTTPError as exc:
        if exc.code==404: raise PayoutProviderError('provider_transfer_not_found','Provider has no transfer record for this idempotency key.') from exc
        raise PayoutProviderError('provider_reconcile_http_error',f'Provider reconciliation returned HTTP {exc.code}.',uncertain=True) from exc
    except (urllib.error.URLError,TimeoutError,OSError) as exc:
        raise PayoutProviderError('provider_reconcile_unavailable','Provider reconciliation is unavailable; leave payout pending.',uncertain=True) from exc
    if status<200 or status>=300: raise PayoutProviderError('provider_reconcile_http_error',f'Provider reconciliation returned HTTP {status}.',uncertain=True)
    try: result=json.loads(raw)
    except (ValueError,TypeError) as exc: raise PayoutProviderError('provider_invalid_response','Provider reconciliation response was not valid JSON.',uncertain=True) from exc
    if not isinstance(result,dict): raise PayoutProviderError('provider_invalid_response','Provider reconciliation response was invalid.',uncertain=True)
    state=str(result.get('status','')).lower(); reference=str(result.get('reference','')).strip()[:180]
    if state not in ('accepted','processing','paid','failed'):
        raise PayoutProviderError('provider_status_unknown','Provider reconciliation status is unknown.',uncertain=True)
    if state=='paid' and not reference:
        raise PayoutProviderError('provider_reference_missing','Provider reports paid without a transaction reference.',uncertain=True)
    return {'status':state,'reference':reference}
