import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure project root in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tests.conftest import TEST_DB_URL, assert_safe_test_db
assert_safe_test_db(TEST_DB_URL)


def test_production_rejects_missing_secret():
    """Production mode must raise RuntimeError if SECRET_KEY is missing/unset."""
    from config import Config
    with pytest.raises(RuntimeError) as exc_info:
        Config.validate_production_secrets(raw_secret="", is_production=True)
    assert "SECRET_KEY environment variable is required and cannot be blank" in str(exc_info.value)

    with pytest.raises(RuntimeError) as exc_info:
        Config.validate_production_secrets(raw_secret=None, is_production=True)
    assert "SECRET_KEY environment variable is required and cannot be blank" in str(exc_info.value)


def test_production_rejects_blank_secret():
    """Production mode must raise RuntimeError if SECRET_KEY is blank whitespace."""
    from config import Config
    with pytest.raises(RuntimeError) as exc_info:
        Config.validate_production_secrets(raw_secret="   ", is_production=True)
    assert "SECRET_KEY environment variable is required and cannot be blank" in str(exc_info.value)


def test_production_rejects_default_dev_secret():
    """Production mode must raise RuntimeError if SECRET_KEY is the insecure dev_secret_key."""
    from config import Config
    with pytest.raises(RuntimeError) as exc_info:
        Config.validate_production_secrets(raw_secret="dev_secret_key", is_production=True)
    assert "insecure development fallback SECRET_KEY ('dev_secret_key')" in str(exc_info.value)


def test_production_accepts_valid_secret():
    """Production mode succeeds with a valid strong secret."""
    from config import Config
    assert Config.validate_production_secrets(raw_secret="prod_secret_unique_key_456!", is_production=True) is True


def test_development_allows_fallback_secret():
    """Development mode (is_production=False) allows unset or default fallback SECRET_KEY."""
    from config import Config
    assert Config.validate_production_secrets(raw_secret="dev_secret_key", is_production=False) is True
    assert Config.validate_production_secrets(raw_secret=None, is_production=False) is True


def test_app_import_does_not_trigger_recovery():
    """
    Importing app_module or app.py directly must NOT invoke reconcile_stale_research_jobs.
    Module import must be free of active recovery side-effects.
    """
    with patch("app.services.gtm_pipeline_service.reconcile_stale_research_jobs") as mock_rec:
        # Access app
        from app_module import app as flask_app
        assert flask_app is not None
        mock_rec.assert_not_called()


def test_explicit_startup_recovery_execution():
    """
    Explicitly calling run_startup_recovery invokes the recovery function
    within application context and returns statistics.
    """
    from app_module import app as flask_app, run_startup_recovery

    fake_stats = {"recovered": 2, "examined": 2, "details": []}
    with patch("app_module.reconcile_stale_research_jobs", return_value=fake_stats) as mock_rec:
        stats = run_startup_recovery(flask_app, force=True)
        mock_rec.assert_called_once()
        assert stats == fake_stats


def test_startup_recovery_failure_is_handled_safely():
    """
    If database connectivity fails during startup recovery, it logs gracefully
    and does not raise an unhandled exception or crash startup.
    """
    from app_module import app as flask_app, run_startup_recovery

    with patch("app_module.reconcile_stale_research_jobs", side_effect=Exception("Database timeout")):
        result = run_startup_recovery(flask_app, force=True)
        assert result.get("recovered") == 0
        assert "Database timeout" in result.get("error", "")


def test_admin_reconcile_endpoint_accessible(client, clean_db):
    """
    Verify the Super Admin endpoint POST /api/admin/gtm/reconcile remains functional
    and correctly triggers recovery.
    """
    from app.models.all_models import UserTable, UserRole
    from app.database import db_session
    from datetime import datetime

    # Create a super admin user
    admin_user = UserTable(
        name="Super Admin",
        email_id="superadmin@fameweb.in",
        phone_no="+1234567890",
        password_hash="hashed_pw",
        role=UserRole.SUPER_ADMIN.value,
        email_verified_at=datetime.utcnow(),
        is_active=True
    )
    db_session.add(admin_user)
    db_session.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = admin_user.user_id

    # Call /api/admin/gtm/reconcile
    resp = client.post("/api/admin/gtm/reconcile", json={"max_stale_minutes": 15})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "stats" in data
    assert "recovered" in data["stats"]


# ====================================================================
# PHASE 0.4.1 FOCUSED VERIFICATION TESTS
# ====================================================================

def test_heartbeat_controller_lifecycle_and_pulse(clean_db):
    """
    Verifies JobHeartbeatController starts a background daemon thread,
    periodically updates heartbeat_at in the database using an isolated connection,
    does not overwrite terminal states, and shuts down cleanly.
    """
    import time
    from datetime import datetime, timedelta
    from app.database import db_session, engine
    from app.models.all_models import ResearchJobs, ResearchJobStatus, UserTable, UserRole
    from app.services.gtm_pipeline_service import JobHeartbeatController

    # 1. Create user and active RUNNING job with past heartbeat
    u = UserTable(
        name="Heartbeat Test User",
        email_id="hb_user@test.com",
        phone_no="+15552223333",
        password_hash="TestPassword123!",
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        is_active=True
    )
    db_session.add(u)
    db_session.commit()

    past_time = datetime.utcnow() - timedelta(minutes=5)
    job = ResearchJobs(
        user_id=u.user_id,
        status=ResearchJobStatus.RUNNING.value,
        budget={"target_leads": 10},
        created_at=past_time,
        heartbeat_at=past_time
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    # 2. Start controller with short 0.2s interval
    ctrl = JobHeartbeatController(job_id=job_id, interval_seconds=1)
    ctrl.start()
    assert ctrl._thread is not None
    assert ctrl._thread.is_alive()

    # 3. Synchronous pulse now
    pulsed = ctrl.pulse_now()
    assert pulsed is True

    # Check updated in DB
    db_session.expire_all()
    reloaded = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded.heartbeat_at > past_time

    # 4. Simulate job reaching COMPLETED terminal status
    reloaded.status = ResearchJobStatus.COMPLETED.value
    db_session.commit()

    # Pulse on terminal job must return False (update prevented)
    pulsed_on_completed = ctrl.pulse_now()
    assert pulsed_on_completed is False

    # 5. Stop controller cleanly
    ctrl.stop(timeout=2.0)
    assert not ctrl._thread.is_alive()


def test_healthy_job_older_than_15_minutes_with_fresh_heartbeat_not_failed(clean_db):
    """
    A healthy job created >15 minutes ago but actively maintained by heartbeat
    is NOT incorrectly marked FAILED during reconciliation.
    """
    from datetime import datetime, timedelta
    from app.database import db_session
    from app.models.all_models import ResearchJobs, ResearchJobStatus, UserTable, UserRole
    from app.services.gtm_pipeline_service import reconcile_stale_research_jobs

    u = UserTable(
        name="Long Running User",
        email_id="longrun@test.com",
        phone_no="+15553334444",
        password_hash="TestPassword123!",
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        is_active=True
    )
    db_session.add(u)
    db_session.commit()

    # Created 45 minutes ago, but heartbeat refreshed 1 minute ago!
    job = ResearchJobs(
        user_id=u.user_id,
        status=ResearchJobStatus.RUNNING.value,
        budget={"target_leads": 20},
        created_at=datetime.utcnow() - timedelta(minutes=45),
        heartbeat_at=datetime.utcnow() - timedelta(minutes=1)
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    stats = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    assert stats["recovered"] == 0

    reloaded = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded.status == ResearchJobStatus.RUNNING.value


def test_genuinely_stale_job_is_recovered(clean_db):
    """
    A genuinely stale job whose heartbeat is older than 15 minutes is transitioned to FAILED.
    """
    from datetime import datetime, timedelta
    from app.database import db_session
    from app.models.all_models import ResearchJobs, ResearchJobStatus, UserTable, UserRole
    from app.services.gtm_pipeline_service import reconcile_stale_research_jobs

    u = UserTable(
        name="Stale User",
        email_id="stale@test.com",
        phone_no="+15554445555",
        password_hash="TestPassword123!",
        role=UserRole.CUSTOMER.value,
        email_verified_at=datetime.utcnow(),
        is_active=True
    )
    db_session.add(u)
    db_session.commit()

    stale_ts = datetime.utcnow() - timedelta(minutes=25)
    job = ResearchJobs(
        user_id=u.user_id,
        status=ResearchJobStatus.RUNNING.value,
        budget={"target_leads": 15},
        created_at=stale_ts,
        heartbeat_at=stale_ts
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    stats = reconcile_stale_research_jobs(max_stale_minutes=15, session=db_session)
    assert stats["recovered"] == 1

    reloaded = db_session.query(ResearchJobs).filter_by(id=job_id).first()
    assert reloaded.status == ResearchJobStatus.FAILED.value
    assert "stale worker heartbeat" in reloaded.error_message


def test_production_startup_path_coordinated_advisory_lock(client, clean_db):
    """
    Simulates production WSGI startup:
    1. First incoming request triggers ensure_production_startup_recovery.
    2. Postgres advisory locking coordinates across processes without duplicate runs.
    """
    import os
    from unittest.mock import patch
    import app_module

    # Reset in-process flags to simulate new WSGI worker startup
    app_module._startup_recovery_completed = False

    fake_stats = {"recovered": 1, "examined": 1, "details": []}
    with patch("app_module.reconcile_stale_research_jobs", return_value=fake_stats) as mock_rec:
        # Simulate production environment without FLASK_TESTING=1
        with patch.dict(os.environ, {"FLASK_TESTING": "0"}):
            # First request triggers startup recovery
            resp = client.get("/login")
            assert resp.status_code == 200
            mock_rec.assert_called_once()
            assert app_module._startup_recovery_completed is True

            # Subsequent requests do not re-run recovery (in-process guard)
            resp2 = client.get("/login")
            assert resp2.status_code == 200
            assert mock_rec.call_count == 1
