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
            obj = HTTPAction.parse(v["action_bytes"])
            self.assertEqual(obj.filter, v["action"]["filter"])


if __name__ == "__main__":
    unittest.main()
