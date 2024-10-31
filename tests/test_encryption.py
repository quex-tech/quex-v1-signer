import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from quex_backend.encryption import EncryptedPatchProcessor, Client
from quex_backend.models import *
from cryptography.hazmat.backends import default_backend

test_vectors = [
    {
        "message": b"Hello, secure world!",
        "ciphertext_hex": "b17bc6d3a83209e8668523ff0bdb944927b848ebf691056ca3684944243693e525654dc66a1074d857b7041751c1773badf9b3c4419ba81c7a586ab844e0060646644f9d8d37f9c7ad914d929610ce916e01459ab51ed1102b983ca0182749cffcfd33cff04914d07326bfee5b974efc45b17afc"
    },
    {
        "message": b"Some encrypted message, to be applied as a patch",
        "ciphertext_hex": "499009dbfebed0abeeaf6b89ab1f168a04bcbed173fc4f1abdbdb4475674a971a4b4977bf89d558f3e4cb243d619455f0a5776d0bdbd0a191cb9b823f8d80a32a647f3538132d2e528d63e87935fd21a5a8d57efc0def657c80fc6ebf357d5389d3c9ef22b17b65738d3fc4f4671c5dc1b20cff737ee8bf1db5f153f144be31dd0b8b82f2e0f72ecfd3c1d5ffeb3a273"
    },
]
PRIVATE_KEY_HEX = "0x73e44e67ae68ffade8b2d555c92599e7cc310ec152202fb6c20abfd12ec2529"

def test_encryption_decryption():
    for v in test_vectors:
        server = EncryptedPatchProcessor.from_hex(PRIVATE_KEY_HEX)
        public_key = server.get_public_key()

        # Client encrypts the message with the server's public key
        client = Client(public_key)
        message = v["message"]
        encrypted_message = client.encrypt_message(message)
        print(f"msg: {message}, encrypted_message:{encrypted_message.hex()}")

        # Server decrypts the message
        decrypted_message = server.decrypt_message(encrypted_message)

        assert decrypted_message == message


def test_decryption():
    for v in test_vectors:
        server = EncryptedPatchProcessor.from_hex(PRIVATE_KEY_HEX)
        message = v["message"]
        encrypted_message = bytes.fromhex(v["ciphertext_hex"])
        decrypted_message = server.decrypt_message(encrypted_message)

        assert decrypted_message == message

def test_apply_patch():
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
    assert decrypted_api_key == api_key.decode()

    # Verify other request properties remain unchanged
    assert patched_request.method == http_request.method
    assert patched_request.host == http_request.host
    assert patched_request.path == http_request.path
    assert patched_request.parameters == http_request.parameters