import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from backend.app.config import settings

logger = logging.getLogger("nexora.email")

class EmailService:
    @staticmethod
    def _send_smtp_email(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
        if not settings.SMTP_HOST:
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = to_email

            part1 = MIMEText(text_content, "plain")
            part2 = MIMEText(html_content, "html")
            msg.attach(part1)
            msg.attach(part2)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, to_email, msg.as_string())
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP to {to_email}: {e}")
            return False

    @classmethod
    def send_verification_email(cls, to_email: str, token: str) -> dict:
        verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        subject = f"Verify your email - {settings.APP_NAME}"
        text_content = f"Welcome to {settings.APP_NAME}!\nPlease verify your email by opening the link:\n{verify_url}\nThis link expires in 24 hours."
        
        html_content = f"""
        <div style="font-family: 'Inter', sans-serif; background-color: #0B0B12; color: #F8FAFC; padding: 40px; border-radius: 12px; max-width: 500px; margin: auto; border: 1px solid #1E1E2E;">
            <h1 style="color: #A78BFA; font-size: 24px; margin-bottom: 8px;">{settings.APP_NAME}</h1>
            <p style="color: #94A3B8; font-size: 14px; margin-bottom: 24px;">One AI. Everything you need.</p>
            <h2 style="color: #F8FAFC; font-size: 18px; margin-bottom: 12px;">Confirm your email address</h2>
            <p style="color: #94A3B8; line-height: 1.5; font-size: 14px;">Thank you for registering. Please click the button below to verify your email and activate your account.</p>
            <div style="margin: 30px 0;">
                <a href="{verify_url}" style="background: linear-gradient(135deg, #8B5CF6, #6D28D9); color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">Verify Email</a>
            </div>
            <p style="color: #64748B; font-size: 12px;">If you didn't create an account, you can safely ignore this email.</p>
        </div>
        """

        # Log for dev/test verification
        print(f"\n{'='*70}\n[EMAIL DISPATCH: VERIFY EMAIL]\nTo: {to_email}\nLink: {verify_url}\nToken: {token}\n{'='*70}\n")
        
        sent = cls._send_smtp_email(to_email, subject, html_content, text_content)
        return {
            "sent": sent,
            "verificationUrl": verify_url,
            "token": token
        }

    @classmethod
    def send_password_reset_email(cls, to_email: str, token: str) -> dict:
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        subject = f"Reset your password - {settings.APP_NAME}"
        text_content = f"You requested a password reset for {settings.APP_NAME}.\nPlease reset your password by opening the link:\n{reset_url}\nThis link expires in 1 hour."
        
        html_content = f"""
        <div style="font-family: 'Inter', sans-serif; background-color: #0B0B12; color: #F8FAFC; padding: 40px; border-radius: 12px; max-width: 500px; margin: auto; border: 1px solid #1E1E2E;">
            <h1 style="color: #A78BFA; font-size: 24px; margin-bottom: 8px;">{settings.APP_NAME}</h1>
            <p style="color: #94A3B8; font-size: 14px; margin-bottom: 24px;">One AI. Everything you need.</p>
            <h2 style="color: #F8FAFC; font-size: 18px; margin-bottom: 12px;">Password Reset Request</h2>
            <p style="color: #94A3B8; line-height: 1.5; font-size: 14px;">We received a request to reset your password. Click the button below to choose a new password.</p>
            <div style="margin: 30px 0;">
                <a href="{reset_url}" style="background: linear-gradient(135deg, #8B5CF6, #6D28D9); color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">Reset Password</a>
            </div>
            <p style="color: #64748B; font-size: 12px;">This link will expire in 60 minutes. If you did not request this, please disregard this email.</p>
        </div>
        """

        # Log for dev/test verification
        print(f"\n{'='*70}\n[EMAIL DISPATCH: PASSWORD RESET]\nTo: {to_email}\nLink: {reset_url}\nToken: {token}\n{'='*70}\n")

        sent = cls._send_smtp_email(to_email, subject, html_content, text_content)
        return {
            "sent": sent,
            "resetUrl": reset_url,
            "token": token
        }

email_service = EmailService()
