import os
import tempfile

# Tests wipe the database, so they never use DATABASE_URL. Set TEST_DATABASE_URL to run them on PostgreSQL.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///./test_portal.db")
os.environ["UPLOAD_DIR"] = os.path.join(tempfile.gettempdir(), "portal_test_uploads")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed


@pytest.fixture(scope="module")
def client():
    """Fresh demo database for each test file."""
    seed(reset=True)
    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    if os.path.exists("test_portal.db"):
        os.remove("test_portal.db")
