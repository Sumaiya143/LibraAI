"""Safe, read-only launch dependency checklist for the floating frontend card."""
import os



def _set(name, expected=None):
    value = os.getenv(name, '').strip()
    return bool(value) and (expected is None or value.lower() == expected.lower())


def readiness_access_status(user):
    """Return HTTP status for the sensitive operator checklist without exposing it publicly."""
    if not user:
        return 401
    try:
        role = user.get('role') if hasattr(user, 'get') else user['role']
    except (KeyError, TypeError, IndexError):
        role = None
    return 200 if role == 'admin' else 403


def build_public_notices(env=None):
    """Safe, non-sensitive notices visible to all users when work remains.

    Only explicit operator attestations are considered; credential presence,
    values, hostnames and detailed provider configuration are never exposed.
    Attestations are not independent proof of the underlying real-world work.
    """
    env = os.environ if env is None else env
    production = str(env.get('LIBRAAI_ENV', 'development')).strip().lower() == 'production'
    def yes(key): return str(env.get(key, 'no')).strip().lower() == 'yes'
    notices = []
    if not (yes('LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED') and yes('LIBRAAI_GATEWAY_E2E_VERIFIED') and str(env.get('SSLCOMMERZ_SANDBOX','true')).lower() == 'false' and str(env.get('BKASH_SANDBOX','true')).lower() == 'false'):
      notices.append({'id':'payments','title':'Live payments need merchant setup','status':'manual',
       'summary':'Before accepting real payments, the owner must complete provider approval, callback configuration and verified sandbox/live transactions.',
       'action':'Review setup steps','href':'/help','routes':['checkout','cart','payment','orders','wallet']})
    # A generic adapter exists, but no provider-specific approval/live proof is assumed.
    notices.append({'id':'creator-payouts','title':'Creator payouts require an approved provider','status':'manual',
       'summary':'The idempotent transfer adapter and reconciliation workflow are implemented, but no provider is approved or live-tested. Keep manual review until credentials and settlement evidence are verified.',
       'action':'Review payout setup','href':'/help','routes':['creator/royalties','royalties','admin/royalty-payouts']})
    if not (yes('LIBRAAI_LICENSE_RIGHTS_VERIFIED') and yes('LIBRAAI_CONTENT_RIGHTS_VERIFIED')):
      notices.append({'id':'content-rights','title':'Publisher and audiobook rights must be verified','status':'manual',
       'summary':'Only upload and distribute titles covered by actual written permissions for the intended format, territory, term and royalty.',
       'action':'Review rights checklist','href':'/help','routes':['audiobook','reader-plus','licensed-content','marketplace']})
    if not (yes('LIBRAAI_SECURITY_REVIEW_PASSED') and yes('LIBRAAI_SECURITY_REVIEW_VERIFIED')):
      notices.append({'id':'security-review','title':'Independent security review is required before launch','status':'manual',
       'summary':'A qualified reviewer should test the deployed service, document findings and confirm remediation before real money or sensitive production data is accepted.',
       'action':'Review launch checklist','href':'/help','routes':['checkout','payment','account','admin']})
    if not yes('LIBRAAI_BACKUP_RESTORE_VERIFIED'):
      notices.append({'id':'backup-restore','title':'Production backup and restore drill required','status':'manual',
       'summary':'Configure encrypted backups for the database and private files, then test restoration and document recovery targets.',
       'action':'Review deployment steps','href':'/help','routes':['admin','account','reader','creator']})
    if production and not yes('LIBRAAI_STORAGE_RESTORE_VERIFIED'):
      notices.append({'id':'cloud-storage','title':'Private cloud storage must be verified','status':'manual',
       'summary':'Production ebooks and audiobooks need private durable object storage with restricted access, encryption and lifecycle/restore checks.',
       'action':'Review storage setup','href':'/help','routes':['audiobook','reader','ebook','admin/audiobook']})
    if production and not yes('LIBRAAI_PRODUCTION_ACCEPTANCE_PASSED'):
      notices.append({'id':'production-acceptance','title':'Production acceptance tests are still required','status':'manual',
       'summary':'Run the full dependency install, production build, browser end-to-end tests, provider integration tests and recovery checks in the deployed environment.',
       'action':'Open release checklist','href':'/help','routes':['admin','checkout','reader','account']})
    if production and str(env.get('LIBRAAI_MULTI_INSTANCE','no')).strip().lower() in ('yes','true','1'):
      notices.append({'id':'multi-instance-database','title':'Shared primary database migration required','status':'manual',
       'summary':'Redis sessions and rate limits can be shared, but this release still uses SQLite for application data. Migrate to PostgreSQL and run concurrency/restore tests before multi-host deployment.',
       'action':'Review scaling plan','href':'/help','routes':['admin','account','checkout','creator']})
    return {'items':notices, 'open_count':len(notices), 'launch_ready':len(notices)==0,
            'scope':'generic operator actions only; no secret or provider configuration details exposed; flags are not independent proof'}


def build_readiness(env=None):
    env = os.environ if env is None else env
    def configured(name): return bool(str(env.get(name, '')).strip())
    def yes(name): return str(env.get(name, 'no')).strip().lower() == 'yes'
    ssl = configured('SSLCOMMERZ_STORE_ID') and configured('SSLCOMMERZ_STORE_PASSWORD')
    bkash = all(configured(k) for k in ('BKASH_USERNAME','BKASH_PASSWORD','BKASH_APP_KEY','BKASH_APP_SECRET'))
    production = str(env.get('LIBRAAI_ENV','development')).lower() == 'production'
    cloud = str(env.get('LIBRAAI_STORAGE_BACKEND','local')).lower() in ('s3','minio') and configured('LIBRAAI_STORAGE_BUCKET') and configured('LIBRAAI_STORAGE_KEY') and configured('LIBRAAI_STORAGE_SECRET')
    embedding_key = configured('LIBRAAI_EMBEDDINGS_API_KEY') or configured('OPENAI_API_KEY')
    llm_key = configured('LIBRAAI_LLM_API_KEY') or configured('OPENAI_API_KEY')
    items = [
      {'id':'payments','title':'Live payment gateway setup','status':'ready' if ssl and bkash and yes('LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED') and str(env.get('SSLCOMMERZ_SANDBOX','true')).lower() == 'false' and str(env.get('BKASH_SANDBOX','true')).lower() == 'false' else 'blocked','summary':'Merchant approval, production credentials, HTTPS callbacks and verified sandbox/live transaction tests are required.','action':'Review payment setup','href':'/help','routes':['checkout','cart','payment','orders','wallet']},
      {'id':'creator-payouts','title':'Automatic creator royalty payouts','status':'manual','summary':'The idempotent generic disbursement adapter, signed webhook and reconciliation route are implemented, but no approved provider is configured or live-tested. Keep manual review until the provider contract, credentials and sandbox/live evidence are approved.','action':'Open creator royalties','href':'/creator/royalties','routes':['creator/royalties','royalties','admin/royalty-payouts']},
      {'id':'semantic-ai','title':'External semantic search provider','status':'ready' if embedding_key else 'optional','summary':'Without an embeddings API key, LibraAI uses its local semantic/keyword fallback. Add a provider key to enable external embeddings.','action':'Review AI setup','href':'/help','routes':['search','discover','library','ai']},
      {'id':'ai-tutor','title':'External AI tutor provider','status':'ready' if llm_key else 'optional','summary':'Configure the server-side LLM API key/model to enable provider-backed AI tutor responses; catalog-grounded recommendations can still work locally.','action':'Review AI setup','href':'/help','routes':['ai','tutor','assistant','study']},
      {'id':'cloud-storage','title':'Production cloud object storage','status':'ready' if cloud else ('blocked' if production else 'optional'),'summary':'For production-scale private ebooks/audiobooks, configure a persistent private S3/MinIO bucket and credentials. Local storage is suitable for development, not a resilient multi-instance deployment.','action':'Review storage setup','href':'/help','routes':['audiobook','reader','ebook','admin/audiobook']},
      {'id':'content-rights','title':'Publisher and audiobook rights verification','status':'ready' if yes('LIBRAAI_LICENSE_RIGHTS_VERIFIED') else 'blocked','summary':'Obtain and document the actual publisher/author licence, territory, format, term and royalty terms. An environment flag is only an operator attestation, not legal proof.','action':'Review licensing checklist','href':'/help','routes':['audiobook','reader-plus','licensed-content','marketplace']},
      {'id':'security-review','title':'Independent security review','status':'ready' if yes('LIBRAAI_SECURITY_REVIEW_PASSED') else 'blocked','summary':'Arrange an independent penetration/security review and remediate findings before accepting real money or sensitive production data.','action':'Open security checklist','href':'/help','routes':['checkout','payment','account','admin']},
      {'id':'backup-restore','title':'Production backup and restore drill','status':'ready' if yes('LIBRAAI_BACKUP_RESTORE_VERIFIED') else 'blocked','summary':'Configure automated encrypted backups and perform a documented restore test against the production database and private files.','action':'Review deployment checklist','href':'/help','routes':['admin','account','reader','creator']},
    ]
    blockers = [x for x in items if x['status'] in ('blocked','manual')]
    return {'items':items,'open_count':len(blockers),'launch_ready':len(blockers)==0,'scope':'configuration checklist only; not independent verification'}


try:
    from flask import Blueprint, jsonify
    setup_readiness_bp = Blueprint('setup_readiness', __name__)

    @setup_readiness_bp.get('/api/setup/notices')
    def public_setup_notices():
        # Public-safe, intentionally generic notices ensure the floating card
        # still works for unauthenticated visitors without leaking config state.
        from flask import make_response
        response = make_response(jsonify(build_public_notices()))
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @setup_readiness_bp.get('/api/setup/readiness')
    def operator_setup_readiness():
        # Configuration status is operationally sensitive: only authenticated admins may inspect it.
        from app import current_user
        from flask import make_response
        access = readiness_access_status(current_user())
        if access != 200:
            response = make_response(jsonify({'error': 'admin_access_required'}), access)
        else:
            response = jsonify(build_readiness())
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
except ImportError:  # Pure readiness tests can run without Flask installed.
    setup_readiness_bp = None
