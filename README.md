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
+ `COINMARKETCAP_API_KEY`: API key for Coinmarketcap
+ `DEBUG`: set this variable to 1 if the server is run outside of TD. In this case, instead of loading TDX quoting
  functionality. The endpoint `/quote` will attempt to read attestation quote from binary file `quote.dat`. To test this
  endpoint, supply `quote.dat` additionally

The environment variables can be set inside `.env` file:
```sh
$ cat .env
CONFIG=/etc/quex_signer.toml
ETH_SIGNER_KEY=0x0000000000000000000000000000000000000000000000000000000000000001
COINMARKETCAP_API_KEY="95e75588-6481-4112-a5cd-d061796fc037"
DEBUG=1
```

## Run server
```sh
./start.sh
```
