from flask import Blueprint, request
from quex_backend import account, cmc_api_key, get_quote
from quex_backend.models import IntDataItem, FeedResponse, b64dict
from quex_backend.td_quote import TDQuote
from quex_backend.utils import *
import requests
import json

cmc_headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': cmc_api_key,
}

bp = Blueprint('v1', __name__)


@bp.route('/quote')
def quote():
    addr = bytes.fromhex(account.address[2:])
    quote_bin = get_quote(addr.rjust(32, b'\x00'))
    quote = TDQuote.deserialize(quote_bin)
    return b64dict(quote)


@bp.route('/data/int')
def int_data_point():
    method = "get"
    url = request.args.get('url')
    jq = request.args.get('jq')

    print("\n Got request with url:" + url + " and jq:" + jq)

    # TODO extract headers from env
    headers: Mapping[str, str] = cmc_headers

    r = requests.request(method, url, headers=headers)
    d = r.json()
    print("\nGot response:" + json.dumps(d))

    int_data = int(process_json(d, jq))
    print("Computed result: " + str(int_data))

    di = IntDataItem(
        timestamp=get_timestamp(),
        value=int_data,
        feed_id=compute_feed_id(method, url, jq)
    )
    sign = di.sign_with_account(account)
    return b64dict(FeedResponse(data=di, signature=sign))
