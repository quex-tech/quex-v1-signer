from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import os


class EncryptedPatchProcessor:
    def __init__(self, private_key: ec.EllipticCurvePrivateKey):
        self.__private_key = private_key
        self.public_key = self.__private_key.public_key()

    @staticmethod
    def from_hex(private_key_hex):
        private_key = ec.derive_private_key(int(private_key_hex, 16), ec.SECP256K1(), default_backend())
        return EncryptedPatchProcessor(private_key)

    def get_public_key(self) -> bytes:
        return self.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)

    def decrypt_message(self, encrypted_data: bytes) -> bytes:
        ephemeral_x = encrypted_data[:32]
        ephemeral_y = encrypted_data[32:64]
        nonce = encrypted_data[64:80]
        tag = encrypted_data[80:96]
        ciphertext = encrypted_data[96:]

        # Reconstruct ephemeral public key
        ephemeral_public_numbers = ec.EllipticCurvePublicNumbers(
            int.from_bytes(ephemeral_x, "big"),
            int.from_bytes(ephemeral_y, "big"),
            ec.SECP256K1()
        )
        ephemeral_public_key = ephemeral_public_numbers.public_key(default_backend())

        # Derive the shared secret
        shared_key = self.__private_key.exchange(ec.ECDH(), ephemeral_public_key)
        shared_public_numbers = ephemeral_public_key.public_numbers()
        server_public_numbers = self.__private_key.public_key().public_numbers()

        # HKDF input with 0x04 prefixes
        hkdf_input = (
                b'\x04' + ephemeral_x + ephemeral_y +
                b'\x04' + server_public_numbers.x.to_bytes(32, "big") + server_public_numbers.y.to_bytes(32, "big")
        )

        symm_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"",
            backend=default_backend()
        ).derive(hkdf_input)

        # Decrypt the message using AES-GCM
        decryptor = Cipher(
            algorithms.AES(symm_key),
            modes.GCM(nonce, tag),
            backend=default_backend()
        ).decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()


class Client:
    def __init__(self, server_public_key_bytes: bytes):
        x = int.from_bytes(server_public_key_bytes[1:33], "big")
        y = int.from_bytes(server_public_key_bytes[33:], "big")
        public_numbers = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256K1())
        self.server_public_key = public_numbers.public_key(default_backend())

    def encrypt_message(self, message: bytes) -> bytes:
        ephemeral_private_key = ec.generate_private_key(ec.SECP256K1(), default_backend())
        ephemeral_public_key = ephemeral_private_key.public_key()

        # Get the x and y coordinates of the ephemeral public key
        ephemeral_x = ephemeral_public_key.public_numbers().x.to_bytes(32, "big")
        ephemeral_y = ephemeral_public_key.public_numbers().y.to_bytes(32, "big")

        # Derive the shared secret using the server's public key
        shared_key = ephemeral_private_key.exchange(ec.ECDH(), self.server_public_key)
        server_public_numbers = self.server_public_key.public_numbers()

        # HKDF input with 0x04 prefixes
        hkdf_input = (
                b'\x04' +
                ephemeral_x +
                ephemeral_y +
                b'\x04' +
                server_public_numbers.x.to_bytes(32, "big") +
                server_public_numbers.y.to_bytes(32, "big")
        )

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
        return ephemeral_x + ephemeral_y + nonce + encryptor.tag + ciphertext
