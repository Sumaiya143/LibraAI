import unittest
from session_lifecycle import (
    ABSOLUTE_TIMEOUT_SECONDS, IDLE_TIMEOUT_SECONDS,
    session_expired, start_authenticated_session, touch_authenticated_session,
)

class SessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.session = {}
        start_authenticated_session(self.session, now=1000)

    def test_new_session_is_valid(self):
        self.assertFalse(session_expired(self.session, now=1001))

    def test_idle_timeout_expires_session(self):
        self.assertTrue(session_expired(self.session, now=1000 + IDLE_TIMEOUT_SECONDS))

    def test_activity_extends_idle_window(self):
        touch_authenticated_session(self.session, now=1000 + IDLE_TIMEOUT_SECONDS - 1)
        self.assertFalse(session_expired(self.session, now=1000 + IDLE_TIMEOUT_SECONDS))

    def test_absolute_timeout_cannot_be_extended_by_activity(self):
        touch_authenticated_session(self.session, now=1000 + ABSOLUTE_TIMEOUT_SECONDS - 1)
        self.assertTrue(session_expired(self.session, now=1000 + ABSOLUTE_TIMEOUT_SECONDS))

    def test_legacy_or_malformed_timestamps_fail_closed(self):
        self.assertTrue(session_expired({}, now=1000))
        self.assertTrue(session_expired({'_auth_started_at': '1000', '_auth_last_seen_at': 1000}, now=1001))

    def test_future_timestamp_fails_closed(self):
        self.assertTrue(session_expired(self.session, now=999))

if __name__ == '__main__':
    unittest.main()
