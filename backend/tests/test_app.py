"""
Foundation test: the application starts successfully.

Per docs/BACKEND.md #18.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_app_starts():
    client = TestClient(app)
    assert client is not None


def test_app_has_title():
    assert app.title == "AMAP Backend"

