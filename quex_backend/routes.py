from flask import Blueprint, jsonify, request
from quex_backend import account, cmc_api_key
from quex_backend.models import DataItem, FeedResponse, b64dict
from quex_backend.td_quote import TDQuote
from quex_backend.cmc_utils import *
import requests
import time
import pyquex_tdx

cmc_headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': cmc_api_key,
}

bp = Blueprint('v1', __name__)

@bp.route('/quote')
def quote():
#    with open("quote3.dat", 'rb') as f:
#        quote_bin = f.read()
    addr = bytes.fromhex(account.address[2:])
    quote_bin = pyquex_tdx.get_quote(addr.rjust(32,b'\x00'))
    quote = TDQuote.deserialize(quote_bin)
    return b64dict(quote)

@bp.route('/price')
def get_price():
    r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
    di = DataItem(
            timestamp=round(time.time()),
            value=round(float(r.json()["price"])*100),
            feed_id=b"BTCUSDT"
            )
    return b64dict(FeedResponse(data=di, signature=di.sign_with_account(account)))

@bp.route('/cmc')
def get_cmc_quotes():
    r = requests.get(cmc_url, params={'id': ','.join([str(x) for x in cmc_ids])}, headers=cmc_headers)
    d = r.json()['data']
    data_items = [DataItem(
            timestamp=cmc_str_to_timestamp(d[str(i)]['quote']['USD']['last_updated']),
            value=round(d[str(i)]['quote']['USD']['price']*1000000),
            feed_id=d[str(i)]['symbol'].encode()
            ) for i in cmc_ids]
    return [b64dict(FeedResponse(data=di, signature=di.sign_with_account(account))) for di in data_items]
