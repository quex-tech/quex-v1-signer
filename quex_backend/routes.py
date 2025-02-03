from flask import Blueprint, request, current_app, abort
import copy

from quex_backend import account, get_quote, get_report, patch_processor
from quex_backend.models import DataItem, OracleResponse, OracleMessage, HTTPAction, b64dict
from quex_backend.vault_structs import TdKeyRequest, TdReport, TdKeyRequestMask, TdMsg
from quex_backend.td_quote import TDQuote, SGXQuote
from quex_backend.key_request import apply_mask, verify_sgx_quote_report_data, verify_sgx_quote
from eth_keys import keys
from quex_backend.utils import make_request, process_json, get_timestamp
from eth_account import Account
from quex_backend.encryption import EncryptedPatchProcessor
from base64 import b64encode, b64decode
import OpenSSL

bp = Blueprint('v1', __name__)


@bp.route('/quote')
def quote():
    sk = keys.PrivateKey(account.key)
    quote_bin = get_quote(sk.public_key.to_bytes())
    quote = TDQuote.deserialize(quote_bin)
    return b64dict(quote)

@bp.route('/key-request')
def key_request():
    sk = keys.PrivateKey(account.key)
    report_bin = get_report(sk.public_key.to_bytes())
    report = TdReport.from_buffer_copy(report_bin)
    request_mask = TdKeyRequestMask(**current_app.config['KEY_REQUEST_MASK'])
    key_req = TdKeyRequest(request_mask, report)
    return { 'key_req': b64encode(bytes(key_req)).decode() }

@bp.route('/instantiate-key', methods=['POST'])
def instantiate_key():
    global account
    global patch_processor
    j = request.get_json()
    quote = SGXQuote.deserialize(b64decode(j['quote']))
    msg = TdMsg.from_buffer_copy(b64decode(j['msg']))
    # get report
    sk = keys.PrivateKey(account.key)
    report_bin = get_report(sk.public_key.to_bytes())
    report = TdReport.from_buffer_copy(report_bin)
    # compare mask with config mask
    mask = TdKeyRequestMask(**current_app.config['KEY_REQUEST_MASK'])
    with open(current_app.config['TDX_ROOT_CERT'], 'rb') as f:
        root_cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, f.read())
    if bytes(msg.mask) != bytes(mask):
        abort(400)
    # compare masked report with own report
    msg_report = copy.deepcopy(msg.tdreport)
    if bytes(apply_mask(report, mask)) != bytes(apply_mask(msg_report, mask)):
        abort(400)
    if quote.isv_enclave_report.mrenclave != bytes.fromhex(current_app.config['VAULT_MRENCLAVE']):
        abort(400)
    try:
        verify_sgx_quote(quote, root_cert)
        verify_sgx_quote_report_data(quote, msg)
        key = patch_processor.decrypt_quoted_message(msg.ciphertext).hex()
        account = Account.from_key("0x"+key)
        patch_processor = EncryptedPatchProcessor.from_hex(key)
        return '', 202
    except:
        abort(400)

@bp.route('/address')
def address():
    return account.address


@bp.route('/query', methods=['POST'])
def query():
    action = request.get_json()['action']
    qr = HTTPAction.parse(action)
    patched_http_request = patch_processor.apply_patch(qr)
    d = make_request(patched_http_request)
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
