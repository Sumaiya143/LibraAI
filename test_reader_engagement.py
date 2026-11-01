import unittest
import importlib.util
if importlib.util.find_spec("flask") is None:
    raise unittest.SkipTest("Flask dependency unavailable in this test environment")
import sqlite3
from datetime import date
from reader_engagement import matches, reading_streak
class TestEngagement(unittest.TestCase):
    def test_match_casefold(self):
        self.assertTrue(matches({'title':'Python Basics','author':'Someone','genre':'Technology'},'PYTHON','Technology'))
    def test_genre_filter(self):
        self.assertFalse(matches({'title':'Python Basics','genre':'Technology'},'python','History'))
    def test_streak(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.execute('CREATE TABLE reading_sessions(user_id INTEGER,minutes INTEGER,created TEXT)')
        c.executemany('INSERT INTO reading_sessions VALUES(?,?,?)',[(1,20,'2026-10-13T12:00'),(1,30,'2026-10-12T12:00'),(2,40,'2026-10-14T12:00')])
        self.assertEqual(reading_streak(c,1,date(2026,10,14)),2)
        self.assertEqual(reading_streak(c,2,date(2026,10,14)),1)
if __name__=='__main__': unittest.main()
