from flask import Blueprint, request

from quex_backend import account, get_quote, patch_processor
from quex_backend.models import DataItem, OracleResponse, OracleMessage, HTTPAction, b64dict
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
    action = request.get_json()['action']
    qr = HTTPAction.parse(action)
    patched_http_request = patch_processor.apply_patch(qr)
    d = make_request(patched_http_request)
    # Process response
    jq = qr.filter
    processed_response = process_json(d, jq, qr.schema)
    msg = OracleMessage(
            data_item=DataItem(
                timestamp=get_timestamp(),
                error=0,
                value=processed_response,
                ),
            action_id=qr.action_id()
            )
    sig = msg.sign_with_account(account)
    response = OracleResponse(msg=msg, sig=sig)

    return b64dict(response)
