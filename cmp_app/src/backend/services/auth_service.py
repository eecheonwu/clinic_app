"""
CMP Authentication Service.

Implements:
- JWT token generation and validation
- OTP generation, verification, and rate limiting
- Patient registration with phone verification
- Staff login with email/password authentication
- Role-based access control
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.user import User, UserRole, PatientProfile, VerificationOTP


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def hash_otp(otp: str) -> str:
    """Hash an OTP code for storage."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(otp.encode('utf-8'), salt).decode('utf-8')


def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    """Verify an OTP code against its hash."""
    return bcrypt.checkpw(plain_otp.encode('utf-8'), hashed_otp.encode('utf-8'))


class AuthService:
    """
    Authentication service for CMP.

    Handles user registration, OTP verification, login, and JWT management.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Password Operations ───────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return hash_password(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return verify_password(plain_password, hashed_password)

    # ── JWT Operations ────────────────────────────────────────────────────

    def create_access_token(self, user_id: str, role: UserRole) -> str:
        """Create a JWT access token for a user."""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        payload = {
            "sub": str(user_id),
            "role": role.value,
            "type": "access",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

    def create_refresh_token(self, user_id: str) -> str:
        """Create a JWT refresh token for a user."""
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

    def decode_token(self, token: str) -> dict:
        """Decode and validate a JWT token."""
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

    # ── OTP Operations ────────────────────────────────────────────────────

    @staticmethod
    def generate_otp() -> str:
        """Generate a 6-digit OTP code."""
        return str(secrets.randbelow(1000000)).zfill(6)

    @staticmethod
    def hash_otp(otp: str) -> str:
        """Hash an OTP code for storage."""
        return hash_otp(otp)

    @staticmethod
    def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
        """Verify an OTP code against its hash."""
        return verify_otp(plain_otp, hashed_otp)

    async def check_rate_limit(self, phone_number: str) -> int:
        """
        Check OTP request rate limit for a phone number.

        Returns the count of requests in the last 15 minutes.
        """
        window_start = datetime.now(timezone.utc) - timedelta(
            seconds=settings.OTP_RATE_LIMIT_WINDOW_SECONDS
        )
        result = await self.db.execute(
            select(func.count(VerificationOTP.id))
            .where(VerificationOTP.phone_number == phone_number)
            .where(VerificationOTP.created_at >= window_start)
        )
        return result.scalar_one()

    async def get_active_otp(self, phone_number: str) -> Optional[VerificationOTP]:
        """Get the active (unused, not expired) OTP for a phone number."""
        result = await self.db.execute(
            select(VerificationOTP)
            .where(VerificationOTP.phone_number == phone_number)
            .where(VerificationOTP.is_used == False)
            .where(VerificationOTP.expires_at > datetime.now(timezone.utc))
            .order_by(VerificationOTP.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def create_otp(
        self,
        phone_number: str,
        delivery_channel: str = "whatsapp",
    ) -> VerificationOTP:
        """
        Create a new OTP for a phone number.

        Rate limits: max 3 requests per phone per 15 minutes.
        """
        # Check rate limit
        request_count = await self.check_rate_limit(phone_number)
        if request_count >= settings.OTP_RATE_LIMIT_REQUESTS:
            raise ValueError("Rate limit exceeded. Please try again later.")

        # Generate and hash OTP
        otp_code = self.generate_otp()
        hashed_otp = self.hash_otp(otp_code)

        # Create OTP record
        otp = VerificationOTP(
            phone_number=phone_number,
            hashed_otp=hashed_otp,
            expires_at=datetime.now(timezone.utc) + timedelta(
                seconds=settings.OTP_TTL_SECONDS
            ),
            delivery_channel=delivery_channel,
        )
        self.db.add(otp)
        await self.db.flush()

        return otp

    async def verify_otp_code(
        self,
        phone_number: str,
        otp_code: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Verify an OTP code for a phone number.

        Returns:
            tuple: (success, error_message)
        """
        # Get active OTP
        otp = await self.get_active_otp(phone_number)
        if not otp:
            return False, "No active OTP found. Please request a new code."

        # Check attempts
        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            return False, "Maximum attempts exceeded. Please request a new code."

        # Verify OTP
        if not self.verify_otp(otp_code, otp.hashed_otp):
            otp.attempts += 1
            await self.db.flush()
            return False, "Invalid OTP code."

        # Mark OTP as used
        otp.is_used = True
        await self.db.flush()

        return True, None

    # ── User Operations ───────────────────────────────────────────────────

    async def get_user_by_phone(self, phone_number: str) -> Optional[User]:
        """Get a user by phone number."""
        result = await self.db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def register_patient(
        self,
        phone_number: str,
        full_name: str,
        date_of_birth: Optional[datetime] = None,
        gender: Optional[str] = None,
        emergency_contact: Optional[str] = None,
    ) -> User:
        """
        Register a new patient user.

        Creates a user with role=patient and associated patient profile.
        """
        # Check if user already exists
        existing_user = await self.get_user_by_phone(phone_number)
        if existing_user:
            raise ValueError("User with this phone number already exists.")

        # Generate a random password for patient (they'll verify via OTP)
        temp_password = secrets.token_urlsafe(16)
        password_hash = self.hash_password(temp_password)

        # Create user
        user = User(
            phone_number=phone_number,
            password_hash=password_hash,
            role=UserRole.PATIENT,
        )
        self.db.add(user)
        await self.db.flush()

        # Create patient profile
        profile = PatientProfile(
            user_id=user.id,
            full_name=full_name,
            date_of_birth=date_of_birth,
            gender=gender,
            emergency_contact=emergency_contact,
        )
        self.db.add(profile)
        await self.db.flush()

        return user

    async def authenticate_staff(
        self,
        email: str,
        password: str,
    ) -> Optional[User]:
        """
        Authenticate a staff user with email and password.

        Returns the user if authentication succeeds, None otherwise.
        """
        user = await self.get_user_by_email(email)
        if not user:
            return None

        # Check if user is staff (not patient)
        if user.role == UserRole.PATIENT:
            return None

        # Verify password
        if not self.verify_password(password, user.password_hash):
            return None

        return user

    async def get_user_verification_status(self, user_id: str) -> bool:
        """Check if user's phone is verified (has used an OTP)."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        # Check if user has any used OTPs
        result = await self.db.execute(
            select(func.count(VerificationOTP.id))
            .where(VerificationOTP.phone_number == user.phone_number)
            .where(VerificationOTP.is_used == True)
        )
        return result.scalar_one() > 0
