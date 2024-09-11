from datetime import datetime, timezone

cmc_url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
cmc_ids = [1, 1027, 825, 1839, 5426, 3408, 52, 74, 1958, 11419]

def cmc_str_to_timestamp(s):
    dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")
    return round(dt.replace(tzinfo=timezone.utc).timestamp())
