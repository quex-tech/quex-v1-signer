import base64
import json
import unittest
from pathlib import Path

from ecdsa import SECP256k1, SigningKey
from tests.client import Client

from quex_backend.encryption import EncryptedPatchProcessor
from quex_backend.models import EthereumHTTPActionWithProof, QueryParameter, RequestHeader


class TestModelsEncoding(unittest.TestCase):
    vectors = json.loads((Path(__file__).parent.resolve() / "test_vectors" / "http_action_test_vectors.json").read_text())

    messages = [b"", b"Hello, secure world!", b"Some encrypted message, to be applied as a patch"]

    def test_encryption_decryption(self):
        for message in self.messages:
            private_key = SigningKey.generate(curve=SECP256k1)
            public_key = private_key.get_verifying_key()
            patch_processor = EncryptedPatchProcessor.from_hex(private_key.to_string().hex())

            client = Client(public_key)
            encrypted_message = client.encrypt_message(message)
            print(f"msg: {message}, encrypted_message:{encrypted_message.hex()}, ephemeral_public_key:{client.ephemeral_public_key.to_string().hex()}")

            decrypted_message = patch_processor.decrypt_message(encrypted_message, client.ephemeral_public_key)

            assert decrypted_message == message

    def test_apply_patch(self):
        for v in self.vectors:
            patch_processor = EncryptedPatchProcessor.from_hex(v["private_key"])

            action = EthereumHTTPActionWithProof.parse(base64.b64decode(v["action_bytes"]))
            original_request = action.action.request
            patched_request = patch_processor.apply_patch(action.action, action.proof)
            print(f"\nOriginal request: {original_request}")
            print(f"\nPatched request : {patched_request}")

            expected_request = v["patched_request"]
            expected_headers = [RequestHeader(h["key"], h["value"]) for h in expected_request["headers"]]
            expected_parameters = [QueryParameter(h["key"], h["value"]) for h in expected_request["parameters"]]

            self.assertEqual(patched_request.method, expected_request["method"])
            self.assertEqual(patched_request.host, expected_request["host"])
            self.assertEqual(patched_request.path, expected_request["path"])
            self.assertEqual(patched_request.headers, expected_headers)
            self.assertEqual(patched_request.parameters, expected_parameters)
            self.assertEqual(patched_request.body, base64.b64decode(expected_request["body"]))
