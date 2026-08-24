"""
Tests for AMAP Supabase Integration and Row-Level Security (RLS) Policies (Phase 15).
Validates SQL RLS policy coverage, PostgreSQL session context injection,
multi-tenant boundary enforcement, and Supabase client helpers.
"""

from pathlib import Path
from unittest.mock import MagicMock
import uuid
import pytest

from utils.supabase import SupabaseClientHelper
from utils.tenant_context import scoped_tenant_transaction, set_tenant_context


# =====================================================================
# 1. SQL Migration Policy Verification
# =====================================================================

def test_rls_migration_file_exists_and_covers_tables():
    migration_path = Path(__file__).resolve().parent.parent.parent / "database" / "migrations" / "040_supabase_row_level_security.sql"
    assert migration_path.exists(), "Migration 040_supabase_row_level_security.sql must exist"

    sql_content = migration_path.read_text(encoding="utf-8")

    # Verify RLS helper functions are declared
    assert "CREATE OR REPLACE FUNCTION current_app_org_id()" in sql_content
    assert "CREATE OR REPLACE FUNCTION current_app_user_id()" in sql_content
    assert "CREATE OR REPLACE FUNCTION is_app_super_admin()" in sql_content

    # Verify key multi-tenant tables have RLS enabled
    required_tables = [
        "organizations",
        "departments",
        "users",
        "worker_profiles",
        "work_sessions",
        "tasks",
        "workflows",
        "interaction_configurations",
        "assistance_requests",
        "audit_events",
    ]
    for table in required_tables:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in sql_content
        assert f"CREATE POLICY" in sql_content


# =====================================================================
# 2. Tenant Context Manager Tests
# =====================================================================

def test_set_tenant_context_executes_set_config():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    set_tenant_context(
        connection=mock_conn,
        organization_id=org_id,
        user_id=user_id,
        is_super_admin=False,
    )

    # Verify set_config calls were made
    assert mock_cursor.execute.call_count == 3
    calls = [c[0] for c in mock_cursor.execute.call_args_list]

    # Verify parameterized set_config was used (no SQL interpolation)
    assert calls[0][0] == "SELECT set_config('app.current_organization_id', %s, true);"
    assert calls[0][1] == (str(org_id),)

    assert calls[1][0] == "SELECT set_config('app.current_user_id', %s, true);"
    assert calls[1][1] == (str(user_id),)

    assert calls[2][0] == "SELECT set_config('app.is_super_admin', %s, true);"
    assert calls[2][1] == ("false",)


def test_scoped_tenant_transaction_context_manager():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    org_id = uuid.uuid4()

    with scoped_tenant_transaction(mock_conn, organization_id=org_id, is_super_admin=True) as conn:
        assert conn == mock_conn

    assert mock_cursor.execute.call_count == 3


# =====================================================================
# 3. Supabase Integration Helper Tests
# =====================================================================

def test_supabase_client_helper_headers_and_claims():
    helper = SupabaseClientHelper()

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    roles = ["worker", "station_operator"]

    claims = helper.build_tenant_claim(organization_id=org_id, user_id=user_id, roles=roles)
    assert claims["organization_id"] == str(org_id)
    assert claims["sub"] == str(user_id)
    assert claims["roles"] == roles
    assert claims["role"] == "authenticated"

    headers = helper.get_auth_headers(jwt_token="mock-jwt-token")
    assert headers["Authorization"] == "Bearer mock-jwt-token"
    assert headers["Content-Type"] == "application/json"
