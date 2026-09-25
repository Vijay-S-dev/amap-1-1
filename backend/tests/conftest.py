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
