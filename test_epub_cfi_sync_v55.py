"""Contract checks for EPUB.js CFI-based location sync."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parent
READER = (ROOT / 'static' / 'reader.html').read_text(encoding='utf-8')
ADVANCED = (ROOT / 'advanced.py').read_text(encoding='utf-8')

class EpubCFISyncTests(unittest.TestCase):
    def test_epubjs_engine_and_reader_stage_are_present(self):
        self.assertIn('epubjs@0.3.93/dist/epub.min.js', READER)
        self.assertIn('id="epubStage"', READER)
        self.assertIn("epubBook=ePub(url)", READER)
        self.assertIn("renderTo('epubStage'", READER)

    def test_saved_cfi_is_restored_for_the_same_file(self):
        self.assertIn("savedProgress.location.startsWith('epubcfi(')", READER)
        self.assertIn('await epubRendition.display(target)', READER)
        self.assertIn('Number(savedProgress.file_id)===Number(f.id)', READER)

    def test_relocated_event_persists_exact_cfi(self):
        self.assertIn("epubRendition.on('relocated'", READER)
        self.assertIn('await saveProgress(true,total,cfi,page)', READER)
        self.assertIn('locationOverride||(isAudio?', READER)

    def test_epub_navigation_and_font_controls_exist(self):
        self.assertIn('function stepEpub(delta)', READER)
        self.assertIn('function changeEpubFont(delta)', READER)

    def test_progress_location_can_hold_longer_cfi(self):
        self.assertIn("location=str(b.get('location',''))[:2000]", ADVANCED)

if __name__ == '__main__': unittest.main()
