import json
import unittest
from dataclasses import dataclass
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import Timeout

from quex_backend.models import HTTPRequest, QueryParameter, RequestHeader, RequestMethod
from quex_backend.utils import (
    RequestConnectionError,
    Response4XXError,
    Response5XXError,
    ResponseNotSupportedResponseCodeError,
    make_request,
)


@dataclass
class TestVector:
    __test__ = False
    host: str
    expected_exception_type: type[Exception] | None = None
    expected_error: str = ""
    path: str = ""
    as_json: bool = False

    def get_request(self) -> HTTPRequest:
        return HTTPRequest(method=RequestMethod.GET, host=self.host, path=self.path, headers=[], parameters=[], body=[])


class TestRequests(unittest.TestCase):
    # Correct requests that should pass without errors
    correct_requests = [
        TestVector("www.binance.com", None, "", "/api/v3/ticker/price", as_json=True),
        TestVector("sha256.badssl.com/"),
        TestVector("ecc256.badssl.com/"),
        TestVector("ecc384.badssl.com/"),
        TestVector("ecc384.badssl.com/"),
        TestVector("rsa2048.badssl.com/"),
        TestVector("rsa4096.badssl.com/"),
        TestVector("https-everywhere.badssl.com/"),
        TestVector("long-extended-subdomain-name-containing-many-letters-and-dashes.badssl.com/"),
        TestVector("longextendedsubdomainnamewithoutdashesinordertotestwordwrapping.badssl.com/"),
        TestVector("mozilla-modern.badssl.com/"),
        # These certificates are expired
        # TestVector("sha512.badssl.com/"),
        # TestVector("1000-sans.badssl.com/"),
        # TestVector("10000-sans.badssl.com/"),
        # TestVector("extended-validation.badssl.com/"),
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
        TestVector("expired.badssl.com/", RequestConnectionError, "certificate has expired"),
        TestVector("wrong.host.badssl.com", RequestConnectionError, "Hostname mismatch"),
        TestVector("self-signed.badssl.com/", RequestConnectionError, "self-signed certificate"),
        TestVector("untrusted-root.badssl.com/", RequestConnectionError, "self-signed certificate in certificate chain"),
        TestVector("no-subject.badssl.com/", RequestConnectionError, "certificate has expired"),
        TestVector("no-common-name.badssl.com", RequestConnectionError, "certificate has expired"),
        TestVector("incomplete-chain.badssl.com", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        # Key Exchange
        TestVector("dh480.badssl.com", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("dh512.badssl.com", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("dh1024.badssl.com", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("static-rsa.badssl.com", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("dh2048.badssl.com", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("dh-small-subgroup.badssl.com", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("dh-composite.badssl.com", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        # Protocol
        TestVector("tls-v1-0.badssl.com:1010/", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("tls-v1-1.badssl.com:1011/", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        # Upgrade
        TestVector("subdomain.preloaded-hsts.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        # HTTP
        TestVector("http.badssl.com/", ResponseNotSupportedResponseCodeError),
        TestVector("http-textarea.badssl.com/", ResponseNotSupportedResponseCodeError),
        TestVector("http-password.badssl.com/", ResponseNotSupportedResponseCodeError),
        TestVector("http-login.badssl.com/", ResponseNotSupportedResponseCodeError),
        TestVector("http-dynamic-login.badssl.com/", ResponseNotSupportedResponseCodeError),
        TestVector("http-credit-card.badssl.com/", ResponseNotSupportedResponseCodeError),
        # Known Bad
        TestVector("superfish.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        TestVector("edellroot.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        TestVector("dsdtestprovider.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        TestVector("preact-cli.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        TestVector("webpack-dev-server.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        # Chrome Tests
        TestVector("captive-portal.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        TestVector("mitm-software.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        # Defunct
        TestVector("sha1-2016.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        TestVector("sha1-2017.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        TestVector("sha1-intermediate.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        TestVector("invalid-expected-sct.badssl.com/", RequestConnectionError, "CERTIFICATE_VERIFY_FAILED"),
        # Cipher Suite
        TestVector("rc4-md5.badssl.com/", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("3des.badssl.com/", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("null.badssl.com/", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("cbc.badssl.com/", RequestConnectionError, "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("client-cert-missing.badssl.com/", Response4XXError),
    ]

    mock_test_vectors = [
        (Mock(status_code=200, json=lambda: {"key": "value"}), {"key": "value"}, None),
        (Mock(status_code=201, json=lambda: {"key": "value"}), {"key": "value"}, None),
        (Mock(status_code=204), "", None),
        (Mock(status_code=400), {}, Response4XXError),
        (Mock(status_code=500), {}, Response5XXError),
        (Timeout(), {}, RequestConnectionError),
    ]

    def test_make_request(self):
        for effect, expected_result, expected_error in self.mock_test_vectors:
            with patch("requests.Session.request") as mock_request:
                print(f"Testing {effect}, {expected_result}, {expected_error}")

                # Setup
                body_content = {"param1": "value1", "param2": 42, "param3": {"nested_key": "nested_value"}}
                body_bytes = json.dumps(body_content).encode()

                http_request = HTTPRequest(
                    method=RequestMethod.GET,
                    host="api.example.com",
                    path="/v1/resource",
                    headers=[RequestHeader("Content-Type", "application/json")],
                    parameters=[QueryParameter("id", "1")],
                    body=body_bytes,
                )

                # Mock response
                if isinstance(effect, Mock):
                    mock_request.return_value = effect
                else:
                    mock_request.side_effect = effect

                if expected_error is not None:
                    with self.assertRaises(expected_error):
                        response = make_request(http_request)
                        print(f"Response: {response}")
                else:
                    response = make_request(http_request)
                    self.assertEqual(response, expected_result)

                # Check the parameters
                mock_request.assert_called_once_with(
                    "GET",
                    "https://api.example.com/v1/resource",
                    params={"id": "1"},
                    headers={"Content-Type": "application/json"},
                    data=body_bytes,
                    verify=True,
                    allow_redirects=False,
                )

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
            resp = make_request(request, as_json=False)

        except Exception as e:
            if v.expected_exception_type is None:
                self.assertTrue(False, f"Expected no exception for {v}, got {e}")
            self.assertIsInstance(e, v.expected_exception_type)
            exception_string = repr(e.__cause__)
            self.assertIn(v.expected_error, exception_string)

        else:
            if v.expected_error != "":
                self.assertTrue(False, f"Expected error for {v}, got response {resp} with no errors")


if __name__ == "__main__":
    pytest.main()
