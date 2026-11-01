"""Contract checks for PDF.js page rendering and automatic position persistence."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
READER = (ROOT / 'static' / 'reader.html').read_text(encoding='utf-8')

class PDFJSLivePageTrackingTests(unittest.TestCase):
    def test_pdfjs_and_worker_are_configured(self):
        self.assertIn('pdf.js/3.11.174/pdf.min.js', READER)
        self.assertIn('pdf.worker.min.js', READER)
        self.assertIn("pdfjsLib.getDocument({url,withCredentials:true})", READER)

    def test_page_controls_use_actual_document_page_count(self):
        self.assertIn("$('pdfPage').max=doc.numPages", READER)
        self.assertIn('function stepPdfPage(n)', READER)
        self.assertIn('function zoomPdf(delta)', READER)
        self.assertIn("pdfDocument.getPage(activePage+1)", READER)

    def test_rendered_page_is_saved_to_account_progress(self):
        self.assertIn("await saveProgress(true,pdfDocument.numPages)", READER)
        self.assertIn("$('percent').value=Math.round(((activePage+1)/pdfDocument.numPages)*100)", READER)

    def test_native_viewer_fallback_is_disclosed(self):
        self.assertIn('automatic page tracking is unavailable in fallback mode', READER)

if __name__ == '__main__':
    unittest.main()
