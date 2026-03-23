import json
import unittest
from base64 import b64decode
from pathlib import Path

from quex_backend.models import (
    EthereumHTTPActionWithProof,
    PlutusHTTPActionWithProof,
    QueryParameter,
    QueryParameterPatch,
    RequestHeader,
    RequestHeaderPatch,
    RideHTTPActionWithProof,
)


class TestModelsParsing(unittest.TestCase):
    def assert_action_matches_vector(self, obj, v):
        self.assertEqual(obj.action.filter, v["action"]["action"]["filter"])
        self.assertEqual(obj.action.schema, v["action"]["action"]["schema"])
        self.assertEqual(obj.action.request.method, v["action"]["action"]["request"]["method"])
        self.assertEqual(obj.action.request.host, v["action"]["action"]["request"]["host"])
        self.assertEqual(obj.action.request.path, v["action"]["action"]["request"]["path"])
        self.assertEqual(obj.action.request.headers, [RequestHeader(h["key"], h["value"]) for h in v["action"]["action"]["request"]["headers"]])
        self.assertEqual(obj.action.request.parameters, [QueryParameter(p["key"], p["value"]) for p in v["action"]["action"]["request"]["parameters"]])
        self.assertEqual(obj.action.request.body, b64decode(v["action"]["action"]["request"]["body"]))
        self.assertEqual(obj.action.patch.path_suffix, b64decode(v["action"]["action"]["patch"]["path_suffix"]))
        self.assertEqual(
            obj.action.patch.headers, [RequestHeaderPatch(h["key"], b64decode(h["ciphertext"])) for h in v["action"]["action"]["patch"]["headers"]]
        )
        self.assertEqual(
            obj.action.patch.parameters, [QueryParameterPatch(p["key"], b64decode(p["ciphertext"])) for p in v["action"]["action"]["patch"]["parameters"]]
        )
        self.assertEqual(obj.action.patch.body, b64decode(v["action"]["action"]["patch"]["body"]))
        self.assertEqual(obj.action.patch.td_address, v["action"]["action"]["patch"]["td_address"])
        self.assertEqual(obj.proof, b64decode(v["action"]["proof"]))

    def test_ethereum_test_vectors_parsing(self):
        vectors = json.loads((Path(__file__).parent.resolve() / "test_vectors" / "http_action_test_vectors.json").read_text())
        for v in vectors:
            obj = EthereumHTTPActionWithProof.parse(b64decode(v["action_bytes"]))
            self.assert_action_matches_vector(obj, v)

    def test_plutus_test_vectors_parsing(self):
        vectors = json.loads((Path(__file__).parent.resolve() / "test_vectors" / "plutus_http_action_test_vectors.json").read_text())
        for v in vectors:
            obj = PlutusHTTPActionWithProof.parse(b64decode(v["action_bytes"]))
            self.assert_action_matches_vector(obj, v)

    def test_ride_test_vectors_parsing(self):
        vectors = json.loads((Path(__file__).parent.resolve() / "test_vectors" / "ride_http_action_test_vectors.json").read_text())
        for v in vectors:
            obj = RideHTTPActionWithProof.parse(b64decode(v["action_bytes"]))
            self.assert_action_matches_vector(obj, v)


if __name__ == "__main__":
    unittest.main()
