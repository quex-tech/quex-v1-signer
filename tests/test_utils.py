from quex_backend.utils import *


def test_get_timestamp():
    ts = get_timestamp()
    assert ts > 1727864076


def test_get_feed_id():
    url: str = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
    params: Mapping[str, str] = {"basa": "!val", "az": "!val2", "cde": "!val3"}
    jq: str = "test_filer"
    feed_id = get_feed_id(url, params, jq)
    assert feed_id.hex() == "bb85081952f79f8fa5fed15c22a2f8c0bbae05cfc50339941a91cb7534afa249"
