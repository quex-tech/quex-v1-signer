from copy import deepcopy

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF
from ecdsa import SECP256k1, SigningKey, VerifyingKey

from quex_backend.models import HTTPRequest, RequestHeader, QueryParameter, HTTPAction

class EncryptedPatchProcessingError(Exception):
    pass

class EncryptedPatchProcessor:
    def __init__(self, private_key: SigningKey):
        self.__private_key = private_key
        self.public_key = private_key.get_verifying_key()

    @staticmethod
    def from_hex(private_key_hex: str) -> "EncryptedPatchProcessor":
        private_key = SigningKey.from_secret_exponent(int(private_key_hex, 16), curve=SECP256k1)
        return EncryptedPatchProcessor(private_key)

    def get_public_key(self) -> VerifyingKey:
        return self.public_key

    def decrypt_message(self, encrypted_data: bytes, ephemeral_public_key: VerifyingKey) -> bytes:
        nonce = encrypted_data[:16]
        tag = encrypted_data[16:32]
        ciphertext = encrypted_data[32:]

        # Perform ECDH to obtain the shared secret point
        shared_point = ephemeral_public_key.pubkey.point * self.__private_key.privkey.secret_multiplier
        shared_key = b'\x04' + shared_point.to_bytes()
        symm_key = HKDF(b'\x04' + ephemeral_public_key.to_string() + shared_key, 32, salt=None, hashmod=SHA256)  # type: ignore[arg-type]  # pycryptodome HKDF accepts None

        # Decrypt the message using AES-GCM
        if not isinstance(symm_key, bytes):
            raise TypeError(f"HKDF returned {type(symm_key)}, expected bytes")
        cipher = AES.new(symm_key, AES.MODE_GCM, nonce=nonce)
        decrypted_message = cipher.decrypt_and_verify(ciphertext, tag)

        return decrypted_message

    def apply_patch(self, quex_request: HTTPAction, proof: bytes) -> 'HTTPRequest':
        """
        Apply the HTTPPrivatePatch to the HTTPRequest within the QuexRequest,
        decrypting any encrypted fields and updating the HTTPRequest.
        
        Returns:
            HTTPRequest: The patched HTTPRequest
        """
        try:
            http_request = deepcopy(quex_request.request)
            http_patch = quex_request.patch
            ephemeral_public_key = None

            for header_patch in http_patch.headers:
                if ephemeral_public_key is None:
                    ephemeral_public_key = self.recover_ephemeral_public_key(quex_request.action_id(), proof)
                decrypted_value = self.decrypt_message(header_patch.ciphertext, ephemeral_public_key)
                http_request.headers.append(RequestHeader(header_patch.key, decrypted_value.decode('utf-8')))

            for param_patch in http_patch.parameters:
                if ephemeral_public_key is None:
                    ephemeral_public_key = self.recover_ephemeral_public_key(quex_request.action_id(), proof)
                decrypted_value = self.decrypt_message(param_patch.ciphertext, ephemeral_public_key)
                http_request.parameters.append(QueryParameter(param_patch.key, decrypted_value.decode('utf-8')))

            if http_patch.body:
                if ephemeral_public_key is None:
                    ephemeral_public_key = self.recover_ephemeral_public_key(quex_request.action_id(), proof)
                decrypted_body = self.decrypt_message(http_patch.body, ephemeral_public_key)
                http_request.body = decrypted_body

            if http_patch.path_suffix:
                if ephemeral_public_key is None:
                    ephemeral_public_key = self.recover_ephemeral_public_key(quex_request.action_id(), proof)
                decrypted_path_suffix = self.decrypt_message(http_patch.path_suffix, ephemeral_public_key)
                http_request.path += decrypted_path_suffix.decode('utf-8')

            return http_request
        except Exception as exc:
            raise EncryptedPatchProcessingError from exc
    
    def recover_ephemeral_public_key(self, action_id: bytes, proof: bytes) -> VerifyingKey:
        """
        Recover 64-byte (x||y) public key from a signature produced by the
        ephemeral private key that also encrypted the message.
        """
        ephemeral_public_key = VerifyingKey.from_string(proof[:64], curve=SECP256k1)
        encrypted_data = proof[64:]
        decrypted_data = self.decrypt_message(encrypted_data, ephemeral_public_key)
        if decrypted_data != action_id:
            raise ValueError("Action ID does not match the decrypted data.")
        return ephemeral_public_key
