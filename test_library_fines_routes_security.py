from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SERVICE = (ROOT / "library_fines.py").read_text(encoding="utf-8")
CIRCULATION = (ROOT / "circulation.py").read_text(encoding="utf-8")


class LibraryFineRouteSecurityTests(unittest.TestCase):
    def test_customer_fine_and_clearance_routes_require_login(self):
        for route in ("@app.route('/account/fines'", "@app.route('/account/library-clearance'"):
            start = APP.index(route)
            decorator = APP[start:APP.index("def ", start)]
            self.assertIn("@login_required", decorator)

    def test_admin_payment_review_routes_require_login_and_admin_role(self):
        for route in ("@app.route('/admin/fines'", "@app.post('/admin/fines/<int:payment_id>/approve')"):
            start = APP.index(route)
            body = APP[start:APP.index("\n\n", start) + 2]
            self.assertIn("@login_required", body)
            self.assertIn("current_user()['role'] != 'admin'", body)

    def test_customer_cannot_self_approve_payment(self):
        self.assertIn("def approve_payment(conn, payment_id, reviewer_id", SERVICE)
        self.assertIn("reviewer_id=?", SERVICE)
        self.assertIn("def admin_approve_library_fine(payment_id)", APP)
        self.assertIn("current_user()['role'] != 'admin'", APP)

    def test_unpaid_balance_blocks_borrow(self):
        self.assertIn("outstanding_balance(conn, user_id, now.date())", CIRCULATION)
        self.assertIn("CirculationError('fine_due'", CIRCULATION)

    def test_fine_and_payment_forms_use_global_csrf_injection(self):
        self.assertIn("def verify_form_csrf():", APP)
        self.assertIn("def page(title, body, **ctx):", APP)
        self.assertIn('action="/backend/account/fines"', APP)

    def test_clearance_is_library_no_dues_not_academic_certificate(self):
        self.assertIn("not an academic graduation certificate", APP)


if __name__ == "__main__":
    unittest.main()
