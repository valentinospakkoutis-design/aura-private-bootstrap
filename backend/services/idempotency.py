"""
Durable idempotency service for order submissions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from cache.connection import get_redis
from database.connection import SessionLocal
from database.models import OrderSubmissionLedger

IDEMPOTENCY_TTL_SECONDS = 60 * 60 * 24


class IdempotencyService:
    """Provides durable deduplication for order submission routes."""

    @staticmethod
    def _unavailable_exception() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "IDEMPOTENCY_UNAVAILABLE",
                "message": "Idempotency backend unavailable. Order submission blocked.",
            },
        )

    @staticmethod
    def build_fingerprint(payload: Dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _redis_get(self, key: str) -> Optional[Dict[str, Any]]:
        client = get_redis()
        if client is None:
            return None
        raw = client.get(key)
        if not raw:
            return None
        return json.loads(raw)

    def _redis_set(self, key: str, value: Dict[str, Any], only_if_missing: bool = False) -> bool:
        client = get_redis()
        if client is None:
            return False
        payload = json.dumps(value)
        return bool(client.set(key, payload, ex=IDEMPOTENCY_TTL_SECONDS, nx=only_if_missing))

    @staticmethod
    def _db_get(principal_id: str, idempotency_key: str) -> Optional[OrderSubmissionLedger]:
        db = SessionLocal()
        try:
            return (
                db.query(OrderSubmissionLedger)
                .filter(
                    OrderSubmissionLedger.principal_id == principal_id,
                    OrderSubmissionLedger.idempotency_key == idempotency_key,
                )
                .first()
            )
        finally:
            db.close()

    @staticmethod
    def _record_to_dict(record: OrderSubmissionLedger) -> Dict[str, Any]:
        return {
            "principal_id": record.principal_id,
            "endpoint": record.endpoint,
            "idempotency_key": record.idempotency_key,
            "request_fingerprint": record.request_fingerprint,
            "status": record.status,
            "result_order_id": record.result_order_id,
            "result_payload": record.result_payload,
            "error_message": record.error_message,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "processed_at": record.processed_at.isoformat() if record.processed_at else None,
        }

    def _db_create_processing(
        self,
        principal_id: str,
        endpoint: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            record = OrderSubmissionLedger(
                principal_id=principal_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                status="processing",
                created_at=datetime.utcnow(),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._record_to_dict(record)
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(OrderSubmissionLedger)
                .filter(
                    OrderSubmissionLedger.principal_id == principal_id,
                    OrderSubmissionLedger.idempotency_key == idempotency_key,
                )
                .first()
            )
            return self._record_to_dict(existing) if existing else None
        except Exception:
            db.rollback()
            return None
        finally:
            db.close()

    def _db_update(
        self,
        principal_id: str,
        idempotency_key: str,
        *,
        status_value: str,
        result_order_id: Optional[str],
        result_payload: Optional[Dict[str, Any]],
        error_message: Optional[str],
    ) -> bool:
        db = SessionLocal()
        try:
            record = (
                db.query(OrderSubmissionLedger)
                .filter(
                    OrderSubmissionLedger.principal_id == principal_id,
                    OrderSubmissionLedger.idempotency_key == idempotency_key,
                )
                .first()
            )
            if not record:
                return False
            record.status = status_value
            record.result_order_id = result_order_id
            record.result_payload = result_payload
            record.error_message = error_message
            record.processed_at = datetime.utcnow()
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()

    def begin_request(
        self,
        *,
        principal_id: str,
        endpoint: str,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> Dict[str, Any]:
        """
        Reserve idempotency key and determine whether to proceed, replay, or reject.
        """
        redis_key = f"idempotency:{principal_id}:{idempotency_key}"
        processing_record = {
            "principal_id": principal_id,
            "endpoint": endpoint,
            "idempotency_key": idempotency_key,
            "request_fingerprint": request_fingerprint,
            "status": "processing",
            "created_at": datetime.utcnow().isoformat(),
            "processed_at": None,
            "result_order_id": None,
            "result_payload": None,
            "error_message": None,
        }

        # Redis primary: atomic reservation with NX.
        try:
            created = self._redis_set(redis_key, processing_record, only_if_missing=True)
            if created:
                return {"action": "proceed", "backend": "redis"}

            existing = self._redis_get(redis_key)
            if existing:
                return self._classify_existing(existing, request_fingerprint)
        except Exception:
            pass

        # DB fallback: durable record.
        try:
            existing_db = self._db_get(principal_id, idempotency_key)
        except Exception:
            raise self._unavailable_exception()

        if existing_db is None:
            try:
                created_db = self._db_create_processing(
                    principal_id=principal_id,
                    endpoint=endpoint,
                    idempotency_key=idempotency_key,
                    request_fingerprint=request_fingerprint,
                )
            except Exception:
                raise self._unavailable_exception()
            if created_db is None:
                raise self._unavailable_exception()
            if created_db["status"] == "processing" and created_db["request_fingerprint"] == request_fingerprint:
                return {"action": "proceed", "backend": "db"}
            return self._classify_existing(created_db, request_fingerprint)

        return self._classify_existing(self._record_to_dict(existing_db), request_fingerprint)

    @staticmethod
    def _classify_existing(existing: Dict[str, Any], request_fingerprint: str) -> Dict[str, Any]:
        if existing.get("request_fingerprint") != request_fingerprint:
            return {
                "action": "conflict",
                "http_status": status.HTTP_409_CONFLICT,
                "error": "IDEMPOTENCY_KEY_REUSE_MISMATCH",
                "message": "Idempotency key already used with a different request payload.",
                "existing": existing,
            }

        if existing.get("status") == "succeeded":
            return {"action": "replay", "existing": existing}

        if existing.get("status") == "failed":
            return {
                "action": "replay_failed",
                "existing": existing,
            }

        return {
            "action": "in_progress",
            "http_status": status.HTTP_409_CONFLICT,
            "error": "IDEMPOTENCY_IN_PROGRESS",
            "message": "An order with this idempotency key is already being processed.",
            "existing": existing,
        }

    def finalize_success(
        self,
        *,
        principal_id: str,
        endpoint: str,
        idempotency_key: str,
        request_fingerprint: str,
        result_order_id: Optional[str],
        result_payload: Dict[str, Any],
    ) -> None:
        record = {
            "principal_id": principal_id,
            "endpoint": endpoint,
            "idempotency_key": idempotency_key,
            "request_fingerprint": request_fingerprint,
            "status": "succeeded",
            "result_order_id": result_order_id,
            "result_payload": result_payload,
            "error_message": None,
            "processed_at": datetime.utcnow().isoformat(),
        }
        redis_key = f"idempotency:{principal_id}:{idempotency_key}"
        try:
            self._redis_set(redis_key, record, only_if_missing=False)
        except Exception:
            pass

        self._db_update(
            principal_id,
            idempotency_key,
            status_value="succeeded",
            result_order_id=result_order_id,
            result_payload=result_payload,
            error_message=None,
        )

    def finalize_failure(
        self,
        *,
        principal_id: str,
        endpoint: str,
        idempotency_key: str,
        request_fingerprint: str,
        error_message: str,
    ) -> None:
        record = {
            "principal_id": principal_id,
            "endpoint": endpoint,
            "idempotency_key": idempotency_key,
            "request_fingerprint": request_fingerprint,
            "status": "failed",
            "result_order_id": None,
            "result_payload": None,
            "error_message": error_message,
            "processed_at": datetime.utcnow().isoformat(),
        }
        redis_key = f"idempotency:{principal_id}:{idempotency_key}"
        try:
            self._redis_set(redis_key, record, only_if_missing=False)
        except Exception:
            pass

        self._db_update(
            principal_id,
            idempotency_key,
            status_value="failed",
            result_order_id=None,
            result_payload=None,
            error_message=error_message,
        )


idempotency_service = IdempotencyService()
