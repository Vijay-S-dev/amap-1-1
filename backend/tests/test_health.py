"""
Foundation test: health endpoint responds correctly and independently
of the database, per docs/BACKEND.md #12, #17, #18.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_returns_ok_status():
    response = client.get("/api/v1/health")
    assert response.json() == {"status": "ok"}

