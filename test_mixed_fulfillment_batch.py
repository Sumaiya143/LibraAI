import unittest
from test_mixed_fulfillment_audit import MixedFulfillmentAuditTests
from mixed_fulfillment_audit import inspect_orders

class BatchAuditTests(MixedFulfillmentAuditTests):
    def test_clean_batch(self):
        result = inspect_orders(self.c)
        self.assertEqual((result['scanned'], result['ready'], result['exceptions']), (1,1,0))
    def test_exceptions_only(self):
        self.c.execute('DELETE FROM digital_entitlements')
        result = inspect_orders(self.c, exceptions_only=True)
        self.assertEqual(result['exceptions'], 1)
        self.assertIn('digital_fulfillment_incomplete', result['orders'][0]['issues'])
    def test_offset(self):
        self.assertEqual(inspect_orders(self.c, offset=1)['scanned'],0)
    def test_reject_invalid_limit(self):
        for value in (0,501,True,'5'):
            with self.subTest(value=value), self.assertRaises(ValueError): inspect_orders(self.c,limit=value)
    def test_reject_invalid_offset(self):
        for value in (-1,False,'0'):
            with self.subTest(value=value), self.assertRaises(ValueError): inspect_orders(self.c,offset=value)
