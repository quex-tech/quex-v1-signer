import dataclasses
from base64 import b64encode
from dataclasses import dataclass, astuple, fields
from enum import IntEnum
from typing import List
from urllib.parse import urljoin
from abc import ABC, abstractmethod

import eth_abi
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak

from quex_backend.plutus.cbor import PlutusByteString, PlutusRawData, PlutusTuple
from quex_backend.plutus.mixins import PlutusEncodable, PlutusDecodable
from quex_backend.ride.mixins import RideDecodable, RideEncodable, write_ride_bytes


def b64dict(obj):
    return dataclasses.asdict(
        obj,
        dict_factory=lambda fields: {
            key: (b64encode(value).decode() if type(value) == bytes else value)
            for (key, value) in fields
        },
    )


def from_nested_tuple(t, class_constructor):
    if "_name" in dir(class_constructor) and class_constructor._name == "List":
        return [from_nested_tuple(x, class_constructor.__args__[0]) for x in t]
    elif type(t) == tuple:
        return class_constructor(
            *(
                from_nested_tuple(x, y.type)
                for x, y in zip(t, fields(class_constructor))
            )
        )
    else:
        return class_constructor(t)


#######################################
# Data structures for making requests #
#######################################


# Define the parent abstract class
class ABIEncodable(ABC):
    @staticmethod
    @abstractmethod
    def obj_schema() -> str:
        """
        Abstract static method for returning the schema as a string.
        Must be implemented by subclasses.
        """
        pass

    def bytes(self) -> bytes:
        """
        Default method to encode the object as bytes using the eth_abi library.
        It uses the obj_schema() method and encodes the result of astuple(self).
        """
        return eth_abi.encode([self.obj_schema()], [astuple(self)])  # type: ignore[call-overload]  # always used with @dataclass


class RequestMethod(IntEnum):
    GET = 0
    POST = 1
    PUT = 2
    PATCH = 3
    DELETE = 4
    OPTIONS = 5
    TRACE = 6

    def string_value(self) -> str:
        return self.name


# RequestHeader structure
@dataclass
class RequestHeader(
    ABIEncodable, PlutusEncodable, PlutusDecodable, RideEncodable, RideDecodable
):
    key: str
    value: str

    @staticmethod
    def obj_schema() -> str:
        return "(string,string)"


# QueryParameter structure
@dataclass
class QueryParameter(
    ABIEncodable, PlutusEncodable, PlutusDecodable, RideEncodable, RideDecodable
):
    key: str
    value: str

    @staticmethod
    def obj_schema() -> str:
        return "(string,string)"


# QueryParameterPatch structure (encrypted value in base64)
@dataclass
class QueryParameterPatch(
    ABIEncodable, PlutusEncodable, PlutusDecodable, RideEncodable, RideDecodable
):
    key: str
    ciphertext: bytes  # Encrypted value

    @staticmethod
    def obj_schema() -> str:
        return "(string,bytes)"


# RequestHeaderPatch structure (encrypted value in base64)
@dataclass
class RequestHeaderPatch(
    ABIEncodable, PlutusEncodable, PlutusDecodable, RideEncodable, RideDecodable
):
    key: str
    ciphertext: bytes  # Encrypted value

    @staticmethod
    def obj_schema() -> str:
        return "(string,bytes)"


# HTTPPrivatePatch structure
@dataclass
class HTTPPrivatePatch(
    ABIEncodable, PlutusEncodable, PlutusDecodable, RideEncodable, RideDecodable
):
    path_suffix: bytes
    headers: List[RequestHeaderPatch]
    parameters: List[QueryParameterPatch]
    body: bytes
    td_address: str

    @staticmethod
    def obj_schema() -> str:
        return f"(bytes,{RequestHeaderPatch.obj_schema()}[],{QueryParameterPatch.obj_schema()}[],bytes,address)"


# HTTPRequest structure
@dataclass
class HTTPRequest(
    ABIEncodable, PlutusEncodable, PlutusDecodable, RideEncodable, RideDecodable
):
    method: RequestMethod
    host: str
    path: str
    headers: List[RequestHeader]
    parameters: List[QueryParameter]
    body: bytes

    @staticmethod
    def obj_schema() -> str:
        return f"(uint8,string,string,{RequestHeader.obj_schema()}[],{QueryParameter.obj_schema()}[],bytes)"

    def build_url(self) -> str:
        # Ensure that the host starts with the correct protocol
        protocol = "https://"
        host = f"{protocol}{self.host}"

        # Use urljoin to properly concatenate host and path
        return urljoin(host, self.path)

    def get_parameters(self):
        params = {}
        for p in self.parameters:
            params[p.key] = p.value
        return params

    def get_headers(self):
        headers = {}
        for p in self.headers:
            headers[p.key] = p.value
        return headers

    def get_body(self):
        return self.body


# QuexRequest structure
@dataclass
class HTTPAction(ABC):
    request: HTTPRequest
    patch: HTTPPrivatePatch
    schema: str  # ResultSchema as a string for now
    filter: str  # JqFilter as a string for now

    @abstractmethod
    def action_id(self) -> bytes: ...


# RequestActionWithProof structure
class EthereumHTTPAction(HTTPAction, ABIEncodable):
    @staticmethod
    def obj_schema() -> str:
        return f"({HTTPRequest.obj_schema()},{HTTPPrivatePatch.obj_schema()},string,string)"

    def action_id(self) -> bytes:
        return keccak(self.bytes())


@dataclass
class EthereumHTTPActionWithProof(ABIEncodable):
    action: EthereumHTTPAction
    proof: bytes

    @staticmethod
    def parse(data: bytes):
        (data_tuple,) = eth_abi.decode([EthereumHTTPActionWithProof.obj_schema()], data)
        return from_nested_tuple(data_tuple, EthereumHTTPActionWithProof)

    @staticmethod
    def obj_schema() -> str:
        return f"({EthereumHTTPAction.obj_schema()},bytes)"


class PlutusHTTPAction(HTTPAction, PlutusEncodable, PlutusDecodable):
    def action_id(self) -> bytes:
        return keccak(self.to_plutus_bytes())


@dataclass
class PlutusHTTPActionWithProof(PlutusDecodable):
    action: PlutusHTTPAction
    proof: bytes

    @classmethod
    def parse(cls, data: bytes):
        return cls.from_plutus_bytes(data)


@dataclass
class RideHTTPAction(HTTPAction, RideEncodable, RideDecodable):
    def action_id(self) -> bytes:
        return keccak(self.to_ride_bytes())


@dataclass
class RideHTTPActionWithProof(RideDecodable):
    action: RideHTTPAction
    proof: bytes

    @classmethod
    def parse(cls, data: bytes):
        return cls.from_ride_bytes(data)


#######################################
# Data structures to provide response #
#######################################


@dataclass
class QuexErrorCodes(IntEnum):
    SUCCESS = 0
    PATCH_PROCESSING_ERROR = 1
    REQUEST_CONNECTION_ERROR = 2
    RESPONSE_NOT_SUPPORTED_RESPONSE_CODE_ERROR = 3
    RESPONSE_4XX_ERROR = 4
    RESPONSE_5XX_ERROR = 5
    RESPONSE_NOT_JSON_ERROR = 6
    JQ_PROCESSING_ERROR = 7
    ABI_ENCODING_ERROR = 8
    INTERNAL_OTHER_ERROR = 100
    INTERNAL_REQUEST_PROCESSING_ERROR = 101
    INTERNAL_GET_TIMESTAMP_ERROR = 102

@dataclass
class ETHSignature:
    r: bytes
    s: bytes
    v: int

    def fromETH(sig):
        return ETHSignature(
            r=sig.r.to_bytes(32, "big"), s=sig.s.to_bytes(32, "big"), v=sig.v
        )


@dataclass
class DataItem(PlutusEncodable, RideEncodable):
    timestamp: int
    error: int
    value: bytes

    @staticmethod
    def obj_schema() -> str:
        return "(uint256,uint256,bytes)"

    def to_plutus(self):
        return PlutusTuple([self.timestamp, self.error, PlutusRawData(self.value)])


@dataclass
class OracleMessage:
    action_id: bytes
    data_item: DataItem
    relayer: str


class EthereumOracleMessage(OracleMessage, ABIEncodable):
    @staticmethod
    def obj_schema() -> str:
        return f"(bytes32,{DataItem.obj_schema()},address)"

    def sign_with_account(self, account: Account):
        msg = self.bytes()
        msghash = encode_defunct(keccak(msg))
        return ETHSignature.fromETH(account.sign_message(msghash))


class PlutusOracleMessage(OracleMessage, PlutusEncodable):
    def sign_with_account(self, account: Account):
        msg = self.to_plutus_bytes()
        msghash = keccak(msg)
        return ETHSignature.fromETH(account.unsafe_sign_hash(msghash))

    def to_plutus(self):
        return PlutusTuple(
            [
                PlutusByteString(self.action_id),
                self.data_item.to_plutus(),
                PlutusByteString(bytes.fromhex(self.relayer.removeprefix("0x"))),
            ]
        )


class RideOracleMessage(OracleMessage, RideEncodable):
    def sign_with_account(self, account: Account):
        msg = self.to_ride_bytes()
        msghash = keccak(msg)
        return ETHSignature.fromETH(account.unsafe_sign_hash(msghash))

    def write_ride_bytes(self, buf):
        write_ride_bytes(self.action_id, buf)
        write_ride_bytes(bytes.fromhex(self.relayer.removeprefix("0x")), buf)
        write_ride_bytes(self.data_item, buf)


@dataclass
class OracleResponse:
    msg: OracleMessage
    sig: ETHSignature
