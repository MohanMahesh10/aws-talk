"""Seed employees, policies, and talk-ready sample claims."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Approval, AuditEvent, Claim, ClaimFile, Employee, Expense, PolicyConfig
from app.policy.engine import POLICY_VERSIONS, PolicyEngine


def _write_sample(name: str, body: str) -> str:
    folder = Path(get_settings().upload_dir) / "samples"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    if not path.exists():
        path.write_text(body, encoding="utf-8")
    return str(path)


def _seed_policies(db: Session) -> None:
    if db.query(PolicyConfig).count():
        return
    db.add(
        PolicyConfig(
            version="v1",
            name=POLICY_VERSIONS["v1"]["name"],
            rules_json=json.dumps(POLICY_VERSIONS["v1"]["rules"]),
            active=True,
        )
    )
    db.add(
        PolicyConfig(
            version="v2",
            name=POLICY_VERSIONS["v2"]["name"],
            rules_json=json.dumps(POLICY_VERSIONS["v2"]["rules"]),
            active=False,
        )
    )


def _seed_employees(db: Session) -> None:
    if db.query(Employee).count():
        return
    people = [
        ("EMP-1001", "Rahul Sharma", "EMPLOYEE", "Sales"),
        ("EMP-1002", "Anita Desai", "EMPLOYEE", "Sales"),
        ("EMP-1003", "Vikram Iyer", "EMPLOYEE", "Engineering"),
        ("MGR-01", "Neha Rao", "MANAGER", "Sales"),
        ("BU-01", "Arjun Menon", "BU_HEAD", "Sales"),
        ("CFO-01", "Priya Sen", "CFO", "Finance"),
        ("FIN-01", "Karan Mehta", "FINANCE", "Finance"),
        ("ADM-01", "Admin", "ADMIN", "IT"),
    ]
    for eid, name, role, dept in people:
        db.add(Employee(employee_id=eid, name=name, role=role, department=dept))


def _add_claim(
    db: Session,
    claim_id: str,
    employee_id: str,
    employee_name: str,
    purpose: str,
    location: str,
    start: str,
    end: str,
    lines: list[tuple[str, str, float, str, str]],
    policy_version: str = "v1",
    state: str = "APPROVAL_REQUIRED",
) -> Claim:
    engine = PolicyEngine()
    total = sum(x[2] for x in lines)
    decision = engine.determine_approval(total, policy_version)
    claim = Claim(
        claim_id=claim_id,
        employee_id=employee_id,
        employee_name=employee_name,
        trip_purpose=purpose,
        trip_location=location,
        trip_start=start,
        trip_end=end,
        total_amount=total,
        state=state,
        policy_version=policy_version,
        required_approver=decision.approver,
        policy_reason=decision.reason,
        demo_mode=True,
        extraction_source="demo",
    )
    db.add(claim)
    db.flush()
    for vendor, etype, amount, invoice, fname in lines:
        db.add(
            Expense(
                claim_pk=claim.id,
                vendor=vendor,
                expense_type=etype,
                amount=amount,
                invoice_number=invoice,
                filename=fname,
                date="2026-09-20",
                route={
                    "hotel": "Hotel validation",
                    "travel": "Travel validation",
                    "meal": "Meal policy",
                    "flight": "Travel validation",
                }.get(etype, "General validation"),
                confidence=0.94,
            )
        )
    if state == "APPROVAL_REQUIRED":
        for role in engine.required_roles(decision.approver):
            db.add(Approval(claim_pk=claim.id, required_role=role, status="PENDING"))
    db.add(AuditEvent(claim_pk=claim.id, message="Seed claim loaded", actor="system"))
    db.add(AuditEvent(claim_pk=claim.id, message=f"Total calculated: ₹{total:,.0f}", actor="reem"))
    db.add(AuditEvent(claim_pk=claim.id, message=f"{decision.approver} approval required", actor="reem"))
    return claim


def seed_if_empty(db: Session) -> None:
    _seed_policies(db)
    _seed_employees(db)
    if db.query(Claim).count():
        db.commit()
        return

    hotel = _write_sample(
        "hotel.txt",
        "ABC Hotel\nInvoice INV-12345\nRoom charges INR 8500\nDate 2026-09-20\n",
    )
    uber = _write_sample("uber.txt", "Uber trip\nReceipt UBR-1001\nINR 850\n")
    meal = _write_sample("meal.txt", "Spice Kitchen\nBill ML-4401\nINR 1200\n")
    flight = _write_sample("flight.txt", "IndiGo\nTicket FLT-7788\nINR 14000\n")

    talk = _add_claim(
        db,
        "CLM-1001",
        "EMP-1001",
        "Rahul Sharma",
        "Bangalore Client Visit",
        "Bangalore",
        "2026-09-19",
        "2026-09-21",
        [
            ("Uber", "travel", 850, "UBR-1001", "uber.txt"),
            ("ABC Hotel", "hotel", 8500, "INV-12345", "hotel.txt"),
            ("Spice Kitchen", "meal", 1200, "ML-4401", "meal.txt"),
            ("IndiGo", "flight", 14000, "FLT-7788", "flight.txt"),
        ],
    )
    for path, name in ((hotel, "hotel.txt"), (uber, "uber.txt"), (meal, "meal.txt"), (flight, "flight.txt")):
        db.add(ClaimFile(claim_pk=talk.id, filename=name, stored_path=path, content_type="text/plain"))

    _add_claim(
        db,
        "CLM-A",
        "EMP-1002",
        "Anita Desai",
        "Local client dinner",
        "Mumbai",
        "2026-09-10",
        "2026-09-10",
        [("Spice Kitchen", "meal", 4500, "ML-A-01", "meal-a.txt")],
    )
    _add_claim(
        db,
        "CLM-B",
        "EMP-1001",
        "Rahul Sharma",
        "Hyderabad workshop",
        "Hyderabad",
        "2026-08-01",
        "2026-08-03",
        [
            ("Uber", "travel", 850, "UBR-B-01", "uber-b.txt"),
            ("ABC Hotel", "hotel", 8500, "INV-B-01", "hotel-b.txt"),
            ("Spice Kitchen", "meal", 1200, "ML-B-01", "meal-b.txt"),
            ("IndiGo", "flight", 14000, "FLT-B-01", "flight-b.txt"),
        ],
    )
    _add_claim(
        db,
        "CLM-C",
        "EMP-1003",
        "Vikram Iyer",
        "US customer onsite",
        "San Francisco",
        "2026-07-01",
        "2026-07-08",
        [
            ("Marriott", "hotel", 42000, "HT-C-01", "hotel-c.txt"),
            ("United", "flight", 33000, "FLT-C-01", "flight-c.txt"),
        ],
    )
    db.commit()
