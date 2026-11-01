import sqlite3
import tempfile
import unittest
from pathlib import Path
from launch_gate import inspect

class LaunchGateTests(unittest.TestCase):
    def test_missing_credentials_fail_closed(self):
        result = inspect({})
        self.assertFalse(result['ready'])
        self.assertFalse(next(x for x in result['checks'] if x['check']=='bkash_credentials')['passed'])
    def test_no_secret_leak(self):
        env={'BKASH_PASSWORD':'super-private-value','SSLCOMMERZ_STORE_PASSWORD':'another-private-value'}
        self.assertNotIn('super-private-value',str(inspect(env)))
        self.assertNotIn('another-private-value',str(inspect(env)))
    def test_real_db_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'test.db'
            sqlite3.connect(path).close()
            result=inspect({'LIBRAAI_DB_PATH':str(path)})
            self.assertTrue(next(x for x in result['checks'] if x['check']=='database_integrity')['passed'])
    def test_human_flags_cannot_override_commercial_preflight(self):
        env={'LIBRAAI_ENV':'production','SECRET_KEY':'x'*64,'LIBRAAI_PUBLIC_URL':'https://books.example.org','LIBRAAI_BACKUP_RESTORE_VERIFIED':'yes','LIBRAAI_GATEWAY_E2E_VERIFIED':'yes','LIBRAAI_CONTENT_RIGHTS_VERIFIED':'yes','LIBRAAI_SECURITY_REVIEW_VERIFIED':'yes'}
        self.assertFalse(inspect(env)['ready'])
if __name__=='__main__': unittest.main()
