import tempfile
import unittest
from pathlib import Path
from launch_evidence import collect, main

class LaunchEvidenceTests(unittest.TestCase):
    def test_missing_production_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            result=collect({},temp)
            self.assertFalse(result['ready_for_launch'])
            self.assertFalse(result['database']['exists'])
            self.assertTrue(result['preflight_issues'])
    def test_does_not_expose_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            result=collect({'SECRET_KEY':'SENSITIVE-SECRET-DO-NOT-LEAK','SSLCOMMERZ_STORE_PASSWORD':'SENSITIVE-PAYMENT-PASSWORD'},temp)
            self.assertNotIn('SENSITIVE',str(result))
    def test_operator_claims_are_not_described_as_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            result=collect({'LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED':'yes'},temp)
            self.assertTrue(result['operator_attestations_not_independently_verified']['merchant_payment_e2e'])
            self.assertFalse(result['ready_for_launch'])
    def test_missing_database_integrity_is_not_ok(self):
        with tempfile.TemporaryDirectory() as temp:
            result=collect({},temp)
            self.assertNotEqual(result['database']['integrity'],'ok')

    def test_wal_snapshot_cannot_be_certified(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'libraai.db'
            with sqlite3.connect(db) as conn:
                conn.execute('CREATE TABLE t (id INTEGER)')
            Path(str(db) + '-wal').write_bytes(b'uncheckpointed')
            result = collect({'LIBRAAI_DB_PATH': str(db)}, temp)
            self.assertEqual(result['database']['integrity'], 'wal_requires_checkpoint')
            self.assertFalse(result['ready_for_launch'])

    def test_ci_require_ready_fails_closed(self):
        from unittest.mock import patch
        from io import StringIO
        with patch('launch_evidence.collect', return_value={'ready_for_launch': False}), patch('sys.stdout', new_callable=StringIO):
            self.assertEqual(main(['--require-ready']), 1)

    def test_report_only_mode_keeps_zero_exit(self):
        from unittest.mock import patch
        from io import StringIO
        with patch('launch_evidence.collect', return_value={'ready_for_launch': False}), patch('sys.stdout', new_callable=StringIO):
            self.assertEqual(main([]), 0)

if __name__ == '__main__': unittest.main()
