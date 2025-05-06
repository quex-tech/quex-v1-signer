import os

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from eth_utils import keccak


class Client:
    def __init__(self, spk: VerifyingKey):
        self.server_public_key = spk

    def encrypt_message(self, message: bytes) -> bytes:
        ephemeral_private_key = SigningKey.generate(curve=SECP256k1)
        ephemeral_public_key = ephemeral_private_key.get_verifying_key().to_string()

        # Calculate the shared secret point using ECDH
        shared_point = self.server_public_key.pubkey.point * ephemeral_private_key.privkey.secret_multiplier
        shared_key = shared_point.to_bytes()

        # Derive the symmetric key using HKDF with SHA-256
        hkdf_input = b'\x04' + ephemeral_public_key + b'\x04' + shared_key
        symm_key = HKDF(hkdf_input, 32, salt=None, hashmod=SHA256)

        # Encrypt the message using AES-GCM
        nonce = os.urandom(16)
        cipher = AES.new(symm_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(message)

        return ephemeral_public_key + nonce + tag + ciphertext

    def get_address(self) -> str:
        # Get the public key as bytes and strip the '04' (uncompress format ID) prefix
        public_key_bytes = self.server_public_key.to_string('uncompressed')[1:]

        # Apply Keccak-256 hash to the public key and take the last 20 bytes of the result to get the Ethereum address
        eth_address_bytes = keccak(public_key_bytes)[-20:]

        # Convert to hex and add 0x prefix
        eth_address = '0x' + eth_address_bytes.hex()

        return eth_address
