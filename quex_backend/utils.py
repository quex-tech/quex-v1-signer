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


# Create feed id from params
# TODO include headers here?
def get_feed_id(url: str, params: Mapping[str, str], jq: str) -> bytes:
    params_str = ''
    for key in sorted(params):
        params_str = params_str + key + params[key]

    msg_str = url + params_str + jq
    msg = eth_abi.encode(["bytes"], [msg_str.encode()])
    return keccak(msg)

# TODO allow only whitelisted operations
def process_json(input: str, json_query: str) -> str:
    return jq.compile(json_query).input_value(input).first()
