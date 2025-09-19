from get_candles_delta import get_candles
from indicators import add_indicators
import pandas as pd

print("[DEBUG] Fetching last 20 candles for BTCUSD (5m)...", flush=True)

try:
    df = get_candles(symbol="BTCUSD", resolution="5m", limit=20)
    df = add_indicators(df)
    print(df.tail(5).to_string())
except Exception as e:
    print("[ERROR]", e, flush=True)
