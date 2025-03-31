from base64 import b64decode
import unittest
from pathlib import Path
import json
from quex_backend.models import *


class TestModelsParsing(unittest.TestCase):

    # check that we can parse test vectors without errors
    def test_test_vectors_parsing(self):
        f = open(Path(__file__).parent.resolve() / 'test_vectors' / 'http_action_test_vectors.json')
        vectors = json.load(f)
        for v in vectors:
            obj = EthereumHTTPActionWithProof.parse(b64decode(v["action_bytes"]))
            self.assertEqual(obj.action.filter, v["action"]["action"]["filter"])
            self.assertEqual(obj.action.schema, v["action"]["action"]["schema"])
            self.assertEqual(obj.action.request.method, v["action"]["action"]["request"]["method"])
            self.assertEqual(obj.action.request.host, v["action"]["action"]["request"]["host"])
            self.assertEqual(obj.action.request.path, v["action"]["action"]["request"]["path"])
            self.assertEqual(obj.action.request.headers, [RequestHeader(h["key"], h["value"]) for h in v["action"]["action"]["request"]["headers"]])
            self.assertEqual(obj.action.request.parameters, [QueryParameter(p["key"], p["value"]) for p in v["action"]["action"]["request"]["parameters"]])
            self.assertEqual(obj.action.request.body, b64decode(v["action"]["action"]["request"]["body"]))
            self.assertEqual(obj.action.patch.path_suffix, b64decode(v["action"]["action"]["patch"]["path_suffix"]))
            self.assertEqual(obj.action.patch.headers, [RequestHeaderPatch(h["key"], b64decode(h["ciphertext"])) for h in v["action"]["action"]["patch"]["headers"]])
            self.assertEqual(obj.action.patch.parameters, [QueryParameterPatch(p["key"], b64decode(p["ciphertext"])) for p in v["action"]["action"]["patch"]["parameters"]])
            self.assertEqual(obj.action.patch.body, b64decode(v["action"]["action"]["patch"]["body"]))
            self.assertEqual(obj.action.patch.td_address, v["action"]["action"]["patch"]["td_address"])
            self.assertEqual(obj.proof, b64decode(v["action"]["proof"]))


if __name__ == "__main__":
    unittest.main()
