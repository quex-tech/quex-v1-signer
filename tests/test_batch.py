import json
import unittest
from base64 import b64encode
from pathlib import Path
from typing import Any

from quex_backend.batch import (
    EthereumBatchHTTPAction,
    EthereumBatchHTTPActionWithProof,
)
from quex_backend.models import (
    HTTPPrivatePatch,
    HTTPRequest,
    QueryParameter,
    QueryParameterPatch,
    RequestHeader,
    RequestHeaderPatch,
    RequestMethod,
)


def request_from_dict(data: dict[str, Any]) -> HTTPRequest:
    return HTTPRequest(
        method=RequestMethod(data["method"]),
        host=data["host"],
        path=data["path"],
        headers=[RequestHeader(h["key"], h["value"]) for h in data["headers"]],
        parameters=[QueryParameter(p["key"], p["value"]) for p in data["parameters"]],
        body=data["body"].encode(),
    )


def patch_from_dict(data: dict[str, Any]) -> HTTPPrivatePatch:
    return HTTPPrivatePatch(
        path_suffix=data["path_suffix"].encode(),
        headers=[RequestHeaderPatch(h["key"], h["ciphertext"].encode()) for h in data["headers"]],
        parameters=[QueryParameterPatch(p["key"], p["ciphertext"].encode()) for p in data["parameters"]],
        body=data["body"].encode(),
        td_address=data["td_address"],
    )


def batch_action_from_dict(data: dict[str, Any]) -> EthereumBatchHTTPAction:
    return EthereumBatchHTTPAction(
        requests=[request_from_dict(r) for r in data["requests"]],
        patches=[patch_from_dict(p) for p in data["patches"]],
        schema=data["response_schema"],
        filter=data["jq_filter"],
    )


class TestBatchActionEncoding(unittest.TestCase):
    vectors = json.loads(
        (Path(__file__).parent.resolve() / "test_vectors" / "batch_action_test_vectors.json").read_text()
    )["vectors"]

    def test_batch_action_encoding_and_domain_tagged_id(self):
        for v in self.vectors:
            action = batch_action_from_dict(v["action"])
            self.assertEqual(b64encode(action.bytes()).decode("ascii"), v["bytes"])
            self.assertEqual("0x" + action.action_id().hex(), v["action_id"])

    def test_batch_action_with_proof_parse_roundtrip(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        wrapped = EthereumBatchHTTPActionWithProof(action=action, proof=b"\x01\x02\x03")

        parsed = EthereumBatchHTTPActionWithProof.parse(wrapped.bytes())

        self.assertEqual(parsed, wrapped)
        self.assertEqual(parsed.action.action_id(), action.action_id())


if __name__ == "__main__":
    unittest.main()
