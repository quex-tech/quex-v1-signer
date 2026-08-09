import json
import time
import unittest
from base64 import b64decode, b64encode
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import eth_abi
from ecdsa import SECP256k1, SigningKey
from eth_utils import keccak
from requests.exceptions import Timeout

from quex_backend import create_app
from quex_backend.batch import (
    MAX_BATCH_SIZE,
    SOURCE_TIMEOUT_SECONDS,
    BatchActionValidationError,
    EthereumBatchHTTPAction,
    EthereumBatchHTTPActionWithProof,
    apply_batch_patches,
    fetch_all_sources,
    make_source_request,
    process_json_list,
)
from quex_backend.encryption import EncryptedPatchProcessingError, EncryptedPatchProcessor
from quex_backend.models import (
    HTTPPrivatePatch,
    HTTPRequest,
    QueryParameter,
    QueryParameterPatch,
    QuexErrorCodes,
    RequestHeader,
    RequestHeaderPatch,
    RequestMethod,
)
from quex_backend.utils import (
    GetTimestampError,
    JQProcessingError,
    RequestConnectionError,
    Response4XXError,
    Response5XXError,
    ResponseNotJSONError,
    ResponseNotSupportedResponseCodeError,
    process_json,
)
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


def get_request(host: str) -> HTTPRequest:
    return HTTPRequest(
        method=RequestMethod.GET, host=host, path="/", headers=[], parameters=[], body=b""
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

    def test_action_id_differs_from_untagged_bytes_hash(self):
        # The id preimage is domain-tagged; hashing the plain encoding must give another value,
        # otherwise batch ids could collide with v1 single-request action ids.
        action = batch_action_from_dict(self.vectors[0]["action"])
        self.assertNotEqual(action.action_id(), keccak(action.bytes()))

    def test_validate_accepts_vector_action(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.validate()

    def test_validate_accepts_max_batch_size(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.requests = [action.requests[0]] * MAX_BATCH_SIZE
        action.patches = [action.patches[0]] * MAX_BATCH_SIZE
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

    def test_parse_rejects_invalid_batch(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.patches = action.patches[:1]
        wrapped = EthereumBatchHTTPActionWithProof(action=action, proof=b"")

        with self.assertRaises(BatchActionValidationError):
            EthereumBatchHTTPActionWithProof.parse(wrapped.bytes())

    def test_batch_action_with_proof_parse_roundtrip(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        wrapped = EthereumBatchHTTPActionWithProof(action=action, proof=b"\x01\x02\x03")

        parsed = EthereumBatchHTTPActionWithProof.parse(wrapped.bytes())

        self.assertEqual(parsed, wrapped)
        self.assertEqual(parsed.action.action_id(), action.action_id())


class TestBatchPatchApplication(unittest.TestCase):
    vectors = TestBatchActionEncoding.vectors

    def setUp(self) -> None:
        private_key = SigningKey.generate(curve=SECP256k1)
        self.processor = EncryptedPatchProcessor.from_hex(private_key.to_string().hex())
        self.client = Client(self.processor.get_public_key())

    def encrypted_action(self) -> EthereumBatchHTTPAction:
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.patches[0].parameters = [
            QueryParameterPatch("api_key", self.client.encrypt_message(b"param-secret"))
        ]
        action.patches[1].headers = [
            RequestHeaderPatch("X-Api-Key", self.client.encrypt_message(b"header-secret"))
        ]
        return action

    def test_apply_batch_patches_decrypts_every_pair_with_one_batch_proof(self):
        action = self.encrypted_action()
        proof = self.client.encrypt_message(action.action_id(), include_ephemeral_public_key=True)

        patched = apply_batch_patches(self.processor, action, proof)

        self.assertEqual(len(patched), 2)
        self.assertIn(QueryParameter("api_key", "param-secret"), patched[0].parameters)
        self.assertIn(RequestHeader("X-Api-Key", "header-secret"), patched[1].headers)

    def test_apply_batch_patches_rejects_proof_bound_to_other_id(self):
        action = self.encrypted_action()
        wrong_proof = self.client.encrypt_message(b"\x00" * 32, include_ephemeral_public_key=True)

        with self.assertRaises(EncryptedPatchProcessingError):
            apply_batch_patches(self.processor, action, wrong_proof)


class TestBatchJqProcessing(unittest.TestCase):
    def test_process_json_list_sums_sources_into_encoded_result(self):
        encoded = process_json_list(
            [{"price": "2"}, {"price": "3"}], "map(.price | tonumber) | add | round", "uint256"
        )

        self.assertEqual(eth_abi.decode(["uint256"], encoded), (5,))

    def test_process_json_list_raises_same_error_type_as_v1_process_json(self):
        # process_json_list mirrors utils.process_json for a list root; a bad filter must
        # keep failing identically in both so the copies cannot drift silently.
        with self.assertRaises(JQProcessingError):
            process_json_list([{"a": 1}], "((", "uint256")
        with self.assertRaises(JQProcessingError):
            process_json({"a": 1}, "((", "uint256", eth_abi.encode)


class TestBatchFetch(unittest.TestCase):
    def test_fetch_all_sources_preserves_request_order_and_passes_timeout(self):
        with patch("requests.Session.request") as mock_request:

            def respond(method: str, url: str, **kwargs: Any) -> Mock:
                if "one.example.com" in url:
                    return Mock(status_code=200, json=lambda: {"n": 1})
                return Mock(status_code=200, json=lambda: {"n": 2})

            mock_request.side_effect = respond

            results = fetch_all_sources(
                [get_request("one.example.com"), get_request("two.example.com")]
            )

            self.assertEqual(results, [{"n": 1}, {"n": 2}])
            for call in mock_request.call_args_list:
                self.assertEqual(call.kwargs["timeout"], SOURCE_TIMEOUT_SECONDS)

    def test_fetch_all_sources_fails_all_when_one_source_times_out(self):
        with patch("requests.Session.request") as mock_request:

            def respond(method: str, url: str, **kwargs: Any) -> Mock:
                if "dead.example.com" in url:
                    raise Timeout()
                return Mock(status_code=200, json=lambda: {"n": 1})

            mock_request.side_effect = respond

            with self.assertRaises(RequestConnectionError):
                fetch_all_sources([get_request("live.example.com"), get_request("dead.example.com")])

    def test_fetch_all_sources_enforces_wall_clock_deadline(self):
        with patch("quex_backend.batch.BATCH_DEADLINE_SECONDS", 0.2):
            with patch("requests.Session.request") as mock_request:

                def slow_drip(method: str, url: str, **kwargs: Any) -> Mock:
                    time.sleep(1)
                    return Mock(status_code=200, json=lambda: {"n": 1})

                mock_request.side_effect = slow_drip

                started = time.monotonic()
                with self.assertRaises(RequestConnectionError):
                    fetch_all_sources([get_request("slow.example.com")])
                self.assertLess(time.monotonic() - started, 0.9)

    def test_fetch_all_sources_of_empty_list_returns_empty(self):
        self.assertEqual(fetch_all_sources([]), [])

    def test_make_source_request_maps_status_codes_like_v1(self):
        cases = [
            (301, ResponseNotSupportedResponseCodeError),
            (404, Response4XXError),
            (500, Response5XXError),
            (601, ResponseNotSupportedResponseCodeError),
        ]
        for status, expected in cases:
            with self.subTest(status=status):
                with patch("requests.Session.request") as mock_request:
                    mock_request.return_value = Mock(status_code=status)
                    with self.assertRaises(expected):
                        make_source_request(get_request("api.example.com"))

    def test_make_source_request_handles_204_and_non_json(self):
        with patch("requests.Session.request") as mock_request:
            mock_request.return_value = Mock(status_code=204)
            self.assertEqual(make_source_request(get_request("api.example.com")), "")

        with patch("requests.Session.request") as mock_request:
            mock_request.return_value = Mock(
                status_code=200, json=Mock(side_effect=ValueError("not json"))
            )
            with self.assertRaises(ResponseNotJSONError):
                make_source_request(get_request("api.example.com"))


class TestQueryBatchRoute(unittest.TestCase):
    vectors = TestBatchActionEncoding.vectors

    def setUp(self) -> None:
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
        self.assertEqual(b64decode(data["msg"]["action_id"]), action.action_id())
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

    def test_query_batch_rejects_malformed_payloads_with_400(self):
        cases = [
            {"relayer": "0x1111111111111111111111111111111111111111"},
            {"action": "AAAA", "relayer": "0x1111111111111111111111111111111111111111"},
            {"action": "AAAA"},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                response = self.client.post("/query_batch", json=payload)
                self.assertEqual(response.status_code, 400)

    def test_query_batch_rejects_invalid_relayer_address(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        wrapped = EthereumBatchHTTPActionWithProof(action=action, proof=b"")
        payload = {
            "action": b64encode(wrapped.bytes()).decode("ascii"),
            "relayer": "not-an-address",
        }

        response = self.client.post("/query_batch", json=payload)

        self.assertEqual(response.status_code, 400)

    def test_query_batch_returns_unsigned_503_when_timestamp_unavailable(self):
        action = batch_action_from_dict(self.vectors[0]["action"])
        action.filter = "map(.price | tonumber) | add | round"

        with patch("quex_backend.batch_routes.get_timestamp", side_effect=GetTimestampError()):
            with patch("requests.Session.request") as mock_request:
                mock_request.return_value = Mock(status_code=200, json=lambda: {"price": "2"})

                response = self.post_action(action)

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
