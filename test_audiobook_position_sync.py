"""Static contract tests for cross-session audiobook position sync."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
ADVANCED = (ROOT / 'advanced.py').read_text(encoding='utf-8')
READER = (ROOT / 'static' / 'reader.html').read_text(encoding='utf-8')


class AudiobookPositionSyncTests(unittest.TestCase):
    def test_backward_compatible_database_migration(self):
        self.assertIn("('audio_seconds','REAL NOT NULL DEFAULT 0')", ADVANCED)

    def test_progress_api_reads_and_writes_audio_position(self):
        self.assertIn('file_id,audio_seconds,updated FROM reading_progress', ADVANCED)
        self.assertIn('audio_seconds=float(b.get(\'audio_seconds\',0))', ADVANCED)
        self.assertIn('file_id,audio_seconds) VALUES(?,?,?,?,?,?,?)', ADVANCED)
        self.assertIn('not 0<=audio_seconds<=315360000', ADVANCED)

    def test_reader_restores_and_saves_audio_timestamp(self):
        self.assertIn("['epub','cbz','mp3','m4a','ogg'].includes(lastFile.kind)", READER)
        self.assertIn('savedProgress.audio_seconds', READER)
        self.assertIn('audio_seconds:audioSeconds', READER)
        self.assertIn("addEventListener('timeupdate',updateAudioProgress)", READER)
        self.assertIn("addEventListener('ended'", READER)


if __name__ == '__main__':
    unittest.main()
