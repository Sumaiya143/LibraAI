import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from verified_reading import setup, record, leaderboard

class VerifiedReadingTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        setup(self.db)
        self.now = datetime(2026,10,14,tzinfo=timezone.utc)
    def tearDown(self):
        self.db.close()
    def test_throttle_and_unique_reader(self):
        self.assertTrue(record(self.db, 1, 7, now=self.now))
        self.assertFalse(record(self.db, 1, 7, now=self.now+timedelta(minutes=5)))
        self.assertTrue(record(self.db, 1, 7, now=self.now+timedelta(minutes=21)))
        self.assertTrue(record(self.db, 2, 7, now=self.now))
        row=leaderboard(self.db, now=self.now+timedelta(minutes=22))[0]
        self.assertEqual(row['unique_readers'], 2)
        self.assertEqual(row['sessions'], 3)
    def test_completion_once(self):
        self.assertTrue(record(self.db, 1, 2, 'completion', now=self.now))
        self.assertFalse(record(self.db, 1, 2, 'completion', now=self.now+timedelta(days=3)))
    def test_window(self):
        record(self.db, 1, 2, now=self.now-timedelta(days=40))
        record(self.db, 2, 3, now=self.now)
        self.assertEqual([r['book_id'] for r in leaderboard(self.db, now=self.now)], [3])
    def test_bad_values(self):
        with self.assertRaises(ValueError): record(self.db, 0, 2)
        with self.assertRaises(ValueError): record(self.db, 1, 2, 'fake')
        with self.assertRaises(ValueError): leaderboard(self.db, days=0)

if __name__ == '__main__': unittest.main()
