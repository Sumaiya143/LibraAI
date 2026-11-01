import unittest
from test_refund_engine import RefundTests
from refund_integrity_audit import audit_refunds

class RefundAuditTests(RefundTests):
    def test_clean_refund(self):
        self.request(1000)
        self.assertEqual(audit_refunds(self.db)['issue_count'], 0)

    def test_refunded_without_reference(self):
        rid=self.request(1000)
        self.db.execute("UPDATE refund_requests SET state='refunded' WHERE id=?", (rid,))
        self.assertIn('confirmed_refund_missing_provider_reference',audit_refunds(self.db)['issues'][0]['issues'])

    def test_overallocated_refunds(self):
        rid=self.request(1000)
        self.db.execute('UPDATE refund_requests SET amount_cents=999999 WHERE id=?',(rid,))
        self.assertIn('refunds_exceed_payment',audit_refunds(self.db)['issues'][0]['issues'])

    def test_attempt_order_mismatch(self):
        rid=self.request(1000)
        self.db.execute('UPDATE refund_requests SET order_id=123 WHERE id=?',(rid,))
        self.assertIn('attempt_order_mismatch',audit_refunds(self.db)['issues'][0]['issues'])

    def test_limit_validation(self):
        for value in (0,501,True,'5'):
            with self.assertRaises(ValueError):audit_refunds(self.db,value)

    def test_missing_order_detected(self):
        rid = self.request(1000)
        self.db.execute('UPDATE refund_requests SET order_id=987654 WHERE id=?', (rid,))
        self.assertIn('missing_order', audit_refunds(self.db)['issues'][0]['issues'])

    def test_missing_attempt_detected(self):
        rid = self.request(1000)
        self.db.execute('UPDATE refund_requests SET attempt_id=987654 WHERE id=?', (rid,))
        self.assertIn('missing_payment_attempt', audit_refunds(self.db)['issues'][0]['issues'])

    def test_paginated_audit_does_not_repeat_refunds(self):
        first = self.request(1000)
        second = self.request(1000)
        page1 = audit_refunds(self.db, limit=1, offset=0)
        page2 = audit_refunds(self.db, limit=1, offset=1)
        self.assertTrue(page1['has_more'])
        self.assertFalse(page2['has_more'])
        self.assertEqual(page1['checked'], 1)
        self.assertEqual(page2['checked'], 1)
        self.db.execute("UPDATE refund_requests SET state='refunded' WHERE id=?", (second,))
        self.assertEqual(audit_refunds(self.db, 1, 0)['issues'][0]['refund_id'], second)
        self.assertEqual(audit_refunds(self.db, 1, 1)['issue_count'], 0)

    def test_offset_rejects_invalid_values(self):
        for value in (-1, True, '1', 1000000001):
            with self.assertRaises(ValueError):
                audit_refunds(self.db, offset=value)

    def test_unknown_refund_state_detected(self):
        rid = self.request(1000)
        self.db.execute('PRAGMA ignore_check_constraints=ON')
        self.db.execute("UPDATE refund_requests SET state='mystery' WHERE id=?", (rid,))
        self.assertIn('invalid_refund_state', audit_refunds(self.db)['issues'][0]['issues'])
