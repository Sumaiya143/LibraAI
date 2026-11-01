"""Gateway response validation regression tests (no merchant credentials needed)."""
import io
import json
import unittest
from unittest.mock import patch
from payment_providers import request_json, ssl_init, bkash_init, _trusted_checkout_url, GatewayError, _NoRedirect, MAX_GATEWAY_RESPONSE_BYTES

class FakeResponse:
    status = 200
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.body[:limit]

class FakeOpener:
    def __init__(self, response): self.response = response
    def open(self, request, timeout): return self.response

class GatewayResponseTests(unittest.TestCase):
    def test_json_array_rejected(self):
        with patch('urllib.request.build_opener', return_value=FakeOpener(FakeResponse(b'[]'))):
            with self.assertRaises(GatewayError): request_json('https://example.com')
    def test_duplicate_json_keys_rejected(self):
        body = b'{"status":"FAILED","status":"SUCCESS"}'
        with patch('urllib.request.build_opener', return_value=FakeOpener(FakeResponse(body))):
            with self.assertRaisesRegex(GatewayError, 'Gateway request failed'):
                request_json('https://example.com')

    def test_json_null_rejected(self):
        with patch('urllib.request.build_opener', return_value=FakeOpener(FakeResponse(b'null'))):
            with self.assertRaises(GatewayError): request_json('https://example.com')
    def test_json_object_accepted(self):
        with patch('urllib.request.build_opener', return_value=FakeOpener(FakeResponse(b'{"ok":true}'))):
            self.assertEqual(request_json('https://example.com'), {'ok':True})

    def test_oversized_gateway_response_rejected(self):
        body = b'{"x":"' + (b'a' * MAX_GATEWAY_RESPONSE_BYTES) + b'"}'
        with patch('urllib.request.build_opener', return_value=FakeOpener(FakeResponse(body))):
            with self.assertRaisesRegex(GatewayError, 'size limit'):
                request_json('https://example.com')

    def test_redirect_handler_refuses_redirect(self):
        handler = _NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, 'Found', {}, 'https://attacker.example'))

    def test_gateway_url_with_embedded_credentials_rejected(self):
        with self.assertRaisesRegex(GatewayError, 'HTTPS URL required'):
            request_json('https://user:password@example.com')


    def test_checkout_url_rejects_userinfo_nonstandard_port_and_fragment(self):
        invalid = [
            'https://user@sandbox.sslcommerz.com/checkout',
            'https://sandbox.sslcommerz.com:8443/checkout',
            'https://sandbox.sslcommerz.com/checkout#fragment',
            'http://sandbox.sslcommerz.com/checkout',
            'https://sandbox.sslcommerz.com\\attacker.example/checkout',
        ]
        for url in invalid:
            with self.subTest(url=url):
                self.assertFalse(_trusted_checkout_url(url, expected_host='sandbox.sslcommerz.com'))

    def test_checkout_url_accepts_trusted_provider_https_url(self):
        self.assertTrue(_trusted_checkout_url(
            'https://sandbox.sslcommerz.com/checkout/session?id=abc',
            expected_host='sandbox.sslcommerz.com'))
        self.assertTrue(_trusted_checkout_url(
            'https://checkout.pay.bka.sh/checkout/session', allowed_suffix='bka.sh'))

    def test_bkash_checkout_rejects_untrusted_url_shapes(self):
        attempt={'amount_cents':10000,'merchant_ref':'ref','order_id':1}
        invalid_urls = [
            'https://user@checkout.pay.bka.sh/checkout',
            'https://checkout.pay.bka.sh:8443/checkout',
            'https://checkout.pay.bka.sh/checkout#fragment',
            'https://bka.sh/checkout',
            'https://checkout.bka-sh.example/checkout',
        ]
        with patch('payment_providers.bkash_token', return_value='token'):
            for url in invalid_urls:
                with self.subTest(url=url):
                    with patch('payment_providers.bkash_call', return_value={
                        'statusCode':'0000','paymentID':'pay-1','bkashURL':url}):
                        with self.assertRaises(GatewayError): bkash_init(attempt, 'https://shop.example')

    def test_bkash_rejects_unapproved_subdomains_even_under_bka_sh(self):
        attempt={'amount_cents':10000,'merchant_ref':'ref','order_id':1}
        invalid_urls = [
            'https://evil.checkout.pay.bka.sh/checkout/payment',
            'https://attacker.bka.sh/checkout/payment',
            'https://tokenized.pay.bka.sh.attacker.example/checkout/payment',
        ]
        with patch.dict('os.environ', {'BKASH_SANDBOX':'false'}):
            with patch('payment_providers.bkash_token', return_value='token'):
                for url in invalid_urls:
                    with self.subTest(url=url):
                        with patch('payment_providers.bkash_call', return_value={
                            'statusCode':'0000','paymentID':'pay-1','bkashURL':url}):
                            with self.assertRaises(GatewayError):
                                bkash_init(attempt, 'https://shop.example')

    def test_bkash_rejects_checkout_host_from_different_api_product(self):
        attempt={'amount_cents':10000,'merchant_ref':'ref','order_id':1}
        with patch.dict('os.environ', {'BKASH_SANDBOX':'false'}):
            with patch('payment_providers.bkash_token', return_value='token'):
                with patch('payment_providers.bkash_call', return_value={
                    'statusCode':'0000','paymentID':'pay-1',
                    'bkashURL':'https://checkout.pay.bka.sh/checkout/payment/pay-1'}):
                    with self.assertRaises(GatewayError):
                        bkash_init(attempt, 'https://shop.example')

    def test_bkash_accepts_exact_environment_checkout_host(self):
        attempt={'amount_cents':10000,'merchant_ref':'ref','order_id':1}
        with patch.dict('os.environ', {'BKASH_SANDBOX':'true'}):
            with patch('payment_providers.bkash_token', return_value='token'):
                with patch('payment_providers.bkash_call', return_value={
                    'statusCode':'0000','paymentID':'pay-1',
                    'bkashURL':'https://tokenized.sandbox.bka.sh/checkout/payment/pay-1'}):
                    result = bkash_init(attempt, 'https://shop.example')
                    self.assertEqual(result['url'], 'https://tokenized.sandbox.bka.sh/checkout/payment/pay-1')
        with patch.dict('os.environ', {'BKASH_SANDBOX':'false'}):
            with patch('payment_providers.bkash_token', return_value='token'):
                with patch('payment_providers.bkash_call', return_value={
                    'statusCode':'0000','paymentID':'pay-1',
                    'bkashURL':'https://tokenized.pay.bka.sh/checkout/payment/pay-1'}):
                    result = bkash_init(attempt, 'https://shop.example')
                    self.assertEqual(result['url'], 'https://tokenized.pay.bka.sh/checkout/payment/pay-1')

    def test_ssl_sandbox_cannot_redirect_to_live_gateway(self):
        attempt={'amount_cents':10000,'merchant_ref':'ref','order_id':1}
        response={'status':'SUCCESS','GatewayPageURL':'https://securepay.sslcommerz.com/checkout','sessionkey':'x'}
        with patch.dict('os.environ',{'SSLCOMMERZ_SANDBOX':'true','SSLCOMMERZ_STORE_ID':'x','SSLCOMMERZ_STORE_PASSWORD':'y'}):
            with patch('payment_providers.request_json',return_value=response):
                with self.assertRaises(GatewayError): ssl_init(attempt,{},'https://shop.example')
    def test_ssl_live_cannot_redirect_to_sandbox_gateway(self):
        attempt={'amount_cents':10000,'merchant_ref':'ref','order_id':1}
        response={'status':'SUCCESS','GatewayPageURL':'https://sandbox.sslcommerz.com/checkout','sessionkey':'x'}
        with patch.dict('os.environ',{'SSLCOMMERZ_SANDBOX':'false','SSLCOMMERZ_STORE_ID':'x','SSLCOMMERZ_STORE_PASSWORD':'y'}):
            with patch('payment_providers.request_json',return_value=response):
                with self.assertRaises(GatewayError): ssl_init(attempt,{},'https://shop.example')

if __name__ == '__main__': unittest.main()
