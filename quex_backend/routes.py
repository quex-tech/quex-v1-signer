from flask import Blueprint, request

from quex_backend import account, get_quote, patch_processor
from quex_backend.models import QuexRequest, DataItem, QuexResponse, b64dict
from quex_backend.td_quote import TDQuote
from eth_keys import keys
from quex_backend.utils import make_request, process_json, get_timestamp

bp = Blueprint('v1', __name__)


@bp.route('/quote')
def quote():
    sk = keys.PrivateKey(account.key)
    quote_bin = get_quote(sk.public_key.to_bytes())
    quote = TDQuote.deserialize(quote_bin)
    return b64dict(quote)


@bp.route('/query', methods=['POST'])
def query():
    data = request.get_json()
    print("\n Got request with data:" + str(data))
    qr = QuexRequest.parse(data)
    patched_http_request = patch_processor.apply_patch(qr)
    d = make_request(patched_http_request)

    # Process response
    jq = qr.filter
    processed_response = process_json(d, jq, qr.schema)
    feed_id = qr.feed_id()
    di = DataItem(
        timestamp=get_timestamp(),
        value=processed_response,
        feed_id=feed_id
    )
    sign = di.sign_with_account(account)
    response = QuexResponse(data=di, signature=sign)

    return b64dict(response)
