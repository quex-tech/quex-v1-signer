import unittest
import json
from pathlib import Path

from ecdsa import SECP256k1, SigningKey

from quex_backend.encryption import EncryptedPatchProcessor
from quex_backend.models import *
from tests.client import Client


class TestModelsEncoding(unittest.TestCase):
    f = open(Path(__file__).parent.resolve() / 'test_vectors.json')
    vectors = json.load(f)

    test_vectors = [
        {
            "message": b"Hello, secure world!",
            "ciphertext_hex": "3972834c54f0a7abbd71251edbe00cfd0117b5f8ae071fb266517aaae1cf35ea658dd0b7b041cedc3ef440b1a47b09a6c1de96c56f29d18e6d1de4fc04c2014faaa76dda14365aa5c819c3faf6800f6af6bd02c0103489fdc31ed7f7c66c6b711cb35a18baf311987cf1c8ebfde4572e2c748c42"
        },
        {
            "message": b"Some encrypted message, to be applied as a patch",
            "ciphertext_hex": "c122d23f45ffc06e5543ced11e36829117286c1be8b2351dc90824fae5981b573d7083addb19d873f2f262ea6b2980ac437aec89c4c78248b324486c19b977bf275bbd99066bfc658b472b1822f75bf9311013df52922b43bb0017fec5519fc0541e0665258743cbdab9239a14fc1df675a5089228309ce4e044c12740f6c499151121c6f2db581b8bdffeddeed1adf5"
        },
    ]
    PRIVATE_KEY_HEX = "0x123456789abcdef"
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
        server = EncryptedPatchProcessor(SigningKey.generate(curve=SECP256k1))
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
             v["keccak256_hex"] == "0xa866ffb38f4eadbe3ea0bf38d783c1bcd6277bf32e060f0bd6bf6b6bc009f649"),
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


