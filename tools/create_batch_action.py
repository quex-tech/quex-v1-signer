"""Builds a registration-less batch action .bin for the relayer's batch_actions_dir.

Usage:
  python -m tools.create_batch_action config.json --td-pubkey 0x<64-byte-hex>
      [--td-address 0x<addr>] [--out-dir DIR] [--allow-plaintext-secrets]

Config JSON: {"requests": [...], "patches": [...], "schema": "...", "filter": "..."}.
Requests use the http_action_raw_vectors.json shape (method/host/path/headers/
parameters/body, body base64). Patches carry plaintext secrets (header/parameter
values, body base64, path_suffix); every non-empty patch field is encrypted for
the TD before anything is written, so plaintext never reaches the output.

Trust notes:
- The TD public key comes from the signer's /pubkey; attest it via /quote first
  (DEBUG signers serve canned quotes). Pass --td-address from the on-chain pool
  registry to pin the key: the tool aborts if keccak(pubkey)[-20:] differs.
- Each run draws a fresh ephemeral key, so ciphertexts and the action id change
  on every run; re-running means creating a new on-chain flow.
- Anyone who learns the action id can create their own flow over it; use scoped,
  read-only, rate-limited API credentials.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from ecdsa import SECP256k1, VerifyingKey
from eth_utils import keccak

from quex_backend.batch import (
    EthereumBatchHTTPAction,
    EthereumBatchHTTPActionWithProof,
)
from quex_backend.models import HTTPPrivatePatch, HTTPRequest
from tests.client import Client
from tests.test_vectors_generators.http_action_test_vectors_generator import (
    convert_request,
    prepare_patch,
)

ZERO_ADDRESS = "0x" + "00" * 20
EMPTY_PATCH = HTTPPrivatePatch(b"", [], [], b"", ZERO_ADDRESS)
# Plaintext request header/parameter keys that usually mean a misplaced secret.
SUSPECT_KEYS = (
    "authorization", "x-api-key", "api-key", "apikey", "token", "secret", "cookie",
)
CREATE_FLOW_CMD = (
    'cast send <QuexCore> "createFlow((uint256,uint256,address,address,bytes4))" '
    '"(<gasLimit>,{action_id},<pool>,<consumer>,<callback>)"'
)


def parse_td_pubkey(pubkey_hex: str) -> VerifyingKey:
    raw = bytes.fromhex(pubkey_hex.removeprefix("0x"))
    if len(raw) == 65 and raw[0] == 4:
        raw = raw[1:]
    if len(raw) != 64:
        raise ValueError("TD public key must be 64 bytes (x||y)")
    return VerifyingKey.from_string(raw, curve=SECP256k1)


def pubkey_address(pubkey: VerifyingKey) -> str:
    return "0x" + keccak(pubkey.to_string())[-20:].hex()


def has_secrets(raw_patch: dict[str, Any]) -> bool:
    return any(
        raw_patch.get(field)
        for field in ("headers", "parameters", "body", "path_suffix")
    )


def plaintext_suspect_keys(requests: list[HTTPRequest]) -> list[str]:
    keys = [h.key for request in requests for h in request.headers]
    keys += [p.key for request in requests for p in request.parameters]
    return [k for k in keys if k.lower() in SUSPECT_KEYS]


# One Client per batch: the proof and every patch use the same ephemeral key.
def build_action_with_proof(
    config: dict[str, Any], td_pubkey_hex: str | None
) -> EthereumBatchHTTPActionWithProof:
    requests = [convert_request(r) for r in config["requests"]]
    raw_patches = config.get("patches") or [{} for _ in requests]
    secret_flags = [has_secrets(p) for p in raw_patches]

    client: Client | None = None
    if any(secret_flags):
        if td_pubkey_hex is None:
            raise ValueError("patches contain secrets: --td-pubkey is required")
        client = Client(parse_td_pubkey(td_pubkey_hex))

    action = EthereumBatchHTTPAction(
        requests=requests,
        patches=[
            prepare_patch(p, client) if client is not None and flag else EMPTY_PATCH
            for p, flag in zip(raw_patches, secret_flags, strict=True)
        ],
        schema=config["schema"],
        filter=config["filter"],
    )
    action.validate()
    proof = (
        client.encrypt_message(action.action_id(), include_ephemeral_public_key=True)
        if client
        else b""
    )
    return EthereumBatchHTTPActionWithProof(action, proof)


def run(args: argparse.Namespace) -> None:
    config = json.loads(Path(args.config).read_text())

    if args.td_pubkey and args.td_address:
        actual = pubkey_address(parse_td_pubkey(args.td_pubkey))
        if actual.lower() != args.td_address.lower():
            raise ValueError(f"TD pubkey resolves to {actual}, not {args.td_address}")

    wrapped_obj = build_action_with_proof(config, args.td_pubkey)
    suspects = plaintext_suspect_keys(wrapped_obj.action.requests)
    if suspects and not args.allow_plaintext_secrets:
        raise ValueError(
            f"plaintext request fields look secret: {suspects}; move them into "
            "patches or pass --allow-plaintext-secrets"
        )

    # Round-trip through the signer's own parser so invalid actions never hit disk.
    wrapped = wrapped_obj.bytes()
    parsed = EthereumBatchHTTPActionWithProof.parse(wrapped)
    action_id = parsed.action.action_id()
    action_uint = int.from_bytes(action_id, byteorder="big")
    encrypted = sum(1 for p in parsed.action.patches if p.td_address != ZERO_ADDRESS)
    td_addresses = {p.td_address for p in parsed.action.patches} - {ZERO_ADDRESS}

    out = Path(args.out_dir) / f"{action_id.hex()}.bin"
    out.write_bytes(wrapped)

    print(f"action_id: 0x{action_id.hex()}")
    print(f"actionId (uint256): {action_uint}")
    print(f"td_address: {td_addresses.pop() if td_addresses else 'none (no secrets)'}")
    empty = len(parsed.action.patches) - encrypted
    print(f"patches: {encrypted} encrypted, {empty} empty")
    print(f"wrote: {out}")
    print("next: copy the .bin into the relayer batch_actions_dir, restart the worker,")
    print("then create the flow:")
    print("  " + CREATE_FLOW_CMD.format(action_id=action_uint))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build a registration-less batch action .bin.",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("config", help="batch definition JSON (see below)")
    parser.add_argument("--td-pubkey", help="TD public key hex from the signer /pubkey")
    parser.add_argument("--td-address", help="expected TD address; abort on mismatch")
    parser.add_argument("--out-dir", default=".", help="directory for <action_id>.bin")
    parser.add_argument(
        "--allow-plaintext-secrets",
        action="store_true",
        help="skip the secret-looking plaintext header/parameter check",
    )
    args = parser.parse_args(argv)
    try:
        run(args)
    except Exception as exc:
        # No traceback: process memory holds plaintext secrets, keep errors terse.
        raise SystemExit(f"error: {exc}") from exc


if __name__ == "__main__":
    main()
