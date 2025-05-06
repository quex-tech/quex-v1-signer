import unittest
from unittest.mock import patch

import pytest
import json

from quex_backend.models import *
from quex_backend.utils import *


@dataclass
class TestVector:
    __test__ = False
    host: str
    expected_error: str = ""
    path: str = ""

    def get_request(self) -> HTTPRequest:
        return HTTPRequest(
            method=RequestMethod.GET,
            host=self.host,
            path=self.path,
            headers=[],
            parameters=[],
            body=[]
        )


class TestRequests(unittest.TestCase):
    # Correct requests that should pass without errors
    correct_requests = [
        TestVector("www.binance.com", "", "/api/v3/ticker/price"),
        TestVector("sha256.badssl.com/"),
        TestVector("sha512.badssl.com/"),
        TestVector("1000-sans.badssl.com/"),
        TestVector("10000-sans.badssl.com/"),
        TestVector("ecc256.badssl.com/"),
        TestVector("ecc384.badssl.com/"),
        TestVector("ecc384.badssl.com/"),
        TestVector("rsa2048.badssl.com/"),
        TestVector("rsa4096.badssl.com/"),
        TestVector("extended-validation.badssl.com/"),
        TestVector("https-everywhere.badssl.com/"),
        TestVector("long-extended-subdomain-name-containing-many-letters-and-dashes.badssl.com/"),
        TestVector("longextendedsubdomainnamewithoutdashesinordertotestwordwrapping.badssl.com/"),
        TestVector("mozilla-modern.badssl.com/"),
    ]

    # Weak certificates, that should not be accepted, but requests passes
    failing_vectors = [
        # Certificate section
        # TODO: TestVector("revoked.badssl.com", "???"),
        # # Certificate Transparency
        # TODO TestVector("no-sct.badssl.com", "???"),

        # Cipher Suite
        # TODO: might be fixed be allowing TLS 1.3 only
        # TestVector("mozilla-old.badssl.com", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        # TestVector("mozilla-intermediate.badssl.com/", "SSLV3_ALERT_HANDSHAKE_FAILURE"),

    ]

    # Certificates that should not be accepted
    incorrect_certificates = [

        # TLS errors
        # Certificate section
        TestVector("expired.badssl.com/", "certificate has expired"),
        TestVector("wrong.host.badssl.com", "Hostname mismatch"),
        TestVector("self-signed.badssl.com/", "self-signed certificate"),
        TestVector("untrusted-root.badssl.com/", "self-signed certificate in certificate chain"),
        TestVector("no-subject.badssl.com/", "certificate has expired"),
        TestVector("no-common-name.badssl.com", "certificate has expired"),
        TestVector("incomplete-chain.badssl.com", "CERTIFICATE_VERIFY_FAILED"),

        # Key Exchange
        TestVector("dh480.badssl.com", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("dh512.badssl.com", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("dh1024.badssl.com", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("static-rsa.badssl.com", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("dh2048.badssl.com", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("dh-small-subgroup.badssl.com", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("dh-composite.badssl.com", "SSLV3_ALERT_HANDSHAKE_FAILURE"),

        # Protocol
        TestVector("tls-v1-0.badssl.com:1010/", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("tls-v1-1.badssl.com:1011/", "SSLV3_ALERT_HANDSHAKE_FAILURE"),

        # Upgrade
        TestVector("subdomain.preloaded-hsts.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),

        # HTTP
        TestVector("http.badssl.com/", "Got status code 301"),
        TestVector("http-textarea.badssl.com/", "Got status code 301"),
        TestVector("http-password.badssl.com/", "Got status code 301"),
        TestVector("http-login.badssl.com/", "Got status code 301"),
        TestVector("http-dynamic-login.badssl.com/", "Got status code 301"),
        TestVector("http-credit-card.badssl.com/", "Got status code 301"),

        # Known Bad
        TestVector("superfish.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("edellroot.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("dsdtestprovider.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("preact-cli.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("webpack-dev-server.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),

        # Chrome Tests
        TestVector("captive-portal.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("mitm-software.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),

        # Defunct
        TestVector("sha1-2016.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("sha1-2017.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("sha1-intermediate.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("invalid-expected-sct.badssl.com/", "CERTIFICATE_VERIFY_FAILED"),

        # Cipher Suite
        TestVector("rc4-md5.badssl.com/", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("3des.badssl.com/", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("null.badssl.com/", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("cbc.badssl.com/", "SSLV3_ALERT_HANDSHAKE_FAILURE"),

        TestVector("client-cert-missing.badssl.com/", "Got status code 400 for requ"),

    ]

    @patch("requests.Session.request")
    def test_make_request(self, mock_request):
        # Setup
        body_content = {
            "param1": "value1",
            "param2": 42,
            "param3": {"nested_key": "nested_value"}
        }
        body_bytes = json.dumps(body_content).encode()

        http_request = HTTPRequest(
            method=RequestMethod.GET,
            host="api.example.com",
            path="/v1/resource",
            headers=[RequestHeader("Content-Type", "application/json")],
            parameters=[QueryParameter("id", "1")],
            body=body_bytes
        )

        # Mock response
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {"key": "value"}

        # Call the function
        response = make_request(http_request, as_json=True)

        # Check the parameters
        mock_request.assert_called_once_with(
            "GET",
            "https://api.example.com/v1/resource",
            params={"id": "1"},
            headers={"Content-Type": "application/json"},
            data=body_bytes,
            verify=True,
            allow_redirects=False
        )

        # Check the response
        self.assertEqual(response, {"key": "value"})

    def test_correct_certificates(self):
        for v in self.correct_requests:
            self.check_test_vector(v)

    def test_failing_certificates(self):
        for v in self.failing_vectors:
            self.check_test_vector(v)

    def test_incorrect_certificates(self):
        for v in self.incorrect_certificates:
            print(f"Testing {v}")
            self.check_test_vector(v)

    def check_test_vector(self, v: TestVector):
        request = v.get_request()
        try:
            resp = make_request(request, False)

        except Exception as e:
            exception_string = repr(e)
            self.assertIn(v.expected_error, exception_string)

        else:
            if v.expected_error != "":
                self.assertTrue(False, f"Expected error for {v}, got response {resp} with no errors")


if __name__ == '__main__':
    pytest.main()
