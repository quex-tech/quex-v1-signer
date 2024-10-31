import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class Client:
    def __init__(self, server_public_key_bytes: bytes):
        x = int.from_bytes(server_public_key_bytes[1:33], "big")
        y = int.from_bytes(server_public_key_bytes[33:], "big")
        public_numbers = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1())
        self.server_public_key = public_numbers.public_key(default_backend())

    def encrypt_message(self, message: bytes) -> bytes:
        ephemeral_private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
        ephemeral_public_key = ephemeral_private_key.public_key()
        ephemeral_x = ephemeral_public_key.public_numbers().x.to_bytes(32, "big")
        ephemeral_y = ephemeral_public_key.public_numbers().y.to_bytes(32, "big")
        ephemeral = ephemeral_x + ephemeral_y

        shared_key = ephemeral_private_key.exchange(ec.ECDH(), self.server_public_key)

        # HKDF input with 0x04 prefixes, using R_x and R_y
        hkdf_input = (b'\x04' + ephemeral + b'\x04' + shared_key)

        # Derive the symmetric key using HKDF
        symm_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"",
            backend=default_backend()
        ).derive(hkdf_input)

        # Encrypt the message using AES-GCM
        nonce = os.urandom(16)
        encryptor = Cipher(
            algorithms.AES(symm_key),
            modes.GCM(nonce),
            backend=default_backend()
        ).encryptor()
        ciphertext = encryptor.update(message) + encryptor.finalize()

        # Concatenate ephemeral public key, nonce, tag, and ciphertext
        return ephemeral + nonce + encryptor.tag + ciphertext
