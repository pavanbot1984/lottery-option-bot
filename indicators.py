# indicators.py
import pandas as pd
import pandas_ta as ta

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds Supertrend(10,3), MACD(12,26,9) and RSI(14).
    Expects columns: high, low, close
    Produces columns: st, st_dir, macd_hist, rsi
    """
    st = ta.supertrend(high=df["high"], low=df["low"], close=df["close"], length=10, multiplier=3.0)
    # pandas_ta returns columns like SUPERT_10_3.0, SUPERTd_10_3.0, SUPERTl_10_3.0, etc.
    df["st"] = st[f"SUPERT_10_3.0"]
    df["st_dir"] = st[f"SUPERTd_10_3.0"]  # +1 or -1

    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df["macd_hist"] = macd["MACDh_12_26_9"]

    df["rsi"] = ta.rsi(df["close"], length=14)
    return df
