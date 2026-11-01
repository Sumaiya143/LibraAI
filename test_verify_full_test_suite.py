import unittest
from verify_full_test_suite import missing_runtime_dependencies

class RuntimePreflightTests(unittest.TestCase):
    def test_missing_dependencies_are_reported(self):
        def finder(name):
            return None if name == "flask" else object()
        self.assertEqual(missing_runtime_dependencies(finder), ["flask"])

    def test_broken_test_stub_is_treated_as_missing(self):
        def finder(_name):
            raise ValueError("module has no __spec__")
        self.assertEqual(missing_runtime_dependencies(finder), ["flask", "werkzeug"])

    def test_all_dependencies_present(self):
        self.assertEqual(missing_runtime_dependencies(lambda _name: object()), [])

if __name__ == "__main__":
    unittest.main()
