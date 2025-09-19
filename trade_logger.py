# trade_logger.py
import os, json, csv, time, base64
from datetime import datetime, timezone, timedelta
from pathlib import Path

_gs_sheet = None
def _init_sheets():
    """Optional Google Sheets hookup. If env vars not set, it silently skips."""
    global _gs_sheet
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        b64 = os.getenv("GOOGLE_SHEETS_CRED_B64")
        sid = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        sname = os.getenv("GOOGLE_SHEETS_SHEET_NAME","logs")
        if not (b64 and sid): 
            return
        creds_json = json.loads(base64.b64decode(b64).decode("utf-8"))
        creds = Credentials.from_service_account_info(creds_json, scopes=["https://www.googleapis.com/auth/spreadsheets"])
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
        hdr = ["ts_epoch","date","time_utc","time_ist","trade_id","session","symbol","expiry",
               "kind","direction","side","strike","stage","size_btc","mark","note",
               "st5_dir","st15_dir","rsi","macd_hist","score"]
        row1 = _gs_sheet.row_values(1)
        if row1 != hdr:
            if row1:
                _gs_sheet.insert_row(hdr, 1)
            else:
                _gs_sheet.append_row(hdr, value_input_option="RAW")
    except Exception as e:
        print("[LOGGER] Sheets init skipped:", e)

def _ist_now_str():
    return datetime.utcnow().astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M:%S IST")

class TradeLogger:
    def __init__(self, csv_path="logs/trades.csv", jsonl_path="logs/trades.jsonl"):
        Path("logs").mkdir(parents=True, exist_ok=True)
        self.csv_path = csv_path; self.jsonl_path = jsonl_path
        if not Path(self.csv_path).exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    "ts_epoch","date","time_utc","time_ist","trade_id","session","symbol","expiry",
                    "kind","direction","side","strike","stage","size_btc","mark","note",
                    "st5_dir","st15_dir","rsi","macd_hist","score"
                ])
        _init_sheets()

    def log(self, action, *, session, symbol, expiry, st5_dir, st15_dir, rsi, macd_hist, score):
        ts = time.time()
        utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        ist = _ist_now_str()
        row_dict = {
            "ts_epoch": ts,
            "date": utc.strftime("%Y-%m-%d"),
            "time_utc": utc.strftime("%H:%M:%S UTC"),
            "time_ist": ist,
            "trade_id": action.trade_id,
            "session": session, "symbol": symbol, "expiry": expiry,
            "kind": action.kind, "direction": action.direction, "side": action.side,
            "strike": int(action.strike),
            "stage": action.stage if action.stage is not None else "",
            "size_btc": action.size_btc, "mark": action.mark, "note": action.note,
            "st5_dir": st5_dir, "st15_dir": st15_dir, "rsi": rsi, "macd_hist": macd_hist, "score": score
        }

        # JSONL as object
        with open(self.jsonl_path, "a", encoding="utf-8") as jf:
            jf.write(json.dumps(row_dict) + "\n")

        # CSV
        with open(self.csv_path, "a", newline="", encoding="utf-8") as cf:
            csv.writer(cf).writerow([
                row_dict["ts_epoch"], row_dict["date"], row_dict["time_utc"], row_dict["time_ist"],
                row_dict["trade_id"], row_dict["session"], row_dict["symbol"], row_dict["expiry"],
                row_dict["kind"], row_dict["direction"], row_dict["side"], row_dict["strike"], row_dict["stage"],
                row_dict["size_btc"], row_dict["mark"], row_dict["note"],
                row_dict["st5_dir"], row_dict["st15_dir"], row_dict["rsi"], row_dict["macd_hist"], row_dict["score"]
            ])

        # Google Sheets (optional)
        if _gs_sheet:
            try:
                _gs_sheet.append_row([
                    row_dict["ts_epoch"], row_dict["date"], row_dict["time_utc"], row_dict["time_ist"],
                    row_dict["trade_id"], row_dict["session"], row_dict["symbol"], row_dict["expiry"],
                    row_dict["kind"], row_dict["direction"], row_dict["side"], row_dict["strike"], row_dict["stage"],
                    row_dict["size_btc"], row_dict["mark"], row_dict["note"],
                    row_dict["st5_dir"], row_dict["st15_dir"], row_dict["rsi"], row_dict["macd_hist"], row_dict["score"]
                ], value_input_option="RAW")
            except Exception as e:
                print("[LOGGER] Sheets append failed:", e)

def build_trade_id(*, session:str, symbol:str, expiry:str, direction:str, side:str, strike:int|float) -> str:
    return f"{session}::{symbol}-{expiry}-{direction}-{side}-K{int(strike)}"
