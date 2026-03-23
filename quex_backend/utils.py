import ssl

import ntplib
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, Timeout

from quex_backend.interpreter import jq_eval, parser
from quex_backend.models import HTTPRequest

c = ntplib.NTPClient()


class RequestConnectionError(Exception):
    pass


class ResponseNotSupportedResponseCodeError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code


class Response4XXError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code


class Response5XXError(Exception):
    def __init__(self, status_code: int):
        self.status_code = status_code


class RequestProcessingError(Exception):
    pass


class JQProcessingError(Exception):
    pass


class ABIEncodingError(Exception):
    pass


class GetTimestampError(Exception):
    pass


class ResponseNotJSONError(Exception):
    pass


def get_timestamp() -> int:
    """
    Get current timestamp.

    # TODO fix this method, see https://github.com/quex-tech/quex-v1-signer/issues/5

    :return: current NTP timestamp
    """
    try:
        response = c.request("europe.pool.ntp.org", version=4)
        return round(response.tx_time)
    except Exception as exc:
        raise GetTimestampError from exc


def process_json(input_json: dict, json_query: str, schema: str, encode) -> bytes:
    """
    Execute JQ program over the input data and encode the result according to the schema provided.
    """
    try:
        ast = parser.parse(json_query)
        result = jq_eval(input_json, ast)
    except Exception as exc:
        raise JQProcessingError from exc

    try:
        return encode([schema], [result])
    except Exception as exc:
        raise ABIEncodingError from exc


class SSLAdapter(HTTPAdapter):
    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)


def make_request(qrr: HTTPRequest, as_json: bool = True):
    try:
        url = qrr.build_url()

        context = ssl.create_default_context()
        context.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20")
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        session = requests.Session()
        session.mount("https://", SSLAdapter(ssl_context=context))

        r = session.request(
            qrr.method.string_value(),
            url,
            params=qrr.get_parameters(),
            headers=qrr.get_headers(),
            data=qrr.get_body(),
            verify=True,
            allow_redirects=False,
        )
    except (ConnectionError, Timeout) as exc:
        raise RequestConnectionError from exc

    if r.status_code >= 300 and r.status_code < 400:
        raise ResponseNotSupportedResponseCodeError(r.status_code)
    elif r.status_code >= 400 and r.status_code < 500:
        raise Response4XXError(r.status_code)
    elif r.status_code >= 500 and r.status_code < 600:
        raise Response5XXError(r.status_code)
    elif r.status_code >= 600:
        raise ResponseNotSupportedResponseCodeError(r.status_code)

    if r.status_code == 204:
        return ""

    if as_json:
        try:
            return r.json()
        except Exception as exc:
            raise ResponseNotJSONError from exc
    else:
        return r.text
