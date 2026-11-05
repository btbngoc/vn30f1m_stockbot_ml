import requests
import time
import pandas as pd

url = "https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart"
headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://trading.vietcap.com.vn/",
    "Origin": "https://trading.vietcap.com.vn",
    "Content-Type": "application/json"
}

# Thử lấy 100,000 nến 1-phút của VN30
print("Testing historical depth for VN30...")
try:
    payload = {
        "timeFrame": "ONE_MINUTE",
        "symbols": ["VN30"],
        "to": int(time.time()),
        "countBack": 100000
    }
    t0 = time.time()
    res = requests.post(url, json=payload, headers=headers, timeout=60)
    data = res.json()
    if isinstance(data, list) and len(data) > 0 and "t" in data[0]:
        t_arr = data[0]["t"]
        unit = "ms" if t_arr[-1] > 1e12 else "s"
        first_t = pd.to_datetime(t_arr[0], unit=unit, utc=True).tz_convert('Asia/Ho_Chi_Minh')
        last_t = pd.to_datetime(t_arr[-1], unit=unit, utc=True).tz_convert('Asia/Ho_Chi_Minh')
        print(f"SUCCESS: Fetched {len(t_arr)} 1-minute bars of VN30 in {time.time()-t0:.2f}s!")
        print(f"Earliest bar: {first_t}")
        print(f"Latest bar  : {last_t}")
    else:
        print("Failed to get data array:", data)
except Exception as e:
    print("Error:", e)
