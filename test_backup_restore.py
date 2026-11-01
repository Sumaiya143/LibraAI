# Disable request throttling in high-volume integration tests only.
import os
os.environ.setdefault('LIBRAAI_AUTH_THROTTLE','0')
import tempfile, pathlib, sqlite3, unittest
from backup_restore import backup, verify_restore

class BackupRestoreTests(unittest.TestCase):
    def test_backup_and_restore_preserves_data(self):
        with tempfile.TemporaryDirectory() as temp:
            source=pathlib.Path(temp)/'source.db'; destination=pathlib.Path(temp)/'backup.db'
            with sqlite3.connect(source) as conn:
                conn.execute('CREATE TABLE sample (value TEXT)')
                conn.execute('INSERT INTO sample VALUES (?)',('kept',))
            backup(destination,source)
            self.assertEqual(verify_restore(destination),1)
            with sqlite3.connect(destination) as conn:
                self.assertEqual(conn.execute('SELECT value FROM sample').fetchone()[0],'kept')
    def test_backup_rejects_overwriting_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source=pathlib.Path(temp)/'source.db'
            sqlite3.connect(source).close()
            with self.assertRaises(ValueError):backup(source,source)
    def test_backup_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):backup(pathlib.Path(temp)/'dest.db',pathlib.Path(temp)/'missing.db')
if __name__=='__main__':unittest.main()
