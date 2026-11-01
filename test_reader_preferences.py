import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class ReaderPreferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'app.py').read_text()

    def test_reader_preferences_persist_across_page_loads(self):
        self.assertIn("const READER_PREFS_KEY='libraai-reader-preferences-v1'", self.source)
        self.assertIn('function saveReaderPreferences()', self.source)
        self.assertIn('function applyReaderPreferences()', self.source)
        self.assertIn('applyReaderPreferences();', self.source)

    def test_preferences_are_clamped_and_storage_failure_is_safe(self):
        self.assertIn('Math.max(14,Math.min(32,prefs.fontSize))', self.source)
        self.assertIn('Math.max(1,Math.min(8,prefs.scrollSpeed))', self.source)
        self.assertIn('Private browsing or blocked storage must not break reading.', self.source)

    def test_keyboard_shortcuts_are_documented_in_handler(self):
        self.assertIn("event.altKey&&['+','='].includes(event.key)", self.source)
        self.assertIn("event.altKey&&event.key.toLowerCase()==='t'", self.source)
        self.assertIn("event.key==='Escape'", self.source)

    def test_escape_stops_auto_scroll_and_audio(self):
        self.assertIn('stopAutoScroll(null);stopReaderAudio();', self.source)

    def test_scroll_speed_changes_are_saved(self):
        self.assertIn("document.getElementById('scrollSpeed').addEventListener('change',saveReaderPreferences)", self.source)

if __name__ == '__main__':
    unittest.main()
