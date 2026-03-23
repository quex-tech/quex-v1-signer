# quex-v1-signer
## Description
Simple http server to be run inside Trusted Domains

## Setup

Initialize `python3` virtual environment
```sh
python3 -m venv venv
```

Activate virtual environment
```sh
source ./venv/bin/activate
```

Install dependencies
```sh
pip install -r requirements.txt
```

To deactivate virual environment, type
```sh
deactivate
```

## Environment Variables
+ `CONFIG`: full path to `config.toml`
+ `ETH_SIGNER_KEY_FILE`: path to the file containing private key of signing service. The file will be created if not
  exists
+ `DEBUG`: set this variable to 1 if the server is run outside of TD. In this case, instead of loading TDX quoting
  functionality. The endpoint `/quote` will attempt to read attestation quote from binary file `quote.dat`. To test this
  endpoint, supply `quote.dat` additionally

The environment variables can be set inside `.env` file:
```sh
$ cat .env
CONFIG=/home/bazil/work/sgx/tdx_scripts/quex-v1-signer/config.toml
ETH_SIGNER_KEY_FILE="./sk.txt"
DEBUG=1
```

## Other Files

The service requires the Intel SGX root CA certificate for operation. The default file location is expected to be
`root.pem` in the project directory

## Run server
From virtual environment
```sh
./start.sh
```

## Usage

Get latest ETHBTC pair from Binance, multiply the result by 1000000, round value to integer:
```sh
curl -X POST http://127.0.0.1:8000/query \
-H "Content-Type: application/json" \
-d '{"action": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABCAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPYXBpLmJpbmFuY2UuY29tAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAES9hcGkvdjMvYXZnUHJpY2U/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGc3ltYm9sAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABkVUSEJUQwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABmludDI1NgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACMucHJpY2UgfCB0b251bWJlciAqIDEwMDAwMDAgfCByb3VuZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA","relayer":"0x70beA06316c51097dF67496feaFb7F50758019b9"}'
```

`action` must be a base64 encoding of either Ethereum Solidity Contract ABI encoded `EthereumHTTPActionWithProof`, or Cardano Plutus CBOR-encoded `PlutusHTTPActionWithProof`.

Response example:

```json
{
  "msg": {
    "action_id": "TWXiib1CQsJu171Q+jd+WS2Eo93IzJQXylhuZEtZ7pw=",
    "data_item": {
      "error": 0,
      "timestamp": 1749900886,
      "value": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAXlE="
    },
    "relayer": "0x70beA06316c51097dF67496feaFb7F50758019b9"
  },
  "sig": {
    "r": "egexUbtz6nFEt2ZecAQS6i0HJoOi9p/CiZD6hIuTeZ8=",
    "s": "RPeCktMZraA3pcc61P5JRfWy2LtpVV2MVzk2X0HAZeQ=",
    "v": 27
  }
}
```

`value` is the base64 encoding of either Ethereum Solidity Contract ABI, or Cardano Plutus CBOR encoding of the jq-processed HTTP response, depending on `action` contents.

## Supported JQ operations
+ `+`, `-`, `*`, `/`, `%`
+ Selectors, both with `.` and `[]`
+ Array slicing operator `[n:m]`
+ Piping `|`
+ Array construction with `[]`
+ `map`
+ Math functions: `floor`, `abs`, `round`, `sqrt`
+ String and list manipulation `split`, `join`
+ Date timestamp conversion `todate`, `fromdate`
+ String to number conversion `tonumber`
