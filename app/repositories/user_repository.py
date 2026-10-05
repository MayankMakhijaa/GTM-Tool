from app.database import db_session
from app.models.all_models import UserTable
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
        onboarding_step="COMPANY",
        optimization_status="NOT_OFFERED",
        is_active=True
    )
    try:
        db_session.add(user)
        db_session.commit()
        return user
    except IntegrityError:
        db_session.rollback()
        return None
