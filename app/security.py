"""Prototype authz: roles, least privilege, tool permissions.

Not production auth. Demo-grade header/session identity.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException


ROLES = ("EMPLOYEE", "MANAGER", "CFO", "FINANCE", "ADMIN", "BU_HEAD")

TOOL_PERMISSIONS: dict[str, list[str]] = {
    "extract_receipt": ["EMPLOYEE", "MANAGER", "CFO", "FINANCE", "ADMIN", "BU_HEAD"],
    "validate_receipt": ["EMPLOYEE", "MANAGER", "CFO", "FINANCE", "ADMIN", "BU_HEAD"],
    "check_policy": ["EMPLOYEE", "MANAGER", "CFO", "FINANCE", "ADMIN", "BU_HEAD"],
    "get_employee": ["EMPLOYEE", "MANAGER", "CFO", "FINANCE", "ADMIN", "BU_HEAD"],
    "check_duplicate_claim": ["EMPLOYEE", "MANAGER", "CFO", "FINANCE", "ADMIN", "BU_HEAD"],
    "create_approval_request": ["EMPLOYEE", "MANAGER", "CFO", "FINANCE", "ADMIN", "BU_HEAD"],
    "send_notification": ["EMPLOYEE", "MANAGER", "CFO", "FINANCE", "ADMIN", "BU_HEAD"],
    "write_audit_event": ["EMPLOYEE", "MANAGER", "CFO", "FINANCE", "ADMIN", "BU_HEAD"],
    "read_claim": ["EMPLOYEE", "MANAGER", "CFO", "FINANCE", "ADMIN", "BU_HEAD"],
    "approve_claim": ["CFO", "MANAGER", "FINANCE", "ADMIN", "BU_HEAD"],
    "reject_claim": ["CFO", "MANAGER", "FINANCE", "ADMIN", "BU_HEAD"],
    "process_payment": ["FINANCE", "ADMIN"],
    "activate_policy": ["ADMIN"],
}

# Who may approve which required role
APPROVER_MAP: dict[str, list[str]] = {
    "MANAGER": ["MANAGER", "ADMIN"],
    "CFO": ["CFO", "ADMIN"],
    "FINANCE": ["FINANCE", "ADMIN"],
    "BU_HEAD": ["BU_HEAD", "ADMIN"],
}


@dataclass
class Actor:
    name: str
    role: str
    employee_id: str


def can_use_tool(role: str, tool: str) -> bool:
    allowed = TOOL_PERMISSIONS.get(tool)
    if allowed is None:
        return False
    return role in allowed or role == "ADMIN"


def assert_tool(role: str, tool: str) -> None:
    if not can_use_tool(role, tool):
        raise HTTPException(status_code=403, detail=f"Role {role} cannot use tool {tool}")


def can_approve_role(actor_role: str, required_role: str) -> bool:
    return actor_role in APPROVER_MAP.get(required_role, [])


def can_view_claim(actor: Actor, employee_id: str) -> bool:
    if actor.role == "EMPLOYEE":
        return actor.employee_id == employee_id
    return True


def get_actor(
    x_role: str = Header(default="EMPLOYEE"),
    x_user: str = Header(default="Rahul Sharma"),
    x_employee_id: str = Header(default="EMP-1001"),
) -> Actor:
    role = (x_role or "EMPLOYEE").upper()
    if role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role}")
    return Actor(name=x_user, role=role, employee_id=x_employee_id)
