"""Fail-closed credential checks for existing databases before a production launch."""

class CredentialIntegrityError(RuntimeError):
    pass


def inspect_users(conn):
    """Return safe aggregate findings; never expose user emails or password hashes."""
    rows = conn.execute('SELECT password FROM users').fetchall()
    accepted = ('scrypt:', 'pbkdf2:')
    invalid = sum(not isinstance(row[0], str) or not row[0].startswith(accepted) for row in rows)
    return {'users_checked': len(rows), 'invalid_password_hashes': invalid}


def require_secure_credentials(conn):
    report = inspect_users(conn)
    if report['invalid_password_hashes']:
        raise CredentialIntegrityError(
            'Production database contains legacy/unsupported password hashes. '
            'Stop deployment and migrate credentials using a verified secure procedure.'
        )
    return report
