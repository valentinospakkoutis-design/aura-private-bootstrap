"""Trailing stop helpers for auto-trading positions."""

from typing import Tuple


class TrailingStopService:
    def initialize_stop(self, side: str, entry_price: float, trail_pct: float = 2.0) -> float:
        pct = max(0.1, float(trail_pct)) / 100.0
        if side == "BUY":
            return round(float(entry_price) * (1.0 - pct), 8)
        return round(float(entry_price) * (1.0 + pct), 8)

    def update_stop(self, position: dict, current_price: float, trail_pct: float = 2.0) -> Tuple[float, bool, str]:
        side = str(position.get("side", "BUY")).upper()
        current_stop = float(position.get("trailing_stop") or position.get("stop_loss") or 0.0)
        candidate = self.initialize_stop(side=side, entry_price=float(current_price), trail_pct=trail_pct)

        if side == "BUY":
            new_stop = max(current_stop, candidate)
            moved = new_stop > current_stop
            move_dir = "up" if moved else "none"
        else:
            new_stop = min(current_stop, candidate) if current_stop > 0 else candidate
            moved = new_stop < current_stop or current_stop == 0
            move_dir = "down" if moved else "none"

        return round(new_stop, 8), moved, move_dir

    def should_stop(self, position: dict, current_price: float) -> bool:
        side = str(position.get("side", "BUY")).upper()
        stop_price = float(position.get("trailing_stop") or position.get("stop_loss") or 0.0)
        if stop_price <= 0:
            return False

        px = float(current_price)
        if side == "BUY":
            return px <= stop_price
        return px >= stop_price


trailing_stop_service = TrailingStopService()
