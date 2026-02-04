"""Authentication API schemas for user registration, login, and API key management.

This module defines Pydantic schemas for:
- User registration and login
- Session management
- API key CRUD operations
- Setup status checks

NEM-5312: Phase 2 API Protection implementation.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SetupStatusResponse(BaseModel):
    """Response schema for setup status check.

    Returns whether initial setup (first user registration) is required.
    """

    setup_required: bool = Field(
        ...,
        description="Whether initial setup is required (no users exist)",
    )


class UserRegisterRequest(BaseModel):
    """Request schema for user registration.

    Used for registering the first admin user during initial setup.
    After the first user exists, this endpoint is blocked.
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Username for login (alphanumeric, underscores, hyphens only)",
    )
    email: str = Field(
        ...,
        min_length=5,
        max_length=255,
        pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        description="Email address for the user",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (minimum 8 characters)",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets minimum security requirements.

        Requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        """
        if not any(c.isupper() for c in v):
            msg = "Password must contain at least one uppercase letter"
            raise ValueError(msg)
        if not any(c.islower() for c in v):
            msg = "Password must contain at least one lowercase letter"
            raise ValueError(msg)
        if not any(c.isdigit() for c in v):
            msg = "Password must contain at least one digit"
            raise ValueError(msg)
        return v


class UserLoginRequest(BaseModel):
    """Request schema for user login."""

    username: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Username",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Password",
    )


class UserResponse(BaseModel):
    """Response schema for user information.

    Does NOT include password hash or other sensitive fields.
    """

    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    is_active: bool = Field(..., description="Whether the user account is active")
    is_admin: bool = Field(..., description="Whether the user has admin privileges")
    created_at: datetime = Field(..., description="When the user was created")
    last_login_at: datetime | None = Field(None, description="Last login timestamp")

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    """Response schema for successful login.

    Returns user info. Session token is set via HTTP-only cookie.
    """

    user: UserResponse = Field(..., description="Authenticated user information")
    message: str = Field(default="Login successful", description="Status message")


class LogoutResponse(BaseModel):
    """Response schema for logout."""

    message: str = Field(default="Logged out successfully", description="Status message")


# =============================================================================
# API Key Schemas
# =============================================================================


class APIKeyCreateRequest(BaseModel):
    """Request schema for creating a new API key."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable name for the API key",
    )
    expires_in_days: int | None = Field(
        None,
        ge=1,
        le=365,
        description="Number of days until the key expires (None = never expires)",
    )


class APIKeyCreateResponse(BaseModel):
    """Response schema for API key creation.

    IMPORTANT: The full API key is only returned once at creation time.
    It cannot be retrieved later - only the prefix is stored.
    """

    id: str = Field(..., description="API key ID")
    name: str = Field(..., description="Human-readable name")
    prefix: str = Field(..., description="Key prefix for identification")
    key: str = Field(
        ...,
        description="Full API key (ONLY returned at creation, store it securely!)",
    )
    created_at: datetime = Field(..., description="When the key was created")
    expires_at: datetime | None = Field(None, description="When the key expires")


class APIKeyResponse(BaseModel):
    """Response schema for API key information (without the key itself)."""

    id: str = Field(..., description="API key ID")
    name: str = Field(..., description="Human-readable name")
    prefix: str = Field(..., description="Key prefix for identification")
    created_at: datetime = Field(..., description="When the key was created")
    last_used_at: datetime | None = Field(None, description="When the key was last used")
    expires_at: datetime | None = Field(None, description="When the key expires")
    is_active: bool = Field(..., description="Whether the key is active")
    is_expired: bool = Field(..., description="Whether the key has expired")

    model_config = {"from_attributes": True}


class APIKeyListResponse(BaseModel):
    """Response schema for listing API keys."""

    items: list[APIKeyResponse] = Field(..., description="List of API keys")
    total: int = Field(..., description="Total number of API keys")


class APIKeyRevokeResponse(BaseModel):
    """Response schema for API key revocation."""

    message: str = Field(
        default="API key revoked successfully",
        description="Status message",
    )


# =============================================================================
# Admin User Management Schemas
# =============================================================================


class AdminUserCreateRequest(BaseModel):
    """Request schema for admin creating a new user."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Username for login (alphanumeric, underscores, hyphens only)",
    )
    email: str = Field(
        ...,
        min_length=5,
        max_length=255,
        pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        description="Email address for the user",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (minimum 8 characters)",
    )
    is_admin: bool = Field(
        default=False,
        description="Whether the user should have admin privileges",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets minimum security requirements."""
        if not any(c.isupper() for c in v):
            msg = "Password must contain at least one uppercase letter"
            raise ValueError(msg)
        if not any(c.islower() for c in v):
            msg = "Password must contain at least one lowercase letter"
            raise ValueError(msg)
        if not any(c.isdigit() for c in v):
            msg = "Password must contain at least one digit"
            raise ValueError(msg)
        return v


class AdminUserListResponse(BaseModel):
    """Response schema for listing users."""

    items: list[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")


class AdminUserDeleteResponse(BaseModel):
    """Response schema for user deletion."""

    message: str = Field(
        default="User deleted successfully",
        description="Status message",
    )
