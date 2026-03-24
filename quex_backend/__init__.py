from typing import Any, cast

from flask import Flask
from werkzeug.wrappers import Response
from flask_limiter.util import get_remote_address
from flask_limiter import Limiter
from werkzeug.exceptions import HTTPException
import json
import dotenv
import os
import pathlib
import tomllib
from eth_account import Account
from quex_backend.encryption import EncryptedPatchProcessor
from Crypto.Random import get_random_bytes

dotenv.load_dotenv()

if os.environ.get("DEBUG"):
    def get_quote(report_data: bytes) -> bytes:
        with open("quote.dat", 'rb') as f:
            quote_bin = f.read()
        return quote_bin
    def get_report(report_data: bytes) -> bytes:
        with open("report.dat", 'rb') as f:
            report_bin = f.read()
        return report_bin
else:
    from pyquex_tdx import get_quote, get_report  # type: ignore[no-redef]

def get_sk() -> str:
    env_sk = os.getenv("TD_SECRET_KEY")
    if env_sk:
        try:
            bytes.fromhex(env_sk)
            return env_sk
        except ValueError:
            pass

    return get_random_bytes(32).hex()

key_file = os.environ["ETH_SIGNER_KEY_FILE"]
if not pathlib.Path(key_file).is_file():
    with open(key_file, 'w') as f:
        f.write(get_sk())

with open(key_file, 'r') as f:
    sk = f.read()

account = Account.from_key("0x"+sk)
patch_processor = EncryptedPatchProcessor.from_hex(sk)

def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_file(
            os.environ["CONFIG"],
            load=tomllib.load,
            text=False
            )


    @app.errorhandler(HTTPException)
    def handle_exception(e: HTTPException) -> Response:
        response = cast(Response, e.get_response())
        response.data = json.dumps({
            "code": e.code,
            "title": e.name,
            "description": e.description,
        })
        response.content_type = "application/json"
        return response

    from . import routes
    app.register_blueprint(routes.bp)

    limiter = Limiter(
            get_remote_address, 
            storage_uri="memory://",
            app=app, 
            default_limits = app.config['RATE_LIMITS']
            )

    return app
