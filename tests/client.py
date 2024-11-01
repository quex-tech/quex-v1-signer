import os

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from ecdsa.util import number_to_string


class Client:
    def __init__(self, spk: VerifyingKey):
        self.server_public_key = spk

    def encrypt_message(self, message: bytes) -> bytes:
        ephemeral_private_key = SigningKey.generate(curve=SECP256k1)
        ephemeral_public_key = ephemeral_private_key.get_verifying_key().to_string()

        # Calculate the shared secret point using ECDH
        shared_point = self.server_public_key.pubkey.point * ephemeral_private_key.privkey.secret_multiplier
        shared_x = number_to_string(shared_point.x(), SECP256k1.order)
        shared_y = number_to_string(shared_point.y(), SECP256k1.order)
        shared_key = b'\x04' + shared_x + shared_y

        # Derive the symmetric key using HKDF with SHA-256
        hkdf_input = b'\x04' + ephemeral_public_key + shared_key
        symm_key = HKDF(hkdf_input, 32, salt=None, hashmod=SHA256)

        # Encrypt the message using AES-GCM
        nonce = os.urandom(16)
        cipher = AES.new(symm_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(message)

        return ephemeral_public_key + nonce + tag + ciphertext
