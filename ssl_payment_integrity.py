"""Atomic SSLCommerz reconciliation after server-to-server validation."""
from decimal import Decimal, InvalidOperation


def amount(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('invalid amount')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError('invalid amount') from exc
    if not result.is_finite() or result <= 0 or result.as_tuple().exponent < -2:
        raise ValueError('invalid amount')
    return result.quantize(Decimal('0.01'))


def reconcile_sslcommerz(conn, transaction_id, validation_id, provider_result):
    """Return confirmed/duplicate or raise ValueError/LookupError/RuntimeError.

    A callback is never payment proof: caller must obtain provider_result from the
    SSLCommerz validation endpoint. This routine additionally matches stored order.
    """
    if not isinstance(provider_result, dict) or not isinstance(transaction_id, str) or not transaction_id:
        raise ValueError('Invalid provider response')
    if not isinstance(validation_id, str) or not validation_id:
        raise ValueError('Invalid validation ID')
    if (provider_result.get('status') not in ('VALID', 'VALIDATED')
            or provider_result.get('tran_id') != transaction_id
            or provider_result.get('currency') != 'BDT'):
        raise ValueError('Provider details mismatch')
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        attempt = conn.execute('SELECT * FROM payment_attempts WHERE transaction_id=?', (transaction_id,)).fetchone()
        if not attempt or attempt['provider'] != 'sslcommerz':
            raise LookupError('Unknown payment attempt')
        order = conn.execute('SELECT * FROM orders WHERE id=?', (attempt['order_id'],)).fetchone()
        if not order or amount(provider_result.get('amount')) != amount(order['amount']):
            raise ValueError('Payment amount mismatch')
        if attempt['status'] == 'validated':
            if attempt['validation_id'] == validation_id and order['status'] == 'paid':
                return 'duplicate'
            raise RuntimeError('Conflicting validation')
        if order['status'] != 'pending' or attempt['status'] != 'initiated':
            raise RuntimeError('Order is not pending')
        updated = conn.execute("UPDATE payment_attempts SET status='validated',validation_id=? WHERE id=? AND status='initiated'", (validation_id, attempt['id']))
        if updated.rowcount != 1:
            raise RuntimeError('Concurrent payment transition')
        paid = conn.execute("UPDATE orders SET status='paid' WHERE id=? AND status='pending'", (order['id'],))
        if paid.rowcount != 1:
            raise RuntimeError('Concurrent order transition')
        conn.execute('INSERT OR IGNORE INTO library(user_id,book_id) VALUES(?,?)', (order['user_id'], order['book_id']))
        conn.execute('INSERT INTO payment_events(transaction_id,event) VALUES(?,?)', (transaction_id, 'validated'))
        return 'confirmed'
