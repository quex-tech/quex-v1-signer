from base64 import b64decode

from eth_abi import encode as eth_abi_encode
from eth_keys import keys
from flask import Blueprint, request

from quex_backend import account, get_quote, patch_processor
from quex_backend.encryption import EncryptedPatchProcessingError
from quex_backend.models import (
    DataItem,
    EthereumHTTPActionWithProof,
    EthereumOracleMessage,
    OracleResponse,
    PlutusHTTPActionWithProof,
    PlutusOracleMessage,
    QuexErrorCodes,
    b64dict,
)
from quex_backend.plutus.abi import encoder as plutus_abi_encoder
from quex_backend.td_quote import TDQuote
from quex_backend.utils import (
    ABIEncodingError,
    GetTimestampError,
    JQProcessingError,
    RequestConnectionError,
    RequestProcessingError,
    Response4XXError,
    Response5XXError,
    ResponseNotJSONError,
    ResponseNotSupportedResponseCodeError,
    get_timestamp,
    make_request,
    process_json,
)


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
    def create_response(msg_cls, action_id: bytes, relayer: str, status_code: QuexErrorCodes, response: bytes = b""):
        msg = msg_cls(
            data_item=DataItem(
                timestamp=get_timestamp(),
                error=status_code.value,
                value=response,
            ),
            action_id=action_id,
            relayer=relayer,
        )
        sig = msg.sign_with_account(account)
        response_obj = OracleResponse(msg=msg, sig=sig)
        return b64dict(response_obj)

    action = request.get_json()["action"]
    relayer = request.get_json()["relayer"]
    action_bytes = b64decode(action)

    if action_bytes[: len(PLUTUS_MAGIC)] == PLUTUS_MAGIC:
        action_cls = PlutusHTTPActionWithProof
        msg_cls = PlutusOracleMessage
        encode = plutus_abi_encoder.encode
    else:
        action_cls = EthereumHTTPActionWithProof
        msg_cls = EthereumOracleMessage
        encode = eth_abi_encode

    qr = action_cls.parse(action_bytes)

    try:
        patched_http_request = patch_processor.apply_patch(qr.action, qr.proof)
        response_json = make_request(patched_http_request)
        processed_response = process_json(response_json, qr.action.filter, qr.action.schema, encode)
        return create_response(msg_cls, qr.action.action_id(), relayer, QuexErrorCodes.SUCCESS, processed_response)
    except EncryptedPatchProcessingError:
        return create_response(msg_cls, qr.action.action_id(), relayer, QuexErrorCodes.PATCH_PROCESSING_ERROR)
    except RequestConnectionError:
        return create_response(msg_cls, qr.action.action_id(), relayer, QuexErrorCodes.REQUEST_CONNECTION_ERROR)
    except ResponseNotSupportedResponseCodeError:
        return create_response(msg_cls, qr.action.action_id(), relayer, QuexErrorCodes.RESPONSE_NOT_SUPPORTED_RESPONSE_CODE_ERROR)
    except Response4XXError:
        return create_response(msg_cls, qr.action.action_id(), relayer, QuexErrorCodes.RESPONSE_4XX_ERROR)
    except Response5XXError:
        return create_response(msg_cls, qr.action.action_id(), relayer, QuexErrorCodes.RESPONSE_5XX_ERROR)
    except ResponseNotJSONError:
        return create_response(msg_cls, qr.action.action_id(), relayer, QuexErrorCodes.RESPONSE_NOT_JSON_ERROR)
    except JQProcessingError:
        return create_response(msg_cls, qr.action.action_id(), relayer, QuexErrorCodes.JQ_PROCESSING_ERROR)
    except ABIEncodingError:
        return create_response(msg_cls, qr.action.action_id(), relayer, QuexErrorCodes.ABI_ENCODING_ERROR)
    except GetTimestampError:
        return create_response(msg_cls, qr.action.action_id(), relayer, QuexErrorCodes.INTERNAL_GET_TIMESTAMP_ERROR)
    except RequestProcessingError as exc:
        return create_response(
            msg_cls,
            qr.action.action_id(),
            relayer,
            QuexErrorCodes.INTERNAL_REQUEST_PROCESSING_ERROR,
            str(exc).encode(),
        )
    except Exception as exc:
        return create_response(
            msg_cls,
            qr.action.action_id(),
            relayer,
            QuexErrorCodes.INTERNAL_OTHER_ERROR,
            str(exc).encode(),
        )
