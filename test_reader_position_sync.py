"""Regression contracts for account-scoped page-level reader position sync."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
ADVANCED = (ROOT / 'advanced.py').read_text(encoding='utf-8')
READER = (ROOT / 'static' / 'reader.html').read_text(encoding='utf-8')


class ReaderPositionSyncTests(unittest.TestCase):
    def test_backward_compatible_progress_schema_migration(self):
        self.assertIn("PRAGMA table_info(reading_progress)", ADVANCED)
        self.assertIn("('page','INTEGER NOT NULL DEFAULT 0')", ADVANCED)
        self.assertIn("('location',\"TEXT NOT NULL DEFAULT ''\")", ADVANCED)
        self.assertIn("('file_id','INTEGER')", ADVANCED)

    def test_position_read_is_account_scoped_and_requires_library_access(self):
        self.assertIn("if query.get('book_id')", ADVANCED)
        self.assertIn("SELECT 1 FROM library WHERE user_id=? AND book_id=?", ADVANCED)
        self.assertIn("WHERE user_id=? AND book_id=?", ADVANCED)

    def test_progress_write_validates_page_and_file_ownership(self):
        self.assertIn("if not 0<=page<=1000000", ADVANCED)
        self.assertIn("SELECT 1 FROM book_files WHERE id=? AND book_id=?", ADVANCED)
        self.assertIn("page=excluded.page,location=excluded.location,file_id=excluded.file_id", ADVANCED)

    def test_epub_cbz_reader_restores_and_syncs_page_position(self):
        self.assertIn("api('/api/extra/progress?book_id='+current)", READER)
        self.assertIn("activePage=(savedProgress&&Number(savedProgress.file_id)===Number(f.id))", READER)
        self.assertIn("await saveProgress(true,d.total)", READER)
        self.assertIn("file_id:activeFile?activeFile.id:null", READER)
        self.assertIn("activeFile.kind+':page:'+(page+1)", READER)


if __name__ == '__main__':
    unittest.main()
