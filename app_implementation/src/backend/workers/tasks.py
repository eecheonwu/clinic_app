"""
CMP Celery Tasks for Notification Processing.

Async tasks for:
- OTP delivery
- Appointment confirmations
- Appointment reminders (24h and 2h)
- Cancellation alerts
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from celery import shared_task

from core.config import settings
from db.session import AsyncSessionLocal
from models.user import VerificationOTP
from services.notification_service import NotificationOrchestrator

logger = logging.getLogger(__name__)


# ── Helper Functions ───────────────────────────────────────────────────────

async def _get_db_session():
    """Get async database session for task context."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ── OTP Task ───────────────────────────────────────────────────────────────

@shared_task(
    name="send_otp_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_otp_task(
    self,
    verification_id: str,
    otp_code: str,
) -> dict:
    """
    Send OTP via notification orchestrator.

    Args:
        verification_id: UUID of the VerificationOTP record
        otp_code: Plain text OTP code to send

    Returns:
        dict with success status and provider used

    Note:
        This task does NOT require a User record to exist. The phone number
        is retrieved directly from the VerificationOTP record, which is
        created before the user account during the registration flow.
        Previously, this task looked up a User by phone number and returned
        early with "User not found" when no user existed yet — preventing
        OTP delivery for the registration flow.
    """
    import asyncio

    async def _send():
        async for db in _get_db_session():
            # Get OTP record
            from sqlalchemy import select
            result = await db.execute(
                select(VerificationOTP).where(VerificationOTP.id == verification_id)
            )
            otp = result.scalar_one_or_none()

            if not otp:
                logger.error(
                    "send_otp_task: OTP record not found (verification_id=%s)",
                    verification_id,
                )
                return {"success": False, "error": "OTP not found"}

            # Send via orchestrator with the actual OTP code.
            # The phone number comes directly from the OTP record — no User
            # lookup is needed. This is critical for the registration flow
            # where the user account is created AFTER OTP verification.
            orchestrator = NotificationOrchestrator(db)
            success, error, provider = await orchestrator.send_otp(
                otp.phone_number,
                otp_code,
            )

            if success:
                logger.info(
                    "send_otp_task: OTP delivered via %s to %s (verification_id=%s)",
                    provider,
                    otp.phone_number,
                    verification_id,
                )
            else:
                logger.error(
                    "send_otp_task: OTP delivery FAILED via %s to %s: %s "
                    "(verification_id=%s)",
                    provider,
                    otp.phone_number,
                    error,
                    verification_id,
                )

            return {
                "success": success,
                "error": error,
                "provider": provider,
            }

    try:
        return asyncio.run(_send())
    except Exception as e:
        logger.error(
            "send_otp_task: Exception during OTP delivery "
            "(verification_id=%s): %s",
            verification_id,
            e,
            exc_info=True,
        )
        self.retry(exc=e, countdown=60)
        return {"success": False, "error": str(e)}


# ── Appointment Confirmation Task ───────────────────────────────────────────

@shared_task(
    name="send_appointment_confirmation_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_appointment_confirmation_task(
    self,
    appointment_id: str,
) -> dict:
    """
    Send appointment confirmation via notification orchestrator.

    Args:
        appointment_id: UUID of the appointment

    Returns:
        dict with success status and provider used
    """
    import asyncio

    async def _send():
        async for db in _get_db_session():
            # Get appointment
            from sqlalchemy import select
            result = await db.execute(
                select(Appointment).where(Appointment.id == appointment_id)
            )
            appointment = result.scalar_one_or_none()

            if not appointment:
                return {"success": False, "error": "Appointment not found"}

            # Get patient phone
            result = await db.execute(
                select(User).where(User.id == appointment.patient_id)
            )
            patient = result.scalar_one_or_none()

            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Send via orchestrator
            orchestrator = NotificationOrchestrator(db)
            success, error, provider = await orchestrator.send_appointment_confirmation(
                patient.phone_number,
                {
                    "doctor": "Doctor",
                    "date": str(appointment.start_datetime.date()) if appointment.start_datetime else "date",
                    "time": str(appointment.start_datetime.time()) if appointment.start_datetime else "time",
                },
            )

            return {
                "success": success,
                "error": error,
                "provider": provider,
            }

    try:
        return asyncio.run(_send())
    except Exception as e:
        self.retry(exc=e, countdown=60)
        return {"success": False, "error": str(e)}


# ── Appointment Reminder Task ───────────────────────────────────────────────

@shared_task(
    name="send_appointment_reminder_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_appointment_reminder_task(
    self,
    appointment_id: str,
    reminder_type: str = "24h",
) -> dict:
    """
    Send appointment reminder via notification orchestrator.

    Args:
        appointment_id: UUID of the appointment
        reminder_type: "24h" or "2h"

    Returns:
        dict with success status and provider used
    """
    import asyncio

    async def _send():
        async for db in _get_db_session():
            # Get appointment
            from sqlalchemy import select
            result = await db.execute(
                select(Appointment).where(Appointment.id == appointment_id)
            )
            appointment = result.scalar_one_or_none()

            if not appointment:
                return {"success": False, "error": "Appointment not found"}

            # Get patient phone
            result = await db.execute(
                select(User).where(User.id == appointment.patient_id)
            )
            patient = result.scalar_one_or_none()

            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Send via orchestrator
            orchestrator = NotificationOrchestrator(db)
            success, error, provider = await orchestrator.send_appointment_reminder(
                patient.phone_number,
                {
                    "doctor": "Doctor",
                    "time": str(appointment.start_datetime.time()) if appointment.start_datetime else "time",
                },
                reminder_type,
            )

            return {
                "success": success,
                "error": error,
                "provider": provider,
            }

    try:
        return asyncio.run(_send())
    except Exception as e:
        self.retry(exc=e, countdown=60)
        return {"success": False, "error": str(e)}


# ── Cancellation Alert Task ───────────────────────────────────────────────────

@shared_task(
    name="send_cancellation_alert_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_cancellation_alert_task(
    self,
    appointment_id: str,
) -> dict:
    """
    Send cancellation alert via notification orchestrator.

    Args:
        appointment_id: UUID of the appointment

    Returns:
        dict with success status and provider used
    """
    import asyncio

    async def _send():
        async for db in _get_db_session():
            # Get appointment
            from sqlalchemy import select
            result = await db.execute(
                select(Appointment).where(Appointment.id == appointment_id)
            )
            appointment = result.scalar_one_or_none()

            if not appointment:
                return {"success": False, "error": "Appointment not found"}

            # Get patient phone
            result = await db.execute(
                select(User).where(User.id == appointment.patient_id)
            )
            patient = result.scalar_one_or_none()

            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Send via orchestrator
            orchestrator = NotificationOrchestrator(db)
            success, error, provider = await orchestrator.send_cancellation_alert(
                patient.phone_number,
                {
                    "doctor": "Doctor",
                    "date": str(appointment.start_datetime.date()) if appointment.start_datetime else "date",
                },
            )

            return {
                "success": success,
                "error": error,
                "provider": provider,
            }

    try:
        return asyncio.run(_send())
    except Exception as e:
        self.retry(exc=e, countdown=60)
        return {"success": False, "error": str(e)}
