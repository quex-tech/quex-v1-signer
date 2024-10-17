import unittest
import base64
from quex_backend.models import *


class TestModelsParsing(unittest.TestCase):

    def test_request_method_parsing(self):
        self.assertEqual(RequestMethod.parse("Get"), RequestMethod.GET)
        self.assertEqual(RequestMethod.parse("POST"), RequestMethod.POST)
        self.assertEqual(RequestMethod.parse("put"), RequestMethod.PUT)

    def test_request_header_parsing(self):
        data = {"key": "Content-Type", "value": "application/json"}
        header = RequestHeader.parse(data)
        self.assertEqual(header.key, "Content-Type")
        self.assertEqual(header.value, "application/json")

    def test_query_parameter_parsing(self):
        data = {"key": "id", "value": "1"}
        param = QueryParameter.parse(data)
        self.assertEqual(param.key, "id")
        self.assertEqual(param.value, "1")

    def test_query_parameter_patch_parsing(self):
        encoded_value = base64.b64encode(b"encrypted_value").decode('utf-8')
        data = {"key": "id", "ciphertext": encoded_value}
        param_patch = QueryParameterPatch.parse(data)
        self.assertEqual(param_patch.key, "id")
        self.assertEqual(param_patch.ciphertext, b"encrypted_value")

    def test_request_header_patch_parsing(self):
        encoded_value = base64.b64encode(b"encrypted_api_key").decode('utf-8')
        data = {"key": "Authorization", "ciphertext": encoded_value}
        header_patch = RequestHeaderPatch.parse(data)
        self.assertEqual(header_patch.key, "Authorization")
        self.assertEqual(header_patch.ciphertext, b"encrypted_api_key")

    def test_http_private_patch_parsing(self):
        encoded_value = base64.b64encode(b"encrypted_api_key").decode('utf-8')
        data = {
            "path_suffix": encoded_value,
            "headers": [{"key": "Authorization", "ciphertext": encoded_value}],
            "parameters": None,
            "body": None,
            "td_id": 12345
        }
        private_patch = HTTPPrivatePatch.parse(data)
        self.assertEqual(private_patch.path_suffix, b"encrypted_api_key")
        self.assertEqual(private_patch.headers[0].key, "Authorization")
        self.assertEqual(private_patch.headers[0].ciphertext, b"encrypted_api_key")
        self.assertEqual(private_patch.td_id, 12345)

    def test_http_request_parsing(self):
        data = {
            "method": "Get",
            "host": "api.example.com",
            "path": "/v1/resource",
            "headers": [{"key": "Content-Type", "value": "application/json"}],
            "parameters": [{"key": "id", "value": "1"}],
            "body": None
        }
        http_request = HTTPRequest.parse(data)
        self.assertEqual(http_request.method, RequestMethod.GET)
        self.assertEqual(http_request.host, "api.example.com")
        self.assertEqual(http_request.path, "/v1/resource")
        self.assertEqual(http_request.headers[0].key, "Content-Type")
        self.assertEqual(http_request.parameters[0].key, "id")

    def test_quex_request_parsing(self):
        encoded_value = base64.b64encode(b"encrypted_api_key").decode('utf-8')
        data = {
            "request": {
                "method": "Get",
                "host": "api.example.com",
                "path": "/v1/resource",
                "headers": [{"key": "Content-Type", "value": "application/json"}],
                "parameters": [{"key": "id", "value": "1"}],
                "body": None
            },
            "patch": {
                "path_suffix": encoded_value,
                "headers": [{"key": "Authorization", "ciphertext": encoded_value}],
                "parameters": None,
                "body": None,
                "td_id": 12345
            },
            "schema": "int256",
            "filter": "(.data[\"1\"].quote.USD.price * 1000000) | round"
        }

        quex_request = QuexRequest.parse(data)
        self.assertEqual(quex_request.request.method, RequestMethod.GET)
        self.assertEqual(quex_request.request.host, "api.example.com")
        self.assertEqual(quex_request.patch.path_suffix, b"encrypted_api_key")
        self.assertEqual(quex_request.schema, "int256")
        self.assertEqual(quex_request.filter, "(.data[\"1\"].quote.USD.price * 1000000) | round")


if __name__ == "__main__":
    unittest.main()
