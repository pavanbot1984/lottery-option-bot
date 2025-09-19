# alerts.py
import os, requests
from datetime import datetime, timezone, timedelta

BOT = os.getenv("TG_BOT_TOKEN")
CHAT = os.getenv("TG_CHAT_ID")

def ist_now():
    return datetime.utcnow().astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M:%S IST")

def notify(text: str):
    if BOT and CHAT:
        try:
            requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage", data={"chat_id": CHAT, "text": text}, timeout=6)
        except Exception as e:
            print("[ALERT ERROR]", e, text)
    else:
        print("[ALERT]", text)

def format_alert(a):
    size_txt = f"{a.size_btc:.6f} BTC" if a.size_btc and a.size_btc>0 else "-"
    mark_txt = f"~{a.mark:.2f}" if a.mark and a.mark>0 else "-"
    head = {"ENTRY50":"🎟️ ENTRY50","ADD50":"🎟️ ADD50","EXIT_SL":"❌ EXIT_SL","TP_HIT":"✅ TP_HIT","TRAIL_UPDATE":"ℹ️ TRAIL_UPDATE","TRAIL_EXIT":"🏁 TRAIL_EXIT"}.get(a.kind,"ℹ️ SIGNAL")
    return f"{head} | {a.side} K{int(a.strike)} | {size_txt} @ {mark_txt} | {ist_now()}\n{a.note}\ntrade_id: {a.trade_id}"
