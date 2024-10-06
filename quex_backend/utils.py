from typing import Mapping
from eth_utils import keccak

import ntplib
import eth_abi
import jq

c = ntplib.NTPClient()


# TODO do not rely on single server
# TODO ensure timestamp increase only
# TODO handle errors
def get_timestamp() -> int:
    response = c.request('europe.pool.ntp.org', version=3)
    return round(response.tx_time)


# Create feed id from request parameters
def compute_feed_id(data: Mapping[str, str]) -> bytes:
    msg_bytes = str(data).encode()
    return keccak(msg_bytes)


# TODO allow only whitelisted operations
def process_json(input: str, json_query: str) -> str:
    return jq.compile(json_query).input_value(input).first()
