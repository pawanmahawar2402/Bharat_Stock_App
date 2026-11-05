
import requests
import json
url = "https://query2.finance.yahoo.com/v1/finance/screener"
payload = {
    "size": 250,
    "offset": 0,
    "sortField": "intradaymarketcap",
    "sortType": "DESC",
    "quoteType": "EQUITY",
    "query": {
        "operator": "AND",
        "operands": [
            {"operator": "eq", "operands": ["region", "in"]}
        ]
    }
}
headers = {"User-Agent": "Mozilla/5.0"}
try:
    resp = requests.post(url, json=payload, headers=headers)
    print(resp.status_code)
except Exception as e:
    print(e)

