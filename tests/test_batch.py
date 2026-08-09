import json
import time
import unittest
from base64 import b64decode, b64encode
from pathlib import Path
from random import Random
from typing import Any, Callable
from unittest.mock import Mock, patch

import eth_abi
from ecdsa import SECP256k1, SigningKey
from eth_utils import keccak
from requests.exceptions import InvalidHeader, Timeout

from quex_backend import create_app
from quex_backend.batch import (
    MAX_BATCH_SIZE,
    MAX_PATCH_FIELDS,
    SOURCE_TIMEOUT_SECONDS,
    BatchActionValidationError,
    EthereumBatchHTTPAction,
    EthereumBatchHTTPActionWithProof,
    apply_batch_patches,
    fetch_all_sources,
    make_source_request,
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
from quex_backend.utils import GetTimestampError, RequestConnectionError
from tests.client import Client

FUZZ_ROUNDS = 50


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


def fuzz_text(rng: Random, alphabet: str = "abcXYZ019 %&?=.-_é中") -> str:
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12)))


def fuzz_bytes(rng: Random) -> bytes:
    return bytes(rng.randrange(256) for _ in range(rng.randint(0, 8)))


def fuzz_request(rng: Random) -> HTTPRequest:
    return HTTPRequest(
        method=RequestMethod(rng.randrange(len(RequestMethod))),
        host=fuzz_text(rng),
        path="/" + fuzz_text(rng, "abz09._-"),
        headers=[RequestHeader(fuzz_text(rng), fuzz_text(rng)) for _ in range(rng.randint(0, 2))],
        parameters=[QueryParameter(fuzz_text(rng), fuzz_text(rng)) for _ in range(rng.randint(0, 2))],
        body=fuzz_bytes(rng),
    )


def fuzz_patch(rng: Random) -> HTTPPrivatePatch:
    # At most 4 fields per patch so a full batch stays within MAX_PATCH_FIELDS.
    return HTTPPrivatePatch(
        path_suffix=fuzz_bytes(rng),
        headers=[RequestHeaderPatch(fuzz_text(rng), fuzz_bytes(rng)) for _ in range(rng.randint(0, 1))],
        parameters=[QueryParameterPatch(fuzz_text(rng), fuzz_bytes(rng)) for _ in range(rng.randint(0, 1))],
        body=fuzz_bytes(rng),
        td_address="0x" + "".join(rng.choice("0123456789abcdef") for _ in range(40)),
    )


def fuzz_action(rng: Random) -> EthereumBatchHTTPAction:
    n = rng.randint(1, MAX_BATCH_SIZE)
    return EthereumBatchHTTPAction(
        requests=[fuzz_request(rng) for _ in range(n)],
        patches=[fuzz_patch(rng) for _ in range(n)],
        schema=rng.choice(["uint256", "int256", "string"]),
        filter=fuzz_text(rng),
    )


class TestBatchActionEncoding(unittest.TestCase):
    vectors = json.loads(
        (Path(__file__).parent.resolve() / "test_vectors" / "batch_action_test_vectors.json").read_text()
    )["vectors"]

    def test_pinned_cross_language_vector(self):
        for v in self.vectors:
            action = batch_action_from_dict(v["action"])
            action.validate()
            self.assertEqual(b64encode(action.bytes()).decode("ascii"), v["bytes"])
            self.assertEqual(action.action_id().hex(), v["action_id"])

    def test_fuzzed_actions_roundtrip_with_domain_tagged_id(self):
        rng = Random(1337)
        for i in range(FUZZ_ROUNDS):
            with self.subTest(round=i):
                action = fuzz_action(rng)
                wrapped = EthereumBatchHTTPActionWithProof(action=action, proof=fuzz_bytes(rng))

                parsed = EthereumBatchHTTPActionWithProof.parse(wrapped.bytes())

                self.assertEqual(parsed, wrapped)
                # The id preimage is domain-tagged; hashing the plain encoding must give another
                # value, otherwise batch ids could collide with v1 single-request action ids.
                self.assertNotEqual(action.action_id(), keccak(action.bytes()))

    # Each mutation breaks exactly one invariant of an otherwise valid fuzzed action.
    def mutations(self) -> list[tuple[str, Callable[[EthereumBatchHTTPAction], None]]]:
        def empty(a): a.requests, a.patches = [], []
        def oversized(a):
            a.requests = [a.requests[0]] * (MAX_BATCH_SIZE + 1)
            a.patches = [a.patches[0]] * (MAX_BATCH_SIZE + 1)
        def patch_mismatch(a): a.patches = a.patches + [a.patches[0]]
        def absolute_url_path(a): a.requests[0].path = "http://169.254.169.254/latest/meta-data/"
        def protocol_relative_path(a): a.requests[0].path = "//evil.example.com/x"
        def unrooted_path(a): a.requests[0].path = "api/v3"
        def too_many_patch_fields(a):
            a.patches[0].parameters = [
                QueryParameterPatch(f"k{i}", b"x") for i in range(MAX_PATCH_FIELDS + 1)
            ]
        return [
            ("empty batch", empty),
            ("oversized batch", oversized),
            ("patch count mismatch", patch_mismatch),
            ("absolute url path", absolute_url_path),
            ("protocol-relative path", protocol_relative_path),
            ("unrooted path", unrooted_path),
            ("too many patch fields", too_many_patch_fields),
        ]

    def test_parse_rejects_fuzzed_actions_with_broken_invariants(self):
        rng = Random(7)
        for name, mutate in self.mutations():
            with self.subTest(mutation=name):
                action = fuzz_action(rng)
                mutate(action)
                data = EthereumBatchHTTPActionWithProof(action=action, proof=b"").bytes()

                with self.assertRaises(BatchActionValidationError):
                    EthereumBatchHTTPActionWithProof.parse(data)


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

    def test_make_source_request_translates_requests_errors_to_connection_error(self):
        # A bad decrypted header byte raises deep in requests; it must become a fail-all
        # connection error, never escape to a handler that would sign its text.
        with patch("requests.Session.request", side_effect=InvalidHeader("sk_live_SECRET")):
            with self.assertRaises(RequestConnectionError):
                make_source_request(get_request("api.example.com"))


class TestQueryBatchRoute(unittest.TestCase):
    vectors = TestBatchActionEncoding.vectors

    def setUp(self) -> None:
        self.client = create_app().test_client()

    def wrapped_action_b64(self, action: EthereumBatchHTTPAction) -> str:
        wrapped = EthereumBatchHTTPActionWithProof(action=action, proof=b"")
        return b64encode(wrapped.bytes()).decode("ascii")

    def post_action(self, action: EthereumBatchHTTPAction) -> Any:
        payload = {
            "action": self.wrapped_action_b64(action),
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

    def test_query_batch_signs_error_with_empty_value_when_one_source_is_dead(self):
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

    def test_query_batch_rejects_malformed_payloads_with_unsigned_400(self):
        valid_action = self.wrapped_action_b64(batch_action_from_dict(self.vectors[0]["action"]))
        invalid_action = batch_action_from_dict(self.vectors[0]["action"])
        invalid_action.patches = invalid_action.patches[:1]
        relayer = "0x1111111111111111111111111111111111111111"
        cases = [
            ("missing action", {"relayer": relayer}),
            ("missing relayer", {"action": valid_action}),
            ("undecodable action bytes", {"action": "AAAA", "relayer": relayer}),
            ("invalid batch", {"action": self.wrapped_action_b64(invalid_action), "relayer": relayer}),
            ("invalid relayer", {"action": valid_action, "relayer": "not-an-address"}),
        ]
        for name, payload in cases:
            with self.subTest(case=name):
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
