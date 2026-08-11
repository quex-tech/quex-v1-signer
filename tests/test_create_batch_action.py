import io
import json
import random
import tempfile
import unittest
from base64 import b64encode
from contextlib import redirect_stdout
from pathlib import Path

from ecdsa import SECP256k1, SigningKey
from eth_utils import keccak

from quex_backend.batch import EthereumBatchHTTPActionWithProof, apply_batch_patches
from quex_backend.encryption import EncryptedPatchProcessor
from tools.create_batch_action import ZERO_ADDRESS, build_action_with_proof, main

FUZZ_ROUNDS = 20

CONFIG = {
    "requests": [
        {
            "method": "GET",
            "host": "api.example.com",
            "path": "/v1/balance",
            "headers": [{"key": "Accept", "value": "application/json"}],
            "parameters": [{"key": "chain", "value": "eth"}],
            "body": "",
        },
        {
            "method": "POST",
            "host": "api.other.com",
            "path": "/v2/portfolio",
            "headers": [],
            "parameters": [],
            "body": b64encode(b'{"scope":"all"}').decode(),
        },
    ],
    "patches": [
        {
            "headers": [{"key": "X-API-Key", "value": "sk_live_1"}],
            "parameters": [{"key": "key", "value": "qk_2"}],
        },
        {
            "body": b64encode(b'{"token":"tk_3"}').decode(),
            "path_suffix": "/hidden",
        },
    ],
    "schema": "uint256",
    "filter": "map(.total) | add",
}


def make_td_key() -> tuple[EncryptedPatchProcessor, str]:
    sk = SigningKey.generate(curve=SECP256k1)
    processor = EncryptedPatchProcessor.from_hex(sk.to_string().hex())
    pubkey_hex = "0x" + sk.get_verifying_key().to_string().hex()
    return processor, pubkey_hex


def address_of(pubkey_hex: str) -> str:
    return "0x" + keccak(bytes.fromhex(pubkey_hex.removeprefix("0x")))[-20:].hex()


class TestBuildActionWithProof(unittest.TestCase):
    def test_round_trip_decrypts_to_config_secrets(self):
        processor, pubkey_hex = make_td_key()
        wrapped = build_action_with_proof(CONFIG, pubkey_hex).bytes()

        for secret in (b"sk_live_1", b"qk_2", b"tk_3", b"/hidden"):
            self.assertNotIn(secret, wrapped)

        parsed = EthereumBatchHTTPActionWithProof.parse(wrapped)
        patched = apply_batch_patches(processor, parsed.action, parsed.proof)

        headers = [(h.key, h.value) for h in patched[0].headers]
        self.assertIn(("X-API-Key", "sk_live_1"), headers)
        parameters = [(p.key, p.value) for p in patched[0].parameters]
        self.assertIn(("key", "qk_2"), parameters)
        self.assertEqual(patched[1].body, b'{"token":"tk_3"}')
        self.assertEqual(patched[1].path, "/v2/portfolio/hidden")

    def test_patches_bound_to_td_address(self):
        _, pubkey_hex = make_td_key()
        action = build_action_with_proof(CONFIG, pubkey_hex).action
        td_addresses = {p.td_address for p in action.patches}
        self.assertEqual(td_addresses, {address_of(pubkey_hex)})

    def test_empty_patches_need_no_key_and_empty_proof(self):
        config = {**CONFIG, "patches": [{}, {}]}
        wrapped_obj = build_action_with_proof(config, td_pubkey_hex=None)
        self.assertEqual(wrapped_obj.proof, b"")

        processor, _ = make_td_key()
        parsed = EthereumBatchHTTPActionWithProof.parse(wrapped_obj.bytes())
        patched = apply_batch_patches(processor, parsed.action, parsed.proof)
        self.assertEqual(patched[0].path, "/v1/balance")

    def test_patches_key_may_be_omitted_entirely(self):
        config = {k: v for k, v in CONFIG.items() if k != "patches"}
        wrapped_obj = build_action_with_proof(config, td_pubkey_hex=None)
        self.assertEqual(len(wrapped_obj.action.patches), 2)
        self.assertEqual(wrapped_obj.proof, b"")
        td_addresses = {p.td_address for p in wrapped_obj.action.patches}
        self.assertEqual(td_addresses, {ZERO_ADDRESS})

    def test_secret_patches_without_pubkey_raise(self):
        with self.assertRaises(ValueError):
            build_action_with_proof(CONFIG, td_pubkey_hex=None)

    def test_bad_length_pubkey_raises(self):
        with self.assertRaises(ValueError):
            build_action_with_proof(CONFIG, td_pubkey_hex="0x" + "ab" * 63)

    def test_pubkey_accepts_uncompressed_prefix(self):
        processor, pubkey_hex = make_td_key()
        prefixed = "0x04" + pubkey_hex.removeprefix("0x")
        wrapped = build_action_with_proof(CONFIG, prefixed).bytes()
        parsed = EthereumBatchHTTPActionWithProof.parse(wrapped)
        patched = apply_batch_patches(processor, parsed.action, parsed.proof)
        headers = [(h.key, h.value) for h in patched[0].headers]
        self.assertIn(("X-API-Key", "sk_live_1"), headers)

    def test_fuzz_round_trip(self):
        rng = random.Random(1337)
        for _ in range(FUZZ_ROUNDS):
            processor, pubkey_hex = make_td_key()
            n = rng.randint(1, 4)
            secrets = [f"secret-{rng.randrange(10**9)}" for _ in range(n)]
            config = {
                "requests": [
                    {
                        "method": rng.choice(["GET", "POST"]),
                        "host": f"host{i}.example.com",
                        "path": f"/v{i}/data",
                        "headers": [],
                        "parameters": [],
                        "body": "",
                    }
                    for i in range(n)
                ],
                "patches": [
                    rng.choice(
                        [
                            {"headers": [{"key": "X-Key", "value": secrets[i]}]},
                            {"parameters": [{"key": "k", "value": secrets[i]}]},
                            {"body": b64encode(secrets[i].encode()).decode()},
                        ]
                    )
                    for i in range(n)
                ],
                "schema": "uint256",
                "filter": ".",
            }
            wrapped = build_action_with_proof(config, pubkey_hex).bytes()
            for secret in secrets:
                self.assertNotIn(secret.encode(), wrapped)
            parsed = EthereumBatchHTTPActionWithProof.parse(wrapped)
            patched = apply_batch_patches(processor, parsed.action, parsed.proof)
            for i, request in enumerate(patched):
                values = (
                    [h.value for h in request.headers]
                    + [p.value for p in request.parameters]
                    + [request.body.decode()]
                )
                self.assertIn(secrets[i], values)


class TestMain(unittest.TestCase):
    def run_main(self, config: dict, *extra_args: str) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(json.dumps(config))
            out = io.StringIO()
            with redirect_stdout(out):
                main([str(config_path), "--out-dir", tmp, *extra_args])
            return out.getvalue(), tmp

    def test_writes_bin_named_by_action_id(self):
        _, pubkey_hex = make_td_key()
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(json.dumps(CONFIG))

            out = io.StringIO()
            with redirect_stdout(out):
                main([str(config_path), "--td-pubkey", pubkey_hex, "--out-dir", tmp])

            bins = list(Path(tmp).glob("*.bin"))
            self.assertEqual(len(bins), 1)
            parsed = EthereumBatchHTTPActionWithProof.parse(bins[0].read_bytes())
            action_id_hex = parsed.action.action_id().hex()
            self.assertEqual(bins[0].name, f"{action_id_hex}.bin")
            self.assertIn(action_id_hex, out.getvalue())
            self.assertIn("createFlow", out.getvalue())

    def test_td_address_mismatch_aborts(self):
        _, pubkey_hex = make_td_key()
        with self.assertRaises(SystemExit):
            self.run_main(
                CONFIG,
                "--td-pubkey",
                pubkey_hex,
                "--td-address",
                "0x" + "11" * 20,
            )

    def test_td_address_match_passes(self):
        _, pubkey_hex = make_td_key()
        out, _ = self.run_main(
            CONFIG, "--td-pubkey", pubkey_hex, "--td-address", address_of(pubkey_hex)
        )
        self.assertIn("action_id", out)

    def test_suspect_plaintext_header_aborts_without_override(self):
        config = json.loads(json.dumps(CONFIG))
        config["requests"][0]["headers"].append(
            {"key": "X-API-Key", "value": "oops_plaintext"}
        )
        _, pubkey_hex = make_td_key()
        with self.assertRaises(SystemExit):
            self.run_main(config, "--td-pubkey", pubkey_hex)
        out, _ = self.run_main(
            config, "--td-pubkey", pubkey_hex, "--allow-plaintext-secrets"
        )
        self.assertIn("action_id", out)


if __name__ == "__main__":
    unittest.main()
