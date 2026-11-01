import os
import sys
import tempfile
from pathlib import Path
import pytest


def pytest_configure(config):
    # Several test modules import app.db during collection, before fixtures run.
    # Freeze disposable paths before that first import, never the developer DB.
    directory = tempfile.TemporaryDirectory(prefix="navowork-backend-tests-")
    root = Path(directory.name)
    values = {"DATABASE_URL": f"sqlite:///{(root / 'test.sqlite3').as_posix()}",
              "STORAGE_ROOT": str(root / "storage"), "APP_ENV": "demo", "MODEL_API_KEY": ""}
    if os.getenv("NAVOWORK_LIVE_RESEARCH") == "1":
        values.pop("MODEL_API_KEY")
    old = {key: os.environ.get(key) for key in values}
    os.environ.update(values)

    def cleanup():
        if "app.db" in sys.modules:
            sys.modules["app.db"].engine.dispose()
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        directory.cleanup()

    config.add_cleanup(cleanup)


@pytest.fixture(scope="session", autouse=True)
def isolated_backend(tmp_path_factory):
    from app.main import app
    yield app


@pytest.fixture(autouse=True)
def clean_database(isolated_backend):
    from app.db import Base, engine
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture
def client(isolated_backend):
    from fastapi.testclient import TestClient
    with TestClient(isolated_backend) as client:
        assert client.post("/api/v1/auth/session", json={"email": "demo@navowork.local", "password": "ChangeMe123!"}).status_code == 200
        yield client


@pytest.fixture
def other_client(isolated_backend, client):
    from fastapi.testclient import TestClient
    from app.core import password_hash
    from app.db import SessionLocal
    from app.models import User
    with SessionLocal() as db:
        db.add(User(id="other", email="other@example.test", name="Other", password_hash=password_hash("testing123"), role="member"))
        db.commit()
    with TestClient(isolated_backend) as other:
        assert other.post("/api/v1/auth/session", json={"email": "other@example.test", "password": "testing123"}).status_code == 200
        yield other
