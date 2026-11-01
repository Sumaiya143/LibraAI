import os, sqlite3, unittest
from royalty_payouts import setup, balance, request_payout, transition, list_requests, decrypt_destination
from royalty_engine import setup as setup_royalty

class CreatorPayoutTests(unittest.TestCase):
    def setUp(self):
        self.old_secret=os.environ.get('SECRET_KEY')
        os.environ['SECRET_KEY']='test-secret-key-for-creator-payouts-0123456789'
        self.db=sqlite3.connect(':memory:'); self.db.row_factory=sqlite3.Row
        self.db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT,email TEXT,role TEXT)')
        self.db.execute("INSERT INTO users VALUES(7,'Creator','creator@example.test','creator')")
        setup_royalty(self.db); setup(self.db)
        self.db.execute('INSERT INTO royalty_contracts VALUES(1,7,1250,1)')
        self.db.execute('INSERT INTO royalty_ledger(order_item_id,order_id,book_id,creator_user_id,gross_cents,royalty_cents) VALUES(11,5,1,7,10000,2500)')
        self.db.commit()
    def tearDown(self):
        self.db.close()
        if self.old_secret is None: os.environ.pop('SECRET_KEY',None)
        else: os.environ['SECRET_KEY']=self.old_secret
    def test_request_reserves_balance_and_encrypts_destination(self):
        pid,created=request_payout(self.db,7,1000,'bkash','01712345678','request-key-0001')
        self.assertTrue(created)
        self.assertEqual(balance(self.db,7)['available_cents'],1500)
        row=self.db.execute('SELECT * FROM creator_payout_requests WHERE id=?',(pid,)).fetchone()
        self.assertNotIn('01712345678',row['destination_ciphertext'])
        self.assertEqual(decrypt_destination(row['destination_ciphertext']),'01712345678')
        self.assertEqual(row['destination_masked'][-4:],'5678')
    def test_idempotency(self):
        a=request_payout(self.db,7,500,'nagad','01712345678','request-key-0002')
        b=request_payout(self.db,7,500,'nagad','01712345678','request-key-0002')
        self.assertEqual(a[0],b[0]); self.assertFalse(b[1])
    def test_cannot_overdraw(self):
        with self.assertRaises(ValueError): request_payout(self.db,7,2501,'bkash','01712345678','request-key-0003')
    def test_paid_requires_real_unique_reference_and_consumes_balance(self):
        pid,_=request_payout(self.db,7,1000,'bkash','01712345678','request-key-0004')
        transition(self.db,pid,1,'approved')
        transition(self.db,pid,1,'processing')
        with self.assertRaises(ValueError): transition(self.db,pid,1,'paid')
        transition(self.db,pid,1,'paid',reference='TXN-ABC-001')
        self.assertEqual(balance(self.db,7)['paid_cents'],1000)
        with self.assertRaises(ValueError):
            pid2,_=request_payout(self.db,7,100,'nagad','01712345678','request-key-0005')
            transition(self.db,pid2,1,'approved')
            transition(self.db,pid2,1,'paid',reference='TXN-ABC-001')
    def test_rejected_request_releases_reserved_balance(self):
        pid,_=request_payout(self.db,7,1000,'bkash','01712345678','request-key-0006')
        transition(self.db,pid,1,'rejected',note='Destination invalid')
        self.assertEqual(balance(self.db,7)['available_cents'],2500)
    def test_audit_events_are_written(self):
        pid,_=request_payout(self.db,7,1000,'bkash','01712345678','request-key-0007')
        transition(self.db,pid,1,'approved',note='Verified creator')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM creator_payout_events WHERE payout_id=?',(pid,)).fetchone()[0],2)

if __name__=='__main__': unittest.main()
