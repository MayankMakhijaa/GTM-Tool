import os
import sys
import importlib.util
import pytest
from dotenv import load_dotenv

load_dotenv()

# Force tests to use an isolated test database so the development/manual testing database is NEVER modified
test_db_url = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://postgres:root@localhost:5432/fameweb_test")
os.environ["DATABASE_URL"] = test_db_url
os.environ["FLASK_TESTING"] = "1"

# App.py is located at workspace root, while app/ is a package directory.
# We load app.py dynamically under the name 'app_module' to avoid shadowing conflicts.
if "app_module" not in sys.modules:
    spec = importlib.util.spec_from_file_location("app_module", "app.py")
    app_module = importlib.util.module_from_spec(spec)
    sys.modules["app_module"] = app_module
    spec.loader.exec_module(app_module)

app = sys.modules["app_module"].app
app.config["TESTING"] = True
app.config["RATELIMIT_ENABLED"] = False
app.config["WTF_CSRF_ENABLED"] = False

from app.security.limiter import limiter
limiter.enabled = False

@pytest.fixture(scope="session")
def flask_app():
    return sys.modules["app_module"].app
