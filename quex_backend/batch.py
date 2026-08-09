import ssl
from concurrent.futures import ThreadPoolExecutor
from dataclasses import astuple, dataclass
from typing import Any, List

import eth_abi
import requests
from eth_utils import keccak
from requests.exceptions import ConnectionError, Timeout

from quex_backend.models import (
    ABIEncodable,
    HTTPPrivatePatch,
    HTTPRequest,
    from_nested_tuple,
)
from quex_backend.utils import (
    RequestConnectionError,
    Response4XXError,
    Response5XXError,
    ResponseNotJSONError,
    ResponseNotSupportedResponseCodeError,
    SSLAdapter,
)

BATCH_ACTION_DOMAIN = keccak(text="quex.action.batchRequest.v1")
MAX_BATCH_SIZE = 8
SOURCE_TIMEOUT_SECONDS = 3


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

    def action_id(self) -> bytes:
        # Domain-tagged so batch ids can never collide with single-request v1 action ids.
        return keccak(
            eth_abi.encode(["bytes32", self.obj_schema()], [BATCH_ACTION_DOMAIN, astuple(self)])
        )


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
        return result


# Mirror of utils.make_request with a per-source timeout. The v1 code path must stay
# byte-for-byte untouched, so the timeout lives here instead of a shared parameter.
def make_batch_request(qrr: HTTPRequest) -> Any:
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


def fetch_all(batch_requests: List[HTTPRequest]) -> List[Any]:
    # Fail-all: the first raising future propagates; the with-block still joins the rest,
    # each bounded by its own per-source timeout.
    with ThreadPoolExecutor(max_workers=len(batch_requests)) as pool:
        futures = [pool.submit(make_batch_request, r) for r in batch_requests]
        return [f.result() for f in futures]
