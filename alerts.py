# alerts.py
import os
import requests
from datetime import datetime, timezone, timedelta

# Accept BOTH naming styles
BOT  = os.getenv("TG_BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
CHAT = os.getenv("TG_CHAT_ID")   or os.getenv("TELEGRAM_CHAT_ID")

IST_TZ = timezone(timedelta(hours=5, minutes=30))

def ist_now() -> str:
    """Return current time in IST using aware UTC→IST conversion."""
    return datetime.now(timezone.utc).astimezone(IST_TZ).strftime("%Y-%m-%d %H:%M:%S IST")

def _send_one(chat_id: str, text: str) -> None:
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT}/sendMessage",
            data={"chat_id": chat_id.strip(), "text": text},
            timeout=6,
        )
    except Exception as e:
        # Don't crash the app because Telegram failed
        print("[ALERT TG ERROR]", e, text)

def notify(text: str) -> None:
    """Send alert to Telegram if configured; else print to console."""
    if BOT and CHAT:
        for cid in str(CHAT).split(","):
            cid = cid.strip()
            if cid:
                _send_one(cid, text)
    else:
        print("[ALERT]", text)

def format_alert(a) -> str:
    """Human-friendly alert text for a trade action dataclass."""
    size_txt = f"{a.size_btc:.6f} BTC" if getattr(a, "size_btc", 0) else "-"
    mark_val = getattr(a, "mark", 0.0)
    mark_txt = f"~{mark_val:.2f}" if mark_val else "-"
    head = {
        "ENTRY50": "🎟️ ENTRY50",
        "ADD50": "🎟️ ADD50",
        "EXIT_SL": "❌ EXIT_SL",
        "TP_HIT": "✅ TP_HIT",
        "TRAIL_UPDATE": "ℹ️ TRAIL_UPDATE",
        "TRAIL_EXIT": "🏁 TRAIL_EXIT",
    }.get(getattr(a, "kind", ""), "ℹ️ SIGNAL")

    return (
        f"{head} | {a.side} K{int(a.strike)} | {size_txt} @ {mark_txt} | {ist_now()}\n"
        f"{getattr(a, 'note', '')}\n"
        f"trade_id: {getattr(a, 'trade_id', '')}"
    )
