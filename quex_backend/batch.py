from dataclasses import astuple, dataclass
from typing import List

import eth_abi
from eth_utils import keccak

from quex_backend.models import (
    ABIEncodable,
    HTTPPrivatePatch,
    HTTPRequest,
    from_nested_tuple,
)

BATCH_ACTION_DOMAIN = keccak(text="quex.action.batchRequest.v1")


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
