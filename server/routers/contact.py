import logging
import os
import ssl
from email.message import EmailMessage

import aiosmtplib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)
router = APIRouter()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.hostinger.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
CONTACT_TO_EMAIL = os.getenv("CONTACT_TO_EMAIL", "support@clawditnow.com")


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    subject: str = ""
    message: str


@router.post("/contact")
async def send_contact(body: ContactRequest) -> dict:
    if not body.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")
    if not SMTP_USER or not SMTP_PASS:
        raise HTTPException(status_code=503, detail="Email service is not configured.")

    subject = body.subject.strip() or "New contact form submission"

    msg = EmailMessage()
    msg["From"] = f"OpenClaw Contact <{SMTP_USER}>"
    msg["To"] = CONTACT_TO_EMAIL
    msg["Subject"] = f"[Contact] {subject}"
    msg["Reply-To"] = body.email
    msg.set_content(
        f"From: {body.name} <{body.email}>\n"
        f"Subject: {subject}\n"
        f"{'─' * 40}\n\n"
        f"{body.message}"
    )
    msg.add_alternative(
        f"<p><strong>From:</strong> {body.name} &lt;{body.email}&gt;</p>"
        f"<p><strong>Subject:</strong> {subject}</p>"
        f"<hr>"
        f"<p>{body.message.replace(chr(10), '<br>')}</p>",
        subtype="html",
    )

    try:
        tls_context = ssl.create_default_context()
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASS,
            use_tls=True,
            tls_context=tls_context,
        )
    except Exception as exc:
        logger.error("SMTP send failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to send email. Please try again later.")

    logger.info("Contact email sent from %s <%s>", body.name, body.email)
    return {"sent": True}
