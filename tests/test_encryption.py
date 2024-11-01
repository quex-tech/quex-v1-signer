import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from quex_backend.encryption import EncryptedPatchProcessor
from quex_backend.models import *
from cryptography.hazmat.backends import default_backend
import unittest
from pathlib import Path

from tests.client import Client


class TestModelsEncoding(unittest.TestCase):
    f = open(Path(__file__).parent.resolve() / 'test_vectors.json')
    vectors = json.load(f)

    test_vectors = [
        {
            "message": b"Hello, secure world!",
            "ciphertext_hex": "8fae6e336ec560f6035d7fd7a827bf26c8a2978d897cf73faea4a84ee838eb30be0d2a863c4562b75964a4ee7dc247f59e4711bae733d77718ea1c810dce94511717962a5bb5ef98744dfe41791ea8af50e827eae89a20abf8221434f05fb3f74c4664fe530856e769e6c0b8dbf78804bb899f1d"
        },
        {
            "message": b"Some encrypted message, to be applied as a patch",
            "ciphertext_hex": "7c60e54d0ca1fed95a49e718bf75900cfbf2f482596b5cc0325a8c8b309c244156db3a18aaa7bc23ccd436a1555b307cc29b1d89c6105951e13d745b108d809cf33f032b187720a0c2ac37f956b127b397486ec614a3ae615fb9e787bd1d9ed0f52eb541b9cefdd2167325eaf7251278ae2b3a46a275088bbdf266b6a43cd7c6ec54a9c76d0c0e4b541a1c4e4c91dd67"
        },
    ]
    PRIVATE_KEY_HEX = "0x73e44e67ae68ffade8b2d555c92599e7cc310ec152202fb6c20abfd12ec2529"
    patch_processor = EncryptedPatchProcessor.from_hex(PRIVATE_KEY_HEX)

    def test_encryption_decryption(self):
        for v in self.test_vectors:
            public_key = self.patch_processor.get_public_key()

            # Client encrypts the message with the server's public key
            client = Client(public_key)
            message = v["message"]
            encrypted_message = client.encrypt_message(message)
            print(f"msg: {message}, encrypted_message:{encrypted_message.hex()}")

            # Server decrypts the message
            decrypted_message = self.patch_processor.decrypt_message(encrypted_message)

            assert decrypted_message == message

    def test_decryption(self):
        for v in self.test_vectors:
            message = v["message"]
            encrypted_message = bytes.fromhex(v["ciphertext_hex"])
            decrypted_message = self.patch_processor.decrypt_message(encrypted_message)

            assert decrypted_message == message

    def test_apply_patch(self):
        # Generate server key for decryption
        private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
        server = EncryptedPatchProcessor(private_key)
        public_key = server.get_public_key()

        # Set up client with server's public key
        client = Client(public_key)

        # Define the original HTTPRequest
        http_request = HTTPRequest(
            method="GET",
            host="api.example.com",
            path="/v1/resource",
            headers=[RequestHeader("Accept", "application/json")],
            parameters=[{"key": "id", "value": "1"}],
            body=b""
        )

        # Encrypt an API key for testing
        api_key = b"my_secret_api_key"
        encrypted_api_key = client.encrypt_message(api_key)

        # Create HTTPPrivatePatch with encrypted API key
        http_private_patch = HTTPPrivatePatch(
            path_suffix=b"",
            headers=[RequestHeaderPatch("X-API-KEY", encrypted_api_key)],
            parameters=[],
            body=b"",
            td_id=1
        )

        # Create the QuexRequest
        quex_request = QuexRequest(
            request=http_request,
            patch=http_private_patch,
            schema="string",
            filter=""
        )

        # Apply the patch to the request
        patched_request = server.apply_patch(quex_request)

        # Assert that patched request contains the decrypted API key
        patched_headers = patched_request.get_headers()

        decrypted_api_key = patched_headers["X-API-KEY"]
        self.assertEqual(decrypted_api_key, api_key.decode())

        # Verify other request properties remain unchanged
        self.assertEqual(patched_request.method, http_request.method)
        self.assertEqual(patched_request.host, http_request.host)
        self.assertEqual(patched_request.path, http_request.path)
        self.assertEqual(patched_request.parameters, http_request.parameters)

    def test_apply_patch_from_test_vectors(self):
        v = next(
            (v for v in self.vectors if
             v["keccak256_hex"] == "0xf89767b3dbd2346540d343cb3a61daff7998489b566e617979652efe574666a9"),
            None  # Returns None if no matching vector is found
        )

        qr = QuexRequest.parse(v["quex_request"])
        original_request = qr.request
        patched_request = self.patch_processor.apply_patch(qr)
        print(f"\nOriginal request: {original_request}")
        print(f"\nPatched request : {patched_request}")

        self.assertNotEqual(original_request.path, patched_request.path)
        self.assertNotEqual(original_request.headers, patched_request.headers)
        self.assertNotEqual(original_request.parameters, patched_request.parameters)
        self.assertNotEqual(original_request.body, patched_request.body)

        self.assertIn("patch_for_path_suffix", patched_request.path)
        self.assertEqual(patched_request.body, b"patched body")
        self.assertIn("my_secret_api_key", str(patched_request.headers))
        self.assertIn("param_value_1", str(patched_request.parameters))
        self.assertIn("param_value_2", str(patched_request.parameters))


