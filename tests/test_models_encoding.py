import unittest
from pathlib import Path

from quex_backend.models import *
from quex_backend.utils import *


class TestModelsEncoding(unittest.TestCase):
    f = open(Path(__file__).parent.resolve() / 'test_vectors.json')
    vectors = json.load(f)

    # check that we can serialize test vectors without errors and get the same result, as expected
    def test_models_encoding(self):
        for v in self.vectors:
            obj = QuexRequest.parse(v["quex_request"])

            self.assertEqual("0x" + obj.bytes().hex(), v["encoded_hex"])
            self.assertEqual("0x" + obj.feed_id().hex(), v["keccak256_hex"])


if __name__ == "__main__":
    unittest.main()
