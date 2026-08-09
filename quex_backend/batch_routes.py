import re
from base64 import b64decode
from typing import Any

from eth_abi import encode as eth_abi_encode
from eth_abi.exceptions import DecodingError
from flask import Blueprint, request
from werkzeug.exceptions import BadRequest, ServiceUnavailable

from quex_backend import account, patch_processor
from quex_backend.batch import (
    BatchActionValidationError,
    EthereumBatchHTTPActionWithProof,
    apply_batch_patches,
    fetch_all_sources,
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
    process_json,
)

bp = Blueprint("v1_batch", __name__)

ERROR_CODES = [
    (EncryptedPatchProcessingError, QuexErrorCodes.PATCH_PROCESSING_ERROR),
    (RequestConnectionError, QuexErrorCodes.REQUEST_CONNECTION_ERROR),
    (ResponseNotSupportedResponseCodeError, QuexErrorCodes.RESPONSE_NOT_SUPPORTED_RESPONSE_CODE_ERROR),
    (Response4XXError, QuexErrorCodes.RESPONSE_4XX_ERROR),
    (Response5XXError, QuexErrorCodes.RESPONSE_5XX_ERROR),
    (ResponseNotJSONError, QuexErrorCodes.RESPONSE_NOT_JSON_ERROR),
    (JQProcessingError, QuexErrorCodes.JQ_PROCESSING_ERROR),
    (ABIEncodingError, QuexErrorCodes.ABI_ENCODING_ERROR),
    (RequestProcessingError, QuexErrorCodes.INTERNAL_REQUEST_PROCESSING_ERROR),
]


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
    except (KeyError, TypeError, ValueError, DecodingError, BatchActionValidationError) as exc:
        raise BadRequest(str(exc)) from exc

    try:
        patched_requests = apply_batch_patches(patch_processor, qr.action, qr.proof)
        results = fetch_all_sources(patched_requests)
        value = process_json(results, qr.action.filter, qr.action.schema, eth_abi_encode)
        status_code = QuexErrorCodes.SUCCESS
    except Exception as exc:
        # Never sign exception text: it can carry a decrypted patch secret or attacker-chosen
        # bytes from a source. The signed value stays empty on every error path.
        status_code = next(
            (code for exc_type, code in ERROR_CODES if isinstance(exc, exc_type)),
            QuexErrorCodes.INTERNAL_OTHER_ERROR,
        )
        value = b""

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
