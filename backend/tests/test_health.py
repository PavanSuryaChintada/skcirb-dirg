import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, normalise_db_url
from app.main import app

client = TestClient(app)


def test_health_is_green_on_an_empty_database():
    r = client.get("/api/health")
    assert r.status_code == 200
    # tables do not exist until ingestion; null, not 0, says so honestly
    assert r.json() == {"status": "ok", "db": "connected", "rows": {"actuals": None, "forecasts": None}}


def test_health_returns_503_when_database_is_unreachable(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'no' / 'such' / 'dir.db').as_posix()}")
    r = client.get("/api/health")
    assert r.status_code == 503
    assert r.json()["status"] == "error"
    assert r.json()["db"] == "unreachable"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("postgresql://u:p@h:5432/d?sslmode=require", "postgresql+psycopg://u:p@h:5432/d?sslmode=require"),
        ("postgres://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
        ("postgresql+psycopg://u:p@h/d", "postgresql+psycopg://u:p@h/d"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_database_url_scheme_is_pointed_at_psycopg3(raw, expected):
    assert normalise_db_url(raw) == expected


def test_wildcard_cors_is_refused(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "*")
    with pytest.raises(ValidationError):
        Settings()
