"""Authentication API routes for user management, login, and API keys.

This module provides authentication endpoints for:
- Setup status checking (is initial setup required?)
- User registration (first admin user only)
- User login/logout with session cookies
- Current user info
- API key management (admin only)

NEM-5312: Phase 2 API Protection implementation.

Endpoints:
    GET  /api/auth/setup-status     - Check if initial setup is required
    POST /api/auth/register         - Register first admin user
    POST /api/auth/login            - Login with username/password
    POST /api/auth/logout           - Clear session
    GET  /api/auth/me               - Get current authenticated user
    POST /api/auth/api-keys         - Create API key (admin only)
    GET  /api/auth/api-keys         - List API keys (admin only)
    DELETE /api/auth/api-keys/{id}  - Revoke API key (admin only)
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_redis_optional
from backend.api.schemas.auth import (
    APIKeyCreateRequest,
    APIKeyCreateResponse,
    APIKeyListResponse,
    APIKeyResponse,
    APIKeyRevokeResponse,
    LoginResponse,
    LogoutResponse,
    SetupStatusResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.api_key import APIKey
from backend.models.user import User
from backend.services.auth_service import AuthService
from backend.services.session_service import SessionExpiredError, SessionService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Session cookie configuration
SESSION_COOKIE_NAME = "session_id"
SESSION_COOKIE_MAX_AGE = 24 * 60 * 60  # 24 hours in seconds
SESSION_COOKIE_SECURE = True  # Set to False in development if not using HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"


def _generate_user_id() -> str:
    """Generate a unique user ID.

    Returns:
        UUID string for user ID.
    """
    import uuid

    return str(uuid.uuid4())


def _generate_api_key_id() -> str:
    """Generate a unique API key ID.

    Returns:
        UUID string for API key ID.
    """
    import uuid

    return str(uuid.uuid4())


# =============================================================================
# Setup Status
# =============================================================================


@router.get(
    "/setup-status",
    response_model=SetupStatusResponse,
    responses={
        200: {"description": "Setup status returned successfully"},
        500: {"description": "Internal server error"},
    },
)
async def get_setup_status(
    db: AsyncSession = Depends(get_db),
) -> SetupStatusResponse:
    """Check if initial setup is required.

    Returns whether the system needs initial setup (first admin user registration).
    Setup is required if no users exist in the database.

    Returns:
        SetupStatusResponse indicating if setup is required.
    """
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar() or 0

    setup_required = count == 0

    logger.info(
        "Setup status checked",
        extra={
            "setup_required": setup_required,
            "user_count": count,
        },
    )

    return SetupStatusResponse(setup_required=setup_required)


# =============================================================================
# User Registration
# =============================================================================


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User registered successfully"},
        400: {"description": "Validation error"},
        409: {"description": "Registration blocked (users already exist)"},
        500: {"description": "Internal server error"},
    },
)
async def register_user(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register the first admin user.

    This endpoint is ONLY available when no users exist in the system.
    Once the first user is registered, this endpoint returns 409 Conflict.

    The first user is automatically granted admin privileges.

    Args:
        request: User registration data (username, email, password).
        db: Database session.

    Returns:
        UserResponse with the created user's information.

    Raises:
        HTTPException: 409 if users already exist.
        HTTPException: 400 if username or email already taken.
    """
    # Check if any users exist
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar() or 0

    if count > 0:
        logger.warning(
            "Registration attempt blocked: users already exist",
            extra={"existing_user_count": count},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration is closed. Users already exist in the system.",
        )

    # Check for duplicate username
    username_check = await db.execute(select(User).where(User.username == request.username))
    if username_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Check for duplicate email
    email_check = await db.execute(select(User).where(User.email == request.email))
    if email_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create auth service and hash password
    auth_service = AuthService()
    password_hash = auth_service.hash_password(request.password)

    # Create user (first user is always admin)
    user = User(
        id=_generate_user_id(),
        username=request.username,
        email=request.email,
        password_hash=password_hash,
        is_active=True,
        is_admin=True,  # First user gets admin privileges
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(
        "First admin user registered",
        extra={
            "user_id": user.id,
            "username": user.username,
        },
    )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


# =============================================================================
# Login/Logout
# =============================================================================


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials"},
        500: {"description": "Internal server error"},
    },
)
async def login(
    request: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Login with username and password.

    On successful login, sets an HTTP-only session cookie and returns
    the authenticated user's information.

    Args:
        request: Login credentials (username, password).
        response: FastAPI Response object for setting cookies.
        db: Database session.

    Returns:
        LoginResponse with user information.

    Raises:
        HTTPException: 401 if credentials are invalid.
    """
    # Find user by username
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()

    # Invalid username
    if not user:
        logger.warning(
            "Login failed: user not found",
            extra={"username": request.username},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Check if user is active
    if not user.is_active:
        logger.warning(
            "Login failed: user account disabled",
            extra={"user_id": user.id, "username": user.username},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    # Verify password
    auth_service = AuthService()
    if not auth_service.verify_password(request.password, user.password_hash):
        logger.warning(
            "Login failed: invalid password",
            extra={"user_id": user.id, "username": user.username},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Update last login timestamp
    user.last_login_at = datetime.now(UTC)
    await db.commit()

    # Create session (if Redis is available)
    session_id = None
    redis_client = await get_redis_optional()
    if redis_client:
        session_service = SessionService(redis_client)
        session_id = await session_service.create_session(
            user_id=user.id,
            session_data={
                "username": user.username,
                "is_admin": user.is_admin,
            },
            ttl=timedelta(hours=24),
        )

        # Set session cookie
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            max_age=SESSION_COOKIE_MAX_AGE,
            httponly=SESSION_COOKIE_HTTPONLY,
            samesite=SESSION_COOKIE_SAMESITE,
            secure=SESSION_COOKIE_SECURE,
        )

    logger.info(
        "User logged in",
        extra={
            "user_id": user.id,
            "username": user.username,
            "session_created": session_id is not None,
        },
    )

    return LoginResponse(
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        ),
        message="Login successful",
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    responses={
        200: {"description": "Logged out successfully"},
        500: {"description": "Internal server error"},
    },
)
async def logout(
    response: Response,
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> LogoutResponse:
    """Logout and clear session.

    Deletes the session from Redis (if available) and clears the session cookie.

    Args:
        response: FastAPI Response object for clearing cookies.
        session_id: Session ID from cookie.

    Returns:
        LogoutResponse confirming logout.
    """
    # Delete session from Redis if we have a session ID
    if session_id:
        redis_client = await get_redis_optional()
        if redis_client:
            session_service = SessionService(redis_client)
            await session_service.delete_session(session_id)

    # Clear session cookie
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=SESSION_COOKIE_HTTPONLY,
        samesite=SESSION_COOKIE_SAMESITE,
        secure=SESSION_COOKIE_SECURE,
    )

    logger.info("User logged out", extra={"had_session": session_id is not None})

    return LogoutResponse(message="Logged out successfully")


# =============================================================================
# Current User
# =============================================================================


async def get_current_user(
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency to get the current authenticated user.

    Args:
        session_id: Session ID from cookie.
        db: Database session.

    Returns:
        The authenticated User object.

    Raises:
        HTTPException: 401 if not authenticated or session expired.
    """
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Get Redis client
    redis_client = await get_redis_optional()
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session service unavailable",
        )

    # Get session data
    session_service = SessionService(redis_client)
    try:
        session_data = await session_service.get_session(session_id)
    except SessionExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        ) from None

    # Get user from database
    user_id = session_data.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    return user


async def get_current_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """Dependency to get the current authenticated admin user.

    Args:
        user: Current authenticated user.

    Returns:
        The authenticated admin User object.

    Raises:
        HTTPException: 403 if user is not an admin.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        200: {"description": "Current user information"},
        401: {"description": "Not authenticated"},
        500: {"description": "Internal server error"},
    },
)
async def get_me(
    user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user information.

    Args:
        user: Current authenticated user (from dependency).

    Returns:
        UserResponse with the user's information.
    """
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


# =============================================================================
# API Key Management (Admin Only)
# =============================================================================


@router.post(
    "/api-keys",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "API key created successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Admin privileges required"},
        500: {"description": "Internal server error"},
    },
)
async def create_api_key(
    request: APIKeyCreateRequest,
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIKeyCreateResponse:
    """Create a new API key.

    Only admin users can create API keys. The full API key is only returned
    once at creation time - it cannot be retrieved later.

    Args:
        request: API key creation data (name, optional expiration).
        user: Current admin user (from dependency).
        db: Database session.

    Returns:
        APIKeyCreateResponse with the full API key (store it securely!).
    """
    auth_service = AuthService()

    # Generate the full API key
    full_key = auth_service.generate_api_key()
    key_hash = auth_service.hash_api_key(full_key)

    # Extract prefix for identification (first 12 chars)
    prefix = full_key[:12]

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(UTC) + timedelta(days=request.expires_in_days)

    # Create API key record
    api_key = APIKey(
        id=_generate_api_key_id(),
        user_id=user.id,
        prefix=prefix,
        key_hash=key_hash,
        name=request.name,
        expires_at=expires_at,
        is_active=True,
    )

    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    logger.info(
        "API key created",
        extra={
            "api_key_id": api_key.id,
            "user_id": user.id,
            "name": request.name,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    )

    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        key=full_key,  # Only returned at creation!
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
    )


@router.get(
    "/api-keys",
    response_model=APIKeyListResponse,
    responses={
        200: {"description": "List of API keys"},
        401: {"description": "Not authenticated"},
        403: {"description": "Admin privileges required"},
        500: {"description": "Internal server error"},
    },
)
async def list_api_keys(
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIKeyListResponse:
    """List all API keys for the current admin user.

    Note: The full API key is never returned - only the prefix for identification.

    Args:
        user: Current admin user (from dependency).
        db: Database session.

    Returns:
        APIKeyListResponse with all API keys belonging to the user.
    """
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == user.id).order_by(APIKey.created_at.desc())
    )
    api_keys = result.scalars().all()

    items = [
        APIKeyResponse(
            id=key.id,
            name=key.name,
            prefix=key.prefix,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            expires_at=key.expires_at,
            is_active=key.is_active,
            is_expired=key.is_expired,
        )
        for key in api_keys
    ]

    return APIKeyListResponse(items=items, total=len(items))


@router.delete(
    "/api-keys/{key_id}",
    response_model=APIKeyRevokeResponse,
    responses={
        200: {"description": "API key revoked successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Admin privileges required"},
        404: {"description": "API key not found"},
        500: {"description": "Internal server error"},
    },
)
async def revoke_api_key(
    key_id: str,
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> APIKeyRevokeResponse:
    """Revoke (deactivate) an API key.

    The key is not deleted, but marked as inactive. This preserves audit trail.

    Args:
        key_id: ID of the API key to revoke.
        user: Current admin user (from dependency).
        db: Database session.

    Returns:
        APIKeyRevokeResponse confirming revocation.

    Raises:
        HTTPException: 404 if API key not found or doesn't belong to user.
    """
    result = await db.execute(select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id))
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found",
        )

    # Deactivate the key
    api_key.is_active = False
    await db.commit()

    logger.info(
        "API key revoked",
        extra={
            "api_key_id": key_id,
            "user_id": user.id,
        },
    )

    return APIKeyRevokeResponse(message="API key revoked successfully")
