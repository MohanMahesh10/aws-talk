"""Claim → JSON for UI and API."""

from __future__ import annotations

from app.agent.state import PIPELINE, ClaimState
from app.db.models import Claim
from app.services.memory import compact_context, get_memory

_STATE_RANK = [
    "UPLOADED",
    "EXTRACTING",
    "VALIDATING",
    "CLASSIFYING",
    "POLICY_CHECK",
    "APPROVAL_REQUIRED",
    "APPROVED",
    "PAYMENT_PROCESSING",
    "COMPLETED",
]

_GRAPH = [
    {"id": "upload", "label": "Upload", "kind": "input", "hint": "Receipts in", "until": "UPLOADED"},
    {"id": "extract", "label": "Understand", "kind": "ai", "hint": "Extract JSON", "until": "EXTRACTING"},
    {"id": "validate", "label": "Validate", "kind": "tool", "hint": "Guardrails", "until": "CLASSIFYING"},
    {"id": "policy", "label": "Policy", "kind": "code", "hint": "Thresholds", "until": "POLICY_CHECK"},
    {"id": "approval", "label": "Human", "kind": "human", "hint": "Authorize", "until": "APPROVED"},
    {"id": "payment", "label": "Payment", "kind": "act", "hint": "Reimburse", "until": "COMPLETED"},
]


def _rank(state: str) -> int:
    try:
        return _STATE_RANK.index(state)
    except ValueError:
        return -1


def graph_nodes(claim: Claim) -> list[dict]:
    """Six talk nodes. Status derived from claim state."""
    state = claim.state
    current = _rank(state)
    files = len(claim.files) if claim.files is not None else 0
    live_exp = [e for e in claim.expenses if not e.is_duplicate]
    details = {
        "upload": f"{files or len(claim.expenses)} files",
        "extract": claim.extraction_source or "—",
        "validate": f"{len(live_exp)} expenses",
        "policy": claim.required_approver or "routing",
        "approval": claim.required_approver or "human",
        "payment": claim.payment_status or claim.state.lower(),
    }
    failed_id = ""
    if state == ClaimState.REJECTED.value:
        failed_id = "approval"
    elif state in (ClaimState.EXCEPTION.value, ClaimState.FAILED.value):
        if claim.circuit_open or "payment" in (claim.exception_reason or "").lower():
            failed_id = "payment"
        elif claim.loop_detected or claim.duplicate_blocked:
            failed_id = "validate"
        elif claim.injection_detected and "inject" in (claim.demo_scenario or ""):
            failed_id = "validate"
        else:
            failed_id = "validate"

    nodes = []
    selected = _GRAPH[0]["id"]
    for spec in _GRAPH:
        until = _rank(spec["until"])
        if failed_id == spec["id"]:
            status = "failed"
            selected = spec["id"]
        elif state == ClaimState.COMPLETED.value or current > until:
            status = "completed"
        elif current == until or (
            spec["id"] == "approval" and state == ClaimState.APPROVAL_REQUIRED.value
        ) or (
            spec["id"] == "validate" and state in ("VALIDATING", "CLASSIFYING")
        ) or (
            spec["id"] == "payment" and state == ClaimState.PAYMENT_PROCESSING.value
        ):
            status = "running"
            selected = spec["id"]
        else:
            status = "pending"
        if status == "completed":
            selected = spec["id"]
        nodes.append(
            {
                **spec,
                "status": status,
                "detail": details[spec["id"]],
            }
        )
    if state == ClaimState.COMPLETED.value:
        selected = "payment"
    elif state == ClaimState.APPROVAL_REQUIRED.value:
        selected = "approval"
    for n in nodes:
        n["selected"] = n["id"] == selected
    return nodes


def pipeline_status(state: str) -> list[dict]:
    terminal_fail = state in {ClaimState.FAILED.value, ClaimState.EXCEPTION.value, ClaimState.REJECTED.value}
    reached = False
    out = []
    for step in PIPELINE:
        if state == step.value:
            status = "failed" if terminal_fail and step in (ClaimState.COMPLETED,) else "running"
            if state in (
                ClaimState.COMPLETED.value,
                ClaimState.APPROVAL_REQUIRED.value,
                ClaimState.APPROVED.value,
                ClaimState.PAYMENT_PROCESSING.value,
            ):
                status = "completed" if step.value != state else (
                    "completed" if state == ClaimState.COMPLETED.value else "running"
                )
            if state == ClaimState.COMPLETED.value:
                status = "completed"
            elif state == step.value:
                status = "running"
            reached = True
        elif not reached:
            status = "completed"
        else:
            status = "pending"
        out.append({"name": step.value, "status": status})

    if state == ClaimState.REJECTED.value:
        for item in out:
            if item["name"] == ClaimState.APPROVAL_REQUIRED.value:
                item["status"] = "failed"
            if item["name"] in (ClaimState.APPROVED.value, ClaimState.PAYMENT_PROCESSING.value, ClaimState.COMPLETED.value):
                item["status"] = "pending"
    if state in (ClaimState.FAILED.value, ClaimState.EXCEPTION.value):
        for item in out:
            if item["name"] == state or item["status"] == "running":
                item["status"] = "failed"
                break
    return out


def claim_detail(claim: Claim, db=None) -> dict:
    memory = get_memory(db, claim.employee_id) if db is not None else None
    return {
        "claim_id": claim.claim_id,
        "employee_name": claim.employee_name,
        "employee_id": claim.employee_id,
        "trip_purpose": claim.trip_purpose,
        "trip_location": claim.trip_location,
        "trip_start": claim.trip_start,
        "trip_end": claim.trip_end,
        "total_amount": claim.total_amount,
        "currency": claim.currency,
        "state": claim.state,
        "policy_version": claim.policy_version,
        "required_approver": claim.required_approver,
        "policy_reason": claim.policy_reason,
        "demo_mode": claim.demo_mode,
        "extraction_source": claim.extraction_source,
        "injection_detected": claim.injection_detected,
        "loop_detected": claim.loop_detected,
        "retry_count": claim.retry_count,
        "circuit_open": claim.circuit_open,
        "rate_limited": claim.rate_limited,
        "cache_hit": claim.cache_hit,
        "duplicate_blocked": claim.duplicate_blocked,
        "exception_reason": claim.exception_reason,
        "demo_scenario": claim.demo_scenario,
        "payment_status": claim.payment_status,
        "estimated_cost_usd": claim.estimated_cost_usd,
        "created_at": claim.created_at.isoformat() if claim.created_at else "",
        "pipeline": pipeline_status(claim.state),
        "nodes": graph_nodes(claim),
        "context": compact_context(claim).model_dump(),
        "memory": {
            "claim_count": memory.claim_count if memory else 0,
            "last_vendors": memory.last_vendors if memory else "",
            "last_approver": memory.last_approver if memory else "",
            "last_total": memory.last_total if memory else 0,
        },
        "expenses": [
            {
                "vendor": e.vendor,
                "expense_type": e.expense_type,
                "amount": e.amount,
                "currency": e.currency,
                "date": e.date,
                "invoice_number": e.invoice_number,
                "confidence": e.confidence,
                "filename": e.filename,
                "route": e.route,
                "is_duplicate": e.is_duplicate,
                "injection_flag": e.injection_flag,
            }
            for e in claim.expenses
        ],
        "approvals": [
            {
                "id": a.id,
                "required_role": a.required_role,
                "status": a.status,
                "decided_by": a.decided_by,
                "decided_at": a.decided_at.isoformat() if a.decided_at else "",
            }
            for a in claim.approvals
        ],
        "events": [
            {
                "time": ev.timestamp.strftime("%H:%M") if ev.timestamp else "",
                "message": ev.message,
                "actor": ev.actor,
                "event_type": ev.event_type,
            }
            for ev in sorted(claim.events, key=lambda x: x.id)
        ],
        "traces": [
            {
                "step": t.step_number,
                "tool": t.tool_name,
                "input": t.input_data,
                "output": t.output_data,
                "latency_ms": t.latency_ms,
                "cost_usd": t.cost_usd,
                "success": t.success,
                "error": t.error,
                "parallel": t.parallel,
                "cached": t.cached,
            }
            for t in sorted(claim.traces, key=lambda x: x.step_number)
        ],
        "payments": [
            {
                "attempt": p.attempt_no,
                "status": p.status,
                "error": p.error,
            }
            for p in sorted(claim.payments, key=lambda x: x.attempt_no)
        ],
        "files": [f.filename for f in claim.files],
    }
