import unittest
from catalog_pagination import parse_catalog_query, paginate

class CatalogPaginationTests(unittest.TestCase):
    def test_default(self):
        self.assertEqual(parse_catalog_query({}), (1,12,'trending','',''))
    def test_invalid_values(self):
        for args in ({'page':'0'}, {'page_size':'999'}, {'page':'abc'}, {'sort':'bad'}, {'q':'x'*161}):
            with self.subTest(args=args), self.assertRaises(ValueError): parse_catalog_query(args)
    def test_pages(self):
        data=paginate(list(range(25)),2,12)
        self.assertEqual(data['items'],list(range(12,24)))
        self.assertEqual(data['pages'],3)
        self.assertTrue(data['has_more'])
    def test_final_page(self):
        data=paginate(list(range(25)),3,12)
        self.assertEqual(data['items'],[24])
        self.assertFalse(data['has_more'])
    def test_empty(self):
        self.assertEqual(paginate([],1,12)['pages'],0)
