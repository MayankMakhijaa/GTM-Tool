import sys
import importlib.util
import pytest

spec = importlib.util.spec_from_file_location("app_module", "app.py")
app_module = importlib.util.module_from_spec(spec)
sys.modules["app_module"] = app_module
spec.loader.exec_module(app_module)

@pytest.fixture(scope="session")
def flask_app():
    return app_module.app
