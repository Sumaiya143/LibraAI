"""Guard environment templates against duplicate keys and unsafe deployment defaults."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent


def parse_env(path):
    values = {}
    duplicates = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in values:
            duplicates.append((key, line_no))
        values[key] = value.strip()
    return values, duplicates


class EnvironmentTemplateTests(unittest.TestCase):
    def test_development_template_has_no_duplicate_keys(self):
        values, duplicates = parse_env(ROOT / ".env.example")
        self.assertEqual(duplicates, [])
        self.assertEqual(values["LIBRAAI_ENV"], "development")
        self.assertEqual(values["LIBRAAI_SESSION_BACKEND"], "sqlite")
        self.assertEqual(values["SSLCOMMERZ_SANDBOX"], "true")
        self.assertEqual(values["BKASH_SANDBOX"], "true")

    def test_production_template_has_no_duplicate_keys_and_fails_closed(self):
        path = ROOT / ".env.production.example"
        self.assertTrue(path.is_file())
        values, duplicates = parse_env(path)
        self.assertEqual(duplicates, [])
        self.assertEqual(values["LIBRAAI_ENV"], "production")
        self.assertEqual(values["LIBRAAI_DEBUG"], "0")
        self.assertEqual(values["LIBRAAI_SESSION_BACKEND"], "sqlite")
        self.assertTrue(values["SECRET_KEY"].startswith("REPLACE_WITH_"))
        self.assertEqual(values["SSLCOMMERZ_SANDBOX"], "true")
        self.assertEqual(values["BKASH_SANDBOX"], "true")
        self.assertEqual(values["LIBRAAI_BACKUP_RESTORE_VERIFIED"], "no")

    def test_production_template_is_not_accidentally_development_template(self):
        values, _ = parse_env(ROOT / ".env.production.example")
        self.assertNotEqual(values["LIBRAAI_PUBLIC_URL"], "http://localhost:5000")
        self.assertNotEqual(values["SECRET_KEY"], parse_env(ROOT / ".env.example")[0]["SECRET_KEY"])


if __name__ == "__main__":
    unittest.main()
