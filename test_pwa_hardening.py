import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class PwaHardeningTests(unittest.TestCase):
    def test_manifest_declares_installable_png_icons(self):
        source = (ROOT / 'app.py').read_text()
        self.assertIn("'sizes':'192x192'", source)
        self.assertIn("'sizes':'512x512'", source)
        self.assertIn("'purpose':'maskable'", source)

    def test_icon_assets_exist_and_have_png_signature(self):
        for size in (192, 512):
            path = ROOT / f'pwa-icon-{size}.png'
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def test_browser_favicon_reuses_local_icon(self):
        source = (ROOT / 'app.py').read_text()
        self.assertIn("@app.get('/favicon.ico')", source)
        self.assertLess(source.index("@app.get('/favicon.ico')"),
                        source.index('def pwa_icon_192():'))

    def test_service_worker_only_caches_public_assets_and_offline_fallback(self):
        source = (ROOT / 'app.py').read_text()
        self.assertIn("const CACHE='libraai-public-shell-v2'", source)
        self.assertIn("if(request.mode==='navigate')", source)
        self.assertIn("cache.match('/offline')", source)
        self.assertIn("Never cache private pages, account data, or API responses", source)

    def test_offline_page_warns_private_pages_are_not_cached(self):
        source = (ROOT / 'app.py').read_text()
        self.assertIn('Your private account, library, and checkout pages are not saved for offline use.', source)

if __name__ == '__main__':
    unittest.main()
