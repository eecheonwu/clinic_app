"""
CMP Auth API Router.

Implements authentication endpoints:
- POST /api/v1/auth/register - Patient registration
- POST /api/v1/auth/verify-request - Request OTP (rate limited)
- POST /api/v1/auth/verify-code - Verify OTP and issue JWT
- POST /api/v1/auth/login - Staff login
"""

import logging
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

logger = logging.getLogger(__name__)

# Import Celery task for OTP delivery
try:
    from workers.tasks import send_otp_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

# Create router
router = APIRouter()


# ── Helper Functions ───────────────────────────────────────────────────

def create_token_response(user: User) -> TokenResponse:
    """Create token response for a user."""
    auth_service = AuthService(None)  # Not using db for this
    # Ensure role is a UserRole enum (it may come as a string from DB)
    role = user.role if isinstance(user.role, UserRole) else UserRole(user.role)
    access_token = auth_service.create_access_token(user.id, role)
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


async def _send_otp_notification(db: AsyncSession, otp_id: str, phone_number: str, otp_code: str) -> None:
    """
    Send OTP via notification service with proper error handling.

    Uses Celery if available, otherwise falls back to synchronous delivery.
    Logs all failures so they are visible in monitoring.
    """
    try:
        if CELERY_AVAILABLE:
            send_otp_task.delay(otp_id, otp_code)
            logger.info(
                "OTP delivery enqueued via Celery for %s (otp_id=%s)",
                phone_number,
                otp_id,
            )
        else:
            from services.notification_service import NotificationOrchestrator
            orchestrator = NotificationOrchestrator(db)
            success, error, provider = await orchestrator.send_otp(
                phone_number,
                otp_code,
            )
            if success:
                logger.info(
                    "OTP delivered via %s to %s (otp_id=%s)",
                    provider,
                    phone_number,
                    otp_id,
                )
            else:
                logger.error(
                    "OTP delivery FAILED for %s via %s: %s (otp_id=%s). "
                    "OTP is stored in DB but was not delivered.",
                    phone_number,
                    provider,
                    error,
                    otp_id,
                )
    except Exception as e:
        logger.error(
            "OTP delivery exception for %s (otp_id=%s): %s",
            phone_number,
            otp_id,
            e,
            exc_info=True,
        )


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_patient(
    request: PatientRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate patient registration.

    Validates that the phone number is not already registered,
    generates and sends an OTP code to the target phone number,
    and returns a signed registration token. Patient data is NOT
    persisted to the database until OTP verification completes.
    """
    auth_service = AuthService(db)

    # Check if user already exists
    existing_user = await auth_service.get_user_by_phone(request.phone_number)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists",
        )

    # Generate OTP
    try:
        otp, otp_code = await auth_service.create_otp(request.phone_number)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )

    # Send OTP via notification service (with proper error logging)
    await _send_otp_notification(db, str(otp.id), otp.phone_number, otp_code)

    # Create signed registration token with pending details
    reg_token = auth_service.create_registration_token({
        "phone_number": request.phone_number,
        "full_name": request.full_name,
        "date_of_birth": request.date_of_birth,
        "gender": request.gender,
        "emergency_contact": request.emergency_contact,
    })

    # In development, include the OTP code in the response for testing
    if settings.is_development:
        return AuthResponse(
            message="OTP code generated and sent to target phone number. Verify OTP to complete registration.",
            registration_token=reg_token,
            otp=otp_code,  # Return actual OTP code in development for testing
        )

    return AuthResponse(
        message="OTP code generated and sent to target phone number. Verify OTP to complete registration.",
        registration_token=reg_token,
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
        otp, otp_code = await auth_service.create_otp(request.phone_number)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )

    # Send OTP via notification service (with proper error logging)
    await _send_otp_notification(db, str(otp.id), otp.phone_number, otp_code)

    # In development, return the OTP for testing
    if settings.is_development:
        return {
            "message": "OTP sent successfully",
            "otp": otp_code,  # Return actual OTP code in development for testing
        }

    return {"message": "OTP sent successfully"}


@router.post("/verify-code", response_model=TokenResponse)
async def verify_code(
    request: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify an OTP code and issue JWT tokens.

    Validates the OTP and creates patient record in DB if registering, returning fresh tokens.
    """
    auth_service = AuthService(db)

    # 1. Verify OTP code
    success, error = await auth_service.verify_otp_code(
        request.phone_number,
        request.otp_code,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or "Invalid OTP code",
        )

    # 2. Get existing user or finalize patient registration upon valid OTP
    user = await auth_service.get_user_by_phone(request.phone_number)
    if not user:
        reg_payload = None
        if request.registration_token:
            try:
                reg_payload = auth_service.decode_registration_token(request.registration_token)
            except Exception:
                pass

        if not reg_payload and request.registration_data:
            reg_payload = request.registration_data

        if not reg_payload:
            reg_payload = {
                "phone_number": request.phone_number,
                "full_name": f"Patient {request.phone_number[-4:]}",
            }

        try:
            user = await auth_service.register_patient(
                phone_number=request.phone_number,
                full_name=reg_payload.get("full_name", f"Patient {request.phone_number[-4:]}"),
                date_of_birth=reg_payload.get("date_of_birth"),
                gender=reg_payload.get("gender"),
                emergency_contact=reg_payload.get("emergency_contact"),
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
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
