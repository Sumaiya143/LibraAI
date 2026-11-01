"""Fail-closed runner for payment callback HTTP integration tests.

Unlike ordinary unittest discovery, this command fails if Flask is unavailable
or if any callback-route test is skipped. It prevents CI from reporting a green
suite while the payment HTTP boundary has not actually been exercised.
"""
import sys
import unittest

import test_payment_callbacks_integration as payment_tests

EXPECTED_TESTS = 5


def main() -> int:
    if payment_tests.FLASK_IMPORT_ERROR is not None:
        print(
            "ERROR: payment callback route tests cannot run; missing runtime "
            f"dependency: {payment_tests.FLASK_IMPORT_ERROR}",
            file=sys.stderr,
        )
        return 2

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        payment_tests.PaymentCallbackRouteIntegrationTests
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != EXPECTED_TESTS:
        print(
            f"ERROR: expected {EXPECTED_TESTS} payment route tests, "
            f"ran {result.testsRun}",
            file=sys.stderr,
        )
        return 3
    if result.skipped:
        print(
            f"ERROR: {len(result.skipped)} payment route tests were skipped",
            file=sys.stderr,
        )
        return 4
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
