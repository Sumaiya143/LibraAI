"""Regression tests for functional, keyboard-accessible reader controls."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent

class ReaderAccessibilityControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'app.py').read_text(encoding='utf-8')

    def test_font_size_is_adjustable_and_bounded(self):
        self.assertIn('function changeReaderFont(delta)', self.source)
        self.assertIn('Math.max(14,Math.min(32,readerFontSize+delta*2))', self.source)

    def test_auto_scroll_can_start_stop_and_adjust_speed(self):
        self.assertIn('function toggleAutoScroll()', self.source)
        self.assertIn("clearInterval(autoScrollTimer)", self.source)
        self.assertIn('id="scrollSpeed" type="range"', self.source)

    def test_read_aloud_has_stop_and_feature_detection(self):
        self.assertIn('function speakReader()', self.source)
        self.assertIn("'speechSynthesis' in window", self.source)
        self.assertIn('function stopReaderAudio()', self.source)

    def test_accessibility_controls_expose_state_and_status(self):
        self.assertIn('aria-live="polite"', self.source)
        self.assertIn('id="contrastToggle" aria-pressed="false"', self.source)
        self.assertIn('function toggleReaderSpacing()', self.source)
        self.assertIn('function toggleReaderContrast()', self.source)


    def test_reader_theme_control_has_unique_id_and_uses_it(self):
        # The global app theme and in-reader theme must not share an HTML id.
        self.assertIn('id="themeToggle"', self.source)
        self.assertIn('id="readerThemeToggle"', self.source)
        self.assertIn("document.getElementById('readerThemeToggle').setAttribute('aria-pressed',String(readerThemeDark))", self.source)
        self.assertNotIn("document.getElementById('themeToggle').setAttribute('aria-pressed',String(readerThemeDark))", self.source)

    def test_reader_responsive_layout(self):
        self.assertIn('@media(max-width:700px){.reader.two{column-count:1}', self.source)

if __name__ == '__main__':
    unittest.main()
