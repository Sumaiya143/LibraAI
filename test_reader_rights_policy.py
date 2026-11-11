import unittest
from datetime import datetime, timezone, timedelta
from reader_access_policy import document_is_readable

class ReaderRightsPolicyTests(unittest.TestCase):
 def base(self, **extra):
  row={'access_policy':'licensed','license_status':'active','license_valid_from':None,'license_expires_at':None,'license_territories':'*','licensed_formats':'ebook'}; row.update(extra); return row
 def test_active_sample_is_free(self): self.assertTrue(document_is_readable(self.base(access_policy='sample'),False,False))
 def test_active_licensed_book_requires_entitlement(self): self.assertFalse(document_is_readable(self.base(),True,False)); self.assertTrue(document_is_readable(self.base(),True,True))
 def test_revoked_and_suspended_documents_are_blocked(self):
  self.assertFalse(document_is_readable(self.base(license_status='revoked'),True,True)); self.assertFalse(document_is_readable(self.base(license_status='suspended'),True,True))
 def test_expired_document_is_blocked(self): self.assertFalse(document_is_readable(self.base(license_expires_at='2020-01-01T00:00:00+00:00'),True,True))
 def test_territory_restriction_fails_closed(self):
  self.assertFalse(document_is_readable(self.base(license_territories='BD'),True,True,territory=None)); self.assertTrue(document_is_readable(self.base(license_territories='BD'),True,True,territory='BD'))
 def test_non_ebook_license_does_not_grant_text_reader(self): self.assertFalse(document_is_readable(self.base(licensed_formats='audiobook'),True,True))
 def test_unknown_policy_is_blocked(self): self.assertFalse(document_is_readable(self.base(access_policy='open'),True,True))
if __name__=='__main__': unittest.main()
