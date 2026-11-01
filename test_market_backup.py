import pathlib
import unittest

ROOT = pathlib.Path(__file__).parent

class MarketBackupTests(unittest.TestCase):
    def test_backup_uses_sqlite_online_backup_not_raw_copy(self):
        s = (ROOT / 'market_backup.sh').read_text()
        self.assertIn('backup_manager.py backup', s)
        self.assertIn('backup_manager.py verify', s)
        self.assertNotIn('cp /data/libraai.db', s)

    def test_backup_is_private_and_fail_closed(self):
        s = (ROOT / 'market_backup.sh').read_text()
        self.assertIn('set -Eeuo pipefail', s)
        self.assertIn('umask 077', s)
        self.assertIn('chmod 600', s)
        self.assertIn('sha256sum', s)

    def test_backup_dir_ignored(self):
        self.assertIn('private-backups/', (ROOT / '.gitignore').read_text())

if __name__ == '__main__':
    unittest.main()
