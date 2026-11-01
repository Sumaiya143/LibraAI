"""Regression tests for truthful bounded fulfillment dashboard pagination."""
import sqlite3
import unittest
from admin_fulfillment_dashboard import dashboard_page
from unittest.mock import patch


class PaginationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY)')
        self.conn.executemany('INSERT INTO orders(id) VALUES (?)', [(i,) for i in range(1, 6)])

    def tearDown(self):
        self.conn.close()

    def test_first_page_has_next_but_no_previous(self):
        with patch('admin_fulfillment_dashboard.inspect_order', side_effect=lambda c, i: self.fake(i)):
            page = dashboard_page(self.conn, 2, 0)
        self.assertEqual([x['order_id'] for x in page['rows']], [5, 4])
        self.assertTrue(page['has_next'])
        self.assertFalse(page['has_previous'])

    def test_last_page_has_previous_but_no_next(self):
        with patch('admin_fulfillment_dashboard.inspect_order', side_effect=lambda c, i: self.fake(i)):
            page = dashboard_page(self.conn, 2, 4)
        self.assertEqual([x['order_id'] for x in page['rows']], [1])
        self.assertFalse(page['has_next'])
        self.assertTrue(page['has_previous'])

    def test_exceptions_filter_is_page_scoped(self):
        with patch('admin_fulfillment_dashboard.inspect_order', side_effect=lambda c, i: self.fake(i, ready=(i == 5))):
            page = dashboard_page(self.conn, 2, 0, True)
        self.assertEqual([x['order_id'] for x in page['rows']], [4])
        self.assertTrue(page['has_next'])

    def test_invalid_pagination_rejected(self):
        with self.assertRaises(ValueError):
            dashboard_page(self.conn, 101, 0)

    @staticmethod
    def fake(i, ready=False):
        return dict(order_id=i, status='paid', ready=ready, issues=[] if ready else ['review'], print_line_count=1, digital_line_count=0)

if __name__ == '__main__':
    unittest.main()
