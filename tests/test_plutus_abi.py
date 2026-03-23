import json
import unittest

from quex_backend.plutus.abi import encoder


class TestEncoder(unittest.TestCase):
    def test_encode(self):
        cases = [
            ("1", "int", "01"),
            ('"Hello, 世界"', "string", "4d48656c6c6f2c20e4b896e7958c"),
            ("true", "bool", "d87a80"),
            ("false", "bool", "d87980"),
            ("[]", "int[]", "80"),
            ("[1]", "int[]", "9f01ff"),
            ("[1]", "(int)", "d8799f01ff"),
            ("[1,2]", "(int,int)", "d8799f0102ff"),
            ("[1,[2]]", "(int,(int))", "d8799f01d8799f02ffff"),
            ("[1,[2]]", "(int,int[])", "d8799f019f02ffff"),
            ('["BTC","USD"]', "(string,string)", "d8799f4342544343555344ff"),
            ("[true,[1,2,3]]", "(bool,uint[])", "d8799fd87a809f010203ffff"),
            ("[[1,[2]],[3,[4,5]]]", "(int,int[])[]", "9fd8799f019f02ffffd8799f039f0405ffffff"),
            ("[[1,[2]],[3,[4]]]", "(int,(int))[]", "9fd8799f01d8799f02ffffd8799f03d8799f04ffffff"),
            ("[1,2,3,4,5,6]", "(uint,uint8,uint256,int,int8,int256)", "d8799f010203040506ff"),
        ]

        for json_str, schema, expected_hex in cases:
            with self.subTest(json=json_str, schema=schema, expected_primitive=expected_hex):
                actual = encoder.encode([schema], [json.loads(json_str)])
                self.assertEqual(actual.hex(), expected_hex)

    def test_encode_invalid_value(self):
        with self.assertRaises(Exception):
            encoder.encode(["uint"], [-1])


if __name__ == "__main__":
    unittest.main()
