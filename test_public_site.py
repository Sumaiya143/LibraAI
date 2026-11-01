"""Static and structural checks that work without optional Flask installation."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class PublicSiteTests(unittest.TestCase):
    def test_landing_sections(self):
        html = (ROOT/'landing.html').read_text()
        for section in ('id="features"','id="experience"','id="for-everyone"','id="questions"'):
            with self.subTest(section=section): self.assertIn(section,html)
    def test_links_to_existing_routes(self):
        app = (ROOT/'app.py').read_text()
        for endpoint in ('/discover','/marketplace','/community','/creator','/admin','/study'):
            self.assertIn(endpoint,app)
    def test_signup_password_hashing_and_uniqueness(self):
        app=(ROOT/'app.py').read_text()
        self.assertIn('generate_password_hash,',app)
        self.assertIn('create_account(',app)
        self.assertIn('except sqlite3.IntegrityError:',app)
        registration=(ROOT/'account_registration.py').read_text()
        self.assertIn("'customer': ('reader', 'Free')",registration)
    def test_signup_and_public_asset_routes(self):
        app=(ROOT/'app.py').read_text()
        for route in ("'/welcome'","'/register'","'/assets/landing.css'","'/assets/landing.js'"):
            self.assertIn(route,app)
    def test_new_public_homepage_and_role_entry_points(self):
        app=(ROOT/'app.py').read_text()
        html=(ROOT/'landing_home.html').read_text()
        js=(ROOT/'landing_home.js').read_text()
        for asset_route in ("'/assets/landing-home.css'", "'/assets/landing-home.js'"):
            self.assertIn(asset_route,app)
        self.assertIn("'landing_home.html'",app)
        for phrase in ('Customer account','Merchant account','Administrator sign in','Explore the library'):
            self.assertIn(phrase,html)
        self.assertIn('question-search',html)
        self.assertIn('question-search', js)
        self.assertIn('hero-artwork', html)
        self.assertIn('promo-artwork', html)
        self.assertIn('community-art', html)
        self.assertIn('footer-main', html)
        self.assertIn('library-showcase', html)
        self.assertNotIn('book-scene', html)
        self.assertNotIn('three.module.js', js)
        self.assertNotIn('admin@libra.ai',html)
    def test_no_external_js_dependency(self):
        html=(ROOT/'landing.html').read_text()
        self.assertIn('src="/assets/landing.js"',html)
        self.assertNotIn('src="https://',html)
    def test_mobile_and_reduced_motion(self):
        css=(ROOT/'landing.css').read_text()
        self.assertIn('@media(max-width:760px)',css)
        self.assertIn('prefers-reduced-motion',css)

if __name__=='__main__': unittest.main()
