import base64
import json
from pathlib import Path

from quex_backend.models import DataItem, EthereumOracleMessage, PlutusOracleMessage


def read_raw_vectors():
    with open(Path(__file__).parent.resolve() / "oracle_message_raw_vectors.json") as f:
        return json.load(f)


def save_vectors(filename: str, vectors):
    with open(Path(__file__).parent.parent.resolve() / "test_vectors" / filename, "w") as f:
        json.dump(vectors, f, indent=2)


def build_messages(raw_vector):
    msg_data = raw_vector["msg"]
    common_kwargs = dict(
        action_id=base64.b64decode(msg_data["action_id"]),
        data_item=DataItem(
            timestamp=msg_data["data_item"]["timestamp"],
            error=msg_data["data_item"]["error"],
            value=base64.b64decode(msg_data["data_item"]["value"]),
        ),
        relayer=msg_data["relayer"],
    )
    return (
        EthereumOracleMessage(**common_kwargs),
        PlutusOracleMessage(**common_kwargs),
    )


def prepare_ethereum_vector(raw_vector):
    msg, _ = build_messages(raw_vector)
    return {
        "msg": raw_vector["msg"],
        "bytes": base64.b64encode(msg.bytes()).decode("ascii"),
    }


def prepare_plutus_vector(raw_vector):
    _, msg = build_messages(raw_vector)
    return {
        "msg": raw_vector["msg"],
        "bytes": base64.b64encode(msg.to_plutus_bytes()).decode("ascii"),
    }


if __name__ == "__main__":
    raw_vectors = read_raw_vectors()
    save_vectors(
        "oracle_message_test_vectors.json",
        [prepare_ethereum_vector(raw_vector) for raw_vector in raw_vectors],
    )
    save_vectors(
        "plutus_oracle_message_test_vectors.json",
        [prepare_plutus_vector(raw_vector) for raw_vector in raw_vectors],
    )
