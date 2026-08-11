from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import astuple, dataclass
from typing import Any

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

# Domain tag pinned cross-language by tests/test_vectors/batch_action_test_vectors.json.
BATCH_ACTION_DOMAIN = keccak(text="quex.action.batchRequest.v1")
# Consensus-relevant code constants, never config: TDs must derive identical results.
MAX_BATCH_SIZE = 8
# Each encrypted patch field costs one ECDH multiplication, so the total is capped.
MAX_PATCH_FIELDS = 32
# Per-socket timeout; does not bound a source dripping bytes slowly.
SOURCE_TIMEOUT_SECONDS = 3
# Wall-clock bound for the whole batch, covers slow-drip sources.
BATCH_DEADLINE_SECONDS = 10


class BatchActionValidationError(Exception):
    pass


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
        if not 1 <= len(self.requests) <= MAX_BATCH_SIZE:
            raise BatchActionValidationError(
                f"batch must contain 1..{MAX_BATCH_SIZE} requests, "
                f"got {len(self.requests)}"
            )
        if len(self.patches) != len(self.requests):
            raise BatchActionValidationError(
                f"patch count {len(self.patches)} does not match request count "
                f"{len(self.requests)}"
            )
        for request in self.requests:
            # Absolute or protocol-relative paths let urljoin override the host (SSRF).
            if (
                not request.path.startswith("/")
                or request.path.startswith("//")
                or "://" in request.path
            ):
                raise BatchActionValidationError(
                    "request path must be a rooted relative path"
                )
        total_patch_fields = sum(
            len(p.headers) + len(p.parameters) + bool(p.body) + bool(p.path_suffix)
            for p in self.patches
        )
        if total_patch_fields > MAX_PATCH_FIELDS:
            raise BatchActionValidationError(
                f"batch has {total_patch_fields} encrypted patch fields, "
                f"max {MAX_PATCH_FIELDS}"
            )

    # Canonical id preimage; the domain tag keeps batch ids disjoint from v1 action ids.
    def id_preimage(self) -> bytes:
        return eth_abi.encode(
            ["bytes32", self.obj_schema()], [BATCH_ACTION_DOMAIN, astuple(self)]
        )

    def action_id(self) -> bytes:
        return keccak(self.id_preimage())


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


# One (request, patch) pair for apply_patch; binds the proof to the whole-batch id.
@dataclass
class _BatchPairAction(HTTPAction):
    batch_action_id: bytes

    def action_id(self) -> bytes:
        return self.batch_action_id


def apply_batch_patches(
    processor: EncryptedPatchProcessor, action: EthereumBatchHTTPAction, proof: bytes
) -> list[HTTPRequest]:
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


# Translates raw requests-layer errors so exception text can never reach a signed value.
def make_source_request(qrr: HTTPRequest) -> Any:
    try:
        return make_request(qrr, timeout=SOURCE_TIMEOUT_SECONDS)
    except (RequestException, ValueError) as exc:
        raise RequestConnectionError from exc


# Fail-all in request order; a deadline miss maps to RequestConnectionError.
def fetch_all_sources(batch_requests: list[HTTPRequest]) -> list[Any]:
    pool = ThreadPoolExecutor(max_workers=len(batch_requests) or 1)
    try:
        futures = [pool.submit(make_source_request, r) for r in batch_requests]
        _, pending = wait(futures, timeout=BATCH_DEADLINE_SECONDS)
        if pending:
            raise RequestConnectionError
        return [f.result() for f in futures]
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
