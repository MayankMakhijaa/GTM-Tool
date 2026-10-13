import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, UniqueConstraint, text
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

class UserTable(Base):
    __tablename__ = 'user_table'
    user_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email_id = Column(String, unique=True, nullable=True)
    phone_no = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=False)
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
