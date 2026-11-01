"""Contract tests for book-wide EPUB progress percentages (v56)."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parent
READER = (ROOT / 'static' / 'reader.html').read_text(encoding='utf-8')

class EpubGlobalProgressTests(unittest.TestCase):
    def test_global_location_index_is_generated(self):
        self.assertIn('epubBook.locations.generate(1000)', READER)
        self.assertIn('epubLocationsReady=true', READER)

    def test_global_percentage_uses_cfi_when_index_ready(self):
        self.assertIn('epubBook.locations.percentageFromCfi(cfi)', READER)
        self.assertIn('Number.isFinite(ratio)', READER)
        self.assertIn('Math.max(0,Math.min(1,ratio))', READER)

    def test_section_page_percentage_is_only_fallback(self):
        self.assertIn("let pct=total>0?Math.round(page/total*100):0", READER)
        self.assertIn("'Page '+page+' of current section'", READER)

    def test_new_book_resets_location_index_state(self):
        self.assertIn('epubLocationsReady=false', READER)

if __name__ == '__main__':
    unittest.main()
