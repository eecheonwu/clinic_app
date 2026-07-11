"""
CMP Auth Pydantic Schemas.

Request and response models for authentication endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from models.user import UserRole


class PatientRegisterRequest(BaseModel):
    """Request schema for patient registration."""

    phone_number: str = Field(..., min_length=10, max_length=15, description="Phone number")
    full_name: str = Field(..., min_length=1, max_length=255, description="Full legal name")
    date_of_birth: Optional[datetime] = Field(None, description="Date of birth")
    gender: Optional[str] = Field(None, max_length=10, description="Gender identity")
    emergency_contact: Optional[str] = Field(None, max_length=255, description="Emergency contact")


class VerifyRequestRequest(BaseModel):
    """Request schema for OTP verification request."""

    phone_number: str = Field(..., min_length=10, max_length=15, description="Phone number to verify")


class VerifyCodeRequest(BaseModel):
    """Request schema for OTP code verification."""

    phone_number: str = Field(..., min_length=10, max_length=15, description="Phone number")
    otp_code: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")


class StaffLoginRequest(BaseModel):
    """Request schema for staff login."""

    email: EmailStr = Field(..., description="Staff email address")
    password: str = Field(..., min_length=1, description="Password")


class TokenResponse(BaseModel):
    """Response schema for JWT tokens."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")


class UserResponse(BaseModel):
    """Response schema for user data."""

    id: str = Field(..., description="User UUID")
    phone_number: str = Field(..., description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    role: UserRole = Field(..., description="User role")
    is_verified: bool = Field(..., description="Phone verification status")

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Response schema for authentication operations."""

    user: UserResponse = Field(..., description="User data")
    tokens: TokenResponse = Field(..., description="JWT tokens")


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code for client handling")
