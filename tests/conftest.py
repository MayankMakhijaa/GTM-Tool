import os
import sys
import pytest
import importlib.util
from urllib.parse import urlparse

# Ensure project root is in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

PROTECTED_DB_NAMES = {"fameweb", "fameweb_prod", "fameweb_dev", "production", "development"}

def extract_db_name(db_url: str) -> str:
    if not db_url:
        return ""
    try:
        parsed = urlparse(db_url)
        path = parsed.path.lstrip('/')
        return path.split('?')[0].lower()
    except Exception:
        return ""

def assert_safe_test_db(db_url: str):
    db_name = extract_db_name(db_url)
    if not db_name:
        raise RuntimeError("CRITICAL SAFETY BLOCK: Database URL does not specify a valid database name.")
    if db_name in PROTECTED_DB_NAMES or db_name == "fameweb":
        raise RuntimeError(
            f"CRITICAL SAFETY BLOCK: Refusing to connect or execute test actions against protected database '{db_name}'. "
            f"Tests MUST run against a dedicated test database (e.g., 'fameweb_test')."
        )

# Configure environment variables BEFORE importing any app modules
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB_URL:
    TEST_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/fameweb_test"

assert_safe_test_db(TEST_DB_URL)

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["FLASK_TESTING"] = "1"
os.environ["SMTP_HOST"] = ""
os.environ["GOOGLE_MAPS_API_KEY"] = ""
os.environ["GOOGLE_PLACES_API_KEY"] = ""

# Load root app.py as sys.modules["app_module"] if not present
if "app_module" not in sys.modules:
    app_py_path = os.path.join(project_root, "app.py")
    spec = importlib.util.spec_from_file_location("app_module", app_py_path)
    app_module = importlib.util.module_from_spec(spec)
    sys.modules["app_module"] = app_module
    spec.loader.exec_module(app_module)

from app_module import app as flask_app
import app.database as app_db
from app.database import Base, engine, db_session
from app.models.all_models import UserTable, UsersCompanyDetails, UsersICP, EmailVerificationOTP
from app.security.session import login_required

if '/api/protected_test' not in [rule.rule for rule in flask_app.url_map.iter_rules()]:
    @flask_app.route('/api/protected_test', methods=['GET'])
    @login_required
    def protected_test():
        return "OK"

@pytest.fixture(scope="session", autouse=True)
def print_effective_test_db():
    safe_url = f"postgresql://.../{extract_db_name(TEST_DB_URL)}"
    print(f"\n[TEST SUITE SAFETY GUARD] Effective Test Database: {safe_url}")
    assert_safe_test_db(TEST_DB_URL)
    assert_safe_test_db(str(engine.url))
    # Ensure tables exist in fameweb_test
    import app.models  # noqa
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def clean_db():
    assert_safe_test_db(str(engine.url))
    # Clean up test database before test
    db_session.query(EmailVerificationOTP).delete(synchronize_session=False)
    db_session.query(UsersICP).delete(synchronize_session=False)
    db_session.query(UsersCompanyDetails).delete(synchronize_session=False)
    db_session.query(UserTable).delete(synchronize_session=False)
    db_session.commit()
    yield
    db_session.remove()

@pytest.fixture
def client(clean_db):
    flask_app.config['TESTING'] = True
    flask_app.config['SMTP_HOST'] = None
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['RATELIMIT_ENABLED'] = False
    from app.security.limiter import limiter
    limiter.enabled = False

    with flask_app.test_client() as test_client:
        with flask_app.app_context():
            yield test_client
