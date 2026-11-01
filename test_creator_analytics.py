import sqlite3
import unittest

from creator_analytics import creator_dashboard_data


class CreatorAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
            CREATE TABLE royalty_contracts(book_id INTEGER,creator_user_id INTEGER,royalty_bps INTEGER,active INTEGER);
            CREATE TABLE books(id INTEGER PRIMARY KEY,title TEXT,author TEXT,genre TEXT,format TEXT,reads INTEGER,sales INTEGER,rating REAL);
            CREATE TABLE qualified_reading_events(user_id INTEGER,book_id INTEGER,event_type TEXT,recorded_at TEXT);
            CREATE TABLE order_items(id INTEGER PRIMARY KEY,order_id INTEGER,book_id INTEGER,quantity INTEGER,unit_price_cents INTEGER,line_total_cents INTEGER);
            CREATE TABLE orders(id INTEGER PRIMARY KEY,status TEXT);
            CREATE TABLE payment_attempts(order_id INTEGER,state TEXT);
            CREATE TABLE reviews(id INTEGER PRIMARY KEY,user_id INTEGER,book_id INTEGER,rating INTEGER,text TEXT,created TEXT);
            CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT);

            INSERT INTO users VALUES (1,'Merchant One'),(2,'Merchant Two'),(10,'Reader A'),(11,'Reader B');
            INSERT INTO books VALUES
                (1,'Fantasy Audio','Author A','Fantasy','eBook · Audio · PDF',0,0,0),
                (2,'Fantasy Reader','Author A','Fantasy','eBook',0,0,0),
                (3,'History Notes','Author A','History','PDF',0,0,0),
                (4,'Other Creator Book','Author B','History','Audio',0,0,0);
            INSERT INTO royalty_contracts VALUES (1,1,1000,1),(2,1,1000,1),(3,1,1000,1),(4,2,1000,1);
            INSERT INTO qualified_reading_events VALUES
                (10,1,'session','2026-10-28T10:00:00+00:00'),
                (11,1,'session','2026-10-28T11:00:00+00:00'),
                (10,2,'session','2026-10-28T12:00:00+00:00'),
                (11,4,'session','2026-10-28T12:00:00+00:00');
            INSERT INTO orders VALUES (1,'Paid — fulfillment pending'),(2,'Awaiting payment'),(3,'Paid — fulfillment pending');
            INSERT INTO payment_attempts VALUES (1,'paid'),(2,'pending'),(3,'paid');
            INSERT INTO order_items VALUES (1,1,1,3,1000,3000),(2,2,1,50,1000,50000),(3,3,2,2,1500,3000),(4,3,4,9,1000,9000);
            INSERT INTO reviews VALUES
                (1,10,1,5,'Loved the story','2026-10-28T10:00:00'),
                (2,11,1,3,'Good audio edition','2026-10-28T11:00:00'),
                (3,10,4,1,'Other creator private review','2026-10-28T12:00:00');
        ''')

    def tearDown(self):
        self.conn.close()

    def test_scoped_paid_sales_reading_reviews_and_format_mix(self):
        report = creator_dashboard_data(self.conn, 1)
        self.assertEqual(report['total_titles'], 3)
        self.assertEqual(report['total_sales'], 5)
        self.assertEqual(report['total_gross_cents'], 6000)
        self.assertEqual(report['total_views'], 3)
        self.assertEqual(report['review_count'], 2)
        self.assertEqual(report['formats'], {'Audio books': 1, 'eBooks': 2, 'PDFs': 2})
        self.assertEqual(report['format_count'], 5)
        self.assertIn('conic-gradient(', report['format_chart'])
        by_title = {book['title']: book for book in report['books']}
        self.assertEqual(by_title['Fantasy Audio']['paid_units'], 3)
        self.assertEqual(by_title['Fantasy Audio']['display_rating'], 4.0)
        self.assertEqual(by_title['Fantasy Audio']['review_count'], 2)
        self.assertEqual([comment['text'] for comment in report['comments']], ['Good audio edition', 'Loved the story'])
        self.assertEqual(report['next_book']['genre'], 'Fantasy')
        self.assertIn('5 paid copies', report['next_book']['signals'])
        self.assertFalse(report['notes_tracking'])
        self.assertFalse(report['lectures_tracking'])

    def test_creator_without_linked_titles_has_no_invented_recommendation(self):
        report = creator_dashboard_data(self.conn, 99)
        self.assertEqual(report['books'], [])
        self.assertEqual(report['total_sales'], 0)
        self.assertIsNone(report['next_book'])
        self.assertEqual(report['comments'], [])


if __name__ == '__main__':
    unittest.main()
