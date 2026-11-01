"""Fail-closed commercial inventory and content-rights validation."""
import os

class SalePolicyError(ValueError):
    pass

def validate_sale(conn, rows, address, *, production=None):
    """Check selected cart rows before stock is reserved or an order is created.

    Non-production demo data remains usable; production digital sales require
    a recorded licensed document and an actual non-empty licensed chunk.
    """
    if production is None:
        production = os.environ.get('LIBRAAI_ENV') == 'production'
    if not production:
        return
    if not rows:
        raise SalePolicyError('Cart is empty')
    for row in rows:
        book_id, quantity, fmt = row[0], row[1], row[2]
        if fmt not in ('eBook', 'Print'):
            raise SalePolicyError('Unsupported commercial format')
        if fmt == 'Print':
            if not address or len(address.strip()) < 10:
                raise SalePolicyError('Delivery address required for print orders')
        else:
            try:
                allowed = conn.execute('''SELECT 1 FROM licensed_documents d
                    JOIN licensed_chunks c ON c.document_id=d.id
                    WHERE d.book_id=? AND d.access_policy='licensed'
                      AND LENGTH(TRIM(d.rights_holder))>0
                      AND LENGTH(TRIM(d.license_reference))>0
                      AND LENGTH(TRIM(c.content))>0 LIMIT 1''', (book_id,)).fetchone()
            except Exception as exc:
                raise SalePolicyError('Licensed content inventory is not configured') from exc
            if not allowed:
                raise SalePolicyError('This eBook is not licensed and ready for delivery')
