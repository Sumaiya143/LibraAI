"""Immutable, append-only payment reconciliation audit records (no secrets)."""
import json

ALLOWED = {'confirmed', 'mismatch', 'replayed', 'conflict', 'unknown'}

def install(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS payment_audit_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      provider TEXT NOT NULL,
      payment_id TEXT NOT NULL,
      order_id INTEGER,
      outcome TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    connection.execute('CREATE INDEX IF NOT EXISTS idx_payment_audit_payment ON payment_audit_events(provider,payment_id)')

def record(connection, provider, payment_id, order_id, outcome):
    if outcome not in ALLOWED or provider != 'bkash':
        raise ValueError('Invalid audit event')
    connection.execute('INSERT INTO payment_audit_events(provider,payment_id,order_id,outcome) VALUES(?,?,?,?)',
                       (provider, payment_id, order_id, outcome))
