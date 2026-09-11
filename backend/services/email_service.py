"""Email notification service for SkyZen.

Wires Resend API for real transactional email dispatch (verification codes, alerts).
Gracefully falls back to sandbox logging if API key is invalid or offline.
"""

import os
import logging
from typing import Optional
import httpx

logger = logging.getLogger("weathergpt.email")


def is_test_environment() -> bool:
    return bool(
        os.environ.get("PYTEST_CURRENT_TEST") or
        os.getenv("TESTING", "").lower() in ("true", "1") or
        os.getenv("ENVIRONMENT", "").lower() == "testing"
    )


async def send_verification_email(to_email: str, user_name: str, verification_code: str) -> bool:
    """Sends account verification code via Resend API if configured, otherwise logs safely."""
    if is_test_environment():
        logger.info(f"[Test Email Sandbox] Verification token for {to_email}: {verification_code}")
        return True

    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        logger.info(f"[Email Sandbox] Verification token for {to_email}: {verification_code}")
        return False

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 540px; margin: 0 auto; padding: 24px; border: 1px solid #E2E8F0; border-radius: 12px;">
      <h2 style="color: #1D4ED8; margin-top: 0;">SkyZen Weather Intelligence</h2>
      <p>Hello <strong>{user_name}</strong>,</p>
      <p>Welcome to SkyZen. Your 6-digit email verification code is:</p>
      <div style="font-size: 28px; font-weight: 800; letter-spacing: 6px; color: #0F172A; padding: 16px; background: #EFF6FF; border-radius: 8px; text-align: center; margin: 16px 0;">
        {verification_code}
      </div>
      <p style="font-size: 13px; color: #64748B;">This verification code will expire in 24 hours. If you did not request this, you can safely ignore this email.</p>
      <hr style="border: none; border-top: 1px solid #E2E8F0; margin: 20px 0;" />
      <p style="font-size: 11px; color: #94A3B8;">Ministry of Earth Sciences (MoES) & India Meteorological Department (IMD) | SkyZen SIH26068</p>
    </div>
    """

    payload = {
        "from": "SkyZen Weather <onboarding@resend.dev>",
        "to": [to_email],
        "subject": f"Your SkyZen Verification Code: {verification_code}",
        "html": html_content
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            if resp.status_code in (200, 201):
                logger.info(f"Verification email dispatched via Resend to {to_email}")
                return True
            else:
                logger.warning(f"Resend API returned status {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        logger.warning(f"Resend dispatch error: {str(e)}")
        return False


async def send_password_reset_email(to_email: str, user_name: str, reset_token: str) -> bool:
    """Sends password reset token via Resend API."""
    if is_test_environment():
        logger.info(f"[Test Email Sandbox] Password reset token for {to_email}: {reset_token}")
        return True

    api_key = os.getenv("RESEND_API_KEY", "").strip()
    if not api_key:
        logger.info(f"[Email Sandbox] Password reset token for {to_email}: {reset_token}")
        return False

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 540px; margin: 0 auto; padding: 24px; border: 1px solid #E2E8F0; border-radius: 12px;">
      <h2 style="color: #DC2626; margin-top: 0;">SkyZen Password Reset</h2>
      <p>Hello <strong>{user_name}</strong>,</p>
      <p>We received a request to reset your SkyZen password. Your reset code is:</p>
      <div style="font-size: 26px; font-weight: 800; letter-spacing: 4px; color: #0F172A; padding: 14px; background: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; text-align: center; margin: 16px 0;">
        {reset_token}
      </div>
      <p style="font-size: 13px; color: #64748B;">This code is valid for 1 hour. If you did not initiate this request, please change your password immediately.</p>
    </div>
    """

    payload = {
        "from": "SkyZen Security <onboarding@resend.dev>",
        "to": [to_email],
        "subject": f"Your SkyZen Password Reset Code: {reset_token}",
        "html": html_content
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            return resp.status_code in (200, 201)
    except Exception as e:
        logger.warning(f"Resend reset dispatch error: {str(e)}")
        return False
