import unittest
from input_validation import validate_progress, validate_review, InputValidationError

class InputValidationTests(unittest.TestCase):
    def test_valid_progress(self):
        self.assertEqual(validate_progress('10','34.5'), (10,34.5))
    def test_invalid_progress(self):
        for value in ('nan','inf','-1','101','broken'):
            with self.subTest(value=value), self.assertRaises(InputValidationError):
                validate_progress('2', value)
    def test_invalid_page(self):
        for value in ('0','-1','100001','oops'):
            with self.subTest(value=value), self.assertRaises(InputValidationError):
                validate_progress(value, '50')
    def test_valid_review(self):
        self.assertEqual(validate_review('5',' Nice '), (5,'Nice'))
    def test_invalid_rating(self):
        for value in ('0','6','abc',None):
            with self.subTest(value=value), self.assertRaises(InputValidationError):
                validate_review(value,'good')
    def test_invalid_review(self):
        for value in ('','   ','x'*2001,None):
            with self.subTest(value=str(value)[:8]), self.assertRaises(InputValidationError):
                validate_review('4',value)
if __name__ == '__main__': unittest.main()
