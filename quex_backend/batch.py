from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import astuple, dataclass
from typing import Any, List

import eth_abi
from eth_utils import keccak
from requests.exceptions import RequestException

from quex_backend.encryption import EncryptedPatchProcessor
from quex_backend.models import (
    ABIEncodable,
    HTTPAction,
    HTTPPrivatePatch,
    HTTPRequest,
    from_nested_tuple,
)
from quex_backend.utils import RequestConnectionError, make_request

# Shared wire constant: the same domain tag and tuple order are pinned by
# tests/test_vectors/batch_action_test_vectors.json and must be reproduced by every
# other component computing batch action ids (client tooling, future contracts).
BATCH_ACTION_DOMAIN = keccak(text="quex.action.batchRequest.v1")
# Consensus-relevant: every TD must derive identical results for the same action id,
# so these are code constants, never config.
MAX_BATCH_SIZE = 8
# Each encrypted patch field costs an ECDH scalar multiplication with the TD long-term
# key, so an unbounded count is a CPU-exhaustion vector.
MAX_PATCH_FIELDS = 32
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
        for request in self.requests:
            # urljoin lets an absolute (scheme://) or protocol-relative (//host) path override
            # the host or scheme (e.g. a cloud-metadata URL), so only a plain rooted path passes.
            if (
                not request.path.startswith("/")
                or request.path.startswith("//")
                or "://" in request.path
            ):
                raise BatchActionValidationError("request path must be a rooted relative path")
        total_patch_fields = sum(
            len(p.headers) + len(p.parameters) + bool(p.body) + bool(p.path_suffix)
            for p in self.patches
        )
        if total_patch_fields > MAX_PATCH_FIELDS:
            raise BatchActionValidationError(
                f"batch has {total_patch_fields} encrypted patch fields, max {MAX_PATCH_FIELDS}"
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


def make_source_request(qrr: HTTPRequest) -> Any:
    try:
        return make_request(qrr, timeout=SOURCE_TIMEOUT_SECONDS)
    except (RequestException, ValueError) as exc:
        # Translate the failures make_request leaves raw (InvalidHeader/InvalidURL and plain
        # ValueErrors from bad header bytes) so nothing escapes to a handler where its text,
        # possibly containing a decrypted secret, would be signed on-chain.
        raise RequestConnectionError from exc


def fetch_all_sources(batch_requests: List[HTTPRequest]) -> List[Any]:
    # Fail-all, deterministically: results are collected in request order after ALL futures
    # settle, so every TD reports the same error code regardless of source timing. A batch
    # missing the wall-clock deadline maps to RequestConnectionError; shutdown(wait=False)
    # returns the serving thread immediately and abandons any stuck fetch threads.
    pool = ThreadPoolExecutor(max_workers=len(batch_requests) or 1)
    try:
        futures = [pool.submit(make_source_request, r) for r in batch_requests]
        _, pending = wait(futures, timeout=BATCH_DEADLINE_SECONDS)
        if pending:
            raise RequestConnectionError
        return [f.result() for f in futures]
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
