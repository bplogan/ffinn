"""EmailService: the admin test button must report real failures, and HELO uses the sender's domain."""
from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.email import EmailService


def _svc(from_address: str = "info@example.com", host: str = "smtp.example.com") -> EmailService:
    return EmailService.from_config(
        host=host, port=587, use_ssl=True, username="", password="",
        from_address=from_address, from_name="ffinn",
    )


@pytest.mark.asyncio
async def test_send_test_reports_success():
    fake = MagicMock()
    fake.__enter__.return_value = fake
    with patch("app.infrastructure.email.smtplib.SMTP", return_value=fake) as smtp:
        svc = _svc()
        assert await svc.send_test("to@example.com") is True
    assert svc.last_error == ""
    fake.sendmail.assert_called_once()
    # HELO announces the sender's domain, not the container's random hostname.
    assert smtp.call_args.kwargs["local_hostname"] == "example.com"


@pytest.mark.asyncio
async def test_send_test_reports_the_servers_refusal():
    fake = MagicMock()
    fake.__enter__.return_value = fake
    fake.sendmail.side_effect = smtplib.SMTPSenderRefused(550, b"5.7.0 Mail relay denied\n5.7.0 check your settings", "x@y")
    with patch("app.infrastructure.email.smtplib.SMTP", return_value=fake):
        svc = _svc()
        assert await svc.send_test("to@example.com") is False
    assert svc.last_error.startswith("550 ")
    assert "Mail relay denied" in svc.last_error
    assert "\n" not in svc.last_error


@pytest.mark.asyncio
async def test_send_test_without_host_says_so():
    svc = _svc(host="")
    assert await svc.send_test("to@example.com") is False
    assert "No SMTP host" in svc.last_error


@pytest.mark.asyncio
async def test_normal_sends_still_swallow_failures():
    """Sign-up and password reset must not break when the mail server is down."""
    with patch("app.infrastructure.email.smtplib.SMTP", side_effect=OSError("connection refused")):
        await _svc()._send("to@example.com", "subject", "<p>hi</p>")  # does not raise
