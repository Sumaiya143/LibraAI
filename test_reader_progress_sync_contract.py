"""Dependency-free static contract checks for reader progress synchronization."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
APP = (ROOT / 'app.py').read_text(encoding='utf-8')


class ReaderProgressSyncContractTests(unittest.TestCase):
    def test_account_scoped_json_endpoint_exists(self):
        self.assertIn("@app.route('/api/reader/<int:bid>/progress', methods=['GET', 'POST'])", APP)
        self.assertIn("'SELECT page, percent, updated FROM progress WHERE user_id=? AND book_id=?'", APP)
        self.assertIn("int(user['id']), bid", APP)

    def test_progress_writes_use_validated_upsert(self):
        self.assertIn('page_number, percent = validate_progress(data.get(\'page\'), data.get(\'percent\'))', APP)
        self.assertIn('ON CONFLICT(user_id,book_id) DO UPDATE SET page=excluded.page', APP)
        self.assertIn("return jsonify({'error': str(exc)}), 400", APP)

    def test_reader_automatically_restores_and_saves_progress(self):
        self.assertIn('async function restoreReadingProgress()', APP)
        self.assertIn('function scheduleProgressSync()', APP)
        self.assertIn("window.addEventListener('scroll',scheduleProgressSync", APP)
        self.assertIn("'X-CSRF-Token':progressCsrfToken", APP)
        self.assertIn("localStorage.setItem(progressLocalKey", APP)


if __name__ == '__main__':
    unittest.main()
