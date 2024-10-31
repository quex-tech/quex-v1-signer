from copy import deepcopy
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from quex_backend.models import *


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

    def apply_patch(self, quex_request) -> 'HTTPRequest':
        """
        Apply the HTTPPrivatePatch to the HTTPRequest within the QuexRequest,
        decrypting any encrypted fields and updating the HTTPRequest.
        """
        # Get the HTTPRequest and HTTPPrivatePatch from the QuexRequest
        http_request = deepcopy(quex_request.request)
        http_patch = quex_request.patch

        # Decrypt any encrypted headers and apply
        for header_patch in http_patch.headers:
            decrypted_value = self.decrypt_message(header_patch.ciphertext)
            http_request.headers.append(RequestHeader(header_patch.key, decrypted_value.decode('utf-8')))

        # Decrypt any encrypted parameters
        for param_patch in http_patch.parameters:
            decrypted_value = self.decrypt_message(param_patch.ciphertext)
            http_request.parameters.append(QueryParameter(param_patch.key, decrypted_value.decode('utf-8')))

        # Decrypt the body if it is encrypted
        if http_patch.body:
            decrypted_body = self.decrypt_message(http_patch.body)
            http_request.body = decrypted_body

        # Update the path with path_suffix if provided
        if http_patch.path_suffix:
            decrypted_path_suffix = self.decrypt_message(http_patch.path_suffix)
            http_request.path += decrypted_path_suffix.decode('utf-8')

        return http_request


