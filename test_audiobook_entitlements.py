import sqlite3
import unittest
from digital_entitlements import setup, grant_paid_order, has_access

class AudiobookEntitlementTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.c.executescript('''
            CREATE TABLE users(id INTEGER PRIMARY KEY);
            CREATE TABLE orders(id INTEGER PRIMARY KEY,user_id INTEGER,status TEXT);
            CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,book_id INTEGER,format TEXT,unit_price_cents INTEGER,quantity INTEGER);
            CREATE TABLE licensed_documents(id INTEGER PRIMARY KEY,book_id INTEGER,access_policy TEXT);
            CREATE TABLE audiobook_assets(book_id INTEGER,active INTEGER,license_status TEXT,access_policy TEXT,license_expires_at TEXT);
            INSERT INTO orders VALUES(7,3,'Paid — fulfillment pending');
            INSERT INTO order_items VALUES(1,7,42,'Audiobook',1200,1);
            INSERT INTO audiobook_assets VALUES(42,1,'active','licensed',NULL);
        ''')
        setup(self.c)
    def tearDown(self): self.c.close()
    def test_paid_order_grants_audio_entitlement_when_license_active(self):
        self.assertEqual(grant_paid_order(self.c,7),1)
        self.c.execute("UPDATE orders SET status='Completed' WHERE id=7")
        self.assertTrue(has_access(self.c,3,42))
    def test_no_entitlement_when_audio_license_revoked_before_settlement(self):
        self.c.execute("UPDATE audiobook_assets SET license_status='revoked',active=0 WHERE book_id=42")
        self.assertEqual(grant_paid_order(self.c,7),0)
        self.assertFalse(has_access(self.c,3,42))

if __name__=='__main__': unittest.main()
