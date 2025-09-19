# main_multi.py
import time, yaml, pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta

from get_candles_delta import get_candles
from indicators import add_indicators
from otm_option_monitor import SingleOptionMonitor
from trade_logger import TradeLogger, build_trade_id
from alerts import notify, format_alert

print("[BOOT] lottery-option-bot starting...", flush=True)

IST_TZ = timezone(timedelta(hours=5, minutes=30))
CFG = Path("instruments.yaml")

logger = TradeLogger()
monitors = {}   # name -> (monitor, meta)
cfg_cache_mtime = None

def load_cfg():
    with open(CFG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def ensure_monitors(cfg):
    global monitors
    session = cfg.get("session", "forward_test")
    symbol  = cfg.get("symbol", "BTCOPTIONS")
    expiry  = str(cfg.get("expiry", "2025-09-21"))
    defaults = cfg.get("defaults", {}) or {}
    wanted = {ins["name"]: ins for ins in (cfg.get("instruments") or [])}

    for name in list(monitors.keys()):
        if name not in wanted:
            print("[CFG] remove monitor:", name, flush=True)
            monitors.pop(name)

    for name, ins in wanted.items():
        if name in monitors:
            continue
        params = defaults.copy(); params.update(ins)
        if not params.get("delta_symbol"):
            print(f"[CFG] {name} missing delta_symbol → skipping", flush=True)
            continue
        mon = SingleOptionMonitor(
            side=params["side"],
            strike=params["strike"],
            half_size_btc=float(params.get("half_size_btc", 0.005)),
            rr_mult=float(params.get("rr_mult", 1.0)),
            trail_drop_pct=float(params.get("trail_drop_pct", 0.25)),
            rsi_bull_min=float(params.get("rsi_bull_min", 55)),
            only_on_bar_close=bool(params.get("only_on_bar_close", True)),
        )
        monitors[name] = (mon, {"session":session,"symbol":symbol,"expiry":expiry,"params":params})
        print(f"[CFG] added {name} -> {params['side']} {params['strike']}", flush=True)

def fetch_leg_snapshot(delta_symbol: str):
    """
    Pull last 100 closed 5m candles for THIS OPTION symbol,
    compute indicators, and return the latest closed bar.
    """
    df = get_candles(symbol=delta_symbol, resolution="5m", limit=100)
    df = add_indicators(df)
    last = df.iloc[-1]
    st5_dir = 1 if float(last["st_dir"]) > 0 else -1
    rsi = float(last["rsi"]) if pd.notna(last["rsi"]) else 50.0
    macd_h = float(last["macd_hist"]) if pd.notna(last["macd_hist"]) else 0.0
    mark = float(last["close"])  # option’s own close
    return st5_dir, rsi, macd_h, mark

def is_just_after_5m_close(window_s: int) -> bool:
    now_ist = datetime.now(timezone.utc).astimezone(IST_TZ)
    return (now_ist.minute % 5 == 0) and (now_ist.second < max(10, min(window_s, 30)))

def tick_all(cfg):
    loop_secs = int(cfg.get("reload_secs", 60))
    bar_closed = is_just_after_5m_close(loop_secs)

    for name, (mon, meta) in monitors.items():
        p = meta["params"]; side = p["side"]; strike = int(p["strike"])
        session, symbol, expiry = meta["session"], meta["symbol"], meta["expiry"]
        delta_symbol = p["delta_symbol"]

        try:
            st5, rsi, macd_h, mark = fetch_leg_snapshot(delta_symbol)
        except Exception as e:
            print(f"[WARN] snapshot failed for {name} ({delta_symbol}):", e, flush=True)
            continue

        acts = mon.update(
            st5_dir=st5,
            st15_dir=0,             # 15m confirm disabled for now
            rsi_value=rsi,
            macd_hist_value=macd_h,
            mark=mark,
            bar_closed=bar_closed,
        )

        direction = "BULL" if side == "CALL" else "BEAR"
        trade_id = build_trade_id(session=session, symbol=symbol, expiry=expiry,
                                  direction=direction, side=side, strike=strike)
        for a in acts:
            a.trade_id = trade_id
            a.direction = direction
            notify(format_alert(a))
            logger.log(a, session=session, symbol=symbol, expiry=expiry,
                       st5_dir=st5, st15_dir=0, rsi=rsi, macd_hist=macd_h, score=0.0)

if __name__ == "__main__":
    if not CFG.exists():
        raise SystemExit("instruments.yaml not found")
    while True:
        try:
            mtime = CFG.stat().st_mtime
            if mtime != cfg_cache_mtime:
                cfg = load_cfg()
                ensure_monitors(cfg)
                cfg_cache_mtime = mtime
            tick_all(cfg)
            time.sleep(cfg.get("reload_secs", 60))
        except Exception as e:
            print("[ERROR]", e, flush=True)
            time.sleep(5)
