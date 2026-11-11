import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, UniqueConstraint, text, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from app.database import Base

class OnboardingStep(str, enum.Enum):
    LINKEDIN = "LINKEDIN"
    COMPANY = "COMPANY"
    ICP = "ICP"
    OPTIMIZATION = "OPTIMIZATION"
    DONE = "DONE"

class OptimizationStatus(str, enum.Enum):
    NOT_OFFERED = "NOT_OFFERED"
    SKIPPED = "SKIPPED"
    ACCEPTED = "ACCEPTED"
    COMPLETED = "COMPLETED"

class UserRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"

class UserTable(Base):
    __tablename__ = 'user_table'
    user_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email_id = Column(String, unique=True, nullable=True)
    phone_no = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, default=UserRole.CUSTOMER.value, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)
    onboarding_step = Column(String, default=OnboardingStep.LINKEDIN.value)
    optimization_status = Column(String, default=OptimizationStatus.NOT_OFFERED.value)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ScrapeStatus(str, enum.Enum):
    PENDING = "PENDING"
    OK = "OK"
    FAILED = "FAILED"
    MANUAL = "MANUAL"

class UsersCompanyDetails(Base):
    __tablename__ = 'users_company_details'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id'), unique=True, nullable=False)
    company_name = Column(String, nullable=True)
    website_url = Column(String, nullable=False)
    description = Column(String, nullable=True)
    what_company_sells = Column(String, nullable=True)
    products_services = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    company_size = Column(String, nullable=True)
    revenue = Column(String, nullable=True)
    location = Column(String, nullable=True)
    rating = Column(String, nullable=True)
    other_details = Column(String, nullable=True)
    scrape_status = Column(String, default=ScrapeStatus.PENDING.value)
    edited_fields = Column(JSONB, nullable=True)
    scraped_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Tone(str, enum.Enum):
    FORMAL = "FORMAL"
    SEMI_FORMAL = "SEMI_FORMAL"
    CASUAL = "CASUAL"
    FRIENDLY = "FRIENDLY"

class UsersICP(Base):
    __tablename__ = 'users_icp'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id'), unique=True, nullable=False)
    target_customer = Column(String, nullable=True)
    company_size = Column(String, nullable=True)
    revenue_range = Column(String, nullable=True)
    target_jobs_roles = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    location = Column(String, nullable=True)
    keywords = Column(String, nullable=True)
    exclusions = Column(String, nullable=True)
    signals = Column(JSONB, nullable=True)
    tone = Column(String, nullable=True)
    summary_report = Column(JSONB, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProfileSource(str, enum.Enum):
    OIDC = "OIDC"
    UPLOAD = "UPLOAD"
    PASTE = "PASTE"

class ConnectionStatus(str, enum.Enum):
    CONNECTED = "CONNECTED"
    NEEDS_REAUTH = "NEEDS_REAUTH"
    DISCONNECTED = "DISCONNECTED"
    RESTRICTED = "RESTRICTED"

class UsersLinkedinDetails(Base):
    __tablename__ = 'users_linkedin_details'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id'), unique=True, nullable=False)
    oidc_sub = Column(String, unique=True, nullable=True)
    linkedin_id = Column(String, unique=True, nullable=True)
    profile_url = Column(String, nullable=True)
    name = Column(String, nullable=True)
    headline = Column(String, nullable=True)
    about = Column(String, nullable=True)
    current_position = Column(String, nullable=True)
    location = Column(String, nullable=True)
    experience = Column(JSONB, nullable=True)
    education = Column(JSONB, nullable=True)
    skills = Column(JSONB, nullable=True)
    profile_data = Column(JSONB, nullable=True)
    profile_source = Column(String, nullable=True)
    profile_completeness = Column(String, nullable=True)
    optimization_suggestions = Column(JSONB, nullable=True)
    auth_data_encrypted = Column(String, nullable=True)
    connection_status = Column(String, nullable=True)
    consent_at = Column(DateTime, nullable=True)
    last_verified_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class GlobalProfileSource(str, enum.Enum):
    SEED = "SEED"
    CSV_IMPORT = "CSV_IMPORT"
    USER_MANUAL = "USER_MANUAL"
    WEB = "WEB"

class GlobalProfiles(Base):
    __tablename__ = 'global_profiles'
    global_id = Column(Integer, primary_key=True)
    linkedin_id = Column(String, unique=True, nullable=False)
    profile_url = Column(String, nullable=True)
    name = Column(String, nullable=True)
    role = Column(String, nullable=True)
    headline = Column(String, nullable=True)
    company = Column(String, nullable=True)
    location = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    company_data = Column(JSONB, nullable=True)
    source = Column(String, nullable=True)
    do_not_contact = Column(Boolean, default=False)
    recommended_no_of_times = Column(Integer, default=0)
    last_updated = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ResearchSource(str, enum.Enum):
    GLOBAL_DB = "GLOBAL_DB"
    CSV_IMPORT = "CSV_IMPORT"
    USER_MANUAL = "USER_MANUAL"
    WEB = "WEB"

class LeadStatus(str, enum.Enum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    SAVED = "SAVED"
    CONTACTED = "CONTACTED"
    ARCHIVED = "ARCHIVED"

class UsersProfiles(Base):
    __tablename__ = 'users_profiles'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id'), nullable=False)
    global_id = Column(Integer, ForeignKey('global_profiles.global_id'), nullable=False)
    research_job_id = Column(Integer, ForeignKey('research_jobs.id'), nullable=True)
    research_source = Column(String, nullable=True)
    match_score = Column(Integer, nullable=True)
    qualification_reason = Column(String, nullable=True)
    lead_status = Column(String, default=LeadStatus.NEW.value)
    icp_version = Column(Integer, nullable=True)
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'global_id', name='uq_users_profiles_user_global'),
    )

class ResearchJobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class ResearchType(str, enum.Enum):
    GLOBAL_ONLY = "GLOBAL_ONLY"
    IMPORT_QUALIFY = "IMPORT_QUALIFY"
    WEB_DISCOVERY = "WEB_DISCOVERY"

class ResearchJobs(Base):
    __tablename__ = 'research_jobs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id'), nullable=False)
    status = Column(String, default=ResearchJobStatus.QUEUED.value)
    research_type = Column(String, nullable=True)
    icp_version = Column(Integer, nullable=True)
    budget = Column(JSONB, nullable=True)
    progress = Column(JSONB, nullable=True)
    stop_reason = Column(String, nullable=True)
    results_count = Column(Integer, default=0)
    error_message = Column(String, nullable=True)
    attempts = Column(Integer, default=0)
    heartbeat_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_active_research_job', 
              'user_id', 
              postgresql_where=text("status IN ('QUEUED', 'RUNNING', 'PAUSED')"), 
              unique=True),
    )

class OutreachConnectionStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    DRAFTED = "DRAFTED"
    REQUESTED = "REQUESTED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    WITHDRAWN = "WITHDRAWN"

class FollowUpStatus(str, enum.Enum):
    NONE = "NONE"
    SCHEDULED = "SCHEDULED"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"

class ConnectAndMessage(Base):
    __tablename__ = 'connect_and_message'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id'), nullable=False)
    global_id = Column(Integer, ForeignKey('global_profiles.global_id'), nullable=False)
    connection_status = Column(String, default=OutreachConnectionStatus.NOT_STARTED.value)
    connection_message = Column(String, nullable=True)
    messages = Column(JSONB, nullable=True)
    follow_up_status = Column(String, default=FollowUpStatus.NONE.value)
    next_follow_up_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=0)
    connection_requested_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    last_activity_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'global_id', name='uq_connect_and_message_user_global'),
    )

class EmailVerificationOTP(Base):
    __tablename__ = 'email_verification_otps'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id', ondelete='CASCADE'), nullable=False, index=True)
    otp_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    admin_user_id = Column(Integer, ForeignKey('user_table.user_id'), nullable=True, index=True)
    target_user_id = Column(Integer, ForeignKey('user_table.user_id'), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class UserCreditWallet(Base):
    __tablename__ = 'user_credit_wallets'
    user_id = Column(Integer, ForeignKey('user_table.user_id', ondelete='RESTRICT'), primary_key=True)
    total_balance = Column(Numeric(12, 2), nullable=False, default=0)
    reserved_balance = Column(Numeric(12, 2), nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint('total_balance >= 0', name='chk_wallet_total_balance_non_negative'),
        CheckConstraint('reserved_balance >= 0', name='chk_wallet_reserved_balance_non_negative'),
        CheckConstraint('reserved_balance <= total_balance', name='chk_wallet_reserved_le_total'),
    )

class FeaturePricing(Base):
    __tablename__ = 'feature_pricing'
    feature_code = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(String(255), nullable=True)
    unit_name = Column(String(32), nullable=False, default='qualified_lead')
    credit_cost = Column(Numeric(10, 2), nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    updated_by_user_id = Column(Integer, ForeignKey('user_table.user_id'), nullable=True)

    __table_args__ = (
        CheckConstraint('credit_cost >= 0', name='chk_feature_pricing_credit_cost_non_negative'),
    )

class ReservationStatus(str, enum.Enum):
    RESERVED = "RESERVED"
    SETTLED = "SETTLED"
    RELEASED = "RELEASED"

class CreditReservation(Base):
    __tablename__ = 'credit_reservations'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id', ondelete='RESTRICT'), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey('research_jobs.id', ondelete='RESTRICT'), nullable=True, index=True)
    billing_operation_id = Column(String(160), unique=True, nullable=False, index=True)
    feature_code = Column(String(64), ForeignKey('feature_pricing.feature_code', ondelete='RESTRICT'), nullable=False)
    requested_quantity = Column(Integer, nullable=False)
    unit_price_snapshot = Column(Numeric(10, 2), nullable=False)
    pricing_version_snapshot = Column(Integer, nullable=False)
    reserved_amount = Column(Numeric(12, 2), nullable=False)
    charged_amount = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String(32), nullable=False, default=ReservationStatus.RESERVED.value, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    settled_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint('reserved_amount >= 0', name='chk_res_reserved_amount_non_negative'),
        CheckConstraint('charged_amount >= 0', name='chk_res_charged_amount_non_negative'),
        CheckConstraint('charged_amount <= reserved_amount', name='chk_res_charged_le_reserved'),
    )

class TransactionType(str, enum.Enum):
    ADMIN_GRANT = "ADMIN_GRANT"
    ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT"
    RESERVATION = "RESERVATION"
    SETTLEMENT = "SETTLEMENT"
    RELEASE = "RELEASE"
    REFUND = "REFUND"

class CreditTransaction(Base):
    __tablename__ = 'credit_transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id', ondelete='RESTRICT'), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey('research_jobs.id', ondelete='RESTRICT'), nullable=True, index=True)
    reservation_id = Column(Integer, ForeignKey('credit_reservations.id', ondelete='RESTRICT'), nullable=True, index=True)
    transaction_type = Column(String(32), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    reserved_delta = Column(Numeric(12, 2), nullable=False, default=0)
    balance_after = Column(Numeric(12, 2), nullable=False)
    reserved_after = Column(Numeric(12, 2), nullable=False)
    feature_code = Column(String(64), ForeignKey('feature_pricing.feature_code', ondelete='RESTRICT'), nullable=True)
    unit_price_snapshot = Column(Numeric(10, 2), nullable=True)
    pricing_version_snapshot = Column(Integer, nullable=True)
    quantity = Column(Integer, nullable=True)
    idempotency_key = Column(String(160), unique=True, nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey('user_table.user_id'), nullable=True)
    reason = Column(String(255), nullable=False)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_credit_tx_user_created', 'user_id', 'created_at'),
    )

class AIProviderUsageLog(Base):
    __tablename__ = 'ai_provider_usage_logs'
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('research_jobs.id', ondelete='SET NULL'), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id', ondelete='CASCADE'), nullable=False, index=True)
    correlation_id = Column(String(64), nullable=False, index=True)
    provider = Column(String(32), nullable=False)
    model_name = Column(String(64), nullable=False)
    operation = Column(String(64), nullable=False)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Numeric(10, 6), nullable=True)
    provider_cost = Column(Numeric(10, 6), nullable=True)
    provider_currency = Column(String(8), nullable=True, default='USD')
    status = Column(String(32), nullable=False, default='SUCCESS')
    error_category = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TenantStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class TenantRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class TenantMembershipStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INVITED = "INVITED"
    SUSPENDED = "SUSPENDED"


class Tenant(Base):
    __tablename__ = 'tenants'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), nullable=False, default=TenantStatus.ACTIVE.value)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_tenants_status', 'status'),
    )


class TenantMembership(Base):
    __tablename__ = 'tenant_memberships'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='RESTRICT'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id', ondelete='RESTRICT'), nullable=False, index=True)
    role = Column(String(50), nullable=False, default=TenantRole.MEMBER.value)
    status = Column(String(50), nullable=False, default=TenantMembershipStatus.ACTIVE.value)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_membership_tenant_user'),
    )


# ==============================================================================
# Bulk Email & User-Owned SMTP Models
# ==============================================================================

class SMTPConnectionType(str, enum.Enum):
    SMTP = "SMTP"
    OAUTH = "OAUTH"


class SMTPAccountStatus(str, enum.Enum):
    CONNECTED = "CONNECTED"
    NEEDS_REAUTH = "NEEDS_REAUTH"
    FAILED = "FAILED"
    DISCONNECTED = "DISCONNECTED"


class EmailBatchSendingMode(str, enum.Enum):
    PERSONALIZED = "PERSONALIZED"
    IDENTICAL = "IDENTICAL"


class EmailBatchStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class EmailRecipientStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    ACCEPTED = "ACCEPTED"
    FAILED = "FAILED"
    DELIVERED = "DELIVERED"
    BOUNCED = "BOUNCED"


class UserSMTPAccount(Base):
    __tablename__ = 'user_smtp_accounts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id', ondelete='CASCADE'), nullable=False, index=True)
    email_address = Column(String(255), nullable=False, index=True)
    sender_name = Column(String(255), nullable=True)
    provider = Column(String(64), nullable=True)
    connection_type = Column(String(32), default=SMTPConnectionType.SMTP.value, nullable=False)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, nullable=True, default=587)
    smtp_username = Column(String(255), nullable=True)
    use_tls = Column(Boolean, default=True, nullable=False)
    use_ssl = Column(Boolean, default=False, nullable=False)
    encrypted_credentials = Column(String, nullable=True)
    encryption_key_version = Column(Integer, default=1, nullable=False)
    connection_status = Column(String(32), default=SMTPAccountStatus.CONNECTED.value, nullable=False)
    is_primary = Column(Boolean, default=False, nullable=False)
    last_tested_at = Column(DateTime, nullable=True)
    last_error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class EmailBatch(Base):
    __tablename__ = 'email_batches'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id', ondelete='CASCADE'), nullable=False, index=True)
    smtp_account_id = Column(Integer, ForeignKey('user_smtp_accounts.id', ondelete='SET NULL'), nullable=True, index=True)
    batch_name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=True)
    subject = Column(String, nullable=False)
    body_html = Column(String, nullable=True)
    body_text = Column(String, nullable=True)
    sending_mode = Column(String(32), default=EmailBatchSendingMode.PERSONALIZED.value, nullable=False)
    total_recipients = Column(Integer, default=0, nullable=False)
    valid_recipients = Column(Integer, default=0, nullable=False)
    invalid_recipients = Column(Integer, default=0, nullable=False)
    accepted_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    status = Column(String(32), default=EmailBatchStatus.DRAFT.value, nullable=False, index=True)
    error_message = Column(String, nullable=True)
    detected_headers = Column(JSONB, nullable=True)
    header_mapping = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class EmailRecipient(Base):
    __tablename__ = 'email_recipients'

    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey('email_batches.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('user_table.user_id', ondelete='CASCADE'), nullable=False, index=True)
    email_address = Column(String(255), nullable=False, index=True)
    recipient_data = Column(JSONB, nullable=True)
    rendered_subject = Column(String, nullable=True)
    rendered_body = Column(String, nullable=True)
    status = Column(String(32), default=EmailRecipientStatus.PENDING.value, nullable=False, index=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    error_message = Column(String, nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    bounced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)



class SystemSetting(Base):
    __tablename__ = 'system_settings'

    key = Column(String(128), primary_key=True, nullable=False, index=True)
    encrypted_value = Column(String, nullable=True)
    encryption_key_version = Column(Integer, default=1, nullable=False)
    metadata_json = Column(JSONB, nullable=True)
    is_secret = Column(Boolean, default=True, nullable=False)
    description = Column(String(255), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey('user_table.user_id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
