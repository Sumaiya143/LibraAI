import sqlite3, unittest
from admin_payouts import list_payouts

class AdminPayoutsTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.execute('CREATE TABLE merchant_payouts(id INTEGER PRIMARY KEY,merchant_id INTEGER,amount TEXT,currency TEXT,status TEXT,created TEXT)')
        self.c.execute('CREATE TABLE payout_review_events(id INTEGER PRIMARY KEY,payout_id INTEGER,reviewer_id INTEGER,previous_status TEXT,new_status TEXT,reference TEXT,created TEXT)')
        self.c.execute("INSERT INTO merchant_payouts VALUES(1,3,'100.00','BDT','manual_review','today')")
        self.c.execute("INSERT INTO payout_review_events VALUES(1,1,2,'manual_review','approved',NULL,'today')")
    def tearDown(self):self.c.close()
    def test_lists_payouts_and_events(self):
        r=list_payouts(self.c)
        self.assertEqual(r['payouts'][0]['id'],1)
        self.assertEqual(r['review_events'][0]['new_status'],'approved')
    def test_bounded_limit(self):
        for value in (0,101,-1,'1',True):
            with self.subTest(value=value),self.assertRaises(ValueError):list_payouts(self.c,value)
    def test_empty_ledger(self):
        self.c.execute('DELETE FROM merchant_payouts');self.c.execute('DELETE FROM payout_review_events')
        self.assertEqual(list_payouts(self.c)['payouts'],[])
    def test_limit(self):
        self.assertEqual(len(list_payouts(self.c,1)['payouts']),1)
if __name__=='__main__':unittest.main()
