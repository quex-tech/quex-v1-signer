import ssl
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import astuple, dataclass
from typing import Any, List

import eth_abi
import requests
from eth_utils import keccak
from requests.exceptions import ConnectionError, Timeout

from quex_backend.encryption import EncryptedPatchProcessor
from quex_backend.models import (
    ABIEncodable,
    HTTPAction,
    HTTPPrivatePatch,
    HTTPRequest,
    from_nested_tuple,
)
from quex_backend.interpreter import jq_eval, parser
from quex_backend.utils import (
    ABIEncodingError,
    JQProcessingError,
    RequestConnectionError,
    Response4XXError,
    Response5XXError,
    ResponseNotJSONError,
    ResponseNotSupportedResponseCodeError,
    SSLAdapter,
)

# Shared wire constant: the same domain tag and tuple order are pinned by
# tests/test_vectors/batch_action_test_vectors.json and must be reproduced by every
# other component computing batch action ids (client tooling, future contracts).
BATCH_ACTION_DOMAIN = keccak(text="quex.action.batchRequest.v1")
# Consensus-relevant: every TD must derive identical results for the same action id,
# so these are code constants, never config.
MAX_BATCH_SIZE = 8
# Per-socket connect/read timeout: it does NOT bound a source dripping bytes slowly.
SOURCE_TIMEOUT_SECONDS = 3
# Wall-clock bound for the whole batch, covering slow-drip sources the socket timeout misses.
BATCH_DEADLINE_SECONDS = 10


class BatchActionValidationError(Exception):
    pass


# Batch of parallel HTTP requests processed as one action: the JSON results are collected
# into an array (in request order) and the jq filter runs over that array.
@dataclass
class EthereumBatchHTTPAction(ABIEncodable):
    requests: List[HTTPRequest]
    patches: List[HTTPPrivatePatch]
    schema: str
    filter: str

    @staticmethod
    def obj_schema() -> str:
        return f"({HTTPRequest.obj_schema()}[],{HTTPPrivatePatch.obj_schema()}[],string,string)"

    def validate(self) -> None:
        if not 1 <= len(self.requests) <= MAX_BATCH_SIZE:
            raise BatchActionValidationError(
                f"batch must contain 1..{MAX_BATCH_SIZE} requests, got {len(self.requests)}"
            )
        if len(self.patches) != len(self.requests):
            raise BatchActionValidationError(
                f"patch count {len(self.patches)} does not match request count {len(self.requests)}"
            )

    def id_preimage(self) -> bytes:
        # Domain-tagged so batch ids can never collide with single-request v1 action ids
        # (whose preimage is the untagged bytes()). This is the canonical hashing preimage.
        return eth_abi.encode(["bytes32", self.obj_schema()], [BATCH_ACTION_DOMAIN, astuple(self)])

    def action_id(self) -> bytes:
        return keccak(self.id_preimage())


@dataclass
class EthereumBatchHTTPActionWithProof(ABIEncodable):
    action: EthereumBatchHTTPAction
    proof: bytes

    @staticmethod
    def obj_schema() -> str:
        return f"({EthereumBatchHTTPAction.obj_schema()},bytes)"

    @staticmethod
    def parse(data: bytes) -> "EthereumBatchHTTPActionWithProof":
        (data_tuple,) = eth_abi.decode([EthereumBatchHTTPActionWithProof.obj_schema()], data)
        result: EthereumBatchHTTPActionWithProof = from_nested_tuple(
            data_tuple, EthereumBatchHTTPActionWithProof
        )
        # Validate at the decode boundary: an invalid batch action is unconstructible
        # from bytes, so every consumer of parse() inherits the size invariants.
        result.action.validate()
        return result


# Adapter presenting one (request, patch) pair to EncryptedPatchProcessor.apply_patch,
# which binds the decryption proof to the id of the WHOLE batch action.
@dataclass
class _BatchPairAction(HTTPAction):
    batch_action_id: bytes

    def action_id(self) -> bytes:
        return self.batch_action_id


def apply_batch_patches(
    processor: EncryptedPatchProcessor, action: EthereumBatchHTTPAction, proof: bytes
) -> List[HTTPRequest]:
    action_id = action.action_id()
    return [
        processor.apply_patch(
            _BatchPairAction(
                request=request,
                patch=patch,
                schema=action.schema,
                filter=action.filter,
                batch_action_id=action_id,
            ),
            proof,
        )
        for request, patch in zip(action.requests, action.patches, strict=True)
    ]


# Mirror of utils.make_request with a per-socket timeout, fetching ONE source. The v1
# code path must stay byte-for-byte untouched, so the timeout lives here instead of a
# shared parameter.
def make_source_request(qrr: HTTPRequest) -> Any:
    try:
        url = qrr.build_url()

        context = ssl.create_default_context()
        context.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20")
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        session = requests.Session()
        session.mount("https://", SSLAdapter(ssl_context=context))

        r = session.request(
            qrr.method.string_value(),
            url,
            params=qrr.get_parameters(),
            headers=qrr.get_headers(),
            data=qrr.get_body(),
            verify=True,
            allow_redirects=False,
            timeout=SOURCE_TIMEOUT_SECONDS,
        )
    except (ConnectionError, Timeout) as exc:
        raise RequestConnectionError from exc

    if 300 <= r.status_code < 400 or r.status_code >= 600:
        raise ResponseNotSupportedResponseCodeError(r.status_code)
    elif 400 <= r.status_code < 500:
        raise Response4XXError(r.status_code)
    elif 500 <= r.status_code < 600:
        raise Response5XXError(r.status_code)

    if r.status_code == 204:
        return ""

    try:
        return r.json()
    except Exception as exc:
        raise ResponseNotJSONError from exc


# EVM-only sibling of utils.process_json for a list-shaped jq input (the v1 signature
# is annotated for a dict root and must stay untouched).
def process_json_list(input_list: List[Any], json_query: str, schema: str) -> bytes:
    try:
        ast = parser.parse(json_query)
        result = jq_eval(input_list, ast)
    except Exception as exc:
        raise JQProcessingError from exc

    try:
        encoded: bytes = eth_abi.encode([schema], [result])
        return encoded
    except Exception as exc:
        raise ABIEncodingError from exc


def fetch_all_sources(batch_requests: List[HTTPRequest]) -> List[Any]:
    # Fail-all, deterministically: results are collected in request order after ALL futures
    # settle, so every TD reports the same error code regardless of source timing. A batch
    # missing the wall-clock deadline maps to RequestConnectionError; shutdown(wait=False)
    # returns the serving thread immediately and abandons any stuck fetch threads.
    pool = ThreadPoolExecutor(max_workers=min(max(len(batch_requests), 1), MAX_BATCH_SIZE))
    try:
        futures = [pool.submit(make_source_request, r) for r in batch_requests]
        _, pending = wait(futures, timeout=BATCH_DEADLINE_SECONDS)
        if pending:
            raise RequestConnectionError
        return [f.result() for f in futures]
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
