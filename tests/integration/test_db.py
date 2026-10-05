import pytest
import os
from sqlalchemy import create_engine
from app.database import Base
from app import models

from tests.conftest import TEST_DB_URL, assert_safe_test_db

DB_URL = TEST_DB_URL
assert_safe_test_db(DB_URL)

def test_postgres_connection():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        assert conn is not None

def test_models_exist():
    # Verify all 8 models are accessible
    assert hasattr(models, 'UserTable')
    assert hasattr(models, 'UsersCompanyDetails')
    assert hasattr(models, 'UsersICP')
    assert hasattr(models, 'UsersLinkedinDetails')
    assert hasattr(models, 'GlobalProfiles')
    assert hasattr(models, 'UsersProfiles')
    assert hasattr(models, 'ResearchJobs')
    assert hasattr(models, 'ConnectAndMessage')

def test_foreign_keys_and_constraints():
    # Basic inspection of constraints on ConnectAndMessage
    table = models.ConnectAndMessage.__table__
    fks = [fk.column.table.name for fk in table.foreign_keys]
    assert 'user_table' in fks
    assert 'global_profiles' in fks
    
    unique_constraints = [c for c in table.constraints if getattr(c, 'name', None) == 'uq_connect_and_message_user_global']
    assert len(unique_constraints) > 0

def test_research_jobs_indexes():
    table = models.ResearchJobs.__table__
    active_idx = [idx for idx in table.indexes if idx.name == 'idx_active_research_job']
    assert len(active_idx) == 1
