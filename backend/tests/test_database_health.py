from fastapi.testclient import TestClient

from app.main import app


def test_database_health_endpoint():
    client = TestClient(app)

    response = client.get("/api/v1/database/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
