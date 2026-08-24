"""
Authentication API routes for AMAP.

Provides:
- POST /auth/login: Authenticate user credentials and return JWT access token.
- GET /auth/me: Return current authenticated user context and permissions.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_auth_service, get_current_user
from models.auth import AuthenticatedUserContext, LoginRequest, TokenResponse
from services.auth_service import AuthService
from services.base import UnauthorizedError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and obtain JWT token",
)
def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Authenticate a user within an organization using their email and password.
    Returns a signed JWT bearer token with claims.
    """
    try:
        _, token_response = auth_service.authenticate_user(
            organization_id=payload.organization_id,
            email=payload.email,
            password=payload.password,
        )
        return token_response
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.get(
    "/me",
    response_model=AuthenticatedUserContext,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
def get_me(
    current_user: AuthenticatedUserContext = Depends(get_current_user),
) -> AuthenticatedUserContext:
    """
    Return the authenticated user's profile, organization context, roles, and permissions.
    """
    return current_user
