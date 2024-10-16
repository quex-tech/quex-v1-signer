from dataclasses import dataclass
import dataclasses
from base64 import b64encode
from eth_utils import keccak
from eth_account.messages import encode_defunct
from eth_account import Account
import eth_abi

@dataclass
class ETHSignature:
    r: bytes
    s: bytes
    v: int
    def fromETH(sig):
        return ETHSignature(
                r=sig.r.to_bytes(32,'big'),
                s=sig.s.to_bytes(32,'big'),
                v=sig.v
                )

@dataclass
class IntDataItem:
    timestamp: int
    value: int
    feed_id: bytes
    def sign_with_account(self, account: Account):
        msg = eth_abi.encode(["uint256", "uint256", "bytes32"], [self.value,self.timestamp,self.feed_id])
        msghash = encode_defunct(keccak(msg))
        return ETHSignature.fromETH(account.sign_message(msghash))

# TODO: handle errors?
@dataclass
class FeedResponse:
    data: IntDataItem
    signature: ETHSignature

def b64dict(obj):
    return dataclasses.asdict(obj,
                       dict_factory=lambda fields: {
                           key: (b64encode(value).decode() if type(value) == bytes else value)
                           for (key, value) in fields
                           }
                       )
