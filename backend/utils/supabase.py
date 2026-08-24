"""
Supabase client integration and claim resolution utilities for AMAP.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from app.config import get_settings


class SupabaseClientHelper:
    """
    Helper for interacting with Supabase services and constructing authenticated headers.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        """Return True if Supabase URL and anon key are configured."""
        return bool(self.settings.supabase_url and self.settings.supabase_anon_key)

    def get_auth_headers(self, jwt_token: Optional[str] = None) -> Dict[str, str]:
        """Construct standard Supabase authorization headers."""
        headers: Dict[str, str] = {
            "apikey": self.settings.supabase_anon_key or "",
            "Content-Type": "application/json",
        }
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"
        elif self.settings.supabase_service_role_key:
            headers["Authorization"] = f"Bearer {self.settings.supabase_service_role_key}"
        return headers

    def build_tenant_claim(self, organization_id: UUID, user_id: UUID, roles: list[str]) -> Dict[str, Any]:
        """Construct standard Supabase JWT claims structure for AMAP multi-tenant RLS."""
        return {
            "sub": str(user_id),
            "organization_id": str(organization_id),
            "roles": roles,
            "aud": "authenticated",
            "role": "authenticated",
        }
