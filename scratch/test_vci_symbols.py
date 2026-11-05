import requests
import time
import json

url = "https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart"
headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://trading.vietcap.com.vn/",
    "Origin": "https://trading.vietcap.com.vn",
    "Content-Type": "application/json"
}

symbols_to_test = [
    "VN30", "VN30INDEX", "VNINDEX", "VN30F1M", "VN30F2M", "VN30F1Q", "VN30F2Q"
]

print("Testing VCI API symbols for 1-minute data:")
for sym in symbols_to_test:
    try:
        payload = {
            "timeFrame": "ONE_MINUTE",
            "symbols": [sym],
            "to": int(time.time()),
            "countBack": 10
        }
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        data = res.json()
        if isinstance(data, list) and len(data) > 0 and "c" in data[0] and len(data[0]["c"]) > 0:
            last_c = data[0]["c"][-1]
            last_t = data[0]["t"][-1]
            print(f"  [+] {sym:12s}: SUCCESS! Found {len(data[0]['c'])} bars. Last: {last_c} (epoch {last_t})")
        else:
            print(f"  [-] {sym:12s}: Empty data ({data})")
    except Exception as e:
        print(f"  [!] {sym:12s}: Error {e}")

