import unittest
import importlib.util
if importlib.util.find_spec("flask") is None:
    raise unittest.SkipTest("Flask dependency unavailable in this test environment")
from licensed_library import chunk_text, retrieve

class LicensedLibraryTests(unittest.TestCase):
    def test_overlap(self):
        self.assertEqual(chunk_text('one two three four five',3,1), ['one two three','three four five','five'])
    def test_blank_rejected(self):
        with self.assertRaises(ValueError): chunk_text('  ')
    def test_retrieval(self):
        rows=[{'document_id':1,'chunk_number':0,'title':'A','content':'The galaxy contains stars and planets.'},
              {'document_id':2,'chunk_number':0,'title':'B','content':'A book about cooking vegetables.'}]
        found=retrieve('galaxy stars',rows)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['document_id'],1)
    def test_no_fabrication(self):
        self.assertEqual(retrieve('unicorn', [{'document_id':1,'chunk_number':0,'title':'A','content':'galaxy stars'}]),[])

if __name__=='__main__': unittest.main()
