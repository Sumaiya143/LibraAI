from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parent
APP=(ROOT/'app.py').read_text(encoding='utf-8')
SERVICE=(ROOT/'circulation.py').read_text(encoding='utf-8')
class CirculationRouteSecurityTests(unittest.TestCase):
 def test_borrow_and_member_loan_actions_require_login(self):
  start=APP.index("@app.route('/action/<kind>/<int:bid>'")
  end=APP.index("@app.post('/action/wishlist/<int:bid>/remove')",start)
  self.assertIn('@login_required',APP[start:end])
  start=APP.index("@app.route('/loan/<int:lid>/<op>'")
  end=APP.index("@app.route('/admin/circulation-inventory'",start)
  self.assertIn('@login_required',APP[start:end])
 def test_admin_inventory_page_checks_admin_role(self):
  start=APP.index("@app.route('/admin/circulation-inventory'")
  end=APP.index("@app.get('/librarian')",start)
  self.assertIn("user['role']!='admin'",APP[start:end])
 def test_all_post_routes_keep_global_csrf_guard(self):
  self.assertIn('def verify_form_csrf():',APP)
  self.assertIn("if request.method in ('POST','PUT','PATCH','DELETE'):",APP)
  self.assertIn("hmac.compare_digest(token,supplied)",APP)
 def test_lending_is_serialized_and_stock_changes_atomically(self):
  self.assertIn("conn.execute('BEGIN IMMEDIATE')",SERVICE)
  self.assertIn('available_copies=available_copies-1',SERVICE)
  self.assertIn('available_copies=available_copies+1',SERVICE); self.assertIn("lower(status)!='returned'",SERVICE)
 def test_retail_stock_is_separate_from_circulation_stock(self):
  self.assertIn('CREATE TABLE IF NOT EXISTS library_inventory',SERVICE)
  self.assertIn('independently from retail sales stock',APP)
if __name__=='__main__': unittest.main()
