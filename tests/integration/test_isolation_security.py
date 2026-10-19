import pytest
import os
import psycopg
from sqlalchemy import create_engine
from app.database import engine, db_session
from app.models.all_models import UserTable
from tests.conftest import (
    TEST_DB_URL,
    extract_db_name,
    assert_safe_test_db,
    PROTECTED_DB_NAMES
)

def test_effective_test_database_is_not_fameweb():
    """Verify that tests execute against fameweb_test and never the fameweb development database."""
    effective_name = extract_db_name(str(engine.url))
    assert effective_name == "fameweb_test"
    assert effective_name != "fameweb"
    assert effective_name not in PROTECTED_DB_NAMES

def test_assert_safe_test_db_blocks_fameweb():
    """Verify that assert_safe_test_db raises RuntimeError if fameweb is targeted."""
    dev_url = "postgresql+psycopg://postgres:postgres@localhost:5432/fameweb"
    with pytest.raises(RuntimeError) as excinfo:
        assert_safe_test_db(dev_url)
    assert "CRITICAL SAFETY BLOCK" in str(excinfo.value)
    assert "fameweb" in str(excinfo.value)

def test_assert_safe_test_db_blocks_protected_names():
    """Verify that all protected database names (fameweb_prod, fameweb_dev, production, etc.) are rejected."""
    for protected in PROTECTED_DB_NAMES:
        bad_url = f"postgresql+psycopg://postgres:postgres@localhost:5432/{protected}"
        with pytest.raises(RuntimeError) as excinfo:
            assert_safe_test_db(bad_url)
        assert "CRITICAL SAFETY BLOCK" in str(excinfo.value)

def test_assert_safe_test_db_allows_safe_test_urls():
    """Verify that safe test database URLs pass without error."""
    assert_safe_test_db("postgresql+psycopg://postgres:postgres@localhost:5432/fameweb_test")
    assert_safe_test_db("sqlite:///:memory:")

def test_destructive_operations_refuse_on_fameweb():
    """Simulate destructive fixture cleanup against fameweb and confirm immediate rejection."""
    dev_url = "postgresql+psycopg://postgres:postgres@localhost:5432/fameweb"
    
    def simulate_fixture_cleanup(target_url):
        assert_safe_test_db(target_url)
        # Would execute DELETE FROM user_table if safe
        return "CLEANUP_EXECUTED"

    with pytest.raises(RuntimeError) as excinfo:
        simulate_fixture_cleanup(dev_url)
    assert "CRITICAL SAFETY BLOCK" in str(excinfo.value)

def test_development_db_remains_unmodified_by_test_run(client):
    """Verify that test activity creates records in fameweb_test without touching fameweb."""
    # 1. Create user via test client in test DB
    res = client.post('/api/auth/signup', json={
        "name": "Test Isolation User",
        "email": "isolation_test@company.com",
        "phone": "+14155553311",
        "password": "Valid123!Password"
    })
    assert res.status_code == 201

    # 2. Verify record exists in fameweb_test (test DB)
    test_user = db_session.query(UserTable).filter_by(email_id="isolation_test@company.com").first()
    assert test_user is not None

    # 3. Read-only check against fameweb (development DB) to verify it was NOT modified
    dev_db_url = os.environ.get("DATABASE_URL", "")
    if "fameweb_test" in dev_db_url:
        dev_db_url = dev_db_url.replace("fameweb_test", "fameweb")
    elif not dev_db_url and os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if line.startswith("DATABASE_URL="):
                    dev_db_url = line.split("=", 1)[1].strip()
                    break
    if not dev_db_url:
        dev_db_url = "postgresql://postgres:postgres@localhost:5432/fameweb"
    dev_conn_str = dev_db_url.replace("postgresql+psycopg://", "postgresql://")
    dev_conn = psycopg.connect(dev_conn_str)
    cur = dev_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM user_table WHERE email_id = 'isolation_test@company.com'")
    count = cur.fetchone()[0]
    dev_conn.close()

    assert count == 0, "Security Failure: Test data leaked into fameweb development database!"
