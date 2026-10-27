"""
Email service — SMTP with Jinja2 HTML templates.
"""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)


def _sanitize_header(value: str) -> str:
    """Strip CR/LF to prevent SMTP header injection. Headers split on \\r\\n
    so a malicious display-name containing newlines could inject extra
    headers (e.g. BCC) into outgoing mail.
    """
    if value is None:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").strip()

# ── Inline HTML templates (no template files required) ──────────────────────
_CONFIRM_TEMPLATE = """
<!doctype html>
<html>
<body style="font-family:sans-serif;max-width:600px;margin:auto;padding:32px 16px;background:#ffffff">
  <div style="text-align:center;margin-bottom:32px">
    <div style="display:inline-block;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:12px;padding:12px 20px">
      <span style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.5px">{app_name}</span>
    </div>
  </div>
  <h1 style="font-size:24px;font-weight:700;color:#111827;margin-bottom:8px">Welcome to {app_name} Early Access!</h1>
  <p style="color:#374151;font-size:16px;line-height:1.6;margin-bottom:8px">Hi {name},</p>
  <p style="color:#374151;font-size:16px;line-height:1.6;margin-bottom:24px">
    Thank you for signing up &mdash; you&rsquo;re on the early access list! We&rsquo;re putting the finishing
    touches on the launch and will notify you the moment {app_name} is ready.
  </p>
  <div style="background:#f3f4f6;border-radius:10px;padding:20px;margin-bottom:28px">
    <p style="color:#4b5563;font-size:14px;font-weight:600;margin:0 0 10px 0;text-transform:uppercase;letter-spacing:0.05em">What happens next</p>
    <ul style="margin:0;padding-left:20px;color:#6b7280;font-size:14px;line-height:1.8">
      <li>Confirm your email address using the button below</li>
      <li>We&rsquo;ll send you a notification when early access launches</li>
      <li>Early Access members get first access and priority support</li>
    </ul>
  </div>
  <p style="color:#374151;font-size:15px;margin-bottom:20px">Please confirm your email address to complete your registration:</p>
  <p style="text-align:center;margin-bottom:20px">
    <a href="{link}" style="background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;padding:14px 32px;text-decoration:none;border-radius:8px;display:inline-block;font-weight:600;font-size:15px">Confirm My Email</a>
  </p>
  <p style="color:#9ca3af;font-size:13px;text-align:center;margin-bottom:4px">Or copy this link into your browser:</p>
  <p style="color:#6366f1;font-size:12px;text-align:center;word-break:break-all;margin-bottom:24px">{link}</p>
  <p style="color:#9ca3af;font-size:12px;text-align:center">This link expires in 24 hours. If you didn&rsquo;t sign up, you can safely ignore this email.</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
  <p style="color:#9ca3af;font-size:12px;text-align:center">&copy; {app_name} &mdash; We&rsquo;ll be in touch soon!</p>
</body>
</html>
"""

_RESET_TEMPLATE = """
<!doctype html><html><body style="font-family:sans-serif;max-width:600px;margin:auto">
<h2>Reset your password</h2>
<p>Hi {name},</p>
<p>We received a request to reset your {app_name} password:</p>
<p><a href="{link}" style="background:#4F46E5;color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px;display:inline-block">Reset Password</a></p>
<p>Or copy this link: {link}</p>
<p>This link expires in 1 hour. If you didn't request this, ignore this email.</p>
<hr><p style="color:#6b7280;font-size:12px">&copy; {app_name}</p>
</body></html>
"""

_INVITATION_TEMPLATE = """
<!doctype html><html><body style="font-family:sans-serif;max-width:600px;margin:auto">
<h2>You're invited to join {app_name}</h2>
<p>Hi,</p>
<p><strong>{inviter_name}</strong> has invited you to join <strong>{tenant_name}</strong> on {app_name}.</p>
<p><a href="{link}" style="background:#4F46E5;color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px;display:inline-block">Accept Invitation</a></p>
<p>This invitation expires in 7 days.</p>
<hr><p style="color:#6b7280;font-size:12px">&copy; {app_name}</p>
</body></html>
"""

_EXPIRY_TEMPLATE = """
<!doctype html><html><body style="font-family:sans-serif;max-width:600px;margin:auto">
<h2>Your subscription is expiring soon</h2>
<p>Hi {name},</p>
<p>Your {app_name} subscription will expire on <strong>{expiry_date}</strong>.</p>
<p><a href="{billing_url}" style="background:#4F46E5;color:#fff;padding:12px 24px;text-decoration:none;border-radius:6px;display:inline-block">Manage Subscription</a></p>
<hr><p style="color:#6b7280;font-size:12px">&copy; {app_name}</p>
</body></html>
"""


def _smtp_error_text(exc: Exception) -> str:
    """Short, single-line explanation of an SMTP failure for the admin console."""
    if isinstance(exc, smtplib.SMTPResponseException):
        detail = exc.smtp_error.decode("utf-8", "replace") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
        text = f"{exc.smtp_code} {' '.join(detail.split())}"
    else:
        text = f"{exc.__class__.__name__}: {exc}"
    return text if len(text) <= 400 else text[:397] + "..."


class EmailService:
    """Send transactional emails via SMTP."""

    def __init__(self):
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._use_tls = settings.smtp_use_tls
        self._user = settings.smtp_username
        self._password = settings.smtp_password
        self._from = settings.smtp_from_address
        self._from_name = settings.smtp_from_name
        self._app_url = settings.app_url
        self._app_name = settings.app_name

    @classmethod
    def from_config(
        cls,
        host: str,
        port: int,
        use_ssl: bool,
        username: str,
        password: str,
        from_address: str,
        from_name: str,
        app_url: str = "",
        app_name: str = "ffinn",
    ) -> "EmailService":
        """Create an EmailService from explicit SMTP config (used for test-email and DB-driven settings)."""
        svc = cls.__new__(cls)
        svc._host = host
        svc._port = port
        svc._use_tls = use_ssl
        svc._user = username
        svc._password = password
        svc._from = from_address
        svc._from_name = from_name
        svc._app_url = app_url or settings.app_url
        svc._app_name = app_name or settings.app_name
        return svc

    # Why the last send_test() failed, in words an admin can act on. Empty after a success.
    last_error: str = ""

    async def send_test(self, to: str) -> bool:
        """Send a test email and return True on success, False on failure (see ``last_error``)."""
        html = (
            "<!doctype html><html><body style='font-family:sans-serif;max-width:600px;margin:auto;padding:32px'>"
            f"<h2 style='color:#6366f1'>\u2713 Email settings are working</h2>"
            f"<p>This is a test email from <strong>{self._app_name}</strong>.</p>"
            "<p>Your SMTP configuration is correct — transactional emails will be delivered.</p>"
            f"<hr><p style='color:#6b7280;font-size:12px'>Sent via {self._app_name} admin settings</p>"
            "</body></html>"
        )
        self.last_error = ""
        if not self._host:
            self.last_error = "No SMTP host is configured."
            return False
        try:
            await self._send(to, f"Test email from {self._app_name}", html, raise_errors=True)
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = _smtp_error_text(exc)
            log.error("Test email failed", error=str(exc))
            return False

    async def _send(self, to: str, subject: str, html: str, *, raise_errors: bool = False) -> None:
        """Async wrapper — runs blocking SMTP in a thread pool to avoid stalling the event loop.

        Failures are logged and swallowed by default so a mail outage never breaks sign-up or password reset.
        Pass ``raise_errors=True`` (the admin test button does) to see them.
        """
        if not self._host:
            log.debug("Email not configured — skipping send", to=to, subject=subject)
            return
        msg = MIMEMultipart("alternative")
        msg["Subject"] = _sanitize_header(subject)
        msg["From"] = formataddr((_sanitize_header(self._from_name), _sanitize_header(self._from)))
        msg["To"] = _sanitize_header(to)
        msg.attach(MIMEText(html, "html"))
        # Capture instance fields for use inside the thread
        host, port, use_tls = self._host, self._port, self._use_tls
        user, password, from_addr = self._user, self._password, self._from
        msg_str = msg.as_string()
        # Announce the sender's own domain in HELO. Containers otherwise announce a random hostname, and Google's
        # SMTP relay checks that domain too.
        helo = from_addr.rsplit("@", 1)[-1] if "@" in from_addr else None

        def _send_blocking() -> None:
            try:
                if port == 465:
                    with smtplib.SMTP_SSL(host, port, local_hostname=helo) as server:
                        if user:
                            server.login(user, password)
                        server.sendmail(from_addr, [to], msg_str)
                else:
                    with smtplib.SMTP(host, port, local_hostname=helo) as server:
                        server.ehlo()
                        if use_tls:
                            server.starttls()
                        if user:
                            server.login(user, password)
                        server.sendmail(from_addr, [to], msg_str)
                log.info("Email sent", to=to, subject=subject)
            except Exception as exc:
                log.error("Email failed", to=to, subject=subject, error=str(exc))
                if raise_errors:
                    raise

        import asyncio
        await asyncio.to_thread(_send_blocking)

    def _frontend_url(self, base_url: str | None = None) -> str:
        return (base_url or self._app_url).rstrip("/")

    async def send_email_confirmation(
        self, to: str, name: str, token: str, *, base_url: str | None = None
    ) -> None:
        link = f"{self._frontend_url(base_url)}/auth/confirm-email?token={token}"
        html = _CONFIRM_TEMPLATE.format(name=name, app_name=self._app_name, link=link)
        await self._send(to, f"Confirm your {self._app_name} email", html)

    async def send_password_reset(
        self, to: str, name: str, token: str, *, base_url: str | None = None
    ) -> None:
        link = f"{self._frontend_url(base_url)}/auth/reset-password?token={token}"
        html = _RESET_TEMPLATE.format(name=name, app_name=self._app_name, link=link)
        await self._send(to, f"Reset your {self._app_name} password", html)

    async def send_team_invitation(
        self,
        to: str,
        inviter_name: str,
        tenant_name: str,
        token: str,
        *,
        base_url: str | None = None,
    ) -> None:
        link = f"{self._frontend_url(base_url)}/auth/accept-invitation?token={token}"
        html = _INVITATION_TEMPLATE.format(
            app_name=self._app_name,
            inviter_name=inviter_name,
            tenant_name=tenant_name,
            link=link,
        )
        await self._send(to, f"You're invited to {tenant_name} on {self._app_name}", html)

    async def send_subscription_expiry(
        self, to: str, name: str, expiry_date: str, *, base_url: str | None = None
    ) -> None:
        billing_url = f"{self._frontend_url(base_url)}/app/subscription"
        html = _EXPIRY_TEMPLATE.format(
            name=name,
            app_name=self._app_name,
            expiry_date=expiry_date,
            billing_url=billing_url,
        )
        await self._send(to, f"Your {self._app_name} subscription is expiring soon", html)


# Singleton
email_service = EmailService()
