import unittest
from mixed_format_catalog import available_formats, select_format, FormatUnavailable

class MixedFormatTests(unittest.TestCase):
    def test_both(self):
        self.assertEqual(available_formats('eBook · Print · Audio'), ('eBook','Print'))
    def test_print_only(self):
        self.assertEqual(available_formats('Paperback'), ('Print',))
    def test_digital_only(self):
        self.assertEqual(available_formats('EPUB'), ('eBook',))
    def test_selected_print(self):
        self.assertEqual(select_format('eBook · Print', 'Print'), 'Print')
    def test_reject_unlisted(self):
        with self.assertRaises(FormatUnavailable): select_format('Print', 'eBook')
    def test_reject_unknown(self):
        with self.assertRaises(FormatUnavailable): select_format('eBook · Print', 'Audio')

if __name__ == '__main__': unittest.main()
