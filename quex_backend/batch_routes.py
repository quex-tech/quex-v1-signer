import re
from base64 import b64decode
from typing import Any

from eth_abi.exceptions import DecodingError
from flask import Blueprint, request
from werkzeug.exceptions import BadRequest, ServiceUnavailable

from quex_backend import account, patch_processor
from quex_backend.batch import (
    BatchActionValidationError,
    EthereumBatchHTTPActionWithProof,
    apply_batch_patches,
    fetch_all_sources,
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
    # A malformed request must not yield a signed message binding its action id, so the
    # whole decode boundary maps to an unsigned 400.
    try:
        payload = request.get_json()
        action_bytes = b64decode(payload["action"])
        relayer = payload["relayer"]
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", relayer):
            raise BadRequest("relayer must be a 0x-prefixed 20-byte hex address")
        qr = EthereumBatchHTTPActionWithProof.parse(action_bytes)
    except BadRequest:
        raise
    except (KeyError, TypeError, ValueError, DecodingError, BatchActionValidationError) as exc:
        raise BadRequest(str(exc)) from exc

    def execute_action() -> tuple[QuexErrorCodes, bytes]:
        try:
            patched_requests = apply_batch_patches(patch_processor, qr.action, qr.proof)
            results = fetch_all_sources(patched_requests)
            processed_response = process_json_list(results, qr.action.filter, qr.action.schema)
            return QuexErrorCodes.SUCCESS, processed_response
        except EncryptedPatchProcessingError:
            return QuexErrorCodes.PATCH_PROCESSING_ERROR, b""
        except RequestConnectionError:
            return QuexErrorCodes.REQUEST_CONNECTION_ERROR, b""
        except ResponseNotSupportedResponseCodeError:
            return QuexErrorCodes.RESPONSE_NOT_SUPPORTED_RESPONSE_CODE_ERROR, b""
        except Response4XXError:
            return QuexErrorCodes.RESPONSE_4XX_ERROR, b""
        except Response5XXError:
            return QuexErrorCodes.RESPONSE_5XX_ERROR, b""
        except ResponseNotJSONError:
            return QuexErrorCodes.RESPONSE_NOT_JSON_ERROR, b""
        except JQProcessingError:
            return QuexErrorCodes.JQ_PROCESSING_ERROR, b""
        except ABIEncodingError:
            return QuexErrorCodes.ABI_ENCODING_ERROR, b""
        except RequestProcessingError:
            # Never sign exception text: it can carry a decrypted patch secret or
            # attacker-chosen bytes from a source. Detail is logged locally, not on-chain.
            return QuexErrorCodes.INTERNAL_REQUEST_PROCESSING_ERROR, b""
        except Exception:
            return QuexErrorCodes.INTERNAL_OTHER_ERROR, b""

    status_code, value = execute_action()

    # Signing must be infallible once the action ran; without a trusted timestamp there is
    # nothing safe to sign, so an NTP outage yields an unsigned 503 and the relayer retries.
    try:
        timestamp = get_timestamp()
    except GetTimestampError as exc:
        raise ServiceUnavailable("timestamp source unavailable") from exc

    msg = EthereumOracleMessage(
        data_item=DataItem(timestamp=timestamp, error=status_code.value, value=value),
        action_id=qr.action.action_id(),
        relayer=relayer,
    )
    sig = msg.sign_with_account(account)
    return b64dict(OracleResponse(msg=msg, sig=sig))
