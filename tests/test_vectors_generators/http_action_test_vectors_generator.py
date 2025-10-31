import base64
import enum
import json
from pathlib import Path

from ecdsa import VerifyingKey, SigningKey, SECP256k1

from quex_backend.models import HTTPPrivatePatch, RequestHeaderPatch, QueryParameterPatch, HTTPAction, HTTPRequest, \
    RequestMethod, RequestHeader, QueryParameter, HTTPActionWithProof
from tests.client import Client

from typing import Any, Optional

class CustomEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles the following rules:
    1. For base types, use the default encoder
    2. For bytes, convert to base64
    3. For other types, use their __dict__
    4. Handle nested objects recursively
    """

    def default(self, obj: Any) -> Any:
        # Handle bytes by converting to base64
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode('ascii')

        if isinstance(obj, enum.Enum):
            return obj.value

        # Handle other non-serializable objects
        try:
            # Try default serialization first
            return super().default(obj)
        except TypeError:
            # For objects with __dict__, recursively process their attributes
            if hasattr(obj, "__dict__"):
                result = {}
                for key, value in obj.__dict__.items():
                    # Skip private attributes (optional)
                    if not key.startswith("_"):
                        # Recursively process nested objects
                        if isinstance(value, (dict, list, tuple)) or hasattr(value, "__dict__"):
                            result[key] = self._process_nested(value)
                        else:
                            result[key] = value
                return result
            # If all else fails, convert to string
            return str(obj)

    def _process_nested(self, obj: Any) -> Any:
        """Helper method to handle nested objects recursively"""
        if isinstance(obj, dict):
            return {k: self._process_nested(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._process_nested(item) for item in obj]
        elif isinstance(obj, bytes):
            return {
                "_type": "bytes",
                "data": base64.b64encode(obj).decode('ascii')
            }
        elif hasattr(obj, "__dict__"):
            return self.default(obj)
        else:
            return obj


def read_raw_vectors():
    with open(Path(__file__).parent.resolve() / "http_action_raw_vectors.json") as f:
        return json.load(f)


def save_prepared_vectors(prepared_actions):
    with open(Path(__file__).parent.parent.resolve() / "test_vectors" / "http_action_test_vectors.json", "w") as f:
        json.dump(prepared_actions, f, indent=2, cls=CustomEncoder)


def convert_request(request) -> HTTPRequest:
    headers = request["headers"]
    parameters = request["parameters"]

    return HTTPRequest(
        RequestMethod[request["method"].upper()],
        request["host"],
        request["path"],
        [RequestHeader(header["key"], header["value"]) for header in headers],
        [QueryParameter(param["key"], param["value"]) for param in parameters],
        base64.b64decode(request["body"])
    )


def prepare_patch(raw_patch, client: Client) -> HTTPPrivatePatch:
    path_suffix = raw_patch.get("path_suffix", "")
    headers = raw_patch["headers"] if "headers" in raw_patch else []
    parameters = raw_patch["parameters"] if "parameters" in raw_patch else []
    body = raw_patch.get("body", "")

    if not path_suffix and not headers and not parameters and not body:
        return HTTPPrivatePatch(b"", [], [], b"", "0x0000000000000000000000000000000000000000")

    return HTTPPrivatePatch(
        client.encrypt_message(str.encode(path_suffix)) if path_suffix else b"",
        [RequestHeaderPatch(header["key"], client.encrypt_message(str.encode(header["value"]))) for header in headers],
        [QueryParameterPatch(param["key"], client.encrypt_message(str.encode(param["value"]))) for param in parameters],
        client.encrypt_message(base64.b64decode(body)) if body else b"",
        client.get_address()
    )


def prepare_action(raw_action, public_key) -> HTTPActionWithProof:
    client = Client(public_key)
    action = HTTPAction(
        convert_request(raw_action["request"]),
        prepare_patch(raw_action["patch"], client),
        raw_action["filter"],
        raw_action["schema"]
    )
    action_id = action.action_id()
    proof = client.encrypt_message(action_id, include_ephemeral_public_key=True)
    return HTTPActionWithProof(action, proof)


def create_patched_request(request, patch):
    request = convert_request(request)
    if "path_suffix" in patch:
        request.path = request.path + patch["path_suffix"]
    if "body" in patch:
        request.body = patch["body"]
    headers = patch["headers"] if "headers" in patch else []
    parameters = patch["parameters"] if "parameters" in patch else []
    for header in headers:
        request.headers.append(RequestHeader(header["key"], header["value"]))
    for parameter in parameters:
        request.parameters.append(QueryParameter(parameter["key"], parameter["value"]))
    return request


def prepare_vector(raw_vector):
    raw_action = raw_vector["raw_action"]
    description = raw_vector["description"]

    private_key = SigningKey.generate(curve=SECP256k1)
    public_key = private_key.get_verifying_key()

    action = prepare_action(raw_action, public_key)

    return {
        "description": description,
        "action_id": action.action.action_id().hex(),
        "action": action,
        "action_bytes": action.bytes(),
        "patched_request": create_patched_request(raw_action["request"], raw_action["patch"]),
        "private_key": private_key.to_string().hex(),
        "public_key": public_key.to_string().hex(),
    }


if __name__ == "__main__":
    raw_vectors = read_raw_vectors()
    prepared_vectors = [prepare_vector(raw_vector) for raw_vector in raw_vectors]
    save_prepared_vectors(prepared_vectors)
