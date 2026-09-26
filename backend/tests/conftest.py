"""
Pytest configuration and global fixtures for AMAP backend test suite.
Ensures test isolation by resetting FastAPI dependency overrides between tests.
"""

import pytest
from app.main import app


@pytest.fixture(autouse=True)
def reset_dependency_overrides():
    """Ensure clean dependency overrides for every test to avoid cross-test pollution."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_auth_rate_limiter():
    """
    Clear the in-flight auth rate-limiting window around every test.

    The production limiter (20 logins/60s per IP) is real security behavior,
    but pytest's TestClient shares one client IP across the whole suite, so
    accumulated login tests would otherwise trip HTTP 429 and mask real
    results. Each test still sees a fresh window; tests that specifically
    exercise the limiter manage it themselves.
    """
    from middleware.rate_limiting import auth_rate_limiter

    auth_rate_limiter.reset()
    yield
    auth_rate_limiter.reset()
