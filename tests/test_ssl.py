import unittest

import pytest

from quex_backend.utils import *
from quex_backend.models import *


@dataclass
class TestVector:
    host: str
    path: str
    expected_error: str

    def get_request(self) -> HTTPRequest:
        return HTTPRequest(
            method=RequestMethod.GET,
            host=self.host,
            path=self.path,
            headers=[],
            parameters=[],
            body=[]
        )


class TestUtils(unittest.TestCase):
    test_vectors = [
        # correct requests
        TestVector("www.binance.com", "/api/v3/ticker/price", ""),

        # TLS errors
        # Certificate section
        TestVector("expired.badssl.com/", "", "certificate has expired"),
        TestVector("wrong.host.badssl.com", "", "Hostname mismatch"),
        TestVector("self-signed.badssl.com/", "", "self-signed certificate"),
        TestVector("untrusted-root.badssl.com/", "", "self-signed certificate in certificate chain"),
        TestVector("no-subject.badssl.com/", "", "certificate has expired"),
        TestVector("no-common-name.badssl.com", "", "certificate has expired"),
        TestVector("incomplete-chain.badssl.com", "", "CERTIFICATE_VERIFY_FAILED"),

        # Key Exchange
        TestVector("dh480.badssl.com", "", "BAD_DH_VALUE"),
        TestVector("dh512.badssl.com", "", "DH_KEY_TOO_SMALL"),
        TestVector("dh1024.badssl.com", "", "DH_KEY_TOO_SMALL"),
        TestVector("static-rsa.badssl.com", "", "SSLV3_ALERT_HANDSHAKE_FAILURE"),

        # Protocol
        TestVector("tls-v1-0.badssl.com:1010/", "", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("tls-v1-1.badssl.com:1011/", "", "SSLV3_ALERT_HANDSHAKE_FAILURE"),

        # Upgrade
        TestVector("subdomain.preloaded-hsts.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),

        # HTTP
        TestVector("http.badssl.com/", "", "Got status code 301"),
        TestVector("http-textarea.badssl.com/", "", "Got status code 301"),
        TestVector("http-password.badssl.com/", "", "Got status code 301"),
        TestVector("http-login.badssl.com/", "", "Got status code 301"),
        TestVector("http-dynamic-login.badssl.com/", "", "Got status code 301"),
        TestVector("http-credit-card.badssl.com/", "", "Got status code 301"),

        # Known Bad
        TestVector("superfish.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("edellroot.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("dsdtestprovider.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("preact-cli.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("webpack-dev-server.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),

        # Chrome Tests
        TestVector("captive-portal.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("mitm-software.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),

        # Defunct
        TestVector("sha1-2016.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("sha1-2017.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("sha1-intermediate.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),
        TestVector("invalid-expected-sct.badssl.com/", "", "CERTIFICATE_VERIFY_FAILED"),

        # Cipher Suite
        TestVector("rc4-md5.badssl.com/", "", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("3des.badssl.com/", "", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
        TestVector("null.badssl.com/", "", "SSLV3_ALERT_HANDSHAKE_FAILURE"),
    ]

    failing_vectors = [
        # Certificate section
        TestVector("revoked.badssl.com", "", "???"),
        TestVector("pinning-test.badssl.com", "", "???"),

        # Key Exchange
        TestVector("dh2048.badssl.com", "", "???"),
        TestVector("dh-small-subgroup.badssl.com", "", "???"),
        TestVector("dh-composite.badssl.com", "", "???"),

        # Certificate Transparency
        TestVector("no-sct.badssl.com", "", "???"),

        # Client Certificate
        TestVector("client-cert-missing.badssl.com/", "", "???"),

        # Mixed Content
        TestVector("mixed-script.badssl.com/", "", "???"),
        TestVector("very.badssl.com/", "", "???"),
        TestVector("mixed.badssl.com/", "", "???"),
        TestVector("mixed-favicon.badssl.com/", "", "???"),
        TestVector("mixed-form.badssl.com/", "", "???"),

        # Cipher Suite
        TestVector("cbc.badssl.com/", "", "???"),
        TestVector("mozilla-old.badssl.com/", "", "???"),
        TestVector("mozilla-intermediate.badssl.com/", "", "???"),

    ]

    def test_certificates(self):
        for v in self.test_vectors:
        # for v in self.failing_vectors:
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
