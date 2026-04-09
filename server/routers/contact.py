import logging
import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)
router = APIRouter()

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
CONTACT_TO_EMAIL = os.getenv("CONTACT_TO_EMAIL", "support@clawditnow.com")
CONTACT_FROM_EMAIL = os.getenv("CONTACT_FROM_EMAIL", "noreply@clawditnow.com")


class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    subject: str = ""
    message: str


@router.post("/contact")
async def send_contact(body: ContactRequest) -> dict:
    if not body.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")
    if not RESEND_API_KEY:
        raise HTTPException(status_code=503, detail="Email service is not configured.")

    subject = body.subject.strip() or "New contact form submission"
    html = (
        f"<p><strong>From:</strong> {body.name} &lt;{body.email}&gt;</p>"
        f"<p><strong>Subject:</strong> {subject}</p>"
        f"<hr>"
        f"<p>{body.message.replace(chr(10), '<br>')}</p>"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": f"OpenClaw Contact <{CONTACT_FROM_EMAIL}>",
                    "to": [CONTACT_TO_EMAIL],
                    "reply_to": body.email,
                    "subject": f"[Contact] {subject}",
                    "html": html,
                },
            )
        if not r.is_success:
            logger.warning("Resend API error %s: %s", r.status_code, r.text)
            raise HTTPException(status_code=502, detail="Failed to send email. Please try again later.")
    except httpx.HTTPError as exc:
        logger.error("Resend request failed: %s", exc)
        raise HTTPException(status_code=502, detail="Email service unavailable. Please try again later.")

    logger.info("Contact email sent from %s <%s>", body.name, body.email)
    return {"sent": True}
