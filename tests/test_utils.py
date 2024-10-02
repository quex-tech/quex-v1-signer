from quex_backend.utils import *


def test_get_timestamp():
    ts = get_timestamp()
    assert ts > 1727864076