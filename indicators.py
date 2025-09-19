# indicators.py
import pandas as pd
import pandas_ta as ta

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    st = ta.supertrend(high=df["high"], low=df["low"], close=df["close"], length=10, multiplier=3.0)
    df["st"]     = st["SUPERT_10_3.0"]
    df["st_dir"] = st["SUPERTd_10_3.0"]   # +1/-1
    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    df["macd_hist"] = macd["MACDh_12_26_9"]
    df["rsi"] = ta.rsi(df["close"], length=14)
    return df
