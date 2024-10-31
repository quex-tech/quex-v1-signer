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
+ `ETH_SIGNER_KEY`: private key of signing service
+ `PATCH_PROCESSOR_KEY`: private key of private patch processor
+ `DEBUG`: set this variable to 1 if the server is run outside of TD. In this case, instead of loading TDX quoting
  functionality. The endpoint `/quote` will attempt to read attestation quote from binary file `quote.dat`. To test this
  endpoint, supply `quote.dat` additionally

The environment variables can be set inside `.env` file:
```sh
$ cat .env
CONFIG=/etc/quex_signer.toml
ETH_SIGNER_KEY=0x0000000000000000000000000000000000000000000000000000000000000001
PATCH_PROCESSOR_KEY=0x0000000000000000000000000000000000000000000000000000000000000002
DEBUG=1
```

## Run server
From virtual environment
```sh
./start.sh
```

## Usage

Get latest ETHBTC pair from Binance, multiply the result by 1000000, round value to integer:
```sh
 curl --header "Content-Type: application/json" \
  --request POST \
-d '{
    "request": {
        "method": "Get",
        "host": "www.binance.com",
        "path": "/api/v3/ticker/price",
        "headers": [],
        "body": "",
        "parameters": []
    },
    "patch": {
        "path_suffix": "",
        "headers": [],
        "parameters": [],
        "body": "",
        "td_id": 0
    },
    "filter": ".[] | select(.symbol == \"ETHBTC\") | (.price | tonumber * 100000000 | floor)",
    "schema": "int256"
}' \
  http://127.0.0.1:8000/query



```


Response example:

```json
{
  "data": {
    "feed_id": "q+GOIERkZ3B096lL2CRdf6thh60qmGWsXo57mHTq+MI=",
    "timestamp": 1728054741,
    "value": 61756836504
  },
  "signature": {
    "r": "OowcbtPueR115M19Z0/q2iIIOZ7scdmU3xZbo/QuBuw=",
    "s": "fakF+trWilwUcUUA/3T9li7jykDuBVZ0tJdhfGrAUHc=",
    "v": 27
  }
}
```
