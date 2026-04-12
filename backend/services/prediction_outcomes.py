"""Prediction tracking and evaluation service."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from database.connection import SessionLocal


class PredictionOutcomesService:
    def _ensure_table(self):
        db = SessionLocal()
        try:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS prediction_outcomes (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    action VARCHAR NOT NULL,
                    confidence FLOAT NOT NULL,
                    price_at_prediction FLOAT NOT NULL,
                    onchain_score FLOAT,
                    onchain_sentiment VARCHAR,
                    price_7d_later FLOAT,
                    price_30d_later FLOAT,
                    was_correct_7d BOOLEAN,
                    was_correct_30d BOOLEAN,
                    pnl_7d_pct FLOAT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    evaluated_at TIMESTAMP
                )
            """))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_prediction_outcomes_symbol ON prediction_outcomes (symbol)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_prediction_outcomes_created_at ON prediction_outcomes (created_at DESC)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_prediction_outcomes_eval_7d ON prediction_outcomes (was_correct_7d, created_at)"))
            db.execute(text("ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS onchain_score FLOAT"))
            db.execute(text("ALTER TABLE prediction_outcomes ADD COLUMN IF NOT EXISTS onchain_sentiment VARCHAR"))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _normalize_conf_pct(self, confidence: float) -> float:
        c = float(confidence or 0.0)
        if c <= 1.0:
            c *= 100.0
        return max(0.0, min(100.0, c))

    def _get_current_price(self, symbol: str) -> float:
        try:
            from ai.asset_predictor import asset_predictor
            return float(asset_predictor.get_current_price(symbol) or 0.0)
        except Exception:
            return 0.0

    def track_prediction(
        self,
        symbol: str,
        action: str,
        confidence: float,
        price_at_prediction: float,
        onchain: Optional[Dict[str, Any]] = None,
    ):
        self._ensure_table()
        db = SessionLocal()
        try:
            db.execute(
                text(
                    """
                    INSERT INTO prediction_outcomes (
                        symbol, action, confidence, price_at_prediction, onchain_score, onchain_sentiment
                    )
                    VALUES (
                        :symbol, :action, :confidence, :price_at_prediction, :onchain_score, :onchain_sentiment
                    )
                    """
                ),
                {
                    "symbol": str(symbol or "").upper(),
                    "action": str(action or "HOLD").upper(),
                    "confidence": float(confidence or 0.0),
                    "price_at_prediction": float(price_at_prediction or 0.0),
                    "onchain_score": float((onchain or {}).get("score") or 0.0) if onchain else None,
                    "onchain_sentiment": str((onchain or {}).get("sentiment") or "") if onchain else None,
                },
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    def _compute_correctness(self, action: str, price_then: float, price_now: float) -> bool:
        a = (action or "").upper()
        if a == "BUY":
            return price_now > price_then
        if a == "SELL":
            return price_now < price_then
        return False

    def _compute_directional_pnl_pct(self, action: str, price_then: float, price_now: float) -> float:
        if price_then <= 0:
            return 0.0
        raw = ((price_now - price_then) / price_then) * 100.0
        if (action or "").upper() == "SELL":
            raw = -raw
        return round(raw, 4)

    def evaluate_predictions(self) -> Dict:
        """Evaluate pending predictions at 7d and 30d horizons."""
        self._ensure_table()
        db = SessionLocal()
        evaluated_7d = 0
        evaluated_30d = 0
        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        try:
            pending_7d = db.execute(
                text(
                    """
                    SELECT id, symbol, action, price_at_prediction
                    FROM prediction_outcomes
                    WHERE was_correct_7d IS NULL
                      AND created_at <= :cutoff
                    ORDER BY created_at ASC
                    LIMIT 2000
                    """
                ),
                {"cutoff": seven_days_ago},
            ).mappings().all()

            for row in pending_7d:
                price_then = float(row["price_at_prediction"] or 0.0)
                price_now = self._get_current_price(str(row["symbol"]))
                if price_then <= 0 or price_now <= 0:
                    continue
                was_correct = self._compute_correctness(str(row["action"]), price_then, price_now)
                pnl_7d = self._compute_directional_pnl_pct(str(row["action"]), price_then, price_now)

                db.execute(
                    text(
                        """
                        UPDATE prediction_outcomes
                        SET price_7d_later = :price_7d_later,
                            was_correct_7d = :was_correct_7d,
                            pnl_7d_pct = :pnl_7d_pct,
                            evaluated_at = NOW()
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": int(row["id"]),
                        "price_7d_later": price_now,
                        "was_correct_7d": bool(was_correct),
                        "pnl_7d_pct": float(pnl_7d),
                    },
                )
                evaluated_7d += 1

            pending_30d = db.execute(
                text(
                    """
                    SELECT id, symbol, action, price_at_prediction
                    FROM prediction_outcomes
                    WHERE was_correct_30d IS NULL
                      AND created_at <= :cutoff
                    ORDER BY created_at ASC
                    LIMIT 2000
                    """
                ),
                {"cutoff": thirty_days_ago},
            ).mappings().all()

            for row in pending_30d:
                price_then = float(row["price_at_prediction"] or 0.0)
                price_now = self._get_current_price(str(row["symbol"]))
                if price_then <= 0 or price_now <= 0:
                    continue
                was_correct = self._compute_correctness(str(row["action"]), price_then, price_now)
                db.execute(
                    text(
                        """
                        UPDATE prediction_outcomes
                        SET price_30d_later = :price_30d_later,
                            was_correct_30d = :was_correct_30d,
                            evaluated_at = COALESCE(evaluated_at, NOW())
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": int(row["id"]),
                        "price_30d_later": price_now,
                        "was_correct_30d": bool(was_correct),
                    },
                )
                evaluated_30d += 1

            db.commit()
            return {
                "success": True,
                "evaluated_7d": evaluated_7d,
                "evaluated_30d": evaluated_30d,
            }
        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "error": str(e),
                "evaluated_7d": evaluated_7d,
                "evaluated_30d": evaluated_30d,
            }
        finally:
            db.close()

    def get_accuracy(self, symbol: Optional[str] = None) -> Dict:
        self._ensure_table()
        db = SessionLocal()
        try:
            params = {}
            where = "WHERE was_correct_7d IS NOT NULL"
            if symbol:
                where += " AND symbol = :symbol"
                params["symbol"] = symbol.upper()

            rows = db.execute(
                text(
                    f"""
                    SELECT symbol, confidence, was_correct_7d
                    FROM prediction_outcomes
                    {where}
                    """
                ),
                params,
            ).mappings().all()

            total = len(rows)
            correct = sum(1 for r in rows if bool(r["was_correct_7d"]))
            overall = round((correct / total) * 100.0, 2) if total else 0.0

            bands = {
                "90-100": {"count": 0, "correct": 0},
                "80-90": {"count": 0, "correct": 0},
                "70-80": {"count": 0, "correct": 0},
            }

            by_symbol_counts: Dict[str, Dict[str, int]] = {}
            for r in rows:
                sym = str(r["symbol"])
                conf_pct = self._normalize_conf_pct(float(r["confidence"] or 0.0))
                ok = bool(r["was_correct_7d"])

                if sym not in by_symbol_counts:
                    by_symbol_counts[sym] = {"count": 0, "correct": 0}
                by_symbol_counts[sym]["count"] += 1
                by_symbol_counts[sym]["correct"] += 1 if ok else 0

                if 90 <= conf_pct <= 100:
                    band = "90-100"
                elif 80 <= conf_pct < 90:
                    band = "80-90"
                elif 70 <= conf_pct < 80:
                    band = "70-80"
                else:
                    band = None

                if band:
                    bands[band]["count"] += 1
                    bands[band]["correct"] += 1 if ok else 0

            by_confidence_band = {}
            for k, v in bands.items():
                acc = round((v["correct"] / v["count"]) * 100.0, 2) if v["count"] else 0.0
                by_confidence_band[k] = {"accuracy": acc, "count": v["count"]}

            symbol_accuracy_items = []
            for sym, v in by_symbol_counts.items():
                if v["count"] <= 0:
                    continue
                acc = round((v["correct"] / v["count"]) * 100.0, 2)
                symbol_accuracy_items.append({"symbol": sym, "accuracy": acc, "count": v["count"]})
            symbol_accuracy_items.sort(key=lambda x: x["accuracy"], reverse=True)

            best_assets = [x["symbol"] for x in symbol_accuracy_items[:2]]
            worst_assets = [x["symbol"] for x in sorted(symbol_accuracy_items, key=lambda x: x["accuracy"])[:2]]

            per_symbol_accuracy = {x["symbol"]: x["accuracy"] for x in symbol_accuracy_items}

            response = {
                "overall_accuracy_7d": overall,
                "total_evaluated": total,
                "by_confidence_band": by_confidence_band,
                "best_assets": best_assets,
                "worst_assets": worst_assets,
                "per_symbol_accuracy": per_symbol_accuracy,
            }
            if symbol:
                response["symbol"] = symbol.upper()
            return response
        except Exception:
            return {
                "overall_accuracy_7d": 0.0,
                "total_evaluated": 0,
                "by_confidence_band": {
                    "90-100": {"accuracy": 0.0, "count": 0},
                    "80-90": {"accuracy": 0.0, "count": 0},
                    "70-80": {"accuracy": 0.0, "count": 0},
                },
                "best_assets": [],
                "worst_assets": [],
                "per_symbol_accuracy": {},
                "symbol": symbol.upper() if symbol else None,
            }
        finally:
            db.close()


    def get_accuracy_by_onchain_bucket(self, symbol: Optional[str] = None, days: int = 30) -> Dict:
        """Get accuracy analytics bucketed by on-chain score ranges."""
        self._ensure_table()
        db = SessionLocal()
        try:
            params = {"days": days}
            where = f"""
                WHERE was_correct_7d IS NOT NULL
                  AND onchain_score IS NOT NULL
                  AND created_at >= NOW() - INTERVAL '{days} days'
            """
            if symbol:
                where += " AND symbol = :symbol"
                params["symbol"] = str(symbol or "").upper()

            rows = db.execute(
                text(
                    f"""
                    SELECT 
                        onchain_score, 
                        onchain_sentiment, 
                        was_correct_7d, 
                        symbol,
                        action
                    FROM prediction_outcomes
                    {where}
                    ORDER BY onchain_score DESC
                    """
                ),
                params,
            ).mappings().all()

            # Define buckets: 0-0.25, 0.25-0.5, 0.5-0.75, 0.75-1.0
            buckets = {
                "0.00-0.25": {"count": 0, "hits": 0, "sentiments": {}},
                "0.25-0.50": {"count": 0, "hits": 0, "sentiments": {}},
                "0.50-0.75": {"count": 0, "hits": 0, "sentiments": {}},
                "0.75-1.00": {"count": 0, "hits": 0, "sentiments": {}},
            }

            for row in rows:
                score = float(row["onchain_score"] or 0.0)
                sentiment = str(row["onchain_sentiment"] or "unknown").lower()
                is_correct = bool(row["was_correct_7d"])

                # Assign to bucket
                if score < 0.25:
                    bucket_key = "0.00-0.25"
                elif score < 0.5:
                    bucket_key = "0.25-0.50"
                elif score < 0.75:
                    bucket_key = "0.50-0.75"
                else:
                    bucket_key = "0.75-1.00"

                buckets[bucket_key]["count"] += 1
                if is_correct:
                    buckets[bucket_key]["hits"] += 1

                # Track sentiment distribution in bucket
                if sentiment not in buckets[bucket_key]["sentiments"]:
                    buckets[bucket_key]["sentiments"][sentiment] = 0
                buckets[bucket_key]["sentiments"][sentiment] += 1

            # Calculate hit rates and correlations
            total_predictions = len(rows)
            total_hits = sum(1 for r in rows if bool(r["was_correct_7d"]))
            overall_correlation = round((total_hits / total_predictions) * 100.0, 2) if total_predictions else 0.0

            bucket_results = []
            for bucket_key in ["0.00-0.25", "0.25-0.50", "0.50-0.75", "0.75-1.00"]:
                b = buckets[bucket_key]
                hit_rate = round((b["hits"] / b["count"]) * 100.0, 2) if b["count"] else 0.0
                bucket_results.append({
                    "range": bucket_key,
                    "hit_rate": hit_rate,
                    "count": b["count"],
                    "hits": b["hits"],
                    "sentiment_distribution": b["sentiments"],
                })

            response = {
                "symbol": symbol.upper() if symbol else "ALL",
                "days": days,
                "total_predictions": total_predictions,
                "overall_correlation": overall_correlation,
                "buckets": bucket_results,
                "best_bucket": max(bucket_results, key=lambda x: x["hit_rate"]) if bucket_results else {},
                "worst_bucket": min(bucket_results, key=lambda x: x["hit_rate"]) if bucket_results else {},
            }
            return response
        except Exception as e:
            return {
                "error": str(e),
                "symbol": symbol.upper() if symbol else "ALL",
                "days": days,
                "buckets": [],
                "overall_correlation": 0.0,
            }
        finally:
            db.close()


prediction_outcomes_service = PredictionOutcomesService()
