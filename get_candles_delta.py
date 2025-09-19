# get_candles_delta.py
import requests
import pandas as pd

BASE = "https://api.delta.exchange"

def get_candles(symbol: str, resolution: str = "5m", limit: int = 200) -> pd.DataFrame:
    """
    Fetch OHLCV candles from Delta Exchange for ANY symbol (spot/option/perp).
    Returns ASC by time with columns: time, open, high, low, close, volume
    """
    url = f"{BASE}/v2/history/candles"
    params = {"symbol": symbol, "resolution": resolution, "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json().get("result", [])
    if not data:
        raise RuntimeError(f"Delta returned no candles for {symbol}")
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.sort_values("time").reset_index(drop=True)
    return df[["time","open","high","low","close","volume"]].astype(
        {"open":"float64","high":"float64","low":"float64","close":"float64","volume":"float64"}
    )
