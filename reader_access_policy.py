"""Fail-closed policy for public sample and licensed digital reading."""
from license_policy import license_is_active, license_allows_format

def document_is_readable(document, signed_in=False, entitled=False, is_admin=False, territory=None):
    if not license_is_active(document, territory=territory):
        return False
    policy = document['access_policy']
    if policy == 'sample':
        return license_allows_format(document, 'ebook') or license_allows_format(document, 'sample')
    if policy == 'licensed':
        return bool(is_admin or (signed_in and entitled)) and license_allows_format(document, 'ebook')
    return False
