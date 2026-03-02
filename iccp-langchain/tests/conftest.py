import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure imports like `from app.main import app` work
# regardless of the current working directory running pytest.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session", autouse=True)
def clean_test_db():
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./iccp_test.db"
    os.environ["DATABASE_SYNC_URL"] = "sqlite:///./iccp_test.db"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_API_KEY"] = ""
    os.environ["ADMIN_EMAILS"] = "admin@example.com"

    db_file = Path("iccp_test.db")
    if db_file.exists():
        db_file.unlink()
    yield
    if db_file.exists():
        db_file.unlink()


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
