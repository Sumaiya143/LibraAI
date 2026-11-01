import unittest, sqlite3
from royalty_engine import setup, accrue, cents, creator_report

class RoyaltyTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:'); setup(self.db)
        self.db.execute('INSERT INTO royalty_contracts VALUES (1,7,1250,1)')
    def tearDown(self): self.db.close()
    def test_currency_rounding(self):
        self.assertEqual(cents('10.235'),1024)
        with self.assertRaises(ValueError): cents('-1')
    def test_idempotent_accrual(self):
        self.assertEqual(accrue(self.db,11,5,1,'10.00'),125)
        self.assertEqual(accrue(self.db,11,5,1,'10.00'),125)
        self.assertEqual(creator_report(self.db,7)[0]['items'],1)
    def test_no_contract(self): self.assertIsNone(accrue(self.db,12,5,2,'5.00'))
    def test_fractional_royalty(self):
        self.assertEqual(accrue(self.db,13,5,1,'0.01'),0)
if __name__=='__main__': unittest.main()
