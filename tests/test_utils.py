import unittest

import pytest

from quex_backend.utils import *  # Adjust to your actual module path


class TestUtils(unittest.TestCase):

    def test_process_json_multiple_values(self):
        # Input JSON as a dictionary
        input_json = {
            "value1": 123456,
            "value2": 654321
        }

        # JQ query to extract multiple values
        json_query = '[.value1, .value2]'

        # Expected ABI schema for the result (multiple uint256 values)
        schema = "(uint256,uint256)"

        # Expected result to be encoded
        expected_result = [123456, 654321]

        # Encode the expected result using eth_abi directly to compare
        expected_encoded = eth_abi.encode([schema], [expected_result])

        # Process the input JSON with the process_json function
        actual_encoded = process_json(input_json, json_query, schema)

        # Assert that the actual encoded bytes match the expected encoded bytes
        assert actual_encoded == expected_encoded

    def test_process_json_single_integer(self):
        # Input JSON as a dictionary
        input_json = {
            "value": 123456
        }

        # JQ query to extract a single integer value
        json_query = '.value'

        # Expected ABI schema for a single uint256
        schema = "uint256"

        # Expected result to be encoded
        expected_result = 123456

        # Encode the expected result using eth_abi directly to compare
        expected_encoded = eth_abi.encode(['uint256'], [expected_result])

        # Process the input JSON with the process_json function
        actual_encoded = process_json(input_json, json_query, schema)

        # Assert that the actual encoded bytes match the expected encoded bytes
        assert actual_encoded == expected_encoded

    def test_process_json_complex_data(self):
        # Input JSON from Binance API (example response)
        input_json = {
            "lastUpdateId": 52933493429,
            "bids": [
                ["65615.89000000", "3.36758000"],
                ["65615.88000000", "1.52340000"],
                ["65615.87000000", "2.23400000"],
                ["65615.86000000", "4.34510000"],
                ["65615.85000000", "0.34660000"]
            ],
            "asks": [
                ["65615.90000000", "3.52297000"],
                ["65615.91000000", "2.12340000"],
                ["65615.92000000", "1.03400000"],
                ["65615.93000000", "3.56780000"],
                ["65615.94000000", "4.89000000"]
            ]
        }

        # JQ query to extract and process data
        json_query = '[.lastUpdateId] + ([.bids, .asks] | map(map(map(tonumber*100000000|round))))'

        # Expected ABI schema for the result (OrderBook structure)
        schema = "(uint256,(uint256,uint256)[5],(uint256,uint256)[5])"

        # Expected result after processing the bids and asks, with scaling and conversion
        expected_result = [
            52933493429,  # lastUpdateId
            [  # Bids (price * 1e8, quantity * 1e8)
                (6561589000000, 336758000),
                (6561588000000, 152340000),
                (6561587000000, 223400000),
                (6561586000000, 434510000),
                (6561585000000, 34660000)
            ],
            [  # Asks (price * 1e8, quantity * 1e8)
                (6561590000000, 352297000),
                (6561591000000, 212340000),
                (6561592000000, 103400000),
                (6561593000000, 356780000),
                (6561594000000, 489000000)
            ]
        ]

        # Properly encode the expected result using eth_abi
        expected_encoded = eth_abi.encode([schema], [expected_result])

        # Process the input JSON with the process_json function
        actual_encoded = process_json(input_json, json_query, schema)

        # Assert that the actual encoded bytes match the expected encoded bytes
        assert actual_encoded == expected_encoded


if __name__ == '__main__':
    pytest.main()
