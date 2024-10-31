import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from quex_backend.encryption import EncryptedPatchProcessor, Client
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
