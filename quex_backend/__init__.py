import os

from flask import Flask
from flask_limiter.util import get_remote_address
from flask_limiter import Limiter
from werkzeug.exceptions import HTTPException
import json
import dotenv
import os
import tomllib
from eth_account import Account

dotenv.load_dotenv()
account = Account.from_key(os.environ.get("ETH_SIGNER_KEY"))
cmc_api_key = os.environ.get("COINMARKETCAP_API_KEY")

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_file(
            os.environ.get("CONFIG"),
            load=tomllib.load, 
            text=False
            )


    @app.errorhandler(HTTPException)
    def handle_exception(e):
        response = e.get_response()
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
