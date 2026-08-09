import json
import unittest
from base64 import b64decode, b64encode
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import eth_abi
from requests.exceptions import Timeout

from quex_backend.batch import (
    MAX_BATCH_SIZE,
    SOURCE_TIMEOUT_SECONDS,
    BatchActionValidationError,
    EthereumBatchHTTPAction,
    EthereumBatchHTTPActionWithProof,
    apply_batch_patches,
    fetch_all,
    process_json_list,
)
from quex_backend.models import (
    HTTPPrivatePatch,
    HTTPRequest,
    QueryParameter,
    QueryParameterPatch,
    RequestHeader,
    RequestHeaderPatch,
    QuexErrorCodes,
    RequestMethod,
)
from quex_backend.utils import RequestConnectionError
from quex_backend.encryption import EncryptedPatchProcessor
from ecdsa import SECP256k1, SigningKey
from tests.client import Client


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

    def test_validate_accepts_vector_action(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.validate()

    def test_validate_rejects_empty_batch(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.requests = []
        action.patches = []
        with self.assertRaises(BatchActionValidationError):
            action.validate()

    def test_validate_rejects_oversized_batch(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.requests = [action.requests[0]] * (MAX_BATCH_SIZE + 1)
        action.patches = [action.patches[0]] * (MAX_BATCH_SIZE + 1)
        with self.assertRaises(BatchActionValidationError):
            action.validate()

    def test_validate_rejects_patch_count_mismatch(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.patches = action.patches[:1]
        with self.assertRaises(BatchActionValidationError):
            action.validate()

    def test_batch_action_with_proof_parse_roundtrip(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        wrapped = EthereumBatchHTTPActionWithProof(action=action, proof=b"\x01\x02\x03")

        parsed = EthereumBatchHTTPActionWithProof.parse(wrapped.bytes())

        self.assertEqual(parsed, wrapped)
        self.assertEqual(parsed.action.action_id(), action.action_id())


class TestQueryBatchRoute(unittest.TestCase):
    vectors = TestBatchActionEncoding.vectors

    def setUp(self) -> None:
        from quex_backend import create_app

        self.client = create_app().test_client()

    def post_action(self, action: EthereumBatchHTTPAction) -> Any:
        wrapped = EthereumBatchHTTPActionWithProof(action=action, proof=b"")
        payload = {
            "action": b64encode(wrapped.bytes()).decode("ascii"),
            "relayer": "0x1111111111111111111111111111111111111111",
        }
        return self.client.post("/query_batch", json=payload)

    def test_query_batch_returns_signed_sum_of_sources(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.filter = "map(.price | tonumber) | add | round"

        with patch("quex_backend.batch_routes.get_timestamp", return_value=1700000000):
            with patch("requests.Session.request") as mock_request:

                def respond(method: str, url: str, **kwargs: Any) -> Mock:
                    if "binance" in url:
                        return Mock(status_code=200, json=lambda: {"price": "2"})
                    return Mock(status_code=200, json=lambda: {"price": "3"})

                mock_request.side_effect = respond

                response = self.post_action(action)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["msg"]["data_item"]["error"], 0)
        self.assertEqual(
            b64decode(data["msg"]["action_id"]), action.action_id()
        )
        self.assertEqual(
            eth_abi.decode(["uint256"], b64decode(data["msg"]["data_item"]["value"])), (5,)
        )
        self.assertIn("sig", data)


    def test_query_batch_signs_error_when_one_source_is_dead(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.filter = "map(.price | tonumber) | add | round"

        with patch("quex_backend.batch_routes.get_timestamp", return_value=1700000000):
            with patch("requests.Session.request") as mock_request:

                def respond(method: str, url: str, **kwargs: Any) -> Mock:
                    if "binance" in url:
                        return Mock(status_code=200, json=lambda: {"price": "2"})
                    raise Timeout()

                mock_request.side_effect = respond

                response = self.post_action(action)

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(
            data["msg"]["data_item"]["error"], QuexErrorCodes.REQUEST_CONNECTION_ERROR.value
        )
        self.assertEqual(b64decode(data["msg"]["data_item"]["value"]), b"")

    def test_query_batch_rejects_invalid_batch_without_signing(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.patches = action.patches[:1]

        response = self.post_action(action)

        self.assertEqual(response.status_code, 400)


def get_request(host: str) -> HTTPRequest:
    return HTTPRequest(
        method=RequestMethod.GET, host=host, path="/", headers=[], parameters=[], body=b""
    )


class TestBatchPatchApplication(unittest.TestCase):
    vectors = TestBatchActionEncoding.vectors

    def test_apply_batch_patches_decrypts_per_pair_with_batch_action_id(self):
        private_key = SigningKey.generate(curve=SECP256k1)
        processor = EncryptedPatchProcessor.from_hex(private_key.to_string().hex())
        client = Client(processor.get_public_key())

        action = batch_action_from_dict(self.vectors[0]["action"])
        action.patches[1].headers = [
            RequestHeaderPatch("X-Api-Key", client.encrypt_message(b"secret"))
        ]
        proof = client.encrypt_message(action.action_id(), include_ephemeral_public_key=True)

        patched = apply_batch_patches(processor, action, proof)

        self.assertEqual(len(patched), 2)
        self.assertEqual(patched[0].headers, action.requests[0].headers)
        self.assertIn(RequestHeader("X-Api-Key", "secret"), patched[1].headers)


class TestBatchJqProcessing(unittest.TestCase):
    def test_process_json_list_sums_sources_into_encoded_result(self):
        encoded = process_json_list(
            [{"price": "2"}, {"price": "3"}], "map(.price | tonumber) | add | round", "uint256"
        )

        self.assertEqual(eth_abi.decode(["uint256"], encoded), (5,))


class TestBatchFetch(unittest.TestCase):
    def test_fetch_all_preserves_request_order_and_passes_timeout(self):
        with patch("requests.Session.request") as mock_request:

            def respond(method: str, url: str, **kwargs: Any) -> Mock:
                if "one.example.com" in url:
                    return Mock(status_code=200, json=lambda: {"n": 1})
                return Mock(status_code=200, json=lambda: {"n": 2})

            mock_request.side_effect = respond

            results = fetch_all([get_request("one.example.com"), get_request("two.example.com")])

            self.assertEqual(results, [{"n": 1}, {"n": 2}])
            self.assertEqual(mock_request.call_args.kwargs["timeout"], SOURCE_TIMEOUT_SECONDS)

    def test_fetch_all_fails_all_when_one_source_times_out(self):
        with patch("requests.Session.request") as mock_request:

            def respond(method: str, url: str, **kwargs: Any) -> Mock:
                if "dead.example.com" in url:
                    raise Timeout()
                return Mock(status_code=200, json=lambda: {"n": 1})

            mock_request.side_effect = respond

            with self.assertRaises(RequestConnectionError):
                fetch_all([get_request("live.example.com"), get_request("dead.example.com")])


if __name__ == "__main__":
    unittest.main()
