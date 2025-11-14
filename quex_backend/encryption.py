from copy import deepcopy

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF
from ecdsa import SECP256k1, SigningKey, VerifyingKey

from quex_backend.models import HTTPRequest, RequestHeader, QueryParameter

class EncryptedPatchProcessingError(Exception):
    pass

class EncryptedPatchProcessor:
    def __init__(self, private_key: SigningKey):
        self.__private_key = private_key
        self.public_key = private_key.get_verifying_key()

    @staticmethod
    def from_hex(private_key_hex: str):
        private_key = SigningKey.from_secret_exponent(int(private_key_hex, 16), curve=SECP256k1)
        return EncryptedPatchProcessor(private_key)

    def get_public_key(self) -> VerifyingKey:
        return self.public_key

    def decrypt_message(self, encrypted_data: bytes) -> bytes:
        ephemeral = encrypted_data[:64]
        nonce = encrypted_data[64:80]
        tag = encrypted_data[80:96]
        ciphertext = encrypted_data[96:]

        # Perform ECDH to obtain the shared secret point
        ephemeral_public_key = VerifyingKey.from_string(ephemeral, curve=SECP256k1)
        shared_point = ephemeral_public_key.pubkey.point * self.__private_key.privkey.secret_multiplier
        shared_key = b'\x04' + shared_point.to_bytes()
        symm_key = HKDF(b'\x04' + ephemeral + shared_key, 32, salt=None, hashmod=SHA256)

        # Decrypt the message using AES-GCM
        cipher = AES.new(symm_key, AES.MODE_GCM, nonce=nonce)
        decrypted_message = cipher.decrypt_and_verify(ciphertext, tag)

        return decrypted_message

    def apply_patch(self, quex_request) -> 'HTTPRequest':
        """
        Apply the HTTPPrivatePatch to the HTTPRequest within the QuexRequest,
        decrypting any encrypted fields and updating the HTTPRequest.
        """
        try:
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
        except Exception:
            raise EncryptedPatchProcessingError