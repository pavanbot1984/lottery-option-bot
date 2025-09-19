# indicators.py
import pandas as pd

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = (delta.clip(lower=0)).ewm(alpha=1/period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = up / (down.replace(0, 1e-9))
    return 100 - (100 / (1 + rs))

def macd_hist(series: pd.Series, fast:int=12, slow:int=26, signal:int=9) -> pd.Series:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    return macd - sig

def supertrend(df: pd.DataFrame, atr_period:int=10, atr_mult:float=3.0) -> pd.DataFrame:
    # df must have: open, high, low, close
    hl2 = (df['high'] + df['low']) / 2
    tr = (df['high'] - df['low']).to_frame('h-l')
    tr['h-c'] = (df['high'] - df['close'].shift()).abs()
    tr['l-c'] = (df['low'] - df['close'].shift()).abs()
    tr = tr.max(axis=1)
    atr = tr.ewm(alpha=1/atr_period, adjust=False).mean()
    upper = hl2 + atr_mult * atr
    lower = hl2 - atr_mult * atr

    st = pd.Series(index=df.index, dtype=float)
    dir = pd.Series(index=df.index, dtype=int)

    st.iloc[0] = upper.iloc[0]
    dir.iloc[0] = 1
    for i in range(1, len(df)):
        prev_st = st.iloc[i-1]
        prev_dir = dir.iloc[i-1]
        curr_upper = upper.iloc[i]
        curr_lower = lower.iloc[i]
        if prev_dir == 1:
            st.iloc[i] = curr_lower if df['close'].iloc[i] < prev_st else min(curr_upper, prev_st)
            dir.iloc[i] = -1 if df['close'].iloc[i] < prev_st else 1
        else:
            st.iloc[i] = curr_upper if df['close'].iloc[i] > prev_st else max(curr_lower, prev_st)
            dir.iloc[i] = 1 if df['close'].iloc[i] > prev_st else -1

    out = df.copy()
    out['st'] = st
    out['st_dir'] = dir
    return out
