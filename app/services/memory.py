"""Short-term = claim row. Long-term = employee_memory table. No vector DB."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Claim, EmployeeMemory, Expense
from app.models.claim import CompactContext


def compact_context(claim: Claim) -> CompactContext:
    return CompactContext(
        claim_id=claim.claim_id,
        employee=claim.employee_name,
        trip=claim.trip_purpose,
        total=claim.total_amount,
        expenses=len(claim.expenses),
        policy_version=claim.policy_version,
        current_state=claim.state,
    )


def remember_claim(db: Session, claim: Claim) -> EmployeeMemory:
    row = db.query(EmployeeMemory).filter(EmployeeMemory.employee_id == claim.employee_id).one_or_none()
    vendors = ", ".join(sorted({e.vendor for e in claim.expenses}))
    if row is None:
        row = EmployeeMemory(
            employee_id=claim.employee_id,
            employee_name=claim.employee_name,
            claim_count=1,
            last_vendors=vendors,
            last_total=claim.total_amount,
            last_approver=claim.required_approver,
            last_policy_version=claim.policy_version,
            last_claim_id=claim.claim_id,
        )
        db.add(row)
    else:
        row.claim_count += 1
        row.last_vendors = vendors
        row.last_total = claim.total_amount
        row.last_approver = claim.required_approver
        row.last_policy_version = claim.policy_version
        row.last_claim_id = claim.claim_id
    db.flush()
    return row


def get_memory(db: Session, employee_id: str) -> EmployeeMemory | None:
    return db.query(EmployeeMemory).filter(EmployeeMemory.employee_id == employee_id).one_or_none()


def recent_vendors(db: Session, employee_id: str, limit: int = 8) -> list[str]:
    expenses = (
        db.query(Expense)
        .join(Claim, Expense.claim_pk == Claim.id)
        .filter(Claim.employee_id == employee_id)
        .order_by(Expense.id.desc())
        .limit(limit)
        .all()
    )
    return [e.vendor for e in expenses]
