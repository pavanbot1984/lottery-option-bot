# trade_logger.py
import os, json, csv, time, base64
from datetime import datetime, timezone, timedelta
from pathlib import Path

# --- Optional Telegram (for startup ping) ---
import requests

_TG_TOKEN = os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
_TG_CHAT  = os.getenv("TG_CHAT_ID")   or os.getenv("TELEGRAM_CHAT_ID")

def _ist_tz():
    return timezone(timedelta(hours=5, minutes=30))

def _now_ist_str():
    return datetime.now(_ist_tz()).strftime("%Y-%m-%d %H:%M:%S IST")

def _tg_send(text: str):
    """Best-effort Telegram send; no throw."""
    if not (_TG_TOKEN and _TG_CHAT):
        return
    try:
        for cid in str(_TG_CHAT).split(","):
            cid = cid.strip()
            if not cid:
                continue
            requests.post(
                f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
                data={"chat_id": cid, "text": text},
                timeout=6,
            )
    except Exception as e:
        print("[LOGGER] Telegram send failed:", e)

# --- Optional Google Sheets support ---
_gs_sheet = None

def _init_sheets():
    """Optional Google Sheets hookup. If env vars not set, it silently skips."""
    global _gs_sheet
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        b64 = os.getenv("GOOGLE_SHEETS_CRED_B64")
        sid = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        sname = os.getenv("GOOGLE_SHEETS_SHEET_NAME", "logs")
        if not (b64 and sid):
            return
        creds_json = json.loads(base64.b64decode(b64).decode("utf-8"))
        creds = Credentials.from_service_account_info(
            creds_json,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        sh = client.open_by_key(sid)
        # ensure worksheet
        for ws in sh.worksheets():
            if ws.title == sname:
                _gs_sheet = ws
                break
        if _gs_sheet is None:
            _gs_sheet = sh.add_worksheet(title=sname, rows=1000, cols=25)
        # header
        hdr = [
            "ts_epoch","date","time_utc","time_ist","trade_id",
            "session","symbol","expiry","kind","direction","side",
            "strike","stage","size_btc","mark","note",
            "st5_dir","st15_dir","rsi","macd_hist","score",
        ]
        row1 = _gs_sheet.row_values(1)
        if row1 != hdr:
            if row1:
                _gs_sheet.insert_row(hdr, 1)
            else:
                _gs_sheet.append_row(hdr, value_input_option="RAW")
    except Exception as e:
        print("[LOGGER] Sheets init skipped:", e)

class TradeLogger:
    def __init__(self, csv_path="logs/trades.csv", jsonl_path="logs/trades.jsonl"):
        Path("logs").mkdir(parents=True, exist_ok=True)
        self.csv_path = csv_path
        self.jsonl_path = jsonl_path

        # CSV header if missing
        if not Path(self.csv_path).exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    "ts_epoch","date","time_utc","time_ist","trade_id",
                    "session","symbol","expiry","kind","direction","side",
                    "strike","stage","size_btc","mark","note",
                    "st5_dir","st15_dir","rsi","macd_hist","score",
                ])

        # Optional integrations
        _init_sheets()

        # Startup ping (optional; only if TG envs exist)
        if _TG_TOKEN and _TG_CHAT:
            _tg_send(f"🤖 lottery-option-bot started at {_now_ist_str()}")

    def log(
        self,
        action,
        *,
        session,
        symbol,
        expiry,
        st5_dir,
        st15_dir,
        rsi,
        macd_hist,
        score,
    ):
        """Persist a trade event to JSONL, CSV, and optionally Google Sheets."""
        ts = time.time()
        # UTC + IST strings (IST is your display truth)
        utc_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        time_ist = _now_ist_str()

        # normalize types (avoid YAML date objects, Decimals, etc.)
        row_dict = {
            "ts_epoch": float(ts),
            "date": utc_dt.strftime("%Y-%m-%d"),
            "time_utc": utc_dt.strftime("%H:%M:%S UTC"),
            "time_ist": time_ist,
            "trade_id": str(getattr(action, "trade_id", "")),
            "session": str(session),
            "symbol": str(symbol),
            "expiry": str(expiry),  # <- critical: force string
            "kind": str(getattr(action, "kind", "")),
            "direction": str(getattr(action, "direction", "")),
            "side": str(getattr(action, "side", "")),
            "strike": int(getattr(action, "strike", 0)),
            "stage": getattr(action, "stage", ""),
            "size_btc": float(getattr(action, "size_btc", 0.0) or 0.0),
            "mark": float(getattr(action, "mark", 0.0) or 0.0),
            "note": str(getattr(action, "note", "")),
            "st5_dir": int(st5_dir),
            "st15_dir": int(st15_dir),
            "rsi": float(rsi),
            "macd_hist": float(macd_hist),
            "score": float(score),
        }

        # JSONL
        try:
            with open(self.jsonl_path, "a", encoding="utf-8") as jf:
                jf.write(json.dumps(row_dict) + "\n")
        except Exception as e:
            print("[LOGGER] JSONL write failed:", e)

        # CSV
        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8") as cf:
                csv.writer(cf).writerow(list(row_dict.values()))
        except Exception as e:
            print("[LOGGER] CSV write failed:", e)

        # Google Sheets (optional)
        if _gs_sheet:
            try:
                _gs_sheet.append_row(list(row_dict.values()), value_input_option="RAW")
            except Exception as e:
                print("[LOGGER] Sheets append failed:", e)

def build_trade_id(*, session: str, symbol: str, expiry: str, direction: str, side: str, strike: int | float) -> str:
    return f"{session}::{symbol}-{expiry}-{direction}-{side}-K{int(strike)}"
