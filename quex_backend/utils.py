from typing import Mapping
from eth_utils import keccak
from quex_backend import cmc_api_key
from quex_backend.models import QuexRequest
import json
import eth_abi
import re

import ntplib
import jq

c = ntplib.NTPClient()


def get_timestamp() -> int:
    """
    Get current timestamp.

    # TODO fix this method, see https://github.com/quex-tech/quex-v1-signer/issues/5

    :return: current NTP timestamp
    """
    response = c.request('europe.pool.ntp.org', version=4)
    return round(response.tx_time)


def compute_feed_id(data: QuexRequest) -> bytes:
    """
    Create feed id from request parameters

    :param data: QuexRequest - data item
    :return: hash from encoded data
    """
    # TODO correct serialization here, see https://github.com/quex-tech/quex-v1-signer/issues/3
    msg_bytes = "".encode()
    return keccak(msg_bytes)


def process_json(input_json: dict, json_query: str, schema: str) -> bytes:
    """
    Execute JQ program over the input data and encode the result according to the schema provided.
    """
    # Use JQ to filter the JSON input (input_json is expected to be a dictionary)
    result = jq.compile(json_query).input(input_json).first()

    # Encode the result using the provided schema
    encoded = eth_abi.encode([schema], [result])

    return encoded


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
