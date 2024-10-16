from quex_backend.models import *
from eth_account import Account


def test_IntDataItem():
    idi = IntDataItem(
        timestamp=1727864076,
        value=123,
        feed_id="asda".encode()
    )
    account = Account.from_key("0x0000000000000000000000000000000000000000000000000000000000000001")
    s = idi.sign_with_account(account)

    assert s
