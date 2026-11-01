"""Royalty accounting endpoints (no payout processing)."""
from flask import Blueprint, request, session, jsonify
import os, sqlite3
from royalty_engine import setup, accrue, creator_report
from royalty_payouts import setup as setup_payouts, balance as payout_balance, request_payout, list_requests, transition, decrypt_destination
from payout_provider import config_from_env, submit_transfer, lookup_transfer, verify_webhook, PayoutProviderError


def install(app, connection_factory):
    bp = Blueprint('royalties', __name__)
    with connection_factory() as conn:
        setup(conn)
        setup_payouts(conn)
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS payout_provider_attempts (
          payout_id INTEGER PRIMARY KEY REFERENCES creator_payout_requests(id),
          idempotency_key TEXT NOT NULL UNIQUE, provider_name TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'created' CHECK(status IN ('created','processing','accepted','unknown','failed','paid')),
          provider_reference TEXT, last_error_code TEXT, attempts INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS payout_provider_webhook_events (
          event_id TEXT PRIMARY KEY, payout_id INTEGER NOT NULL, event_status TEXT NOT NULL,
          provider_reference TEXT, received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        ''')

    @bp.get('/api/creator/royalties')
    def report():
        uid = session.get('uid')
        if not uid:
            return jsonify(error='Sign in required'), 401
        with connection_factory() as conn:
            user = conn.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user[0] not in ('creator','admin'):
                return jsonify(error='Creator access required'), 403
            payout_rows=list_requests(conn,uid)
            for payout in payout_rows: payout.pop('destination_ciphertext',None)
            return jsonify(items=creator_report(conn,uid),balance=payout_balance(conn,uid),payout_requests=payout_rows,currency='BDT',unit='cents',payouts_enabled=True,payout_mode='manual_review')


    @bp.post('/api/creator/royalty-payouts')
    def request_creator_payout():
        uid = session.get('uid')
        if not uid:
            return jsonify(error='Sign in required'), 401
        with connection_factory() as conn:
            user = conn.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user[0] not in ('creator','admin'):
                return jsonify(error='Creator access required'),403
            payload=request.get_json(silent=True) or {}
            try:
                conn.execute('BEGIN IMMEDIATE')
                amount=int(payload.get('amount_cents'))
                payout_id,created=request_payout(conn,uid,amount,str(payload.get('method','')),str(payload.get('destination','')),str(payload.get('idempotency_key','')))
                conn.commit()
            except (ValueError,TypeError,RuntimeError) as exc:
                conn.rollback()
                return jsonify(error=str(exc)),400
            return jsonify(ok=True,payout_id=payout_id,created=created,status='requested',message='Request submitted for admin review. This is not a payment.'),201 if created else 200

    @bp.get('/api/admin/royalty-payouts')
    def admin_payout_list():
        uid=session.get('uid')
        if not uid: return jsonify(error='Sign in required'),401
        with connection_factory() as conn:
            user=conn.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user[0]!='admin': return jsonify(error='Admin access required'),403
            rows=list_requests(conn,limit=200)
            for row in rows:
                row.pop('destination_ciphertext',None)
            return jsonify(items=rows,currency='BDT',mode='manual_review')

    @bp.post('/api/admin/royalty-payouts/<int:payout_id>/status')
    def admin_payout_status(payout_id):
        uid=session.get('uid')
        if not uid: return jsonify(error='Sign in required'),401
        with connection_factory() as conn:
            user=conn.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user[0]!='admin': return jsonify(error='Admin access required'),403
            payload=request.get_json(silent=True) or {}
            try:
                changed=transition(conn,payout_id,uid,str(payload.get('status','')),str(payload.get('note','')),str(payload.get('provider_reference','')))
                conn.commit()
            except LookupError as exc:
                conn.rollback(); return jsonify(error=str(exc)),404
            except ValueError as exc:
                conn.rollback(); return jsonify(error=str(exc)),400
            return jsonify(ok=True,changed=changed,status=payload.get('status'),message='Status updated. External transfer is not initiated by this API.')

    @bp.post('/api/admin/royalty-payouts/<int:payout_id>/submit-transfer')
    def admin_submit_payout_transfer(payout_id):
        uid=session.get('uid')
        if not uid: return jsonify(error='Sign in required'),401
        with connection_factory() as conn:
            user=conn.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user[0]!='admin': return jsonify(error='Admin access required'),403
            row=conn.execute('SELECT * FROM creator_payout_requests WHERE id=?',(payout_id,)).fetchone()
            if not row: return jsonify(error='Payout request not found'),404
            if row['status'] not in ('approved','processing','failed'):
                return jsonify(error='Only approved, processing or failed payouts can be submitted/reconciled.'),409
            try:
                provider_config=config_from_env()
                destination=decrypt_destination(row['destination_ciphertext'])
            except PayoutProviderError as exc:
                return jsonify(error=str(exc),code=exc.code),503
            except Exception:
                return jsonify(error='Payout destination cannot be decrypted. Verify the configured encryption key.'),503
            idem=f'libraai-payout-{payout_id}'
            conn.execute('''INSERT INTO payout_provider_attempts(payout_id,idempotency_key,provider_name,status)
                VALUES(?,?,?, 'created') ON CONFLICT(payout_id) DO NOTHING''',(payout_id,idem,os.environ.get('LIBRAAI_PAYOUT_PROVIDER','generic_http')))
            attempt=conn.execute('SELECT * FROM payout_provider_attempts WHERE payout_id=?',(payout_id,)).fetchone()
            if attempt['idempotency_key'] != idem:
                return jsonify(error='Payout idempotency mismatch; manual reconciliation required.'),409
            if row['status'] in ('approved','failed'):
                try:
                    transition(conn,payout_id,uid,'processing','Submitted to configured payout gateway',attempt['provider_reference'] or '')
                except ValueError as exc:
                    return jsonify(error=str(exc)),409
            conn.execute("UPDATE payout_provider_attempts SET status='processing', attempts=attempts+1, last_error_code=NULL, updated_at=CURRENT_TIMESTAMP WHERE payout_id=?",(payout_id,))
            conn.commit()
        try:
            result=submit_transfer(provider_config,payout_id=payout_id,amount_cents=int(row['amount_cents']),currency=str(row['currency']),method=str(row['method']),destination=destination,idempotency_key=idem)
        except PayoutProviderError as exc:
            with connection_factory() as conn:
                status='unknown' if exc.uncertain else 'failed'
                conn.execute('UPDATE payout_provider_attempts SET status=?,last_error_code=?,updated_at=CURRENT_TIMESTAMP WHERE payout_id=?',(status,exc.code,payout_id))
                if not exc.uncertain:
                    try: transition(conn,payout_id,uid,'failed','Provider rejected transfer: '+exc.code)
                    except ValueError: pass
                conn.commit()
            return jsonify(error=str(exc),code=exc.code,reconciliation_required=exc.uncertain),502 if exc.uncertain else 400
        with connection_factory() as conn:
            conn.execute("UPDATE payout_provider_attempts SET status='accepted',provider_reference=?,last_error_code=NULL,updated_at=CURRENT_TIMESTAMP WHERE payout_id=?",(result['reference'],payout_id))
            try: transition(conn,payout_id,uid,'processing','Provider accepted transfer; awaiting signed final webhook or reconciliation',result['reference'])
            except ValueError: pass
            conn.commit()
        return jsonify(ok=True,payout_id=payout_id,status='processing',provider_status=result['provider_status'],provider_reference=result['reference'],message='Transfer initiated. It is not marked paid until a signed final webhook or reconciliation confirms settlement.'),202

    @bp.post('/api/admin/royalty-payouts/<int:payout_id>/reconcile')
    def admin_reconcile_payout_transfer(payout_id):
        uid=session.get('uid')
        if not uid: return jsonify(error='Sign in required'),401
        with connection_factory() as conn:
            user=conn.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user[0]!='admin': return jsonify(error='Admin access required'),403
            payout=conn.execute('SELECT * FROM creator_payout_requests WHERE id=?',(payout_id,)).fetchone()
            attempt=conn.execute('SELECT * FROM payout_provider_attempts WHERE payout_id=?',(payout_id,)).fetchone()
            if not payout or not attempt: return jsonify(error='Payout transfer attempt not found'),404
            if payout['status'] in ('paid','rejected'): return jsonify(error='Terminal payout state cannot be reconciled automatically.'),409
            try: provider_config=config_from_env()
            except PayoutProviderError as exc: return jsonify(error=str(exc),code=exc.code),503
        try: result=lookup_transfer(provider_config,idempotency_key=attempt['idempotency_key'])
        except PayoutProviderError as exc:
            return jsonify(error=str(exc),code=exc.code,reconciliation_required=True),502 if exc.uncertain else 404
        with connection_factory() as conn:
            payout=conn.execute('SELECT * FROM creator_payout_requests WHERE id=?',(payout_id,)).fetchone()
            try:
                if result['status']=='paid':
                    if payout['status']=='failed':
                        transition(conn,payout_id,uid,'processing','Provider reconciliation reopened failed state for verified settlement',result['reference'])
                    transition(conn,payout_id,uid,'paid','Provider reconciliation confirmed settlement',result['reference'])
                    attempt_status='paid'
                elif result['status']=='failed':
                    if payout['status']!='failed': transition(conn,payout_id,uid,'failed','Provider reconciliation confirmed transfer failure',result['reference'])
                    attempt_status='failed'
                else:
                    if payout['status'] in ('approved','failed'): transition(conn,payout_id,uid,'processing','Provider reconciliation found an in-flight transfer',result['reference'])
                    attempt_status='accepted' if result['status']=='accepted' else 'processing'
                conn.execute('UPDATE payout_provider_attempts SET status=?,provider_reference=COALESCE(?,provider_reference),last_error_code=NULL,updated_at=CURRENT_TIMESTAMP WHERE payout_id=?',(attempt_status,result['reference'] or None,payout_id))
                conn.commit()
            except (ValueError,LookupError) as exc:
                conn.rollback(); return jsonify(error=str(exc),reconciliation_required=True),409
        return jsonify(ok=True,payout_id=payout_id,status=result['status'],provider_reference=result['reference'],message='Provider reconciliation result recorded.'),200

    @bp.post('/api/payouts/webhook/generic')
    def payout_provider_webhook():
        raw=request.get_data(cache=True)
        try: provider_config=config_from_env()
        except PayoutProviderError: return jsonify(error='Payout webhook is not configured'),503
        signature=request.headers.get('X-LibraAI-Signature','')
        if not verify_webhook(raw,signature,provider_config.webhook_secret):
            return jsonify(error='Invalid webhook signature'),401
        try: payload=request.get_json(force=True)
        except Exception: return jsonify(error='Invalid JSON payload'),400
        if not isinstance(payload,dict): return jsonify(error='Invalid event payload'),400
        event_id=str(payload.get('event_id','')).strip(); status=str(payload.get('status','')).lower(); reference=str(payload.get('reference','')).strip()[:180]
        try: payout_id=int(payload.get('payout_id')); idem=str(payload.get('idempotency_key',''))
        except (ValueError,TypeError): return jsonify(error='Invalid payout reference'),400
        if not event_id or len(event_id)>160 or status not in ('paid','failed','processing') or not idem.startswith('libraai-payout-'):
            return jsonify(error='Invalid event fields'),400
        with connection_factory() as conn:
            attempt=conn.execute('SELECT * FROM payout_provider_attempts WHERE payout_id=?',(payout_id,)).fetchone()
            payout=conn.execute('SELECT * FROM creator_payout_requests WHERE id=?',(payout_id,)).fetchone()
            if not attempt or not payout or attempt['idempotency_key']!=idem:
                return jsonify(error='Unknown payout/idempotency key'),404
            if payout['status']=='paid' and status!='paid':
                return jsonify(error='A settled payout cannot be regressed by a webhook.'),409
            if payout['status']=='failed' and status=='paid':
                return jsonify(error='Failed payout needs manual reconciliation before settlement can be recorded.'),409
            try:
                conn.execute('INSERT INTO payout_provider_webhook_events(event_id,payout_id,event_status,provider_reference) VALUES(?,?,?,?)',(event_id,payout_id,status,reference or None))
            except sqlite3.IntegrityError:
                return jsonify(ok=True,duplicate=True),200
            try:
                if status=='paid':
                    if not reference: raise ValueError('A provider reference is required for paid status.')
                    if payout['status']!='paid': transition(conn,payout_id,0,'paid','Signed provider webhook confirmed settlement',reference)
                    conn.execute("UPDATE payout_provider_attempts SET status='paid',provider_reference=?,last_error_code=NULL,updated_at=CURRENT_TIMESTAMP WHERE payout_id=?",(reference,payout_id))
                elif status=='failed':
                    if payout['status'] not in ('failed','paid'): transition(conn,payout_id,0,'failed','Signed provider webhook reported failure',reference)
                    conn.execute("UPDATE payout_provider_attempts SET status='failed',provider_reference=?,last_error_code='provider_webhook_failed',updated_at=CURRENT_TIMESTAMP WHERE payout_id=?",(reference or None,payout_id))
                else:
                    conn.execute("UPDATE payout_provider_attempts SET status='processing',provider_reference=COALESCE(?,provider_reference),updated_at=CURRENT_TIMESTAMP WHERE payout_id=?",(reference or None,payout_id))
                conn.commit()
            except (ValueError,LookupError) as exc:
                conn.rollback(); return jsonify(error=str(exc)),409
        return jsonify(ok=True,accepted=True),200

    @bp.get('/api/admin/royalty-payouts/<int:payout_id>/destination')
    def admin_payout_destination(payout_id):
        uid=session.get('uid')
        if not uid: return jsonify(error='Sign in required'),401
        with connection_factory() as conn:
            user=conn.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user[0]!='admin': return jsonify(error='Admin access required'),403
            row=conn.execute('SELECT destination_ciphertext,destination_masked,method FROM creator_payout_requests WHERE id=?',(payout_id,)).fetchone()
            if not row: return jsonify(error='Payout request not found'),404
            try: destination=decrypt_destination(row['destination_ciphertext'])
            except Exception: return jsonify(error='Could not decrypt destination. Verify the original SECRET_KEY.'),503
            return jsonify(method=row['method'],destination=destination,masked=row['destination_masked'],sensitive=True)

    @bp.post('/api/admin/royalty-adjustments')
    def admin_royalty_adjustment():
        uid=session.get('uid')
        if not uid: return jsonify(error='Sign in required'),401
        with connection_factory() as conn:
            user=conn.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user[0]!='admin': return jsonify(error='Admin access required'),403
            payload=request.get_json(silent=True) or {}
            try:
                creator_id=int(payload.get('creator_user_id')); amount=int(payload.get('amount_cents'))
                reason=str(payload.get('reason','')).strip()[:300]; reference=str(payload.get('reference','')).strip()[:160]
                if creator_id<=0 or amount==0 or not reason or not reference: raise ValueError('creator_user_id, non-zero amount_cents, reason and unique reference are required.')
            except (ValueError,TypeError) as exc: return jsonify(error=str(exc)),400
            if not conn.execute("SELECT 1 FROM users WHERE id=? AND role='creator'",(creator_id,)).fetchone(): return jsonify(error='Creator not found'),404
            try:
                conn.execute('INSERT INTO royalty_adjustments(creator_user_id,amount_cents,reason,reference,actor_user_id) VALUES(?,?,?,?,?)',(creator_id,amount,reason,reference,uid))
                conn.commit()
            except Exception:
                conn.rollback(); return jsonify(error='Adjustment reference already exists or could not be recorded'),409
            return jsonify(ok=True,creator_user_id=creator_id,amount_cents=amount,reference=reference,note='Accounting adjustment recorded; no funds were transferred.')

    @bp.post('/api/admin/entitlements/reconcile')
    def admin_reconcile_entitlements():
        uid=session.get('uid')
        if not uid: return jsonify(error='Sign in required'),401
        with connection_factory() as conn:
            user=conn.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user[0]!='admin': return jsonify(error='Admin access required'),403
            from digital_entitlements import reconcile_historical_paid_orders
            payload=request.get_json(silent=True) or {}
            try: limit=int(payload.get('limit',5000))
            except (ValueError,TypeError): return jsonify(error='limit must be an integer'),400
            try:
                result=reconcile_historical_paid_orders(conn,limit)
                conn.commit()
            except Exception:
                conn.rollback(); raise
            return jsonify(ok=True,**result,note='Historical entitlement reconciliation only; order/payment states were not changed.')

    @bp.post('/api/admin/royalty-contracts')
    def set_contract():
        uid = session.get('uid')
        if not uid:
            return jsonify(error='Sign in required'),401
        with connection_factory() as conn:
            user = conn.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
            if not user or user[0] != 'admin':
                return jsonify(error='Admin access required'),403
            payload = request.get_json(silent=True) or {}
            try:
                book_id=int(payload['book_id']); creator_id=int(payload['creator_user_id']); bps=int(payload['royalty_bps'])
                if book_id<=0 or creator_id<=0 or not 0<=bps<=10000:
                    raise ValueError()
            except (ValueError,TypeError,KeyError):
                return jsonify(error='Invalid contract fields'),400
            if not conn.execute('SELECT 1 FROM books WHERE id=?',(book_id,)).fetchone():
                return jsonify(error='Book not found'),404
            if not conn.execute("SELECT 1 FROM users WHERE id=? AND role='creator'",(creator_id,)).fetchone():
                return jsonify(error='Creator not found'),404
            conn.execute('''INSERT INTO royalty_contracts(book_id,creator_user_id,royalty_bps)
                VALUES(?,?,?) ON CONFLICT(book_id) DO UPDATE SET
                creator_user_id=excluded.creator_user_id,royalty_bps=excluded.royalty_bps,active=1''',(book_id,creator_id,bps))
            conn.commit()
            return jsonify(ok=True)
    app.register_blueprint(bp)
