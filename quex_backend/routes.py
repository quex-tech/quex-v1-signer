from flask import Blueprint, request
from quex_backend import account, cmc_api_key, get_quote
from quex_backend.models import *
from quex_backend.td_quote import TDQuote
from quex_backend.utils import *
import requests
import json

bp = Blueprint('v1', __name__)


@bp.route('/quote')
def quote():
    addr = bytes.fromhex(account.address[2:])
    quote_bin = get_quote(addr.rjust(32, b'\x00'))
    quote = TDQuote.deserialize(quote_bin)
    return b64dict(quote)


@bp.route('/query', methods=['POST'])
def query():
    data = request.get_json()
    print("\n Got request with data:" + str(data))
    qr = QuexRequest.parse(data)
    qrr = qr.request
    url = qrr.build_url()
    r = requests.request(qrr.method.value, url, params=qrr.parameters, headers=qrr.headers, data=qrr.body)
    d = r.json()
    print("\nGot response:" + json.dumps(d))

    return "ok"


# todo remove
@bp.route('/data/int', methods=['POST'])
def int_data_point():
    """Get json with the HTTPS request parameters and return processed and signed result

        Json parameters:
        method : str
            method for the Request: ``GET``, ``OPTIONS``, ``HEAD``, ``POST``, ``PUT``, ``PATCH``, or ``DELETE``.
        url: str
            URL you're willing to certify
            Note: we assume here, that URL is coming from trusted source, e.g. it was already filtered outside of this program
        params: str
            Dictionary to send in the query string
        jq: str
            JQ program to be executed on top of the response json
            Note: we assume here, that jq query is coming from trusted source, e.g. it was already filtered outside of this program

        TODO catch errors and handle them in response

        """
    data = request.get_json()
    print("\n Got request with data:" + str(data))

    method = data['method']
    url = data['url']
    params = data['params']
    jq = data['jq']
    headers: Mapping[str, str] = get_headers(url)

    r = requests.request(method, url, params=params, headers=headers)
    d = r.json()
    print("\nGot response:" + json.dumps(d))

    int_data = int(process_json(d, jq))
    print("Computed result: " + str(int_data))

    di = IntDataItem(
        timestamp=get_timestamp(),
        value=int_data,
        feed_id=compute_feed_id(data)
    )
    sign = di.sign_with_account(account)
    return b64dict(FeedResponse(data=di, signature=sign))
