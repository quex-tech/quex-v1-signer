from base64 import b64decode
from eth_abi import encode as eth_abi_encode
from eth_keys import keys
from flask import Blueprint, request

from quex_backend import account, get_quote, patch_processor
from quex_backend.models import (
    DataItem,
    OracleResponse,
    b64dict,
    PlutusHTTPActionWithProof,
    EthereumHTTPActionWithProof,
    PlutusOracleMessage,
    EthereumOracleMessage,
    RideHTTPActionWithProof,
    RideOracleMessage,
)
from quex_backend.td_quote import TDQuote
from quex_backend.utils import make_request, process_json, get_timestamp
from quex_backend.plutus.abi import encoder as plutus_abi_encoder
from quex_backend.ride.abi import encoder as ride_abi_encoder


bp = Blueprint("v1", __name__)

PLUTUS_MAGIC = b"\xd8\x79\x9f"


@bp.route("/quote")
def quote():
    sk = keys.PrivateKey(account.key)
    quote_bin = get_quote(sk.public_key.to_bytes())
    quote = TDQuote.deserialize(quote_bin)
    return b64dict(quote)


@bp.route("/address")
def address():
    return account.address


@bp.route("/pubkey")
def pubkey():
    sk = keys.PrivateKey(account.key)
    return hex(sk.public_key)


@bp.route("/query", methods=["POST"])
def query():
    action = request.get_json()["action"]
    relayer = request.get_json()["relayer"]
    fmt = request.get_json().get("format", "")

    action_bytes = b64decode(action)

    if fmt.casefold() == "ride":
        action_cls = RideHTTPActionWithProof
        msg_cls = RideOracleMessage
        encode = ride_abi_encoder.encode
    elif action_bytes[: len(PLUTUS_MAGIC)] == PLUTUS_MAGIC:
        action_cls = PlutusHTTPActionWithProof
        msg_cls = PlutusOracleMessage
        encode = plutus_abi_encoder.encode
    else:
        action_cls = EthereumHTTPActionWithProof
        msg_cls = EthereumOracleMessage
        encode = eth_abi_encode

    qr = action_cls.parse(action_bytes)
    patched_http_request = patch_processor.apply_patch(qr.action, qr.proof)
    d = make_request(patched_http_request)
    processed_response = process_json(d, qr.action.filter, qr.action.schema, encode)
    msg = msg_cls(
        data_item=DataItem(
            timestamp=get_timestamp(),
            error=0,
            value=processed_response,
        ),
        action_id=qr.action.action_id(),
        relayer=relayer,
    )
    sig = msg.sign_with_account(account)
    response = OracleResponse(msg=msg, sig=sig)
    return b64dict(response)
