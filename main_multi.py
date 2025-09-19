# main_multi.py
import os, time, yaml, random
from pathlib import Path
from otm_option_monitor import SingleOptionMonitor
from trade_logger import TradeLogger, build_trade_id
from alerts import notify, format_alert

print("[BOOT] lottery-option-bot starting...", flush=True)

CFG = Path("instruments.yaml")
logger = TradeLogger()
monitors = {}  # name -> (monitor, meta)
cfg_cache_mtime = None

def load_cfg():
    with open(CFG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def ensure_monitors(cfg):
    global monitors
    session = cfg.get("session","forward_test")
    symbol  = cfg.get("symbol","BTC")
    expiry  = cfg.get("expiry","2025-09-21")
    defaults = cfg.get("defaults",{}) or {}
    wanted = {ins["name"]: ins for ins in (cfg.get("instruments") or [])}

    # remove missing
    for name in list(monitors.keys()):
        if name not in wanted:
            print("[CFG] remove monitor:", name, flush=True)
            monitors.pop(name)

    # add new
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
            rsi_bull_min=float(params.get("rsi_bull_min", 55))
        )
        monitors[name] = (mon, {"session":session,"symbol":symbol,"expiry":expiry,"params":params})
        print(f"[CFG] added {name} -> {params['side']} {params['strike']}", flush=True)

def synthetic_snapshot():
    # Synthetic per-option snapshot so the app runs without external APIs.
    st5 = random.choice([+1, -1])
    st15 = random.choice([+1, 0, -1])
    rsi = 52 + random.uniform(-12, 12)
    macd_h = random.uniform(-0.03, 0.03)
    mark = 120 + random.uniform(-30, 60)
    score = 0.60
    return st5, st15, rsi, macd_h, mark, score

def tick_all(cfg):
    for name, (mon, meta) in monitors.items():
        p = meta["params"]; side = p["side"]; strike = int(p["strike"])
        session, symbol, expiry = meta["session"], meta["symbol"], meta["expiry"]
        st5, st15, rsi, macd_h, mark, score = synthetic_snapshot()

        acts = mon.update(st5_dir=st5, st15_dir=st15, rsi_value=rsi, macd_hist_value=macd_h, mark=mark)
        direction = "BULL" if side=="CALL" else "BEAR"
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
