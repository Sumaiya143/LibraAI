import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from buyer_acceptance import PUBLIC, PRIVATE, static_checks, report
from buyer_preflight import REQUIRED

class BuyerAcceptanceTests(unittest.TestCase):
    def test_static_package_missing_deliverables(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in REQUIRED:
                (Path(tmp) / name).touch()
            self.assertTrue(any('buyer deliverable' in s for s in static_checks(tmp)))

    def test_scope_must_be_valid_json_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in set(REQUIRED) | {'BUYER_START_HERE_BN.md', 'compose.market.yaml', 'Caddyfile'}:
                (root / name).touch()
            (root / 'BUYER_DELIVERY_SCOPE.json').write_text('[]')
            self.assertIn('Buyer scope must be a JSON object', static_checks(root))

    def test_scope_parse_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in set(REQUIRED) | {'BUYER_START_HERE_BN.md', 'compose.market.yaml', 'Caddyfile'}:
                (root / name).touch()
            (root / 'BUYER_DELIVERY_SCOPE.json').write_text('{bad')
            self.assertTrue(any('Invalid buyer scope' in s for s in static_checks(root)))

    def test_acceptance_fails_closed_without_runtime(self):
        with patch('buyer_acceptance.static_checks', return_value=[]), patch('buyer_acceptance.runtime_checks', return_value={'runtime_available': False, 'checks': {}, 'error': 'Flask missing'}):
            self.assertFalse(report()['overall_pass'])

    def test_acceptance_fails_if_private_route_is_public(self):
        checks = {'anonymous GET /admin': {'status': 200, 'pass': False}}
        with patch('buyer_acceptance.static_checks', return_value=[]), patch('buyer_acceptance.runtime_checks', return_value={'runtime_available': True, 'checks': checks}):
            self.assertFalse(report()['overall_pass'])

    def test_route_coverage(self):
        self.assertIn('/marketplace', PUBLIC)
        self.assertIn('/admin', PRIVATE)

if __name__ == '__main__':
    unittest.main()
