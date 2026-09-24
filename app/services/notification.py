"""Mock notifications. Nothing is emailed."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Notification


def send_notification(db: Session, claim_id: str, recipient_role: str, message: str) -> Notification:
    note = Notification(claim_id=claim_id, recipient_role=recipient_role, message=message)
    db.add(note)
    db.flush()
    return note
