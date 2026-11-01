"""Regression contracts for keyboard-accessible reader navigation."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parent
READER = (ROOT / 'static' / 'reader.html').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend' / 'app' / 'globals.css').read_text(encoding='utf-8')
class ReaderAccessibilityV54Tests(unittest.TestCase):
    def test_reader_status_is_announced(self):
        self.assertIn('id="status" role="status" aria-live="polite"', READER)
    def test_pdf_canvas_has_keyboard_instructions(self):
        self.assertIn('tabindex="0" aria-label="PDF page content.', READER)
        self.assertIn("event.altKey&&event.key==='ArrowLeft'", READER)
        self.assertIn("event.altKey&&event.key==='ArrowRight'", READER)
    def test_keyboard_shortcuts_do_not_interfere_with_form_typing(self):
        self.assertIn("target.matches('input,textarea,select')", READER)
    def test_global_focus_and_reduced_motion_support(self):
        self.assertIn(':focus-visible', CSS)
        self.assertIn('@media(prefers-reduced-motion:reduce)', CSS)
    def test_responsive_small_screen_rules_exist(self):
        self.assertIn('@media(max-width:480px)', CSS)
if __name__ == '__main__': unittest.main()
