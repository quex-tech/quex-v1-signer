import base64
import dataclasses
import json
from base64 import b64encode
from dataclasses import dataclass, astuple
from enum import Enum
from typing import List
from urllib.parse import urljoin
from abc import ABC, abstractmethod

import eth_abi
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import keccak


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
        return eth_abi.encode([self.obj_schema()], [astuple(self)])


# Enum for RequestMethod
@dataclass
class RequestMethod(ABIEncodable):
    value: int

    @staticmethod
    def parse(method_str: str):
        match method_str.upper():
            case "GET":
                return RequestMethod(0)
            case "POST":
                return RequestMethod(1)
            case "PUT":
                return RequestMethod(2)
            case "PATCH":
                return RequestMethod(3)
            case "DELETE":
                return RequestMethod(4)
            case "OPTIONS":
                return RequestMethod(5)
            case "TRACE":
                return RequestMethod(6)
            case _:
                raise Exception("Unknown method")

    @staticmethod
    def obj_schema() -> str:
        return f'(uint8)'


# RequestHeader structure
@dataclass
class RequestHeader(ABIEncodable):
    key: str
    value: str

    @staticmethod
    def parse(data: dict):
        return RequestHeader(**data)

    @staticmethod
    def obj_schema() -> str:
        return f'(string,string)'


# QueryParameter structure
@dataclass
class QueryParameter(ABIEncodable):
    key: str
    value: str

    @staticmethod
    def parse(data: dict):
        return QueryParameter(**data)

    @staticmethod
    def obj_schema() -> str:
        return f'(string,string)'


# QueryParameterPatch structure (encrypted value in base64)
@dataclass
class QueryParameterPatch(ABIEncodable):
    key: str
    ciphertext: bytes  # Encrypted value

    @staticmethod
    def parse(data: dict):
        return QueryParameterPatch(
            key=data['key'],
            ciphertext=base64.b64decode(data['ciphertext'])  # Decode base64 string to bytes
        )

    @staticmethod
    def obj_schema() -> str:
        return "(string,bytes)"


# RequestHeaderPatch structure (encrypted value in base64)
@dataclass
class RequestHeaderPatch(ABIEncodable):
    key: str
    ciphertext: bytes  # Encrypted value

    @staticmethod
    def parse(data: dict):
        return RequestHeaderPatch(
            key=data['key'],
            ciphertext=base64.b64decode(data['ciphertext'])  # Decode base64 string to bytes
        )

    @staticmethod
    def obj_schema() -> str:
        return "(string,bytes)"


# HTTPPrivatePatch structure
@dataclass
class HTTPPrivatePatch(ABIEncodable):
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

    @staticmethod
    def obj_schema() -> str:
        return f"(bytes,{RequestHeaderPatch.obj_schema()}[],{QueryParameterPatch.obj_schema()}[],bytes,uint256)"


# HTTPRequest structure
@dataclass
class HTTPRequest(ABIEncodable):
    method: RequestMethod
    host: str
    path: str
    headers: List[RequestHeader]
    parameters: List[QueryParameter]
    body: bytes

    @staticmethod
    def obj_schema() -> str:
        return f'({RequestMethod.obj_schema()},string,string,{RequestHeader.obj_schema()}[],{QueryParameter.obj_schema()}[],bytes)'

    @staticmethod
    def parse(data: dict):
        method = RequestMethod.parse(data['method'])
        headers = [RequestHeader.parse(h) for h in data['headers']]
        parameters = [QueryParameter.parse(p) for p in data['parameters']]

        # Decode the base64-encoded JSON body if it exists
        body = base64.b64decode(data['body'])

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
class QuexRequest(ABIEncodable):
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

    @staticmethod
    def obj_schema() -> str:
        return f"({HTTPRequest.obj_schema()},{HTTPPrivatePatch.obj_schema()},string,string)"

    def feed_id(self) -> bytes:
        return keccak(self.bytes())



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
