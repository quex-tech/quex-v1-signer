import ntplib

c = ntplib.NTPClient()


# TODO do not rely on single server
# TODO ensure timestamp increase only
# TODO handle errors
def get_timestamp() -> int:
    response = c.request('europe.pool.ntp.org', version=3)
    return round(response.tx_time)
