"""Regression: payment callbacks must redirect to an actual order page."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent

class PaymentReturnNavigationTests(unittest.TestCase):
    def test_all_payment_return_links_target_my_orders(self):
        source=(ROOT/'payment_routes.py').read_text()
        self.assertNotIn("redirect('/orders?", source)
        self.assertIn("redirect('/my/orders?payment=confirmed'", source)
        self.assertIn("redirect('/my/orders?payment=unverified'", source)
        self.assertIn("redirect('/my/orders?payment=processing'", source)
    def test_destination_is_registered(self):
        source=(ROOT/'app.py').read_text()
        self.assertIn("@app.get('/my/orders')",source)

if __name__=='__main__': unittest.main()
