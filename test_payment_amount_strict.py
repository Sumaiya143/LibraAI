import unittest
from decimal import Decimal
from payment_engine import cents, PaymentError

class ExactPaymentAmountTests(unittest.TestCase):
    def test_exact_decimal(self):
        self.assertEqual(cents('125.50'), 12550)
        self.assertEqual(cents(Decimal('0.01')), 1)
        self.assertEqual(cents(10), 1000)
    def test_float_rejected(self):
        with self.assertRaises(PaymentError): cents(125.50)
    def test_boolean_rejected(self):
        with self.assertRaises(PaymentError): cents(True)
    def test_overflow_rejected(self):
        with self.assertRaises(PaymentError): cents('999999999999999999999999999999')
    def test_nonfinite_rejected(self):
        for amount in ('NaN','Infinity','-Infinity'):
            with self.subTest(amount=amount), self.assertRaises(PaymentError): cents(amount)
    def test_fractional_cent_rejected(self):
        with self.assertRaises(PaymentError): cents('12.345')
