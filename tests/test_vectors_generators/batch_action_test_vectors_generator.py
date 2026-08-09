"""Regenerates tests/test_vectors/batch_action_test_vectors.json.

Run: python tests/test_vectors_generators/batch_action_test_vectors_generator.py
"""

import json
from base64 import b64encode
from pathlib import Path
from typing import Any

from quex_backend.batch import EthereumBatchHTTPAction
from quex_backend.models import (
    HTTPPrivatePatch,
    HTTPRequest,
    QueryParameter,
    RequestHeader,
    RequestMethod,
)

# Pinned cross-language: the same 2-source action and id are fixed by the Quex contracts
# tooling (originally quex-v1-contracts PR #42). Regeneration must reproduce it exactly.
CANONICAL_ACTION_ID = "e035590569c0d56ce4677afe72743a9009a2aa02f2e2814a44c25e3b5082edf4"

EMPTY_PATCH = HTTPPrivatePatch(
    path_suffix=b"",
    headers=[],
    parameters=[],
    body=b"",
    td_address="0x0000000000000000000000000000000000000000",
)


def canonical_action() -> EthereumBatchHTTPAction:
    return EthereumBatchHTTPAction(
        requests=[
            HTTPRequest(
                method=RequestMethod.GET,
                host="api.binance.com",
                path="/api/v3/ticker/price",
                headers=[],
                parameters=[QueryParameter("symbol", "BTCUSDT")],
                body=b"",
            ),
            HTTPRequest(
                method=RequestMethod.GET,
                host="api.coinbase.com",
                path="/v2/prices/BTC-USD/spot",
                headers=[RequestHeader("Accept", "application/json")],
                parameters=[],
                body=b"",
            ),
        ],
        patches=[EMPTY_PATCH, EMPTY_PATCH],
        schema="uint256",
        filter="map(.price | tonumber) | add",
    )


def request_to_dict(request: HTTPRequest) -> dict[str, Any]:
    return {
        "method": request.method.value,
        "host": request.host,
        "path": request.path,
        "headers": [{"key": h.key, "value": h.value} for h in request.headers],
        "parameters": [{"key": p.key, "value": p.value} for p in request.parameters],
        "body": request.body.decode(),
    }


def patch_to_dict(patch: HTTPPrivatePatch) -> dict[str, Any]:
    return {
        "path_suffix": patch.path_suffix.decode(),
        "headers": [{"key": h.key, "ciphertext": h.ciphertext.decode()} for h in patch.headers],
        "parameters": [{"key": p.key, "ciphertext": p.ciphertext.decode()} for p in patch.parameters],
        "body": patch.body.decode(),
        "td_address": patch.td_address,
    }


def vector(description: str, action: EthereumBatchHTTPAction) -> dict[str, Any]:
    return {
        "description": description,
        "action": {
            "requests": [request_to_dict(r) for r in action.requests],
            "patches": [patch_to_dict(p) for p in action.patches],
            "response_schema": action.schema,
            "jq_filter": action.filter,
        },
        "action_id": action.action_id().hex(),
        "bytes": b64encode(action.bytes()).decode("ascii"),
    }


def main() -> None:
    assert canonical_action().action_id().hex() == CANONICAL_ACTION_ID

    vectors = {
        "_comment": "bytes = abi.encode(batch action tuple); action_id = keccak256(abi.encode(BATCH_ACTION_DOMAIN, action)) where BATCH_ACTION_DOMAIN = keccak256('quex.action.batchRequest.v1')",
        "vectors": [
            vector("canonical 2-source sum, cross-language pinned", canonical_action()),
        ],
    }

    out = Path(__file__).parent.parent / "test_vectors" / "batch_action_test_vectors.json"
    out.write_text(json.dumps(vectors, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
