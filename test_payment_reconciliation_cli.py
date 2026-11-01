import os, subprocess, sys, tempfile, sqlite3, unittest, json
from pathlib import Path

SCRIPT = str(Path(__file__).with_name('payment_reconciliation.py'))
class ReconciliationCLITests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
    def test_missing_database_never_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path=os.path.join(directory,'missing.db')
            result=self.run_cli('--db',path)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(os.path.exists(path))
            self.assertIn('does not exist',result.stderr)
    def test_zero_limit_rejected(self):
        result=self.run_cli('--limit','0')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('--limit',result.stderr)
    def test_excessive_limit_rejected(self):
        result=self.run_cli('--limit','1001')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('--limit',result.stderr)
    def test_backend_limit_501_rejected_before_database_access(self):
        result=self.run_cli('--limit','501')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('between 1 and 500',result.stderr)
    def test_dry_run_uses_read_only_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path=os.path.join(directory,'test.db')
            conn=sqlite3.connect(path)
            conn.execute('CREATE TABLE payment_attempts (state TEXT, provider_ref TEXT, created TEXT, id INTEGER)')
            conn.commit();conn.close()
            # SQLite authorizer is not needed: the CLI must open in mode=ro.
            from unittest.mock import patch
            import payment_reconciliation
            real_connect=sqlite3.connect
            modes=[]
            def capture(db_uri, *args, **kwargs):
                modes.append(db_uri)
                return real_connect(db_uri,*args,**kwargs)
            with patch.object(payment_reconciliation.sqlite3,'connect',side_effect=capture):
                with patch('sys.argv',[SCRIPT,'--db',path]):
                    payment_reconciliation.main()
            self.assertTrue(any('?mode=ro' in uri for uri in modes))
    def test_strict_exits_two_when_gateway_remains_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            path=os.path.join(directory,'pending.db')
            conn=sqlite3.connect(path)
            conn.execute('CREATE TABLE payment_attempts (id INTEGER PRIMARY KEY, merchant_ref TEXT, provider TEXT, state TEXT, provider_ref TEXT, created TEXT)')
            conn.execute("INSERT INTO payment_attempts VALUES(1,'ref-1','bkash','pending','pay-1','2026-01-01')")
            conn.commit();conn.close()
            from unittest.mock import patch
            import payment_reconciliation
            from payment_engine import PaymentError
            with patch.object(payment_reconciliation,'reconcile_one',return_value='pending'):
                with patch('sys.argv',[SCRIPT,'--db',path,'--strict','--summary']):
                    from contextlib import redirect_stdout
                    from io import StringIO
                    output=StringIO()
                    with redirect_stdout(output), self.assertRaises(SystemExit) as exit_result:
                        payment_reconciliation.main()
            self.assertEqual(exit_result.exception.code,2)
            summary=json.loads(output.getvalue().splitlines()[-1])
            self.assertEqual(summary['pending'],1)
            self.assertEqual(summary['processed'],1)
            self.assertEqual(summary['mode'],'dry_run')

    def test_strict_success_for_empty_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            path=os.path.join(directory,'empty.db')
            conn=sqlite3.connect(path)
            conn.execute('CREATE TABLE payment_attempts (id INTEGER PRIMARY KEY, merchant_ref TEXT, provider TEXT, state TEXT, provider_ref TEXT, created TEXT)')
            conn.commit();conn.close()
            result=self.run_cli('--db',path,'--strict','--summary')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['processed'],0)

    def test_existing_empty_db_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path=os.path.join(directory,'existing.db')
            sqlite3.connect(path).close()
            result=self.run_cli('--db',path)
            self.assertNotEqual(result.returncode,0)
            self.assertTrue(os.path.isfile(path))
if __name__=='__main__': unittest.main()
