from base64 import b64decode, b64encode
import json
from pathlib import Path
import unittest

from quex_backend.models import (
    DataItem,
    EthereumHTTPActionWithProof,
    EthereumOracleMessage,
    PlutusHTTPActionWithProof,
    PlutusOracleMessage,
    RideHTTPActionWithProof,
    RideOracleMessage,
)
from quex_backend.plutus.cbor import PlutusTuple, dumps as plutus_dumps
from quex_backend.ride.mixins import write_ride_bytes


class TestModelsEncoding(unittest.TestCase):
    f = open(Path(__file__).parent.resolve() / "test_vectors" / "http_action_test_vectors.json")
    ethereum_httpaction_vectors = json.load(f)
    f2 = open(Path(__file__).parent.resolve() / "test_vectors" / "plutus_http_action_test_vectors.json")
    plutus_httpaction_vectors = json.load(f2)
    f3 = open(Path(__file__).parent.resolve() / "test_vectors" / "ride_http_action_test_vectors.json")
    ride_httpaction_vectors = json.load(f3)
    f4 = open(Path(__file__).parent.resolve() / "test_vectors" / "oracle_message_test_vectors.json")
    ethereum_oracle_message_vectors = json.load(f4)
    f5 = open(Path(__file__).parent.resolve() / "test_vectors" / "plutus_oracle_message_test_vectors.json")
    plutus_oracle_message_vectors = json.load(f5)
    f6 = open(Path(__file__).parent.resolve() / "test_vectors" / "ride_oracle_message_test_vectors.json")
    ride_oracle_message_vectors = json.load(f6)

    def test_ethereum_HTTPAction_models_encoding(self):
        for v in self.ethereum_httpaction_vectors:
            obj = EthereumHTTPActionWithProof.parse(b64decode(v["action_bytes"]))
            self.assertEqual(b64encode(obj.bytes()).decode("ascii"), v["action_bytes"])
            self.assertEqual(obj.action.action_id().hex(), v["action_id"])

    def test_plutus_HTTPAction_models_encoding(self):
        for v in self.plutus_httpaction_vectors:
            obj = PlutusHTTPActionWithProof.parse(b64decode(v["action_bytes"]))
            self.assertEqual(b64encode(obj.proof).decode("ascii"), v["action"]["proof"])
            self.assertEqual(obj.action.action_id().hex(), v["action_id"])
            self.assertEqual(
                b64encode(plutus_dumps(PlutusTuple([obj.action.to_plutus(), obj.proof]))).decode("ascii"),
                v["action_bytes"],
            )

    def test_ride_HTTPAction_models_encoding(self):
        for v in self.ride_httpaction_vectors:
            obj = RideHTTPActionWithProof.parse(b64decode(v["action_bytes"]))
            self.assertEqual(b64encode(obj.proof).decode("ascii"), v["action"]["proof"])
            self.assertEqual(obj.action.action_id().hex(), v["action_id"])
            buf = bytearray()
            write_ride_bytes(obj.action, buf)
            write_ride_bytes(obj.proof, buf)
            self.assertEqual(b64encode(bytes(buf)).decode("ascii"), v["action_bytes"])

    def test_ethereum_OracleMessage_encoding(self):
        for v in self.ethereum_oracle_message_vectors:
            msg_data = v["msg"]
            oracle_msg = EthereumOracleMessage(
                action_id=b64decode(msg_data["action_id"]),
                data_item=DataItem(
                    timestamp=msg_data["data_item"]["timestamp"],
                    error=msg_data["data_item"]["error"],
                    value=b64decode(msg_data["data_item"]["value"]),
                ),
                relayer=msg_data["relayer"],
            )

            encoded_bytes = oracle_msg.bytes()
            self.assertEqual(b64encode(encoded_bytes).decode("ascii"), v["bytes"])

    def test_plutus_OracleMessage_encoding(self):
        for v in self.plutus_oracle_message_vectors:
            msg_data = v["msg"]
            oracle_msg = PlutusOracleMessage(
                action_id=b64decode(msg_data["action_id"]),
                data_item=DataItem(
                    timestamp=msg_data["data_item"]["timestamp"],
                    error=msg_data["data_item"]["error"],
                    value=b64decode(msg_data["data_item"]["value"]),
                ),
                relayer=msg_data["relayer"],
            )

            encoded_bytes = oracle_msg.to_plutus_bytes()
            self.assertEqual(b64encode(encoded_bytes).decode("ascii"), v["bytes"])

    def test_ride_OracleMessage_encoding(self):
        for v in self.ride_oracle_message_vectors:
            msg_data = v["msg"]
            oracle_msg = RideOracleMessage(
                action_id=b64decode(msg_data["action_id"]),
                data_item=DataItem(
                    timestamp=msg_data["data_item"]["timestamp"],
                    error=msg_data["data_item"]["error"],
                    value=b64decode(msg_data["data_item"]["value"]),
                ),
                relayer=msg_data["relayer"],
            )

            encoded_bytes = oracle_msg.to_ride_bytes()
            self.assertEqual(b64encode(encoded_bytes).decode("ascii"), v["bytes"])


if __name__ == "__main__":
    unittest.main()
