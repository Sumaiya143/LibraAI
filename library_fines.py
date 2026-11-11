"""Overdue library fine ledger for LibraAI.

Policy: 14-day loan term; BDT 10 per overdue calendar day, beginning the
calendar day after the due date. Amounts are stored as integer paisa.
Payments are not considered settled until an authorized admin verifies them.
"""
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import os

LOAN_DAYS = 14
FINE_PER_DAY_PAISE = int(os.environ.get("LIBRAAI_FINE_PER_DAY_PAISE", "1000"))
if FINE_PER_DAY_PAISE <= 0:
    raise RuntimeError("LIBRAAI_FINE_PER_DAY_PAISE must be a positive integer.")
CURRENCY = "BDT"


def policy_date(now=None):
    """Use the institution's configured local date (Asia/Dhaka by default)."""
    try:
        zone = ZoneInfo(os.environ.get("LIBRAAI_LIBRARY_TIMEZONE", "Asia/Dhaka"))
    except Exception:
        zone = timezone(timedelta(hours=6))
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=zone)
    return now.astimezone(zone).date()


class FineError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def setup(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS library_fines (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        loan_id INTEGER NOT NULL UNIQUE,
        overdue_days INTEGER NOT NULL DEFAULT 0 CHECK(overdue_days >= 0),
        amount_paise INTEGER NOT NULL DEFAULT 0 CHECK(amount_paise >= 0),
        currency TEXT NOT NULL DEFAULT 'BDT',
        status TEXT NOT NULL DEFAULT 'unpaid' CHECK(status IN ('unpaid','paid')),
        assessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        paid_at TEXT,
        payment_id INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_library_fines_user_status
        ON library_fines(user_id,status);
    CREATE TABLE IF NOT EXISTS library_fine_payments (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        amount_paise INTEGER NOT NULL CHECK(amount_paise > 0),
        currency TEXT NOT NULL DEFAULT 'BDT',
        reference TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending'
            CHECK(status IN ('pending','approved','rejected')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TEXT,
        reviewer_id INTEGER,
        UNIQUE(user_id,reference)
    );
    CREATE INDEX IF NOT EXISTS idx_library_fine_payments_status
        ON library_fine_payments(status,created_at);
    """)


def _as_date(value):
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _now_text(now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).isoformat(timespec="seconds")


def assess_user_fines(conn, user_id, as_of=None):
    """Reconcile unpaid fines from loan due/return dates; safe to call repeatedly."""
    as_of = as_of or policy_date()
    rows = conn.execute(
        "SELECT id,user_id,status,due,returned_at FROM loans WHERE user_id=?",
        (user_id,),
    ).fetchall()
    assessed = 0
    for loan in rows:
        status = str(loan["status"] or "").lower()
        if status not in ("borrowed", "renewed", "returned"):
            continue
        due = _as_date(loan["due"])
        if due is None:
            continue
        returned_at = loan["returned_at"] if "returned_at" in loan.keys() else None
        if status == "returned":
            # Legacy returned loans without a timestamp cannot be fairly fined.
            if not returned_at:
                continue
            effective = _as_date(returned_at)
        else:
            effective = as_of
        overdue_days = max(0, (effective - due).days) if effective else 0
        amount = overdue_days * FINE_PER_DAY_PAISE
        existing = conn.execute(
            "SELECT id,status FROM library_fines WHERE loan_id=?", (loan["id"],)
        ).fetchone()
        if existing and existing["status"] == "paid":
            continue
        if amount <= 0:
            continue
        conn.execute(
            """INSERT INTO library_fines(user_id,loan_id,overdue_days,amount_paise,status,assessed_at)
               VALUES(?,?,?,?, 'unpaid', ?)
               ON CONFLICT(loan_id) DO UPDATE SET
                 overdue_days=excluded.overdue_days,
                 amount_paise=excluded.amount_paise,
                 assessed_at=excluded.assessed_at
               WHERE library_fines.status='unpaid'""",
            (user_id, loan["id"], overdue_days, amount, _now_text()),
        )
        assessed += amount
    return assessed


def outstanding_balance(conn, user_id, as_of=None):
    assess_user_fines(conn, user_id, as_of)
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_paise),0) FROM library_fines WHERE user_id=? AND status='unpaid'",
        (user_id,),
    ).fetchone()
    return int(row[0] or 0)


def user_fines(conn, user_id, as_of=None):
    assess_user_fines(conn, user_id, as_of)
    return conn.execute(
        """SELECT f.*, b.title AS book_title
           FROM library_fines f
           LEFT JOIN loans l ON l.id=f.loan_id
           LEFT JOIN books b ON b.id=l.book_id
           WHERE f.user_id=? ORDER BY f.id DESC""",
        (user_id,),
    ).fetchall()


def submit_payment(conn, user_id, reference, as_of=None):
    reference = (reference or "").strip()
    if not reference or len(reference) > 120:
        raise FineError("invalid_reference", "Enter a valid payment reference (1–120 characters).")
    active_overdue = conn.execute(
        """SELECT COUNT(*) FROM loans
           WHERE user_id=? AND lower(status) IN ('borrowed','renewed') AND due<?""",
        (user_id, (as_of or policy_date()).isoformat()),
    ).fetchone()[0]
    if active_overdue:
        raise FineError("return_overdue_book_first", "Return all overdue books before settling the final fine.")
    amount = outstanding_balance(conn, user_id, as_of)
    if amount <= 0:
        raise FineError("no_fine_due", "There is no unpaid library fine.")
    pending = conn.execute(
        "SELECT 1 FROM library_fine_payments WHERE user_id=? AND status='pending' LIMIT 1",
        (user_id,),
    ).fetchone()
    if pending:
        raise FineError("payment_pending", "A fine payment is already awaiting verification.")
    try:
        cur = conn.execute(
            """INSERT INTO library_fine_payments(user_id,amount_paise,reference)
               VALUES(?,?,?)""",
            (user_id, amount, reference),
        )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise FineError("duplicate_reference", "This payment reference has already been submitted.") from exc
        raise
    conn.commit()
    return {"payment_id": cur.lastrowid, "amount_paise": amount, "currency": CURRENCY}


def approve_payment(conn, payment_id, reviewer_id, now=None):
    now_text = _now_text(now)
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        payment = conn.execute(
            "SELECT * FROM library_fine_payments WHERE id=?", (payment_id,)
        ).fetchone()
        if payment is None:
            raise FineError("not_found", "Payment submission not found.")
        if payment["status"] != "pending":
            raise FineError("already_reviewed", "This payment submission has already been reviewed.")
        current = outstanding_balance(conn, payment["user_id"])
        if current != int(payment["amount_paise"]):
            raise FineError("amount_changed", "The outstanding fine changed; reject this submission and request a new payment.")
        conn.execute(
            """UPDATE library_fines SET status='paid',paid_at=?,payment_id=?
               WHERE user_id=? AND status='unpaid'""",
            (now_text, payment_id, payment["user_id"]),
        )
        conn.execute(
            """UPDATE library_fine_payments SET status='approved',reviewed_at=?,reviewer_id=?
               WHERE id=? AND status='pending'""",
            (now_text, reviewer_id, payment_id),
        )
        conn.commit()
        return {"approved": True, "amount_paise": int(payment["amount_paise"])}
    except Exception:
        conn.rollback()
        raise


def reject_payment(conn, payment_id, reviewer_id, now=None):
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            """UPDATE library_fine_payments SET status='rejected',reviewed_at=?,reviewer_id=?
               WHERE id=? AND status='pending'""",
            (_now_text(now), reviewer_id, payment_id),
        )
        if cur.rowcount != 1:
            raise FineError("not_found_or_reviewed", "Pending payment submission not found.")
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def clearance_eligible(conn, user_id, as_of=None):
    return outstanding_balance(conn, user_id, as_of) == 0
