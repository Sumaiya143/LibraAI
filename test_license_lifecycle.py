import unittest
from datetime import datetime, timezone
from license_policy import license_is_active, license_allows_format

class LicenseLifecycleTests(unittest.TestCase):
    def base(self):
        return {'license_status':'active','license_valid_from':None,'license_expires_at':None,'license_territories':'*'}
    def test_active_unbounded_license(self):
        self.assertTrue(license_is_active(self.base(), datetime(2026,1,1,tzinfo=timezone.utc)))
    def test_future_start_is_not_active(self):
        doc=self.base(); doc['license_valid_from']='2027-01-01'
        self.assertFalse(license_is_active(doc, datetime(2026,12,31,tzinfo=timezone.utc)))
    def test_expired_license_is_not_active(self):
        doc=self.base(); doc['license_expires_at']='2026-01-01'
        self.assertFalse(license_is_active(doc, datetime(2026,1,1,tzinfo=timezone.utc)))
    def test_revoked_license_is_not_active(self):
        doc=self.base(); doc['license_status']='revoked'
        self.assertFalse(license_is_active(doc))
    def test_territory_is_enforced(self):
        doc=self.base(); doc['license_territories']='BD,IN'
        self.assertTrue(license_is_active(doc, territory='BD'))
        self.assertFalse(license_is_active(doc, territory='US'))
    def test_restricted_territory_requires_verified_country(self):
        doc=self.base(); doc['license_territories']='BD,IN'
        self.assertFalse(license_is_active(doc))

    def test_format_scope_is_enforced(self):
        doc=self.base(); doc['licensed_formats']='audiobook'
        self.assertTrue(license_allows_format(doc, 'audiobook'))
        self.assertFalse(license_allows_format(doc, 'ebook'))

    def test_invalid_date_fails_closed(self):
        doc=self.base(); doc['license_expires_at']='not-a-date'
        self.assertFalse(license_is_active(doc))

if __name__ == '__main__': unittest.main()
