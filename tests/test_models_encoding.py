import unittest
import json
from pathlib import Path

from quex_backend.models import *


class TestModelsEncoding(unittest.TestCase):
    f = open(Path(__file__).parent.resolve() / 'test_vectors' / 'http_action_test_vectors.json')
    httpaction_vectors = json.load(f)
    f2 = open(Path(__file__).parent.resolve() / 'test_vectors' / 'oracle_message_test_vectors.json')
    oracle_message_vectors = json.load(f2)

    # check that we can serialize test vectors without errors and get the same result, as expected
    def test_HTTPAction_models_encoding(self):
        for v in self.httpaction_vectors:
            obj = HTTPActionWithProof.parse(v["action_bytes"])

            self.assertEqual(base64.b64encode(obj.bytes()).decode("ascii"), v["action_bytes"])
            self.assertEqual(obj.action.action_id().hex(), v["action_id"])

    def test_OracleMessage_encoding(self):
        for v in self.oracle_message_vectors:
            msg_data = v["msg"]
            oracle_msg = OracleMessage(
                action_id=base64.b64decode(msg_data["action_id"]),
                data_item=DataItem(
                    timestamp=msg_data["data_item"]["timestamp"],
                    error=msg_data["data_item"]["error"],
                    value=base64.b64decode(msg_data["data_item"]["value"])
                ),
                relayer=msg_data["relayer"]
            )

            encoded_bytes = oracle_msg.bytes()
            self.assertEqual(base64.b64encode(encoded_bytes).decode("ascii"), v["bytes"])


if __name__ == "__main__":
    unittest.main()
