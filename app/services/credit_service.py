import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.database import db_session
from app.models.all_models import (
    UserCreditWallet,
    FeaturePricing,
    CreditReservation,
    CreditTransaction,
    ReservationStatus,
    TransactionType,
    UserTable
)

logger = logging.getLogger(__name__)

class CreditServiceError(Exception):
    """Base exception for credit operations."""
    pass

class InsufficientCreditsError(CreditServiceError):
    """Raised when available credits are insufficient."""
    pass

class IdempotencyConflictError(CreditServiceError):
    """Raised when an idempotency key is reused with conflicting parameters."""
    pass

class ReservationStateError(CreditServiceError):
    """Raised when a reservation state transition is invalid."""
    pass

class FeaturePricingNotFoundError(CreditServiceError):
    """Raised when requested feature pricing is missing or inactive."""
    pass


def _to_decimal(value: Any, field_name: str = "amount") -> Decimal:
    """Safely converts value to Decimal, rounding to 2 decimal places and validating finiteness."""
    if value is None:
        raise ValueError(f"{field_name} is required")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid decimal value for {field_name}")

    if not d.is_finite():
        raise ValueError(f"{field_name} must be a finite number")

    # Quantize to 2 decimal places
    return d.quantize(Decimal("0.01"))


class CreditService:
    @staticmethod
    def get_or_create_wallet(user_id: int, session: Optional[Any] = None) -> UserCreditWallet:
        """
        Retrieves or initializes a wallet for user_id with 0 balance.
        Uses PostgreSQL ON CONFLICT DO NOTHING to prevent race conditions.
        """
        if not user_id:
            raise ValueError("user_id is required")

        s = session or db_session
        wallet = s.query(UserCreditWallet).filter_by(user_id=user_id).first()
        if wallet:
            return wallet

        # Concurrency-safe insert
        now = datetime.utcnow()
        stmt = insert(UserCreditWallet).values(
            user_id=user_id,
            total_balance=Decimal("0.00"),
            reserved_balance=Decimal("0.00"),
            created_at=now,
            updated_at=now
        ).on_conflict_do_nothing(index_elements=['user_id'])

        try:
            s.execute(stmt)
            s.commit()
        except Exception:
            s.rollback()

        return s.query(UserCreditWallet).filter_by(user_id=user_id).first()

    @staticmethod
    def get_wallet_balance(user_id: int, session: Optional[Any] = None) -> Dict[str, Any]:
        """
        Returns a dictionary with total_balance, reserved_balance, and available_balance.
        """
        s = session or db_session
        wallet = CreditService.get_or_create_wallet(user_id, session=s)
        available = wallet.total_balance - wallet.reserved_balance
        return {
            "user_id": user_id,
            "total_balance": wallet.total_balance,
            "reserved_balance": wallet.reserved_balance,
            "available_balance": available
        }

    @staticmethod
    def grant_credits(
        user_id: int,
        amount: Any,
        idempotency_key: str,
        reason: str,
        actor_user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Grants credits (increases total_balance).
        Requires non-blank reason, positive amount, and unique idempotency_key.
        """
        s = session or db_session
        dec_amount = _to_decimal(amount, "amount")
        if dec_amount <= Decimal("0.00"):
            raise ValueError("Grant amount must be strictly greater than zero")

        if not reason or not str(reason).strip():
            raise ValueError("A non-blank reason is required for administrative credit mutations")

        if not idempotency_key or len(str(idempotency_key).strip()) > 160:
            raise ValueError("idempotency_key is required and must not exceed 160 characters")

        clean_key = str(idempotency_key).strip()

        # Idempotency pre-check
        existing_tx = s.query(CreditTransaction).filter_by(idempotency_key=clean_key).first()
        if existing_tx:
            if existing_tx.user_id != user_id or existing_tx.amount != dec_amount or existing_tx.transaction_type != TransactionType.ADMIN_GRANT.value:
                raise IdempotencyConflictError(f"Idempotency key '{clean_key}' already used with different parameters.")
            return {
                "transaction_id": existing_tx.id,
                "user_id": user_id,
                "amount": existing_tx.amount,
                "balance_after": existing_tx.balance_after,
                "reserved_after": existing_tx.reserved_after,
                "is_idempotent_replay": True
            }

        # Ensure wallet exists
        CreditService.get_or_create_wallet(user_id, session=s)

        try:
            # Pessimistic row-lock on wallet
            wallet = s.query(UserCreditWallet).filter_by(user_id=user_id).with_for_update().first()
            wallet.total_balance += dec_amount
            wallet.updated_at = datetime.utcnow()

            tx = CreditTransaction(
                user_id=user_id,
                transaction_type=TransactionType.ADMIN_GRANT.value,
                amount=dec_amount,
                reserved_delta=Decimal("0.00"),
                balance_after=wallet.total_balance,
                reserved_after=wallet.reserved_balance,
                idempotency_key=clean_key,
                actor_user_id=actor_user_id,
                reason=str(reason).strip(),
                metadata_json=metadata,
                created_at=datetime.utcnow()
            )
            s.add(tx)
            s.commit()

            return {
                "transaction_id": tx.id,
                "user_id": user_id,
                "amount": tx.amount,
                "balance_after": tx.balance_after,
                "reserved_after": tx.reserved_after,
                "is_idempotent_replay": False
            }
        except IntegrityError as ie:
            s.rollback()
            # Double check for concurrent race condition on idempotency key
            check_tx = s.query(CreditTransaction).filter_by(idempotency_key=clean_key).first()
            if check_tx and check_tx.user_id == user_id and check_tx.amount == dec_amount:
                return {
                    "transaction_id": check_tx.id,
                    "user_id": user_id,
                    "amount": check_tx.amount,
                    "balance_after": check_tx.balance_after,
                    "reserved_after": check_tx.reserved_after,
                    "is_idempotent_replay": True
                }
            raise ie
        except Exception:
            s.rollback()
            raise

    @staticmethod
    def adjust_credits(
        user_id: int,
        amount: Any,
        idempotency_key: str,
        reason: str,
        actor_user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Adjusts credits (signed amount, can be positive or negative).
        Fails safely if adjustment would drop total_balance below reserved_balance.
        """
        s = session or db_session
        dec_amount = _to_decimal(amount, "amount")
        if dec_amount == Decimal("0.00"):
            raise ValueError("Adjustment amount cannot be zero")

        if not reason or not str(reason).strip():
            raise ValueError("A non-blank reason is required for administrative credit mutations")

        if not idempotency_key or len(str(idempotency_key).strip()) > 160:
            raise ValueError("idempotency_key is required and must not exceed 160 characters")

        clean_key = str(idempotency_key).strip()

        # Idempotency pre-check
        existing_tx = s.query(CreditTransaction).filter_by(idempotency_key=clean_key).first()
        if existing_tx:
            if existing_tx.user_id != user_id or existing_tx.amount != dec_amount or existing_tx.transaction_type != TransactionType.ADMIN_ADJUSTMENT.value:
                raise IdempotencyConflictError(f"Idempotency key '{clean_key}' already used with different parameters.")
            return {
                "transaction_id": existing_tx.id,
                "user_id": user_id,
                "amount": existing_tx.amount,
                "balance_after": existing_tx.balance_after,
                "reserved_after": existing_tx.reserved_after,
                "is_idempotent_replay": True
            }

        CreditService.get_or_create_wallet(user_id, session=s)

        try:
            wallet = s.query(UserCreditWallet).filter_by(user_id=user_id).with_for_update().first()
            new_total = wallet.total_balance + dec_amount

            if new_total < Decimal("0.00"):
                raise ValueError(f"Adjustment of {dec_amount} would result in negative total balance ({new_total})")

            if new_total < wallet.reserved_balance:
                raise ValueError(f"Adjustment would result in total balance ({new_total}) below reserved balance ({wallet.reserved_balance})")

            wallet.total_balance = new_total
            wallet.updated_at = datetime.utcnow()

            tx = CreditTransaction(
                user_id=user_id,
                transaction_type=TransactionType.ADMIN_ADJUSTMENT.value,
                amount=dec_amount,
                reserved_delta=Decimal("0.00"),
                balance_after=wallet.total_balance,
                reserved_after=wallet.reserved_balance,
                idempotency_key=clean_key,
                actor_user_id=actor_user_id,
                reason=str(reason).strip(),
                metadata_json=metadata,
                created_at=datetime.utcnow()
            )
            s.add(tx)
            s.commit()

            return {
                "transaction_id": tx.id,
                "user_id": user_id,
                "amount": tx.amount,
                "balance_after": tx.balance_after,
                "reserved_after": tx.reserved_after,
                "is_idempotent_replay": False
            }
        except Exception:
            s.rollback()
            raise

    @staticmethod
    def reserve_credits(
        user_id: int,
        feature_code: str,
        requested_quantity: int,
        billing_operation_id: str,
        job_id: Optional[int] = None,
        reason: Optional[str] = None,
        session: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Reserves credits for an operation before execution.
        Takes snapshot of active pricing and locks reserved_balance atomically.
        """
        s = session or db_session
        if requested_quantity <= 0:
            raise ValueError("requested_quantity must be positive integer")

        if not billing_operation_id or len(str(billing_operation_id).strip()) > 160:
            raise ValueError("billing_operation_id is required and must not exceed 160 characters")

        clean_op_id = str(billing_operation_id).strip()

        # Idempotency check on reservation
        existing_res = s.query(CreditReservation).filter_by(billing_operation_id=clean_op_id).first()
        if existing_res:
            if existing_res.user_id != user_id or existing_res.feature_code != feature_code or existing_res.requested_quantity != requested_quantity:
                raise IdempotencyConflictError(f"Billing operation '{clean_op_id}' already exists with different parameters.")
            return {
                "reservation_id": existing_res.id,
                "user_id": user_id,
                "status": existing_res.status,
                "reserved_amount": existing_res.reserved_amount,
                "unit_price_snapshot": existing_res.unit_price_snapshot,
                "is_idempotent_replay": True
            }

        pricing = s.query(FeaturePricing).filter_by(feature_code=feature_code, is_active=True).first()
        if not pricing:
            raise FeaturePricingNotFoundError(f"Active pricing for feature '{feature_code}' not found.")

        unit_price = pricing.credit_cost
        total_reserved = (unit_price * Decimal(requested_quantity)).quantize(Decimal("0.01"))
        pricing_ver = pricing.version

        CreditService.get_or_create_wallet(user_id, session=s)

        try:
            # Acquire exclusive lock on customer wallet
            wallet = s.query(UserCreditWallet).filter_by(user_id=user_id).with_for_update().first()
            available = wallet.total_balance - wallet.reserved_balance

            if available < total_reserved:
                raise InsufficientCreditsError(f"Insufficient available credits. Required: {total_reserved}, available: {available}")

            # Reserve credits
            wallet.reserved_balance += total_reserved
            wallet.updated_at = datetime.utcnow()

            res_record = CreditReservation(
                user_id=user_id,
                job_id=job_id,
                billing_operation_id=clean_op_id,
                feature_code=feature_code,
                requested_quantity=requested_quantity,
                unit_price_snapshot=unit_price,
                pricing_version_snapshot=pricing_ver,
                reserved_amount=total_reserved,
                charged_amount=Decimal("0.00"),
                status=ReservationStatus.RESERVED.value,
                created_at=datetime.utcnow()
            )
            s.add(res_record)
            s.flush()

            # Record reservation transaction in append-only ledger
            tx_key = f"tx_res_{clean_op_id}"
            tx = CreditTransaction(
                user_id=user_id,
                job_id=job_id,
                reservation_id=res_record.id,
                transaction_type=TransactionType.RESERVATION.value,
                amount=Decimal("0.00"),
                reserved_delta=total_reserved,
                balance_after=wallet.total_balance,
                reserved_after=wallet.reserved_balance,
                feature_code=feature_code,
                unit_price_snapshot=unit_price,
                pricing_version_snapshot=pricing_ver,
                quantity=requested_quantity,
                idempotency_key=tx_key,
                reason=reason or f"Reserved credits for {requested_quantity} {pricing.unit_name}(s)",
                created_at=datetime.utcnow()
            )
            s.add(tx)
            s.commit()

            return {
                "reservation_id": res_record.id,
                "user_id": user_id,
                "status": res_record.status,
                "reserved_amount": res_record.reserved_amount,
                "unit_price_snapshot": res_record.unit_price_snapshot,
                "is_idempotent_replay": False
            }
        except Exception:
            s.rollback()
            raise

    @staticmethod
    def settle_reservation(
        reservation_id: int,
        actual_quantity: int,
        idempotency_key: str,
        reason: Optional[str] = None,
        session: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Settles a reservation by charging for actual qualified quantity using locked unit price snapshot,
        clearing the entire original reservation and reducing total_balance.
        """
        s = session or db_session
        if actual_quantity < 0:
            raise ValueError("actual_quantity cannot be negative")

        if not idempotency_key or len(str(idempotency_key).strip()) > 160:
            raise ValueError("idempotency_key is required and must not exceed 160 characters")

        clean_key = str(idempotency_key).strip()

        # Idempotency pre-check
        existing_tx = s.query(CreditTransaction).filter_by(idempotency_key=clean_key).first()
        if existing_tx:
            return {
                "transaction_id": existing_tx.id,
                "reservation_id": reservation_id,
                "charged_amount": abs(existing_tx.amount),
                "is_idempotent_replay": True
            }

        try:
            res_record = s.query(CreditReservation).filter_by(id=reservation_id).with_for_update().first()
            if not res_record:
                raise ReservationStateError(f"Reservation {reservation_id} not found")

            if res_record.status != ReservationStatus.RESERVED.value:
                raise ReservationStateError(f"Reservation {reservation_id} cannot be settled in state '{res_record.status}'")

            unit_price = res_record.unit_price_snapshot
            actual_charge = (unit_price * Decimal(actual_quantity)).quantize(Decimal("0.01"))

            if actual_charge > res_record.reserved_amount:
                raise ValueError(f"Actual charge ({actual_charge}) cannot exceed reserved amount ({res_record.reserved_amount})")

            wallet = s.query(UserCreditWallet).filter_by(user_id=res_record.user_id).with_for_update().first()

            # Accounting update:
            # Total balance decreases by actual charge
            wallet.total_balance -= actual_charge
            # Reserved balance decreases by full original reservation
            wallet.reserved_balance -= res_record.reserved_amount
            wallet.updated_at = datetime.utcnow()

            res_record.charged_amount = actual_charge
            res_record.status = ReservationStatus.SETTLED.value
            res_record.settled_at = datetime.utcnow()

            # Negative signed amount on total balance
            signed_amount = (-actual_charge)
            tx = CreditTransaction(
                user_id=res_record.user_id,
                job_id=res_record.job_id,
                reservation_id=res_record.id,
                transaction_type=TransactionType.SETTLEMENT.value,
                amount=signed_amount,
                reserved_delta=(-res_record.reserved_amount),
                balance_after=wallet.total_balance,
                reserved_after=wallet.reserved_balance,
                feature_code=res_record.feature_code,
                unit_price_snapshot=unit_price,
                pricing_version_snapshot=res_record.pricing_version_snapshot,
                quantity=actual_quantity,
                idempotency_key=clean_key,
                reason=reason or f"Settlement for {actual_quantity} completed items",
                created_at=datetime.utcnow()
            )
            s.add(tx)
            s.commit()

            return {
                "transaction_id": tx.id,
                "reservation_id": reservation_id,
                "charged_amount": actual_charge,
                "is_idempotent_replay": False
            }
        except Exception:
            s.rollback()
            raise

    @staticmethod
    def release_reservation(
        reservation_id: int,
        idempotency_key: str,
        reason: Optional[str] = None,
        session: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Releases a reservation without charging (e.g. failure, zero results, cancelled job).
        Clears reserved_balance without changing total_balance.
        """
        s = session or db_session
        if not idempotency_key or len(str(idempotency_key).strip()) > 160:
            raise ValueError("idempotency_key is required and must not exceed 160 characters")

        clean_key = str(idempotency_key).strip()

        # Idempotency pre-check
        existing_tx = s.query(CreditTransaction).filter_by(idempotency_key=clean_key).first()
        if existing_tx:
            return {
                "transaction_id": existing_tx.id,
                "reservation_id": reservation_id,
                "released_amount": existing_tx.reserved_delta,
                "is_idempotent_replay": True
            }

        try:
            res_record = s.query(CreditReservation).filter_by(id=reservation_id).with_for_update().first()
            if not res_record:
                raise ReservationStateError(f"Reservation {reservation_id} not found")

            if res_record.status != ReservationStatus.RESERVED.value:
                raise ReservationStateError(f"Reservation {reservation_id} cannot be released in state '{res_record.status}'")

            wallet = s.query(UserCreditWallet).filter_by(user_id=res_record.user_id).with_for_update().first()

            released_amount = res_record.reserved_amount
            wallet.reserved_balance -= released_amount
            wallet.updated_at = datetime.utcnow()

            res_record.status = ReservationStatus.RELEASED.value
            res_record.released_at = datetime.utcnow()

            tx = CreditTransaction(
                user_id=res_record.user_id,
                job_id=res_record.job_id,
                reservation_id=res_record.id,
                transaction_type=TransactionType.RELEASE.value,
                amount=Decimal("0.00"),
                reserved_delta=(-released_amount),
                balance_after=wallet.total_balance,
                reserved_after=wallet.reserved_balance,
                feature_code=res_record.feature_code,
                unit_price_snapshot=res_record.unit_price_snapshot,
                pricing_version_snapshot=res_record.pricing_version_snapshot,
                idempotency_key=clean_key,
                reason=reason or "Full release of uncharged reserved credits",
                created_at=datetime.utcnow()
            )
            s.add(tx)
            s.commit()

            return {
                "transaction_id": tx.id,
                "reservation_id": reservation_id,
                "released_amount": released_amount,
                "is_idempotent_replay": False
            }
        except Exception:
            s.rollback()
            raise
