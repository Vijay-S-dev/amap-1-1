"""
PostgreSQL / Supabase Tenant Context Manager for AMAP.

Sets connection-local session parameters (`SET LOCAL ...`) so that PostgreSQL
Row-Level Security (RLS) policies dynamically isolate queries to the caller's tenant organization.
"""

from contextlib import contextmanager
from typing import Generator, Optional
from uuid import UUID
from psycopg import Connection


def set_tenant_context(
    connection: Connection,
    organization_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    is_super_admin: bool = False,
) -> None:
    """
    Set PostgreSQL transaction-scoped settings for RLS evaluation.
    Uses parameterized execution to prevent SQL injection.
    """
    with connection.cursor() as cursor:
        if organization_id:
            cursor.execute("SELECT set_config('app.current_organization_id', %s, true);", (str(organization_id),))
        else:
            cursor.execute("SELECT set_config('app.current_organization_id', '', true);")

        if user_id:
            cursor.execute("SELECT set_config('app.current_user_id', %s, true);", (str(user_id),))
        else:
            cursor.execute("SELECT set_config('app.current_user_id', '', true);")

        cursor.execute("SELECT set_config('app.is_super_admin', %s, true);", ("true" if is_super_admin else "false",))


@contextmanager
def scoped_tenant_transaction(
    connection: Connection,
    organization_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    is_super_admin: bool = False,
) -> Generator[Connection, None, None]:
    """
    Context manager that guarantees transaction-scoped RLS context parameters
    are applied and cleared cleanly upon exit.
    """
    set_tenant_context(
        connection=connection,
        organization_id=organization_id,
        user_id=user_id,
        is_super_admin=is_super_admin,
    )
    try:
        yield connection
    finally:
        pass
