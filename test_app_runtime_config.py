"""Static release guards for app runtime configuration without external services."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent

class AppRuntimeConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        cls.layout_source = (ROOT / "frontend/app/layout.tsx").read_text(encoding="utf-8")
        cls.css_source = (ROOT / "frontend/app/globals.css").read_text(encoding="utf-8")

    def test_production_secret_rejects_short_and_placeholder_values(self):
        self.assertIn("len(os.environ.get('SECRET_KEY', '')) < 32", self.app_source)
        self.assertIn("Production SECRET_KEY cannot be a template or placeholder value", self.app_source)

    def test_database_path_wal_timeout_and_connection_cleanup(self):
        self.assertIn("Production LIBRAAI_DB_PATH must be an absolute path", self.app_source)
        self.assertIn("PRAGMA journal_mode=WAL", self.app_source)
        self.assertIn("PRAGMA busy_timeout=", self.app_source)
        self.assertIn("class _ClosingSQLiteConnection", self.app_source)
        self.assertIn("finally:\n            self.close()", self.app_source)

    def test_production_supports_configured_redis_sessions_and_rate_limit(self):
        self.assertIn("_session_backend not in ('sqlite', 'redis')", self.app_source)
        self.assertIn("_rate_backend not in ('memory', 'redis')", self.app_source)
        self.assertIn("require a TLS rediss:// URL", self.app_source)
        self.assertIn('primary SQLite database still needs migration to PostgreSQL', self.app_source)

    def test_frontend_has_skip_link_focus_and_reduced_motion_support(self):
        self.assertIn('href="#main-content"', self.layout_source)
        self.assertIn('id="main-content"', self.layout_source)
        self.assertIn('.skip-link:focus', self.css_source)
        self.assertIn('@media(prefers-reduced-motion:reduce)', self.css_source)

if __name__ == "__main__":
    unittest.main()
