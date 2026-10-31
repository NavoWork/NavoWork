import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_backend(tmp_path_factory):
    root = tmp_path_factory.mktemp("backend")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", f"sqlite:///{(root / 'test.sqlite3').as_posix()}")
        patch.setenv("STORAGE_ROOT", str(root / "storage"))
        patch.setenv("APP_ENV", "demo")
        patch.setenv("MODEL_API_KEY", "")
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
