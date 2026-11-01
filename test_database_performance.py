import sqlite3
import unittest
from database_performance import create_indexes

class DatabasePerformanceTests(unittest.TestCase):
    def test_indexes_are_created_and_idempotent(self):
        conn = sqlite3.connect(':memory:')
        conn.executescript('''
        CREATE TABLE progress(user_id INTEGER, updated TEXT);
        CREATE TABLE annotations(user_id INTEGER, book_id INTEGER, created TEXT);
        CREATE TABLE reviews(book_id INTEGER, created TEXT);
        CREATE TABLE wishlist(user_id INTEGER, book_id INTEGER);
        CREATE TABLE cart(user_id INTEGER, book_id INTEGER);
        CREATE TABLE orders(user_id INTEGER, status TEXT, created TEXT);
        CREATE TABLE posts(created TEXT);
        CREATE TABLE flashcards(user_id INTEGER, due TEXT);
        CREATE TABLE loans(user_id INTEGER, status TEXT, due TEXT);
        CREATE TABLE books(genre TEXT, reads INTEGER, sales INTEGER, year INTEGER);
        ''')
        self.assertEqual(create_indexes(conn), 12)
        self.assertEqual(create_indexes(conn), 12)
        names = {row[1] for row in conn.execute("PRAGMA index_list('orders')")}
        self.assertIn('idx_orders_user_created', names)
        self.assertIn('idx_orders_status_created', names)
        conn.close()

if __name__ == '__main__': unittest.main()
