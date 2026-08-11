from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import astuple, dataclass
from typing import Any
from urllib.parse import urlsplit

import eth_abi
from eth_utils import keccak
from requests.exceptions import RequestException

from quex_backend.encryption import (
    EncryptedPatchProcessingError,
    EncryptedPatchProcessor,
)
from quex_backend.models import (
    ABIEncodable,
    HTTPPrivatePatch,
    HTTPRequest,
    from_nested_tuple,
)
from quex_backend.utils import RequestConnectionError, make_request

# Domain tag pinned cross-language by tests/test_vectors/batch_action_test_vectors.json.
BATCH_ACTION_DOMAIN = keccak(text="quex.action.batchRequest.v1")
# Per-socket timeout; does not bound a source dripping bytes slowly.
SOURCE_TIMEOUT_SECONDS = 3
# Wall-clock bound for the whole batch, covers slow-drip sources.
BATCH_DEADLINE_SECONDS = 10
# Fixed pool size: fetch concurrency must not depend on the host, or TDs of one pool
# could disagree on whether a large batch meets the deadline (consensus-relevant).
MAX_FETCH_WORKERS = 32


class BatchActionValidationError(Exception):
    pass


# A scheme, a host, or a backslash lets the path override the declared host.
def is_rooted_relative_path(path: str) -> bool:
    parts = urlsplit(path)
    if parts.scheme or parts.netloc or "\\" in path:
        return False
    return parts.path.startswith("/")


# Parallel HTTP requests as one action; jq runs over the array of JSON results.
@dataclass
class EthereumBatchHTTPAction(ABIEncodable):
    requests: list[HTTPRequest]
    patches: list[HTTPPrivatePatch]
    schema: str
    filter: str

    @staticmethod
    def obj_schema() -> str:
        req, patch = HTTPRequest.obj_schema(), HTTPPrivatePatch.obj_schema()
        return f"({req}[],{patch}[],string,string)"

    def validate(self) -> None:
        if not self.requests:
            raise BatchActionValidationError("batch must contain at least one request")
        if len(self.patches) != len(self.requests):
            raise BatchActionValidationError("patch count does not match request count")
        for request in self.requests:
            if not is_rooted_relative_path(request.path):
                raise BatchActionValidationError("path must be a rooted relative path")

    # The domain-tagged preimage keeps batch ids disjoint from v1 action ids.
    def action_id(self) -> bytes:
        preimage = eth_abi.encode(
            ["bytes32", self.obj_schema()], [BATCH_ACTION_DOMAIN, astuple(self)]
        )
        return keccak(preimage)


@dataclass
class EthereumBatchHTTPActionWithProof(ABIEncodable):
    action: EthereumBatchHTTPAction
    proof: bytes

    @staticmethod
    def obj_schema() -> str:
        return f"({EthereumBatchHTTPAction.obj_schema()},bytes)"

    # Validates at the decode boundary so every consumer inherits the invariants.
    @staticmethod
    def parse(data: bytes) -> "EthereumBatchHTTPActionWithProof":
        schema = EthereumBatchHTTPActionWithProof.obj_schema()
        (data_tuple,) = eth_abi.decode([schema], data)
        result: EthereumBatchHTTPActionWithProof = from_nested_tuple(
            data_tuple, EthereumBatchHTTPActionWithProof
        )
        result.action.validate()
        return result


# One proof covers the whole batch, so the ephemeral key is recovered once (one ECDH),
# not once per pair; batches with no encrypted fields never touch the proof, as in v1.
def apply_batch_patches(
    processor: EncryptedPatchProcessor, action: EthereumBatchHTTPAction, proof: bytes
) -> list[HTTPRequest]:
    action_id = action.action_id()
    key = None
    encrypted = any(
        p.headers or p.parameters or p.body or p.path_suffix for p in action.patches
    )
    if encrypted:
        try:
            key = processor.recover_ephemeral_public_key(action_id, proof)
        except Exception as exc:
            raise EncryptedPatchProcessingError from exc
    patched = [
        processor.apply_patch(request, patch, action_id, proof, key)
        for request, patch in zip(action.requests, action.patches, strict=True)
    ]
    # Re-check after patching: a decrypted path_suffix must not override the host.
    for request in patched:
        if not is_rooted_relative_path(request.path):
            raise EncryptedPatchProcessingError("patched path is not rooted relative")
    return patched


# Translates raw requests-layer errors so exception text can never reach a signed value.
def make_source_request(qrr: HTTPRequest) -> Any:
    try:
        return make_request(qrr, timeout=SOURCE_TIMEOUT_SECONDS)
    except (RequestException, ValueError) as exc:
        raise RequestConnectionError from exc


# Fail-all in request order; a deadline miss maps to RequestConnectionError.
def fetch_all_sources(batch_requests: list[HTTPRequest]) -> list[Any]:
    workers = min(len(batch_requests) or 1, MAX_FETCH_WORKERS)
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = [pool.submit(make_source_request, r) for r in batch_requests]
        _, pending = wait(futures, timeout=BATCH_DEADLINE_SECONDS)
        if pending:
            raise RequestConnectionError
        return [f.result() for f in futures]
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
