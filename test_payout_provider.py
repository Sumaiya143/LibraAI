import json, os, unittest
from unittest.mock import patch, MagicMock
from payout_provider import config_from_env, sign_webhook, verify_webhook, submit_transfer, lookup_transfer, PayoutProviderError, PayoutProviderConfig

class PayoutProviderTests(unittest.TestCase):
    def test_provider_requires_full_configuration(self):
        with self.assertRaises(PayoutProviderError) as ctx: config_from_env({})
        self.assertEqual(ctx.exception.code,'provider_not_configured')
    def test_production_requires_https_endpoint(self):
        env={'LIBRAAI_ENV':'production','LIBRAAI_PAYOUT_PROVIDER':'generic_http','LIBRAAI_PAYOUT_API_URL':'http://payout.example/transfer','LIBRAAI_PAYOUT_API_KEY':'x','LIBRAAI_PAYOUT_WEBHOOK_SECRET':'w'*40}
        with self.assertRaises(PayoutProviderError): config_from_env(env)
    def test_webhook_signature_is_constant_time_verified(self):
        body=b'{"event_id":"evt_1"}'; signature=sign_webhook(body,'secret')
        self.assertTrue(verify_webhook(body,signature,'secret'))
        self.assertFalse(verify_webhook(body,signature,'wrong'))
        self.assertFalse(verify_webhook(body,'','secret'))
    def test_invalid_idempotency_key_is_rejected_before_network(self):
        cfg=PayoutProviderConfig('http://127.0.0.1:1/transfer','token','secret',2)
        with self.assertRaises(PayoutProviderError) as ctx:
            submit_transfer(cfg,payout_id=7,amount_cents=100,currency='BDT',method='bkash',destination='01712345678',idempotency_key='bad')
        self.assertEqual(ctx.exception.code,'idempotency_invalid')
    def test_reconciliation_requires_final_reference_for_paid(self):
        import payout_provider
        response=MagicMock(); response.status=200; response.read.return_value=json.dumps({'status':'paid'}).encode(); response.__enter__.return_value=response
        config=PayoutProviderConfig('https://provider.example/transfers','token','secret',2)
        with patch.object(payout_provider.urllib.request,'urlopen',return_value=response):
            with self.assertRaises(PayoutProviderError) as ctx:
                lookup_transfer(config,idempotency_key='libraai-payout-7')
        self.assertEqual(ctx.exception.code,'provider_reference_missing')

    def test_provider_initiation_never_marks_paid_without_final_webhook(self):
        import payout_provider
        response=MagicMock(); response.status=200
        response.read.return_value=json.dumps({'status':'paid','reference':'txn-123'}).encode()
        response.__enter__.return_value=response
        config=PayoutProviderConfig('https://provider.example/transfers','token','secret',2)
        with patch.object(payout_provider.urllib.request,'urlopen',return_value=response) as send:
            result=submit_transfer(config,payout_id=7,amount_cents=1000,currency='BDT',method='bkash',destination='01712345678',idempotency_key='libraai-payout-7')
        self.assertEqual(result['status'],'processing')
        self.assertEqual(result['reference'],'txn-123')
        req=send.call_args.args[0]
        self.assertEqual(req.get_header('Idempotency-key'),'libraai-payout-7')

if __name__=='__main__': unittest.main()
