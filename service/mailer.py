"""Sending sign-in links.

ConsoleMailer is for local runs and tests: it logs that a link was sent (never the link
itself in production logs) and keeps the last link in memory, which DUMPIT_DEV exposes to
the sign-in page. SmtpMailer sends real email through any SMTP provider.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import List, Optional, Protocol, Tuple
from urllib.parse import unquote, urlparse

log = logging.getLogger("dumpit.mail")


class Mailer(Protocol):
    def send_link(self, email: str, link: str) -> None: ...


class ConsoleMailer:
    def __init__(self) -> None:
        self.sent: List[Tuple[str, str]] = []

    def send_link(self, email: str, link: str) -> None:
        self.sent.append((email, link))
        log.info("sign-in link created (console mailer; not emailed)")

    def last_link(self, email: Optional[str] = None) -> Optional[str]:
        for to, link in reversed(self.sent):
            if email is None or to == email:
                return link
        return None


class SmtpMailer:
    """DUMPIT_SMTP_URL=smtps://user:password@smtp.example.com:465 and DUMPIT_MAIL_FROM."""

    def __init__(self, url: str, sender: str):
        self.url, self.sender = urlparse(url), sender

    def send_link(self, email: str, link: str) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.sender, email, "Your Dumpit sign-in link"
        msg.set_content(f"Open this link to sign in to Dumpit:\n\n{link}\n\n"
                        "It works once and expires in 15 minutes. If you did not ask for it, "
                        "ignore this email.")
        port = self.url.port or (465 if self.url.scheme == "smtps" else 587)
        context = ssl.create_default_context()
        if self.url.scheme == "smtps":
            server = smtplib.SMTP_SSL(self.url.hostname, port, context=context, timeout=20)
        else:
            server = smtplib.SMTP(self.url.hostname, port, timeout=20)
            server.starttls(context=context)
        with server:
            if self.url.username:
                server.login(unquote(self.url.username), unquote(self.url.password or ""))
            server.send_message(msg)
