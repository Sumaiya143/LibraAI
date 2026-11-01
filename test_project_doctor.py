import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import project_doctor


class ProjectDoctorTests(unittest.TestCase):
    def test_reports_missing_required_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = project_doctor.inspect_environment(Path(tmp))
        self.assertFalse(result["ok"])
        self.assertTrue(any("app.py" in item for item in result["errors"]))

    def test_never_reads_or_reports_secret_values(self):
        with patch.dict("os.environ", {"SECRET_KEY": "test-super-secret-value"}):
            result = project_doctor.inspect_environment(project_doctor.ROOT)
        rendered = str(result)
        self.assertNotIn("test-super-secret-value", rendered)
        self.assertIn("checks", result)

    def test_result_schema_is_stable(self):
        result = project_doctor.inspect_environment(project_doctor.ROOT)
        self.assertEqual({"project", "ok", "checks", "errors", "warnings"}, set(result))
        self.assertIsInstance(result["checks"], list)


if __name__ == "__main__":
    unittest.main()
