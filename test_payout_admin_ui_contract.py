from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parent
class PayoutAdminUIContractTests(unittest.TestCase):
    def test_admin_ui_has_explicit_submit_and_reconcile_actions(self):
        source=(ROOT/'ui_gap_routes.py').read_text()
        script=(ROOT/'static/admin-royalty-payouts.js').read_text()
        self.assertIn('data-payout-submit',source)
        self.assertIn('data-payout-reconcile',source)
        self.assertIn("'/api/csrf'",script)
        self.assertIn("'X-CSRF-Token': csrfToken",script)
        self.assertIn("/submit-transfer",source if '/submit-transfer' in source else (ROOT/'royalty_routes.py').read_text())
        self.assertIn('/reconcile', (ROOT/'royalty_routes.py').read_text())
    def test_provider_ui_warns_that_submission_may_move_real_money(self):
        script=(ROOT/'static/admin-royalty-payouts.js').read_text()
        self.assertIn('may initiate a real money transfer',script)
        self.assertIn('Reconcile the provider before retrying',script)
if __name__=='__main__': unittest.main()
