import sqlite3, unittest
from digital_entitlements import setup, reconcile_historical_paid_orders, has_access

class EntitlementReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:'); self.db.row_factory=sqlite3.Row
        self.db.executescript('''
          CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,status TEXT);
          CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,book_id INTEGER,format TEXT,unit_price_cents INTEGER,quantity INTEGER,line_total_cents INTEGER);
          CREATE TABLE licensed_documents(id INTEGER PRIMARY KEY,book_id INTEGER,access_policy TEXT);
          CREATE TABLE refund_item_allocations(id INTEGER PRIMARY KEY,refund_id INTEGER,order_item_id INTEGER,amount_cents INTEGER);
          CREATE TABLE refund_requests(id INTEGER PRIMARY KEY,state TEXT);
        ''')
        setup(self.db)
        self.db.execute("INSERT INTO orders VALUES(1,7,'Completed')")
        self.db.execute("INSERT INTO order_items VALUES(11,1,3,'epub',500,1,500)")
        self.db.execute("INSERT INTO licensed_documents VALUES(1,3,'licensed')")
        self.db.commit()
    def tearDown(self): self.db.close()
    def test_reconciliation_is_idempotent_and_does_not_change_order(self):
        first=reconcile_historical_paid_orders(self.db)
        second=reconcile_historical_paid_orders(self.db)
        self.assertEqual(first['entitlements_granted'],1)
        self.assertEqual(second['entitlements_granted'],0)
        self.assertEqual(self.db.execute('SELECT status FROM orders WHERE id=1').fetchone()[0],'Completed')
        self.assertTrue(has_access(self.db,7,3))
    def test_unlicensed_historical_order_is_not_granted(self):
        self.db.execute('DELETE FROM licensed_documents'); self.db.commit()
        self.assertEqual(reconcile_historical_paid_orders(self.db)['entitlements_granted'],0)

if __name__=='__main__': unittest.main()
