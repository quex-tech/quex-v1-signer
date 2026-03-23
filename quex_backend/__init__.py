import json
import os
import pathlib
import tomllib

import dotenv
from Crypto.Random import get_random_bytes
from eth_account import Account
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException

from quex_backend.encryption import EncryptedPatchProcessor

dotenv.load_dotenv()

if os.environ.get("DEBUG"):

    def get_quote(report_data: bytes) -> bytes:
        with pathlib.Path("quote.dat").open("rb") as f:
            return f.read()

    def get_report(report_data: bytes) -> bytes:
        with pathlib.Path("report.dat").open("rb") as f:
            return f.read()

else:
    from pyquex_tdx import get_quote, get_report  # type: ignore[no-redef]  # noqa: F401


def get_sk():
    env_sk = os.getenv("TD_SECRET_KEY")
    if env_sk:
        try:
            bytes.fromhex(env_sk)
            return env_sk
        except ValueError:
            pass

    return get_random_bytes(32).hex()


key_file = pathlib.Path(os.environ["ETH_SIGNER_KEY_FILE"])
if not key_file.is_file():
    with key_file.open("w") as f:
        f.write(get_sk())

with key_file.open() as f:
    sk = f.read()

account = Account.from_key("0x" + sk)
patch_processor = EncryptedPatchProcessor.from_hex(sk)


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_file(os.environ.get("CONFIG"), load=tomllib.load, text=False)

    @app.errorhandler(HTTPException)
    def handle_exception(e):
        response = e.get_response()
        response.data = json.dumps(
            {
                "code": e.code,
                "title": e.name,
                "description": e.description,
            }
        )
        response.content_type = "application/json"
        return response

    from . import routes  # noqa: PLC0415

    app.register_blueprint(routes.bp)

    Limiter(get_remote_address, storage_uri="memory://", app=app, default_limits=app.config["RATE_LIMITS"])

    return app
