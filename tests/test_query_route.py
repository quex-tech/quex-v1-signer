import json
import unittest
from base64 import b64decode
from pathlib import Path
from typing import Any
from unittest.mock import patch

from quex_backend import create_app
from quex_backend.utils import RequestProcessingError

_VECTOR_FILE = Path(__file__).parent / "test_vectors" / "http_action_test_vectors.json"
VECTORS = json.loads(_VECTOR_FILE.read_text())
ETH_ACTION_B64 = VECTORS[0]["action_bytes"]
RELAYER = "0x1111111111111111111111111111111111111111"


# Regression for the signed-secret disclosure: an internal error must never sign
# exception text, which can carry a decrypted patch secret into an on-chain DataItem.
class TestQueryRouteErrorSigning(unittest.TestCase):
    def setUp(self) -> None:
        self.client = create_app().test_client()

    def post(self) -> Any:
        return self.client.post(
            "/query", json={"action": ETH_ACTION_B64, "relayer": RELAYER}
        )

    def assert_empty_signed_value(self, exc: Exception, expected_error: int) -> None:
        with (
            patch("quex_backend.routes.get_timestamp", return_value=1700000000),
            patch("quex_backend.routes.make_request", side_effect=exc),
        ):
            response = self.post()

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["msg"]["data_item"]["error"], expected_error)
        self.assertEqual(b64decode(data["msg"]["data_item"]["value"]), b"")

    def test_request_processing_error_signs_empty_value_not_exception_text(self):
        self.assert_empty_signed_value(RequestProcessingError("sk_live_SECRET"), 101)

    def test_unexpected_error_signs_empty_value_not_exception_text(self):
        self.assert_empty_signed_value(Exception("sk_live_SECRET"), 100)


if __name__ == "__main__":
    unittest.main()
