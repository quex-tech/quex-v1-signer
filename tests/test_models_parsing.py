import unittest
from pathlib import Path
import binascii
from quex_backend.models import *


class TestModelsParsing(unittest.TestCase):

    # check that we can parse test vectors without errors
    def test_test_vectors_parsing(self):
        f = open(Path(__file__).parent.resolve() / 'test_vectors.json')
        vectors = json.load(f)
        for v in vectors:
            obj = QuexRequest.parse(v["quex_request"])
            self.assertEqual(obj.filter, v["quex_request"]["filter"])

    # Test RequestMethod Parsing
    def test_request_method_parsing(self):
        self.assertEqual(RequestMethod["GET"], 0)
        self.assertEqual(RequestMethod["POST"], 1)
        self.assertEqual(RequestMethod["PUT"], 2)

    def test_request_method_invalid_parsing(self):
        with self.assertRaises(Exception):
            RequestMethod.parse("InvalidMethod")

    # Test RequestHeader Parsing
    def test_request_header_parsing(self):
        data = {"key": "Content-Type", "value": "application/json"}
        header = RequestHeader.parse(data)
        self.assertEqual(header.key, "Content-Type")
        self.assertEqual(header.value, "application/json")

    def test_request_header_missing_field(self):
        data = {"key": "Content-Type"}  # missing 'value'
        with self.assertRaises(TypeError):
            RequestHeader.parse(data)

    # Test QueryParameter Parsing
    def test_query_parameter_parsing(self):
        data = {"key": "id", "value": "1"}
        param = QueryParameter.parse(data)
        self.assertEqual(param.key, "id")
        self.assertEqual(param.value, "1")

    def test_query_parameter_missing_field(self):
        data = {"key": "id"}  # missing 'value'
        with self.assertRaises(TypeError):
            QueryParameter.parse(data)

    # Test QueryParameterPatch Parsing
    def test_query_parameter_patch_parsing(self):
        encrypted_value = base64.b64encode(b"encrypted_value").decode('utf-8')
        data = {"key": "id", "ciphertext": encrypted_value}
        param_patch = QueryParameterPatch.parse(data)
        self.assertEqual(param_patch.key, "id")
        self.assertEqual(param_patch.ciphertext, b"encrypted_value")

    def test_query_parameter_patch_invalid_base64(self):
        data = {"key": "id", "ciphertext": "invalid_base64"}
        with self.assertRaises(base64.binascii.Error):
            QueryParameterPatch.parse(data)

    def test_query_parameter_patch_missing_field(self):
        data = {"key": "id"}  # missing 'ciphertext'
        with self.assertRaises(KeyError):
            QueryParameterPatch.parse(data)

    # Test RequestHeaderPatch Parsing
    def test_request_header_patch_parsing(self):
        encrypted_value = base64.b64encode(b"encrypted_api_key").decode('utf-8')
        data = {"key": "Authorization", "ciphertext": encrypted_value}
        header_patch = RequestHeaderPatch.parse(data)
        self.assertEqual(header_patch.key, "Authorization")
        self.assertEqual(header_patch.ciphertext, b"encrypted_api_key")

    def test_request_header_patch_invalid_base64(self):
        data = {"key": "Authorization", "ciphertext": "invalid_base64"}
        with self.assertRaises(base64.binascii.Error):
            RequestHeaderPatch.parse(data)

    def test_request_header_patch_missing_field(self):
        data = {"key": "Authorization"}  # missing 'ciphertext'
        with self.assertRaises(KeyError):
            RequestHeaderPatch.parse(data)

    # Test HTTPPrivatePatch Parsing
    def test_http_private_patch_parsing(self):
        encrypted_value = base64.b64encode(b"encrypted_value").decode('utf-8')
        patch_body = base64.b64encode(b"patch_body_content").decode('utf-8')
        data = {
            "path_suffix": encrypted_value,
            "headers": [{"key": "Authorization", "ciphertext": encrypted_value}],
            "parameters": [{"key": "id", "ciphertext": encrypted_value}],
            "body": patch_body,
            "td_id": 12345
        }
        private_patch = HTTPPrivatePatch.parse(data)
        self.assertEqual(private_patch.path_suffix, b"encrypted_value")
        self.assertEqual(private_patch.headers[0].key, "Authorization")
        self.assertEqual(private_patch.parameters[0].key, "id")
        self.assertEqual(private_patch.body, b"patch_body_content")
        self.assertEqual(private_patch.td_id, 12345)

    def test_http_private_patch_invalid_base64(self):
        data = {
            "path_suffix": "invalid_base64",
            "headers": [],
            "parameters": [],
            "body": "invalid_base64",
            "td_id": 12345
        }
        with self.assertRaises(base64.binascii.Error):
            HTTPPrivatePatch.parse(data)

    def test_http_private_patch_missing_field(self):
        data = {
            "headers": [],
            "parameters": [],
            "body": base64.b64encode(b"body").decode('utf-8'),
            # missing 'path_suffix' and 'td_id'
        }
        with self.assertRaises(KeyError):
            HTTPPrivatePatch.parse(data)

    # Test HTTPRequest Parsing with JSON
    def test_http_request_parsing(self):
        body_content = {
            "param1": "value1",
            "param2": 42,
            "param3": {"nested_key": "nested_value"}
        }
        body_bytes = json.dumps(body_content).encode()

        base64_encoded_body = base64.b64encode(body_bytes)

        data = {
            "method": "Get",
            "host": "api.example.com",
            "path": "/v1/resource",
            "headers": [{"key": "Content-Type", "value": "application/json"}],
            "parameters": [{"key": "id", "value": "1"}],
            "body": base64_encoded_body
        }

        http_request = HTTPRequest.parse(data)
        self.assertEqual(http_request.body, body_bytes)

    def test_http_request_invalid_body(self):
        data = {
            "method": "Get",
            "host": "api.example.com",
            "path": "/v1/resource",
            "headers": [{"key": "Content-Type", "value": "application/json"}],
            "parameters": [{"key": "id", "value": "1"}],
            "body": b"invalid_json"
        }

        with self.assertRaises(binascii.Error):
            HTTPRequest.parse(data)

    def test_http_request_missing_field(self):
        data = {
            "host": "api.example.com",
            "path": "/v1/resource",
            "headers": [],
            "parameters": [],
            "body": base64.b64encode(b"body").decode('utf-8'),
            # missing 'method'
        }
        with self.assertRaises(KeyError):
            HTTPRequest.parse(data)

    # Test QuexRequest Parsing
    def test_quex_request_parsing(self):
        body_content = {
            "param1": "value1",
            "param2": 42,
            "param3": {"nested_key": "nested_value"}
        }
        body_bytes = json.dumps(body_content).encode()

        body_bytes_encoded = base64.b64encode(body_bytes)

        encrypted_value = base64.b64encode(b"encrypted_value")

        data = {
            "request": {
                "method": "Get",
                "host": "api.example.com",
                "path": "/v1/resource",
                "headers": [{"key": "Content-Type", "value": "application/json"}],
                "parameters": [{"key": "id", "value": "1"}],
                "body": body_bytes_encoded
            },
            "patch": {
                "path_suffix": encrypted_value,
                "headers": [{"key": "Authorization", "ciphertext": encrypted_value}],
                "parameters": [{"key": "id", "ciphertext": encrypted_value}],
                "body": base64.b64encode(b"patch_body_content").decode('utf-8'),
                "td_id": 12345
            },
            "schema": "int256",
            "filter": "(.data[\"1\"].quote.USD.price * 1000000) | round"
        }

        quex_request = QuexRequest.parse(data)
        self.assertEqual(quex_request.request.body, body_bytes)
        self.assertEqual(quex_request.patch.path_suffix, b"encrypted_value")
        self.assertEqual(quex_request.schema, "int256")
        self.assertEqual(quex_request.filter, "(.data[\"1\"].quote.USD.price * 1000000) | round")

    def test_quex_request_missing_field(self):
        body_content = {
            "param1": "value1",
            "param2": 42,
            "param3": {"nested_key": "nested_value"}
        }

        json_encoded_body = base64.b64encode(json.dumps(body_content).encode('utf-8')).decode('utf-8')

        data = {
            "request": {
                "method": "Get",
                "host": "api.example.com",
                "path": "/v1/resource",
                "headers": [{"key": "Content-Type", "value": "application/json"}],
                "parameters": [{"key": "id", "value": "1"}],
                "body": json_encoded_body
            },
            # Missing 'patch', 'schema', and 'filter'
        }

        with self.assertRaises(KeyError):
            QuexRequest.parse(data)


if __name__ == "__main__":
    unittest.main()
