from app.database import db_session
from app.models.all_models import (
    UserTable,
    OnboardingStep,
    Tenant,
    TenantMembership,
    TenantRole,
    TenantStatus,
    TenantMembershipStatus
)
from sqlalchemy.exc import IntegrityError
from typing import Optional

def get_user_by_id(user_id: int) -> Optional[UserTable]:
    return db_session.query(UserTable).filter(UserTable.user_id == user_id).first()

def get_user_by_email(email: str) -> Optional[UserTable]:
    return db_session.query(UserTable).filter(UserTable.email_id == email).first()

def get_user_by_phone(phone: str) -> Optional[UserTable]:
    return db_session.query(UserTable).filter(UserTable.phone_no == phone).first()

def create_user(name: str, email: str, phone: str, password_hash: str) -> Optional[UserTable]:
    user = UserTable(
        name=name,
        email_id=email,
        phone_no=phone,
        password_hash=password_hash,
        onboarding_step=OnboardingStep.LINKEDIN.value,
        optimization_status="NOT_OFFERED",
        is_active=True
    )
    try:
        db_session.add(user)
        db_session.flush()  # Flush to populate user.user_id within the transaction

        tenant_name = f"{name.strip()}'s Workspace" if name and name.strip() else f"Workspace {user.user_id}"
        tenant = Tenant(
            name=tenant_name,
            slug=f"tenant-{user.user_id}",
            status=TenantStatus.ACTIVE.value,
            is_deleted=False
        )
        db_session.add(tenant)
        db_session.flush()  # Flush to populate tenant.id

        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user.user_id,
            role=TenantRole.OWNER.value,
            status=TenantMembershipStatus.ACTIVE.value
        )
        db_session.add(membership)
        db_session.commit()
        return user
    except IntegrityError:
        db_session.rollback()
        return None
    except Exception:
        db_session.rollback()
        raise

