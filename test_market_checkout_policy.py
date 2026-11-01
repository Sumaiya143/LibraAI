import sqlite3
import unittest
from market_checkout_policy import validate_sale, SalePolicyError

class SalePolicyTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.executescript('''CREATE TABLE licensed_documents(id INTEGER PRIMARY KEY,book_id INTEGER,rights_holder TEXT,license_reference TEXT,access_policy TEXT);
        CREATE TABLE licensed_chunks(id INTEGER PRIMARY KEY,document_id INTEGER,content TEXT);''')
    def tearDown(self): self.db.close()
    def test_demo_permitted(self): validate_sale(self.db,[(3,1,'eBook')],'',production=False)
    def test_unlicensed_rejected(self):
        with self.assertRaises(SalePolicyError): validate_sale(self.db,[(3,1,'eBook')],'',production=True)
    def test_sample_rejected(self):
        self.db.execute("INSERT INTO licensed_documents VALUES(1,3,'Publisher','ref','sample')")
        self.db.execute("INSERT INTO licensed_chunks VALUES(1,1,'text')")
        with self.assertRaises(SalePolicyError): validate_sale(self.db,[(3,1,'eBook')],'',production=True)
    def test_missing_content_rejected(self):
        self.db.execute("INSERT INTO licensed_documents VALUES(1,3,'Publisher','ref','licensed')")
        with self.assertRaises(SalePolicyError): validate_sale(self.db,[(3,1,'eBook')],'',production=True)
    def test_licensed_content_allowed(self):
        self.db.execute("INSERT INTO licensed_documents VALUES(1,3,'Publisher','ref','licensed')")
        self.db.execute("INSERT INTO licensed_chunks VALUES(1,1,'Real licensed content')")
        validate_sale(self.db,[(3,1,'eBook')],'',production=True)
    def test_print_requires_address(self):
        with self.assertRaises(SalePolicyError): validate_sale(self.db,[(3,1,'Print')],'',production=True)
    def test_print_with_address_allowed(self): validate_sale(self.db,[(3,1,'Print')],'House 10, Road 12, Dhaka',production=True)
    def test_unsupported_format_rejected(self):
        with self.assertRaises(SalePolicyError): validate_sale(self.db,[(3,1,'Audio')],'',production=True)

if __name__=='__main__': unittest.main()
