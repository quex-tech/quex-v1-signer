import json
import unittest
from quex_backend.ride.abi import encoder


class TestEncoder(unittest.TestCase):
    def test_encode(self):
        cases = [
            ("1", "int", "0000000000000001"),
            ('"Hello, 世界"', "string", "000000000000000d48656c6c6f2c20e4b896e7958c"),
            ("true", "bool", "0000000000000001"),
            ("false", "bool", "0000000000000000"),
            ("[]", "int[]", "0000000000000000"),
            ("[1]", "int[]", "00000000000000010000000000000001"),
            ("[1]", "(int)", "0000000000000001"),
            ("[1,2]", "(int,int)", "00000000000000010000000000000002"),
            ("[1,[2]]", "(int,(int))", "00000000000000010000000000000002"),
            (
                "[1,[2]]",
                "(int,int[])",
                "000000000000000100000000000000010000000000000002",
            ),
            (
                "[[1,[2]],[3,[4,5]]]",
                "(int,int[])[]",
                "0000000000000002"
                "000000000000000100000000000000010000000000000002"
                "0000000000000003000000000000000200000000000000040000000000000005",
            ),
            (
                "[[1,[2]],[3,[4]]]",
                "(int,(int))[]",
                "0000000000000002"
                "00000000000000010000000000000002"
                "00000000000000030000000000000004",
            ),
            (
                "[1,2,3,4,5,6]",
                "(uint,uint8,uint64,int,int8,int64)",
                "000000000000000100000000000000020000000000000003000000000000000400000000000000050000000000000006",
            ),
            ["[1,2]", "int[2]", "00000000000000010000000000000002"],
        ]

        for json_str, schema, expected_hex in cases:
            with self.subTest(
                json=json_str, schema=schema, expected_primitive=expected_hex
            ):
                actual = encoder.encode([schema], [json.loads(json_str)])
                self.assertEqual(actual.hex(), expected_hex)


if __name__ == "__main__":
    unittest.main()
