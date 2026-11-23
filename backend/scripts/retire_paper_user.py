"""
Turn off autopilot for one user and sell that user's paper holdings.

For retiring a duplicate or test account. Disabling alone would leave the
account's paper positions with nobody managing them, so they are sold at the
current price through the paper broker. These sales are bookkeeping on a
retired account: they do not go through the trading engine and are not written
to trade_feedback, so they cannot influence model training.

Paper only. Refuses to run for a user that is not in paper mode.

The running backend caches each user's paper portfolio in memory. To stop it
writing a stale copy back, do this in three moves: disable, restart the
backend, then sell.

Usage (inside the backend container):
    python -m scripts.retire_paper_user --user 2                           # show what would happen
    python -m scripts.retire_paper_user --user 2 --apply --only disable    # 1. stop the engine using it
    #  ... restart the backend ...
    python -m scripts.retire_paper_user --user 2 --apply --only sell       # 2. sell the paper holdings
"""

import argparse
import sys
from typing import List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Disable autopilot and flatten paper holdings for one user.")
    parser.add_argument("--user", type=int, required=True)
    parser.add_argument("--apply", action="store_true", help="Make the changes (default: dry run)")
    parser.add_argument("--only", choices=["disable", "sell"], help="Do just one of the two moves")
    args = parser.parse_args(argv)
    uid = args.user

    from sqlalchemy import text
    from database.connection import SessionLocal
    if SessionLocal is None:
        print("DATABASE_URL is not configured.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        row = db.execute(text(
            "SELECT is_enabled, config_overrides_json FROM user_autopilot_settings WHERE user_id = :u"),
            {"u": uid}).first()
        if row is None:
            print(f"user {uid}: no autopilot settings row — nothing to do")
            return 1
        overrides = row[1] if isinstance(row[1], dict) else {}
        if not overrides.get("paper_mode", False):
            print(f"user {uid} is not in paper mode — refusing to touch a non-paper account")
            return 1
        print(f"user {uid}: autopilot enabled = {bool(row[0])}, paper_mode = True")

        from brokers.paper_broker import PaperBroker
        broker = PaperBroker(user_id=uid)
        holdings = broker.get_positions()
        print(f"user {uid}: {len(holdings)} paper positions")

        if not args.apply:
            for h in holdings:
                print(f"  would sell {h['symbol']} {h['quantity']}")
            print("dry run — nothing changed. Re-run with --apply.")
            return 0

        if args.only != "sell":
            # Disable first, so the engine stops picking this user up on its next scan.
            db.execute(text("UPDATE user_autopilot_settings SET is_enabled = false WHERE user_id = :u"), {"u": uid})
            try:
                db.execute(text("UPDATE autopilot_configs SET is_enabled = false WHERE user_id = :u"), {"u": uid})
            except Exception as exc:   # table may not exist on every deployment
                db.rollback()
                db.execute(text("UPDATE user_autopilot_settings SET is_enabled = false WHERE user_id = :u"), {"u": uid})
                print(f"  note: autopilot_configs not updated ({type(exc).__name__})")
            db.commit()
            print(f"user {uid}: autopilot disabled")
        if args.only == "disable":
            return 0

        still_on = db.execute(text(
            "SELECT is_enabled FROM user_autopilot_settings WHERE user_id = :u"), {"u": uid}).scalar()
        if still_on:
            print(f"user {uid}: autopilot is still enabled — disable it before selling")
            return 1

        failed = 0
        for h in holdings:
            result = broker.place_live_order(symbol=h["symbol"], side="SELL", quantity=h["quantity"])
            if "error" in result:
                failed += 1
                print(f"  NOT sold {h['symbol']}: {result['error']}")
            else:
                print(f"  sold {h['symbol']} {h['quantity']} @ {result['price']}")
        left = broker.get_positions()
        balance = broker.get_account_balance()
        print(f"user {uid}: {len(left)} positions left, cash {balance['available_balance']:.2f}")
        if failed:
            print("  some positions had no price right now (market closed?). Re-run with --apply later.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
