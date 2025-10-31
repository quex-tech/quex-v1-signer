import unittest
import json
from pathlib import Path

from quex_backend.models import *


class TestModelsEncoding(unittest.TestCase):
    f = open(Path(__file__).parent.resolve() / 'test_vectors' / 'http_action_test_vectors.json')
    vectors = json.load(f)

    # check that we can serialize test vectors without errors and get the same result, as expected
    def test_models_encoding(self):
        for v in self.vectors:
            obj = HTTPActionWithProof.parse(v["action_bytes"])

            self.assertEqual(base64.b64encode(obj.bytes()).decode("ascii"), v["action_bytes"])
            self.assertEqual(obj.action.action_id().hex(), v["action_id"])


if __name__ == "__main__":
    unittest.main()
