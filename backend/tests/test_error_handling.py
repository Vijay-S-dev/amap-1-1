"""
Foundation test: basic error handling behaves correctly, per
docs/BACKEND.md #13, #18.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_unknown_route_returns_404_with_consistent_body():
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body


def test_request_id_header_present_on_error():
    response = client.get("/api/v1/does-not-exist")
    assert "X-Request-ID" in response.headers

