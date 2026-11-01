import sqlite3
import unittest
from mixed_fulfillment_audit import inspect_order

class MixedFulfillmentAuditTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.row_factory=sqlite3.Row
        self.c.executescript('''
        CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,status TEXT,address TEXT);
        CREATE TABLE order_items(order_id INTEGER,book_id INTEGER,format TEXT,quantity INTEGER);
        CREATE TABLE payment_attempts(order_id INTEGER,state TEXT);
        CREATE TABLE print_shipments(order_id INTEGER,state TEXT);
        CREATE TABLE licensed_documents(book_id INTEGER,access_policy TEXT);
        CREATE TABLE digital_entitlements(order_id INTEGER,user_id INTEGER,book_id INTEGER);
        INSERT INTO orders VALUES(1,7,'Processing','Dhaka');
        INSERT INTO order_items VALUES(1,11,'print',1);
        INSERT INTO order_items VALUES(1,12,'ebook',1);
        INSERT INTO payment_attempts VALUES(1,'paid');
        INSERT INTO print_shipments VALUES(1,'packing');
        INSERT INTO licensed_documents VALUES(12,'licensed');
        INSERT INTO digital_entitlements VALUES(1,7,12);
        ''')
    def tearDown(self): self.c.close()
    def test_complete_mixed_order(self):
        r=inspect_order(self.c,1)
        self.assertTrue(r['ready']); self.assertEqual((r['print_line_count'],r['digital_line_count']),(1,1))
    def test_missing_entitlement(self):
        self.c.execute('DELETE FROM digital_entitlements')
        self.assertIn('digital_fulfillment_incomplete',inspect_order(self.c,1)['issues'])
    def test_missing_license(self):
        self.c.execute('DELETE FROM licensed_documents')
        self.assertEqual(inspect_order(self.c,1)['digital_exceptions'][0]['reason'],'licensed_document_missing')
    def test_missing_shipping(self):
        self.c.execute('DELETE FROM print_shipments')
        self.assertIn('print_shipment_not_started',inspect_order(self.c,1)['issues'])
    def test_unverified_payment(self):
        self.c.execute('DELETE FROM payment_attempts')
        self.assertIn('paid_status_without_verified_payment',inspect_order(self.c,1)['issues'])
    def test_paid_attempt_with_unpaid_order_status(self):
        self.c.execute("UPDATE orders SET status='Pending' WHERE id=1")
        result = inspect_order(self.c, 1)
        self.assertIn('verified_payment_without_fulfillment_status', result['issues'])
        self.assertFalse(result['ready'])

    def test_duplicate_paid_attempts_flagged_for_manual_review(self):
        self.c.execute("INSERT INTO payment_attempts VALUES(1,'paid')")
        result = inspect_order(self.c, 1)
        self.assertIn('multiple_paid_payment_attempts_review_required', result['issues'])
        self.assertFalse(result['ready'])

    def test_failed_attempt_does_not_count_as_duplicate_payment(self):
        self.c.execute("INSERT INTO payment_attempts VALUES(1,'failed')")
        self.assertTrue(inspect_order(self.c, 1)['ready'])

    def test_unknown_format(self):
        self.c.execute("INSERT INTO order_items VALUES(1,13,'unknown',1)")
        self.assertIn('unknown_item_format',inspect_order(self.c,1)['issues'])
    def test_invalid_quantities(self):
        for qty in (0, -1, None, 'invalid'):
            with self.subTest(qty=qty):
                self.c.execute('UPDATE order_items SET quantity=? WHERE book_id=11', (qty,))
                self.assertIn('invalid_item_quantity', inspect_order(self.c, 1)['issues'])

    def test_unpaid_shipment_detected(self):
        self.c.execute("UPDATE payment_attempts SET state='failed'")
        self.assertIn('shipment_without_verified_payment', inspect_order(self.c, 1)['issues'])

    def test_unpaid_entitlement_detected(self):
        self.c.execute('DELETE FROM payment_attempts')
        self.assertIn('digital_access_without_verified_payment', inspect_order(self.c, 1)['issues'])

    def test_wrong_customer_entitlement_detected(self):
        self.c.execute('UPDATE digital_entitlements SET user_id=999')
        self.assertIn('unexpected_digital_entitlement', inspect_order(self.c, 1)['issues'])

    def test_entitlement_for_non_ordered_book_detected(self):
        self.c.execute('UPDATE digital_entitlements SET book_id=999')
        self.assertIn('unexpected_digital_entitlement', inspect_order(self.c, 1)['issues'])

    def test_shipment_for_ebook_only_detected(self):
        self.c.execute("DELETE FROM order_items WHERE format='print'")
        self.assertIn('shipment_without_print_items', inspect_order(self.c, 1)['issues'])

    def test_invalid_shipment_state_detected(self):
        self.c.execute("UPDATE print_shipments SET state='mystery'")
        self.assertIn('invalid_shipment_state', inspect_order(self.c, 1)['issues'])

    def test_duplicate_entitlement_detected(self):
        self.c.execute('INSERT INTO digital_entitlements VALUES(1,7,12)')
        self.assertIn('duplicate_digital_entitlements_review_required', inspect_order(self.c, 1)['issues'])

    def test_invalid_order(self):
        with self.assertRaises(ValueError): inspect_order(self.c,0)
