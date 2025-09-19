# main_multi.py
import time, yaml
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
    """Create/remove monitors to match the YAML."""
    global monitors
    session = cfg.get("session", "forward_test")
    symbol  = cfg.get("symbol", "BTCUSD")   # <- using Delta spot perpetual symbol for 5m candles
    expiry  = str(cfg.get("expiry", "2025-09-21"))
    defaults = cfg.get("defaults", {}) or {}
    wanted = {ins["name"]: ins for ins in (cfg.get("instruments") or [])}

    # Remove missing
    for name in list(monitors.keys()):
        if name not in wanted:
            print("[CFG] remove monitor:", name, flush=True)
            monitors.pop(name)

    # Add new
    for name, ins in wanted.items():
        if name in monitors:
            continue
        params = defaults.copy(); params.update(ins)
        mon = SingleOptionMonitor(
            side=params["side"],
            strike=params["strike"],
            half_size_btc=float(params.get("half_size_btc", 0.005)),
            rr_mult=float(params.get("rr_mult", 1.0)),
            trail_drop_pct=float(params.get("trail_drop_pct", 0.25)),
            rsi_bull_min=float(params.get("rsi_bull_min", 55)),
            only_on_bar_close=bool(params.get("only_on_bar_close", True)),
        )
        monitors[name] = (mon, {"session": session, "symbol": symbol, "expiry": expiry, "params": params})
        print(f"[CFG] added {name} -> {params['side']} {params['strike']}", flush=True)

def fetch_snapshot(symbol: str):
    """
    Pull last 100 *closed* 5m candles from Delta for `symbol`,
    compute indicators, and return the latest closed bar snapshot.
    """
    df = get_candles(symbol=symbol, resolution="5m", limit=100)
    df = add_indicators(df)
    last = df.iloc[-1]  # last closed bar
    st5_dir = 1 if float(last["st_dir"]) > 0 else -1
    # For now 15m confirm is disabled; keep neutral (0) to avoid ADD logic dependence.
    st15_dir = 0
    rsi = float(last["rsi"]) if pd.notna(last["rsi"]) else 50.0
    macd_h = float(last["macd_hist"]) if pd.notna(last["macd_hist"]) else 0.0
    mark = float(last["close"])
    score = 0.0
    return st5_dir, st15_dir, rsi, macd_h, mark, score

def is_just_after_5m_close(window_s: int) -> bool:
    """
    True only in the first window_s seconds after a 5m boundary in IST.
    Ensures we act on bar close only.
    """
    now_ist = datetime.now(timezone.utc).astimezone(IST_TZ)
    return (now_ist.minute % 5 == 0) and (now_ist.second < max(5, min(window_s, 20)))

def tick_all(cfg):
    loop_secs = int(cfg.get("reload_secs", 30))
    # Only run decisions right after each 5m close
    bar_closed = is_just_after_5m_close(loop_secs)

    for name, (mon, meta) in monitors.items():
        p = meta["params"]; side = p["side"]; strike = int(p["strike"])
        session, symbol, expiry = meta["session"], meta["symbol"], meta["expiry"]

        st5, st15, rsi, macd_h, mark, score = fetch_snapshot(symbol=symbol)

        acts = mon.update(
            st5_dir=st5,
            st15_dir=st15,
            rsi_value=rsi,
            macd_hist_value=macd_h,
            mark=mark,
            bar_closed=bar_closed,
        )
        direction = "BULL" if side == "CALL" else "BEAR"
        trade_id = build_trade_id(session=session, symbol=symbol, expiry=expiry, direction=direction, side=side, strike=strike)
        for a in acts:
            a.trade_id = trade_id
            a.direction = direction
            notify(format_alert(a))
            logger.log(a, session=session, symbol=symbol, expiry=expiry,
                       st5_dir=st5, st15_dir=st15, rsi=rsi, macd_hist=macd_h, score=score)

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
            time.sleep(cfg.get("reload_secs", 30))
        except Exception as e:
            print("[ERROR]", e, flush=True)
            time.sleep(5)
