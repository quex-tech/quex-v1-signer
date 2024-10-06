from typing import Mapping
from eth_utils import keccak
from quex_backend import cmc_api_key
import json

import ntplib
import jq

c = ntplib.NTPClient()


def get_timestamp() -> int:
    """
    Get current timestamp.

    # TODO do not rely on single server
    # TODO handle errors

    :return: current NTP timestamp
    """
    response = c.request('europe.pool.ntp.org', version=4)
    return round(response.tx_time)


def compute_feed_id(data: Mapping[str, str]) -> bytes:
    """
    Create feed id from request parameters

    :param data: dictionary with the request params
    :return: hash from encoded data
    """
    msg_bytes = json.dumps(data, sort_keys=True).encode()
    return keccak(msg_bytes)


def process_json(input: str, json_query: str) -> str:
    """
    Execute JQ program over the input data

    :param input:
    :param json_query:
    :return:
    """
    return jq.compile(json_query).input_value(input).first()


def get_headers(url: str) -> Mapping[str, str]:
    """
    Get headers based on current url
    TODO implement generic logic, allowing set up and extract headers to any web sources

    :param url:
    :return:
    """
    if url.startswith("https://pro-api.coinmarketcap.com"):
        return {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': cmc_api_key,
        }
    else:
        return {
            'X-CMC_PRO_API_KEY': cmc_api_key,
        }
