from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_development_swagger_csp_allows_required_assets(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    response = client.get("/docs")

    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in csp
    assert "script-src" in csp
    assert "style-src" in csp


def test_openapi_and_docs_are_available():
    docs = client.get("/docs")
    openapi = client.get("/openapi.json")
    assert docs.status_code == 200
    assert openapi.status_code == 200
    assert openapi.headers["content-security-policy"] == "default-src 'self'"
