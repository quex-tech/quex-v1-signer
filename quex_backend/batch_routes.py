from base64 import b64decode
from typing import Any

from flask import Blueprint, request
from werkzeug.exceptions import BadRequest

from quex_backend import account, patch_processor
from quex_backend.batch import (
    BatchActionValidationError,
    EthereumBatchHTTPActionWithProof,
    apply_batch_patches,
    fetch_all,
    process_json_list,
)
from quex_backend.encryption import EncryptedPatchProcessingError
from quex_backend.models import (
    DataItem,
    EthereumOracleMessage,
    OracleResponse,
    QuexErrorCodes,
    b64dict,
)
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
)

bp = Blueprint("v1_batch", __name__)


# EVM-only batch endpoint. Any single source failure fails the whole action (fail-all):
# the signed DataItem carries the error code and an empty value.
@bp.route("/query_batch", methods=["POST"])
def query_batch() -> dict[str, Any]:
    payload = request.get_json()
    action_bytes = b64decode(payload["action"])
    relayer = payload["relayer"]

    qr = EthereumBatchHTTPActionWithProof.parse(action_bytes)
    try:
        qr.action.validate()
    except BatchActionValidationError as exc:
        # A malformed action must not yield a signed message binding its id.
        raise BadRequest(str(exc)) from exc

    def create_response(status_code: QuexErrorCodes, response: bytes = b"") -> dict[str, Any]:
        msg = EthereumOracleMessage(
            data_item=DataItem(
                timestamp=get_timestamp(),
                error=status_code.value,
                value=response,
            ),
            action_id=qr.action.action_id(),
            relayer=relayer,
        )
        sig = msg.sign_with_account(account)
        return b64dict(OracleResponse(msg=msg, sig=sig))

    try:
        patched_requests = apply_batch_patches(patch_processor, qr.action, qr.proof)
        results = fetch_all(patched_requests)
        processed_response = process_json_list(results, qr.action.filter, qr.action.schema)
        return create_response(QuexErrorCodes.SUCCESS, processed_response)
    except EncryptedPatchProcessingError:
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
    except RequestProcessingError as exc:
        return create_response(QuexErrorCodes.INTERNAL_REQUEST_PROCESSING_ERROR, str(exc).encode())
    except Exception as exc:
        return create_response(QuexErrorCodes.INTERNAL_OTHER_ERROR, str(exc).encode())
