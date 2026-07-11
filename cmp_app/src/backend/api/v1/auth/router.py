"""
CMP Auth API Router.

Implements authentication endpoints:
- POST /api/v1/auth/register - Patient registration
- POST /api/v1/auth/verify-request - Request OTP (rate limited)
- POST /api/v1/auth/verify-code - Verify OTP and issue JWT
- POST /api/v1/auth/login - Staff login
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import RoleChecker
from db.session import get_db
from models.user import User, UserRole
from services.auth_service import AuthService
from api.v1.auth.schemas import (
    PatientRegisterRequest,
    VerifyRequestRequest,
    VerifyCodeRequest,
    StaffLoginRequest,
    TokenResponse,
    UserResponse,
    AuthResponse,
)

# Create router
router = APIRouter()


# ── Helper Functions ───────────────────────────────────────────────────

def create_token_response(user: User) -> TokenResponse:
    """Create token response for a user."""
    auth_service = AuthService(None)  # Not using db for this
    access_token = auth_service.create_access_token(user.id, user.role)
    refresh_token = auth_service.create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def create_user_response(user: User) -> UserResponse:
    """Create user response for a user."""
    return UserResponse(
        id=str(user.id),
        phone_number=user.phone_number,
        email=user.email,
        role=user.role,
        is_verified=False,  # Will be updated after OTP verification
    )


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_patient(
    request: PatientRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new patient user.

    Creates a user with role=patient and associated patient profile.
    Returns user data and JWT tokens (for initial access before phone verification).
    """
    auth_service = AuthService(db)

    # Check if user already exists
    existing_user = await auth_service.get_user_by_phone(request.phone_number)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists",
        )

    # Register patient
    try:
        user = await auth_service.register_patient(
            phone_number=request.phone_number,
            full_name=request.full_name,
            date_of_birth=request.date_of_birth,
            gender=request.gender,
            emergency_contact=request.emergency_contact,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Create tokens
    tokens = create_token_response(user)

    return AuthResponse(
        user=create_user_response(user),
        tokens=tokens,
    )


@router.post("/verify-request", status_code=status.HTTP_202_ACCEPTED)
async def verify_request(
    request: VerifyRequestRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request an OTP for phone verification.

    Rate limited: max 3 requests per phone per 15 minutes.
    In production, this would enqueue a task to send OTP via WhatsApp/SMS.
    """
    auth_service = AuthService(db)

    # Check if user exists
    user = await auth_service.get_user_by_phone(request.phone_number)
    if not user:
        # Don't reveal if phone exists - return success anyway
        return {"message": "If the phone number is registered, an OTP will be sent."}

    # Check rate limit
    try:
        otp = await auth_service.create_otp(request.phone_number)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )

    # TODO: In production, enqueue Celery task to send OTP
    # For now, return the OTP in development (remove in production)
    if settings.is_development:
        return {
            "message": "OTP sent successfully",
            "otp": otp.hashed_otp[:10] + "...",  # Only show partial in dev
        }

    return {"message": "OTP sent successfully"}


@router.post("/verify-code", response_model=TokenResponse)
async def verify_code(
    request: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify an OTP code and issue JWT tokens.

    Validates the OTP and returns fresh tokens for the user.
    """
    auth_service = AuthService(db)

    # Get user
    user = await auth_service.get_user_by_phone(request.phone_number)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify OTP
    success, error = await auth_service.verify_otp_code(
        request.phone_number,
        request.otp_code,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    # Create tokens
    tokens = create_token_response(user)

    return tokens


@router.post("/login", response_model=TokenResponse)
async def login(
    request: StaffLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Staff login with email and password.

    Only staff users (receptionist, doctor, manager, admin, executive) can login.
    """
    auth_service = AuthService(db)

    # Authenticate staff
    user = await auth_service.authenticate_staff(
        email=request.email,
        password=request.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Create tokens
    tokens = create_token_response(user)

    return tokens


# ── Protected Endpoint Example ───────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: User = Depends(RoleChecker([UserRole.PATIENT, UserRole.DOCTOR, UserRole.RECEPTIONIST, UserRole.MANAGER, UserRole.ADMIN, UserRole.EXECUTIVE])),
):
    """
    Get current authenticated user's information.

    Requires any valid role.
    """
    return create_user_response(current_user)
