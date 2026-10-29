import asyncio, logging, time
from datetime import datetime, timezone
import httpx

log = logging.getLogger("aura.xag_alerts")

TELEGRAM_BOT_TOKEN = None
TELEGRAM_CHAT_ID   = "6296218911"
POLL_INTERVAL_SEC        = 30
DISCONNECT_THRESHOLD_SEC = 60
NO_TICK_THRESHOLD_SEC    = 120
ALERT_COOLDOWN_SEC       = 300
_last_alert_sent: dict = {}

def _is_market_hours():
    now = datetime.now(timezone.utc)
    wd, h = now.weekday(), now.hour
    if wd == 5: return False
    if wd == 6 and h < 21: return False
    if wd == 4 and h >= 22: return False
    return True

def _can_send(key):
    return (time.monotonic() - _last_alert_sent.get(key, 0.0)) >= ALERT_COOLDOWN_SEC

def _mark_sent(key):
    _last_alert_sent[key] = time.monotonic()

async def _send_telegram(message):
    if not TELEGRAM_BOT_TOKEN:
        log.warning("XAG_TELEGRAM_BOT_TOKEN not set")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
            if r.status_code != 200:
                log.error("Telegram failed: %s %s", r.status_code, r.text)
    except Exception as e:
        log.error("Telegram exception: %s", e)

async def mt5_alert_monitor():
    log.info("MT5 alert monitor started (poll=%ss)", POLL_INTERVAL_SEC)
    await asyncio.sleep(15)
    while True:
        try:
            data = None
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.get("http://localhost:8080/api/xag/healthz")
                    if r.status_code == 200:
                        data = r.json()
            except Exception as e:
                log.debug("healthz fetch error: %s", e)

            if data is None:
                if _can_send("healthz_down"):
                    await _send_telegram("WARNING Aura XAG Monitor - Could not reach /api/xag/healthz")
                    _mark_sent("healthz_down")
            else:
                age = data.get("last_tick_age_seconds", 9999)
                mt5_ok = data.get("mt5_connected", False)
                if not mt5_ok or age > DISCONNECT_THRESHOLD_SEC:
                    if _can_send("mt5_disconnected"):
                        await _send_telegram(
                            f"ALERT Aura - MT5 Bridge Disconnected\n"
                            f"mt5_connected: {mt5_ok}\n"
                            f"Last tick: {age:.0f}s ago\n"
                            f"Check bridge on Windows PC port 8765")
                        _mark_sent("mt5_disconnected")
                else:
                    _last_alert_sent.pop("mt5_disconnected", None)
                if age > NO_TICK_THRESHOLD_SEC and _is_market_hours():
                    if _can_send("no_ticks"):
                        await _send_telegram(
                            f"ALERT Aura - No Ticks ({age:.0f}s)\n"
                            f"Market open but no ticks for {age:.0f}s")
                        _mark_sent("no_ticks")
        except Exception as e:
            log.error("Alert monitor loop error: %s", e)
        await asyncio.sleep(POLL_INTERVAL_SEC)

def init_alerts(bot_token):
    global TELEGRAM_BOT_TOKEN
    TELEGRAM_BOT_TOKEN = bot_token
    if not bot_token:
        log.warning("XAG_TELEGRAM_BOT_TOKEN not set - MT5 alerts disabled")
    else:
        log.info("MT5 alert monitor initialized (chat_id=%s)", TELEGRAM_CHAT_ID)
