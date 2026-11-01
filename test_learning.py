import unittest
from datetime import date
from scheduling import schedule
class SchedulingTests(unittest.TestCase):
    def test_failure_resets(self):
        self.assertEqual(schedule(20,2,date(2026,10,14)),(1,date(2026,10,15)))
    def test_success_grows(self):
        self.assertEqual(schedule(4,5,date(2026,10,14)),(10,date(2026,10,24)))
    def test_bounds(self):
        self.assertEqual(schedule(300,5,date(2026,10,14))[0],365)
    def test_invalid(self):
        with self.assertRaises(ValueError):schedule(1,6)
if __name__=='__main__':unittest.main()
