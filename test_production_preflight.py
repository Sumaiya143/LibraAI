import unittest
from production_preflight import audit_environment


class ProductionPreflightTests(unittest.TestCase):
    def good_env(self):
        return {
            "LIBRAAI_ENV": "production", "SECRET_KEY": "a" * 48,
            "LIBRAAI_DEBUG": "0", "LIBRAAI_PUBLIC_URL": "https://libra.example",
            "LIBRAAI_DB_PATH": "/data/libraai.db", "LIBRAAI_SESSION_BACKEND": "sqlite",
            "SSLCOMMERZ_STORE_ID": "merchant-id", "SSLCOMMERZ_STORE_PASSWORD": "merchant-secret",
            "SSLCOMMERZ_SANDBOX": "false", "BKASH_USERNAME": "merchant", "BKASH_PASSWORD": "pass",
            "BKASH_APP_KEY": "key", "BKASH_APP_SECRET": "secret", "BKASH_SANDBOX": "false",
            "LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED": "yes", "LIBRAAI_GATEWAY_E2E_VERIFIED": "yes",
            "LIBRAAI_STORAGE_BACKEND": "s3", "LIBRAAI_STORAGE_BUCKET": "private-books",
            "LIBRAAI_STORAGE_KEY": "key", "LIBRAAI_STORAGE_SECRET": "secret",
            "LIBRAAI_LICENSE_RIGHTS_VERIFIED": "yes", "LIBRAAI_CONTENT_RIGHTS_VERIFIED": "yes",
            "LIBRAAI_SECURITY_REVIEW_PASSED": "yes", "LIBRAAI_SECURITY_REVIEW_VERIFIED": "yes",
            "LIBRAAI_BACKUP_RESTORE_VERIFIED": "yes",
            "LIBRAAI_STORAGE_RESTORE_VERIFIED": "yes",
            "LIBRAAI_PRODUCTION_ACCEPTANCE_PASSED": "yes",
        }

    def status(self, report, check_id):
        return next(item["status"] for item in report["checks"] if item["id"] == check_id)

    def test_safe_configuration_passes_core_checks_without_leaking_secrets(self):
        env = self.good_env()
        report = audit_environment(env)
        self.assertEqual(report["blocker_count"], 0)
        self.assertEqual(self.status(report, "live-payments"), "pass")
        self.assertEqual(self.status(report, "private-storage"), "pass")
        self.assertNotIn("merchant-secret", str(report))
        self.assertNotIn("secret", str(report).lower().replace("secret", ""))

    def test_example_secret_is_blocked(self):
        env = self.good_env()
        env["SECRET_KEY"] = "REPLACE_WITH_STRONG_RANDOM_SECRET"
        self.assertEqual(self.status(audit_environment(env), "secret-key"), "blocker")

    def test_short_secret_is_blocked(self):
        env = self.good_env()
        env["SECRET_KEY"] = "short"
        self.assertEqual(self.status(audit_environment(env), "secret-key"), "blocker")

    def test_debug_mode_is_blocked(self):
        env = self.good_env()
        env["LIBRAAI_DEBUG"] = "1"
        self.assertEqual(self.status(audit_environment(env), "debug"), "blocker")

    def test_http_public_url_is_blocked(self):
        env = self.good_env()
        env["LIBRAAI_PUBLIC_URL"] = "http://libra.example"
        self.assertEqual(self.status(audit_environment(env), "https-url"), "blocker")

    def test_relative_database_path_is_blocked(self):
        env = self.good_env()
        env["LIBRAAI_DB_PATH"] = "libraai.db"
        self.assertEqual(self.status(audit_environment(env), "database-path"), "blocker")

    def test_payment_flags_alone_do_not_pass_without_credentials(self):
        env = self.good_env()
        for key in ("BKASH_APP_KEY", "SSLCOMMERZ_STORE_PASSWORD"):
            env.pop(key)
        self.assertEqual(self.status(audit_environment(env), "live-payments"), "blocker")

    def test_payment_sandbox_must_be_explicitly_disabled(self):
        env = self.good_env()
        env["BKASH_SANDBOX"] = "true"
        self.assertEqual(self.status(audit_environment(env), "live-payments"), "blocker")

    def test_private_storage_requires_credentials_and_bucket(self):
        env = self.good_env()
        env.pop("LIBRAAI_STORAGE_SECRET")
        self.assertEqual(self.status(audit_environment(env), "private-storage"), "blocker")

    def test_rights_need_both_attestations(self):
        env = self.good_env()
        env.pop("LIBRAAI_CONTENT_RIGHTS_VERIFIED")
        self.assertEqual(self.status(audit_environment(env), "content-rights"), "blocker")

    def test_security_review_needs_both_flags(self):
        env = self.good_env()
        env.pop("LIBRAAI_SECURITY_REVIEW_VERIFIED")
        self.assertEqual(self.status(audit_environment(env), "security-review"), "blocker")

    def test_backup_restore_is_independent_blocker(self):
        env = self.good_env()
        env.pop("LIBRAAI_BACKUP_RESTORE_VERIFIED")
        self.assertEqual(self.status(audit_environment(env), "backup-restore"), "blocker")

    def test_storage_restore_requires_live_evidence_flag(self):
        env = self.good_env()
        env.pop("LIBRAAI_STORAGE_RESTORE_VERIFIED")
        self.assertEqual(self.status(audit_environment(env), "storage-restore"), "blocker")

    def test_production_acceptance_is_separate_from_configuration(self):
        env = self.good_env()
        env.pop("LIBRAAI_PRODUCTION_ACCEPTANCE_PASSED")
        self.assertEqual(self.status(audit_environment(env), "production-acceptance"), "blocker")

    def test_automated_payouts_are_external_dependency_without_provider(self):
        report = audit_environment(self.good_env())
        self.assertEqual(self.status(report, "creator-payouts"), "external_dependency")
        self.assertEqual(report["external_dependency_count"], 1)

    def test_payout_flags_never_claim_provider_live_verification_is_complete(self):
        env = self.good_env()
        env["LIBRAAI_PAYOUT_PROVIDER"] = "approved-provider"
        env["LIBRAAI_PAYOUT_API_KEY"] = "configured-key"
        env["LIBRAAI_PAYOUT_LIVE_E2E_VERIFIED"] = "yes"
        self.assertEqual(self.status(audit_environment(env), "creator-payouts"), "external_dependency")

    def test_production_payout_adapter_rejects_insecure_endpoint(self):
        env = self.good_env()
        env.update({"LIBRAAI_ENV":"production", "LIBRAAI_PAYOUT_PROVIDER":"generic_http",
                    "LIBRAAI_PAYOUT_API_URL":"http://gateway.example/transfers",
                    "LIBRAAI_PAYOUT_API_KEY":"configured-key", "LIBRAAI_PAYOUT_WEBHOOK_SECRET":"webhook-secret"})
        self.assertEqual(self.status(audit_environment(env), "creator-payouts"), "blocker")

    def test_ai_is_optional_and_does_not_block_core_config(self):
        report = audit_environment(self.good_env())
        self.assertEqual(self.status(report, "external-ai"), "optional")
        self.assertEqual(report["blocker_count"], 0)

    def test_ai_key_is_reported_without_echoing_it(self):
        env = self.good_env()
        env["LIBRAAI_LLM_API_KEY"] = "private-provider-key-value"
        report = audit_environment(env)
        self.assertEqual(self.status(report, "external-ai"), "pass")
        self.assertNotIn("private-provider-key-value", str(report))

    def test_development_environment_is_reported_explicitly(self):
        env = self.good_env()
        env["LIBRAAI_ENV"] = "development"
        self.assertFalse(audit_environment(env)["production_environment"])

    def test_report_never_claims_live_verification_is_proven(self):
        self.assertIn("cannot prove", audit_environment(self.good_env())["note"])

    def test_missing_everything_produces_actionable_blockers(self):
        report = audit_environment({})
        self.assertGreaterEqual(report["blocker_count"], 7)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(all(item.get("detail") for item in report["checks"]))


    def test_malformed_https_url_is_blocked(self):
        env = self.good_env()
        env["LIBRAAI_PUBLIC_URL"] = "https://"
        self.assertEqual(self.status(audit_environment(env), "https-url"), "blocker")

    def test_public_url_alias_mismatch_is_blocked(self):
        env = self.good_env()
        env["PUBLIC_BASE_URL"] = "https://other.example"
        self.assertEqual(self.status(audit_environment(env), "public-url-alias"), "blocker")

    def test_redis_session_backend_requires_shared_store_url(self):
        env = self.good_env()
        env["LIBRAAI_SESSION_BACKEND"] = "redis"
        self.assertEqual(self.status(audit_environment(env), "session-backend"), "blocker")
        env["REDIS_URL"] = "rediss://user:pass@redis.internal:6379/0"
        self.assertEqual(self.status(audit_environment(env), "session-backend"), "pass")

    def test_multi_instance_is_blocked_until_primary_database_migrates(self):
        env = self.good_env()
        env["LIBRAAI_MULTI_INSTANCE"] = "yes"
        env["LIBRAAI_SESSION_BACKEND"] = "redis"
        env["LIBRAAI_RATE_LIMIT_BACKEND"] = "redis"
        env["REDIS_URL"] = "rediss://user:pass@redis.internal:6379/0"
        report = audit_environment(env)
        self.assertEqual(self.status(report, "session-backend"), "pass")
        self.assertEqual(self.status(report, "shared-rate-limit"), "pass")
        self.assertEqual(self.status(report, "primary-database-scale"), "blocker")

    def test_unsupported_session_backend_is_blocked(self):
        env = self.good_env()
        env["LIBRAAI_SESSION_BACKEND"] = "mongodb"
        self.assertEqual(self.status(audit_environment(env), "session-backend"), "blocker")

    def test_missing_session_backend_is_blocked(self):
        env = self.good_env()
        env.pop("LIBRAAI_SESSION_BACKEND")
        self.assertEqual(self.status(audit_environment(env), "session-backend"), "blocker")


if __name__ == "__main__":
    unittest.main()
