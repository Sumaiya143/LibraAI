"""Defensive payment reconciliation: verified provider data only, no trust in browser callback."""
from decimal import Decimal, InvalidOperation
from payment_audit import install as install_payment_audit, record as record_payment_audit


def canonical_amount(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('Invalid amount')
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Invalid amount')
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
        raise ValueError('Invalid amount')
    return amount.quantize(Decimal('0.01'))


def verify_bkash_result(result, payment_id, order):
    """Validate execute/query response against the stored order before any mutation."""
    if not isinstance(result, dict) or not isinstance(payment_id, str) or not payment_id:
        return False
    if result.get('transactionStatus') != 'Completed':
        return False
    if result.get('paymentID') != payment_id or result.get('currency') != 'BDT':
        return False
    # Transaction ID is provider evidence, needed for reconciliation and replay defense.
    trx_id = result.get('trxID')
    if not isinstance(trx_id, str) or not (1 <= len(trx_id) <= 128):
        return False
    try:
        return canonical_amount(result.get('amount')) == canonical_amount(order['amount'])
    except (ValueError, KeyError, TypeError):
        return False


def reconcile_bkash(db_connection, payment_id, result):
    """Reconcile and audit in one SQLite transaction; never trust callback parameters."""
    with db_connection as c:
        c.execute('BEGIN IMMEDIATE')
        install_payment_audit(c)
        attempt = c.execute('SELECT * FROM bkash_attempts WHERE payment_id=?', (payment_id,)).fetchone()
        order = c.execute('SELECT * FROM orders WHERE id=?', (attempt['order_id'],)).fetchone() if attempt else None
        order_id = attempt['order_id'] if attempt else None
        if not attempt:
            outcome = 'unknown'
        elif not order or order['user_id'] != attempt['user_id'] or not verify_bkash_result(result, payment_id, order):
            outcome = 'mismatch'
        else:
            trx_id = result['trxID']
            previous = c.execute('SELECT order_id FROM bkash_attempts WHERE trx_id=?', (trx_id,)).fetchone()
            if previous and previous['order_id'] != order['id']:
                outcome = 'replayed'
            elif attempt['status'] == 'validated':
                outcome = 'confirmed' if attempt['trx_id'] == trx_id and order['status'] == 'paid' else 'conflict'
            elif order['status'] != 'pending':
                outcome = 'conflict'
            else:
                updated = c.execute("UPDATE bkash_attempts SET status='validated',trx_id=? WHERE id=? AND status='initiated'", (trx_id, attempt['id']))
                if updated.rowcount != 1:
                    outcome = 'conflict'
                else:
                    paid = c.execute("UPDATE orders SET status='paid' WHERE id=? AND status='pending'", (order['id'],))
                    if paid.rowcount != 1:
                        raise RuntimeError('Atomic payment transition failed')
                    c.execute('INSERT OR IGNORE INTO library(user_id,book_id) VALUES(?,?)', (order['user_id'], order['book_id']))
                    outcome = 'confirmed'
        record_payment_audit(c, 'bkash', payment_id, order_id, outcome)
        return outcome
