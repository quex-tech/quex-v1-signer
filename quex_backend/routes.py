from eth_keys import keys
from flask import Blueprint, request

from quex_backend import account, get_quote, patch_processor
from quex_backend.models import DataItem, OracleResponse, OracleMessage, HTTPActionWithProof, QuexErrorCodes, b64dict
from quex_backend.td_quote import TDQuote
from quex_backend.utils import (
    make_request, process_json, get_timestamp, 
    RequestProcessingError, RequestConnectionError, Response4XXError, Response5XXError, ResponseNotJSONError, 
    JQProcessingError, ABIEncodingError, GetTimestampError,
    ResponseNotSupportedResponseCodeError,
    )
from quex_backend.encryption import EncryptedPatchProcessingError

bp = Blueprint('v1', __name__)


@bp.route('/quote')
def quote():
    sk = keys.PrivateKey(account.key)
    quote_bin = get_quote(sk.public_key.to_bytes())
    quote = TDQuote.deserialize(quote_bin)
    return b64dict(quote)


@bp.route('/address')
def address():
    return account.address


@bp.route('/pubkey')
def pubkey():
    sk = keys.PrivateKey(account.key)
    return hex(sk.public_key)


@bp.route('/query', methods=['POST'])
def query():
    def create_response(status_code: QuexErrorCodes, response: bytes = b''):
        msg = OracleMessage(
            data_item=DataItem(
                timestamp=get_timestamp(),
                error=status_code.value,
                value=response
                ),
            action_id=qr.action.action_id(),
            relayer=relayer
            )
        sig = msg.sign_with_account(account)
        response = OracleResponse(msg=msg, sig=sig)

        return b64dict(response)
    
    action = request.get_json()['action']
    relayer = request.get_json()['relayer']
    try:
        qr = HTTPActionWithProof.parse(action)
        patched_http_request = patch_processor.apply_patch(qr.action, qr.proof)
        d = make_request(patched_http_request)
        jq = qr.action.filter
        processed_response = process_json(d, jq, qr.action.schema)
        return create_response(QuexErrorCodes.SUCCESS, processed_response)
    except EncryptedPatchProcessingError as e:
        return create_response(QuexErrorCodes.PATCH_PROCESSING_ERROR)
    except RequestConnectionError:
        return create_response(QuexErrorCodes.REQUEST_CONNECTION_ERROR)
    except ResponseNotSupportedResponseCodeError:
        return create_response(QuexErrorCodes.RESPONSE_NOT_SUPPORTED_RESPONSE_CODE_ERROR)
    except Response4XXError:
        return create_response(QuexErrorCodes.RESPONSE_4XX_ERROR)
    except Response5XXError:
        return create_response(QuexErrorCodes.RESPONSE_5XX_ERROR)
    except ResponseNotJSONError:
        return create_response(QuexErrorCodes.RESPONSE_NOT_JSON_ERROR)
    except JQProcessingError:
        return create_response(QuexErrorCodes.JQ_PROCESSING_ERROR)
    except ABIEncodingError:
        return create_response(QuexErrorCodes.ABI_ENCODING_ERROR)
    except GetTimestampError:
        return create_response(QuexErrorCodes.INTERNAL_GET_TIMESTAMP_ERROR)
    except RequestProcessingError as e:
        return create_response(QuexErrorCodes.INTERNAL_REQUEST_PROCESSING_ERROR, str(e).encode())
    except Exception as e:
        return create_response(QuexErrorCodes.INTERNAL_OTHER_ERROR, str(e).encode())
