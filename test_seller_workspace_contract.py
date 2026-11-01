"""Static and SQLite schema regression checks for the seller workspace.
The live Flask route tests run in the full app environment where Flask is installed.
"""
import pathlib, re, sqlite3, unittest
ROOT=pathlib.Path(__file__).resolve().parent

class SellerWorkspaceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'seller_workspace.py').read_text(encoding='utf-8')
        cls.front=(ROOT/'frontend/components/SellerWorkspace.tsx').read_text(encoding='utf-8')
        cls.dash=(ROOT/'frontend/app/dashboard/page.tsx').read_text(encoding='utf-8')

    def test_seller_routes_are_registered(self):
        for route in ["@bp.get('/api/seller/products')","@bp.post('/api/seller/products')","@bp.put('/api/seller/products/<int:product_id>')","@bp.get('/api/seller/overview')","@bp.post('/api/seller/payout-requests')"]:
            self.assertIn(route,self.source)

    def test_seller_role_and_owner_scoping(self):
        self.assertIn("('merchant','creator')",self.source)
        self.assertGreaterEqual(self.source.count('seller_id=?'),7)

    def test_pending_review_disables_public_sale(self):
        self.assertIn("'pending_review'",self.source)
        self.assertIn('VALUES(?,?,0,?,?,?)',self.source)

    def test_product_editor_supports_full_metadata(self):
        for field in ['description','tags_json','hashtags_json','details_json','discount_percent','image_url','stock','sku']:
            self.assertIn(field,self.source)
        for field in ['Tags (comma separated)','Hashtags (comma separated)','Additional product details','Discount (%)','Product image URL']:
            self.assertIn(field,self.front)

    def test_seller_finance_and_orders_are_visible(self):
        for field in ['gross_earnings','platform_fee','net_earnings','seller_payout_requests','order_status']:
            self.assertIn(field,self.source)
        for field in ['Orders & Sales','Earnings & Payouts','Single price','2 units','Platform charges','This week','This month','This year']:
            self.assertIn(field,self.front)

    def test_seller_navigation_is_role_scoped(self):
        self.assertIn('My Products & Inventory',self.dash)
        self.assertIn('Upload & Edit Products',self.dash)
        self.assertIn('<SellerWorkspace section="Dashboard" onNavigate={navigate}/>',self.dash)
        self.assertIn('onNavigate?onNavigate("Upload & Edit Products"):openNew',self.front)
        self.assertIn("section==='Author Profile'",self.front)
        self.assertIn("section==='Settings'",self.front)

    def test_database_schema_executes(self):
        schema=re.search(r"conn\.executescript\('''(.*?)'''\)",self.source,re.S).group(1)
        conn=sqlite3.connect(':memory:')
        conn.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY); CREATE TABLE books(id INTEGER PRIMARY KEY);')
        conn.executescript(schema)
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn('seller_products',tables); self.assertIn('seller_payout_requests',tables)
        conn.close()

if __name__=='__main__': unittest.main()
