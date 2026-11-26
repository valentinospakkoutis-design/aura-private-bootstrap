"""
Μέτρηση fee λογαριασμού Binance — ΜΟΝΟ ΑΝΑΓΝΩΣΗ. Καμία εντολή.

Δύο υπογεγραμμένα GET:
  GET /sapi/v1/asset/tradeFee   → maker/taker ανά σύμβολο (βασική προμήθεια λογαριασμού)
  GET /sapi/v1/bnbBurn          → αν πληρώνεται fee σε BNB (έκπτωση 25% στο spot)

Τα credentials διαβάζονται από τον πίνακα broker_credentials (ίδια αποκρυπτογράφηση με το main.py).
Τρέχει μέσα στο container:
  docker cp backend/scripts/probe_fees.py aura-backend:/tmp/probe_fees.py
  docker exec -w /app -e PYTHONPATH=/app aura-backend python /tmp/probe_fees.py [--out /tmp/fees.md]

Τα σύμβολα είναι τα 27 του λογιστικού τάσης (ml.auto_trainer.CRYPTO_SYMBOLS) και τα αντίστοιχα USDT.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from datetime import datetime, timezone

BNB_DISCOUNT = 0.25  # spot: −25% όταν spotBNBBurn=true


def _credentials():
    from database.connection import SessionLocal
    from database.models import BrokerCredential
    from utils.security import security_manager

    db = SessionLocal()
    try:
        rows = (db.query(BrokerCredential)
                  .filter(BrokerCredential.is_active == True,  # noqa: E712
                          BrokerCredential.broker_name == "binance")
                  .all())
        live = [r for r in rows if not r.testnet]
        if not live:
            sys.exit(f"Κανένα ενεργό LIVE binance credential ({len(rows)} testnet). "
                     "Το testnet δεν έχει /sapi — fee δεν μετριέται από εκεί.")
        r = live[0]
        return (security_manager.decrypt_api_key(r.encrypted_api_key),
                security_manager.decrypt_api_key(r.encrypted_api_secret), r.user_id)
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="γράψε markdown σε αρχείο")
    args = ap.parse_args()

    from brokers.binance import BinanceAPI
    try:
        from ml.auto_trainer import CRYPTO_SYMBOLS
    except Exception:  # η έκδοση του image μπορεί να διαφέρει — λίστα του dashboard
        from api.dashboard_overview import CRYPTO_SYMBOLS

    key, secret, uid = _credentials()
    api = BinanceAPI(api_key=key, api_secret=secret, testnet=False)

    fees = api._signed_request("GET", "/sapi/v1/asset/tradeFee")
    if not isinstance(fees, list):
        sys.exit(f"tradeFee απέτυχε: {fees}")
    burn = api._signed_request("GET", "/sapi/v1/bnbBurn")
    spot_burn = bool(burn.get("spotBNBBurn")) if isinstance(burn, dict) else None

    by_sym = {f["symbol"]: f for f in fees}
    usdc = list(CRYPTO_SYMBOLS)
    wanted = usdc + [s[:-4] + "USDT" for s in usdc if s.endswith("USDC")]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mult = (1 - BNB_DISCOUNT) if spot_burn else 1.0
    lines = [f"# Aura — fee λογαριασμού Binance ({now})", "",
             f"Πηγή: `GET /sapi/v1/asset/tradeFee`, `GET /sapi/v1/bnbBurn` (user_id {uid}). Καμία εντολή.", "",
             f"- **spotBNBBurn:** `{spot_burn}` → πολλαπλασιαστής {mult:.2f} στη βασική προμήθεια",
             f"- Απάντηση bnbBurn: `{burn}`", "",
             "| Σύμβολο | maker bp | taker bp | maker eff. bp | taker eff. bp |",
             "|---|---|---|---|---|"]
    missing, eff = [], {"USDC": [], "USDT": []}
    for s in wanted:
        f = by_sym.get(s)
        if not f:
            missing.append(s)
            continue
        m = float(f["makerCommission"]) * 1e4
        t = float(f["takerCommission"]) * 1e4
        lines.append(f"| {s} | {m:.2f} | {t:.2f} | {m * mult:.2f} | {t * mult:.2f} |")
        eff[s[-4:]].append((m * mult, t * mult))

    lines += [""]
    for q, v in eff.items():
        if v:
            mk = statistics.median(x[0] for x in v)
            tk = statistics.median(x[1] for x in v)
            lines.append(f"- **{q} διάμεσος (eff.):** maker {mk:.2f} bp, taker {tk:.2f} bp "
                         f"({len(v)} σύμβολα) — η υπόθεση ήταν 8,75")
    if missing:
        lines.append(f"- Δεν επιστράφηκαν (μη διαπραγματεύσιμα/delisted): {', '.join(missing)}")
    lines += ["", "Σημείωση: το tradeFee δίνει τη βασική προμήθεια· η έκπτωση BNB εφαρμόζεται στον "
              "διακανονισμό και υπολογίζεται εδώ από το spotBNBBurn. Το μείγμα maker/taker δεν "
              "μετριέται εδώ — μέχρι να μετρηθεί, το ολικό κόστος παραμένει «υπό όρους μείγματος»."]

    out = "\n".join(lines)
    print(out)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
