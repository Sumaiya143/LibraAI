from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
READER = (ROOT / 'static' / 'reader.html').read_text(encoding='utf-8')

class PDFPagePositionControlsTests(unittest.TestCase):
    def test_pdf_controls_are_present_and_accessible(self):
        self.assertIn('id="pdfControls"', READER)
        self.assertIn('id="pdfPage"', READER)
        self.assertIn('goPdfPage()', READER)

    def test_pdf_restore_uses_saved_page(self):
        self.assertIn("activePage=(savedProgress&&Number(savedProgress.file_id)===Number(f.id))?Math.max(0,Number(savedProgress.page)||0):0", READER)
        self.assertIn("'#page='+(activePage+1)", READER)

    def test_pdf_page_sync_is_explicitly_manual(self):
        self.assertIn('automatic page tracking is unavailable in fallback mode', READER)
        self.assertIn("await saveProgress(true)", READER)

    def test_pdf_file_is_attached_to_progress(self):
        self.assertIn("else if(f.kind==='pdf'){activeFile=f;", READER)
        self.assertIn('file_id:activeFile?activeFile.id:null', READER)

if __name__ == '__main__':
    unittest.main()
