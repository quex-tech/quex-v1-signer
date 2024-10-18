import base64
from dataclasses import dataclass
import dataclasses
from base64 import b64encode
from eth_utils import keccak
from eth_account.messages import encode_defunct
from eth_account import Account
import eth_abi
from enum import Enum
from typing import List, Optional
import json
from urllib.parse import urljoin


def b64dict(obj):
    return dataclasses.asdict(obj,
                              dict_factory=lambda fields: {
                                  key: (b64encode(value).decode() if type(value) == bytes else value)
                                  for (key, value) in fields
                              }
                              )


#######################################
# Data structures for making requests #
#######################################

# Enum for RequestMethod
class RequestMethod(Enum):
    GET = "Get"
    POST = "Post"
    PUT = "Put"
    PATCH = "Patch"
    DELETE = "Delete"
    OPTIONS = "Options"
    TRACE = "Trace"

    @staticmethod
    def parse(method_str: str):
        return RequestMethod[method_str.upper()]


# RequestHeader structure
@dataclass
class RequestHeader:
    key: str
    value: str

    @staticmethod
    def parse(data: dict):
        return RequestHeader(**data)


# QueryParameter structure
@dataclass
class QueryParameter:
    key: str
    value: str

    @staticmethod
    def parse(data: dict):
        return QueryParameter(**data)


# QueryParameterPatch structure (encrypted value in base64)
@dataclass
class QueryParameterPatch:
    key: str
    ciphertext: bytes  # Encrypted value

    @staticmethod
    def parse(data: dict):
        return QueryParameterPatch(
            key=data['key'],
            ciphertext=base64.b64decode(data['ciphertext'])  # Decode base64 string to bytes
        )


# RequestHeaderPatch structure (encrypted value in base64)
@dataclass
class RequestHeaderPatch:
    key: str
    ciphertext: bytes  # Encrypted value

    @staticmethod
    def parse(data: dict):
        return RequestHeaderPatch(
            key=data['key'],
            ciphertext=base64.b64decode(data['ciphertext'])  # Decode base64 string to bytes
        )


# HTTPPrivatePatch structure
@dataclass
class HTTPPrivatePatch:
    path_suffix: bytes
    headers: List[RequestHeaderPatch]
    parameters: List[QueryParameterPatch]
    body: bytes
    td_id: int  # Identifier to tell which TD can decrypt the patch

    @staticmethod
    def parse(data: dict):
        headers = [RequestHeaderPatch.parse(h) for h in data['headers']]
        parameters = [QueryParameterPatch.parse(p) for p in data['parameters']]
        return HTTPPrivatePatch(
            path_suffix=base64.b64decode(data['path_suffix']),  # Decode base64
            headers=headers,
            parameters=parameters,
            body=base64.b64decode(data['body']),  # Decode base64
            td_id=data['td_id']
        )


# HTTPRequest structure
@dataclass
class HTTPRequest:
    method: RequestMethod
    host: str
    path: str
    headers: List[RequestHeader]
    parameters: List[QueryParameter]
    body: dict  # JSON-decoded body, stored as a dictionary.

    @staticmethod
    def parse(data: dict):
        method = RequestMethod.parse(data['method'])
        headers = [RequestHeader.parse(h) for h in data['headers']]
        parameters = [QueryParameter.parse(p) for p in data['parameters']]

        # Decode the base64-encoded JSON body if it exists
        body = {}
        if data.get('body'):  # Checking if 'body' exists and is not empty
            body_json = base64.b64decode(data['body']).decode('utf-8')
            body = json.loads(body_json)

        return HTTPRequest(
            method=method,
            host=data['host'],
            path=data['path'],
            headers=headers,
            parameters=parameters,
            body=body  # Store the unpacked JSON as a dictionary
        )

    def build_url(self) -> str:
        # Ensure that the host starts with the correct protocol
        protocol = "https://"
        host = f"{protocol}{self.host}"

        # Use urljoin to properly concatenate host and path
        return urljoin(host, self.path)


# QuexRequest structure
@dataclass
class QuexRequest:
    request: HTTPRequest
    patch: HTTPPrivatePatch
    schema: str  # ResultSchema as a string for now
    filter: str  # JqFilter as a string for now

    @staticmethod
    def parse(data: dict):
        request = HTTPRequest.parse(data['request'])
        patch = HTTPPrivatePatch.parse(data['patch'])
        return QuexRequest(
            request=request,
            patch=patch,
            schema=data['schema'],
            filter=data['filter']
        )


#######################################
# Data structures to provide response #
#######################################

@dataclass
class ETHSignature:
    r: bytes
    s: bytes
    v: int

    def fromETH(sig):
        return ETHSignature(
            r=sig.r.to_bytes(32, 'big'),
            s=sig.s.to_bytes(32, 'big'),
            v=sig.v
        )


@dataclass
class DataItem:
    timestamp: int
    feed_id: bytes
    value: bytes

    def to_bytes(self) -> bytes:
        return eth_abi.encode(["uint256", "bytes32", "bytes"], [self.timestamp, self.feed_id, self.value])

    def sign_with_account(self, account: Account):
        msg = self.to_bytes()
        msghash = encode_defunct(keccak(msg))
        return ETHSignature.fromETH(account.sign_message(msghash))


@dataclass
class QuexResponse:
    data: DataItem
    signature: ETHSignature
