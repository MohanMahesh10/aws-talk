"""Explicit agent tools. Orchestrator calls these — the model does not execute them."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Approval, AuditEvent, Claim, Employee, Expense, PaymentAttempt, ToolTrace
from app.models.expense import ExtractedExpense
from app.policy.engine import PolicyEngine
from app.security import assert_tool
from app.services.cache import policy_cache
from app.services.extraction import classify_expense, detect_injection, extract_receipt
from app.services.notification import send_notification
from app.services.payment import payment_service
from app.services.rate_limit import rate_limiter


class RateLimitError(RuntimeError):
    pass


def _guard(role: str, tool: str, claim: Claim) -> None:
    assert_tool(role, tool)
    if not rate_limiter.hit(claim.claim_id):
        claim.rate_limited = True
        raise RateLimitError("Rate limit reached — try again later")


def write_audit_event(db: Session, claim: Claim, message: str, actor: str = "reem", event_type: str = "info") -> None:
    db.add(AuditEvent(claim_pk=claim.id, message=message, actor=actor, event_type=event_type))
    db.flush()


def write_trace(
    db: Session,
    claim: Claim,
    tool_name: str,
    input_data: str,
    output_data: str,
    latency_ms: float,
    *,
    cost_usd: float = 0.0,
    success: bool = True,
    error: str = "",
    parallel: bool = False,
    cached: bool = False,
) -> None:
    step = (db.query(ToolTrace).filter(ToolTrace.claim_pk == claim.id).count()) + 1
    db.add(
        ToolTrace(
            claim_pk=claim.id,
            step_number=step,
            tool_name=tool_name,
            input_data=input_data[:2000],
            output_data=output_data[:2000],
            latency_ms=round(latency_ms, 1),
            cost_usd=cost_usd,
            success=success,
            error=error,
            parallel=parallel,
            cached=cached,
        )
    )
    claim.estimated_cost_usd = float(claim.estimated_cost_usd or 0) + cost_usd
    db.flush()


def extract_receipts_parallel(db: Session, claim: Claim, role: str) -> list[ExtractedExpense]:
    """Concurrency: extract all files in a thread pool."""
    _guard(role, "extract_receipt", claim)
    files = list(claim.files)
    if not files:
        return []

    started = time.perf_counter()
    results: list[ExtractedExpense] = []

    def _one(filename: str, path: str) -> tuple[ExtractedExpense, str, float]:
        return extract_receipt(filename, path)

    with ThreadPoolExecutor(max_workers=min(4, len(files))) as pool:
        futs = {pool.submit(_one, f.filename, f.stored_path): f for f in files}
        for fut in as_completed(futs):
            expense, source, cost = fut.result()
            results.append(expense)
            claim.extraction_source = source
            write_trace(
                db,
                claim,
                "extract_receipt",
                futs[fut].filename,
                f"{expense.vendor} ₹{expense.amount:,.0f} ({source})",
                (time.perf_counter() - started) * 1000,
                cost_usd=cost,
                parallel=True,
            )

    elapsed = (time.perf_counter() - started) * 1000
    write_audit_event(db, claim, f"Extracted {len(results)} receipts")
    write_trace(db, claim, "extract_receipts_parallel", f"{len(files)} files", f"{len(results)} expenses", elapsed, parallel=True)
    return results


def persist_expenses(db: Session, claim: Claim, extracted: list[ExtractedExpense]) -> list[Expense]:
    rows: list[Expense] = []
    for item in extracted:
        row = Expense(
            claim_pk=claim.id,
            vendor=item.vendor,
            expense_type=item.expense_type,
            amount=item.amount,
            currency=item.currency,
            date=item.date,
            invoice_number=item.invoice_number,
            confidence=item.confidence,
            filename=item.filename,
            route=classify_expense(item),
            injection_flag=item.injection_flag,
            raw_text=item.raw_text[:2000],
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def validate_receipt(db: Session, claim: Claim, expense: Expense, role: str) -> dict[str, Any]:
    _guard(role, "validate_receipt", claim)
    t0 = time.perf_counter()
    issues: list[str] = []
    if expense.amount <= 0:
        issues.append("Amount must be positive")
    if not expense.invoice_number:
        issues.append("Missing invoice number")
    if expense.injection_flag or detect_injection(expense.raw_text):
        expense.injection_flag = True
        claim.injection_detected = True
        issues.append("Suspicious instruction detected — treated as data")
    ok = not any(i.startswith("Amount") or i.startswith("Missing") for i in issues)
    write_trace(
        db,
        claim,
        "validate_receipt",
        expense.invoice_number,
        "ok" if ok else "; ".join(issues),
        (time.perf_counter() - t0) * 1000,
        success=ok or expense.injection_flag,
    )
    return {"ok": ok, "issues": issues}


def check_duplicate_claim(db: Session, claim: Claim, expense: Expense, role: str) -> bool:
    _guard(role, "check_duplicate_claim", claim)
    t0 = time.perf_counter()
    match = (
        db.query(Expense)
        .filter(
            Expense.invoice_number == expense.invoice_number,
            Expense.amount == expense.amount,
            Expense.id != expense.id,
            Expense.is_duplicate.is_(False),
        )
        .first()
    )
    is_dup = match is not None
    expense.is_duplicate = is_dup
    write_trace(
        db,
        claim,
        "check_duplicate_claim",
        f"{expense.invoice_number} ₹{expense.amount}",
        "duplicate" if is_dup else "unique",
        (time.perf_counter() - t0) * 1000,
    )
    return is_dup


def classify_and_route(db: Session, claim: Claim, expense: Expense, role: str) -> str:
    _guard(role, "validate_receipt", claim)
    t0 = time.perf_counter()
    route = classify_expense(
        ExtractedExpense(
            vendor=expense.vendor,
            expense_type=expense.expense_type,  # type: ignore[arg-type]
            amount=expense.amount,
            currency=expense.currency,
            date=expense.date,
            invoice_number=expense.invoice_number,
            confidence=expense.confidence,
            filename=expense.filename,
        )
    )
    expense.route = route
    write_trace(db, claim, "classify_expense", expense.vendor, f"{expense.expense_type.upper()} → {route}", (time.perf_counter() - t0) * 1000)
    return route


def get_employee(db: Session, employee_id: str, role: str) -> Employee | None:
    assert_tool(role, "get_employee")
    return db.query(Employee).filter(Employee.employee_id == employee_id).one_or_none()


def check_policy(db: Session, claim: Claim, role: str) -> Any:
    _guard(role, "check_policy", claim)
    t0 = time.perf_counter()
    cache_key = f"{claim.policy_version}:{claim.total_amount}"
    cached = policy_cache.get(cache_key)
    if cached is not None:
        claim.cache_hit = True
        decision = cached
        write_trace(
            db,
            claim,
            "check_policy",
            f"total={claim.total_amount} version={claim.policy_version}",
            f"{decision.approver} (cache)",
            (time.perf_counter() - t0) * 1000,
            cached=True,
        )
        write_audit_event(db, claim, "Policy lookup served from cache")
        return decision

    engine = PolicyEngine()
    decision = engine.determine_approval(claim.total_amount, claim.policy_version)
    policy_cache.set(cache_key, decision)
    write_trace(
        db,
        claim,
        "check_policy",
        f"total={claim.total_amount} version={claim.policy_version}",
        decision.approver,
        (time.perf_counter() - t0) * 1000,
    )
    write_audit_event(db, claim, "Policy evaluated")
    return decision


def create_approval_request(db: Session, claim: Claim, roles: list[str], actor_role: str) -> list[Approval]:
    _guard(actor_role, "create_approval_request", claim)
    t0 = time.perf_counter()
    created: list[Approval] = []
    for req in roles:
        row = Approval(claim_pk=claim.id, required_role=req, status="PENDING")
        db.add(row)
        created.append(row)
    db.flush()
    write_trace(db, claim, "create_approval_request", ",".join(roles), "APPROVAL_CREATED", (time.perf_counter() - t0) * 1000)
    write_audit_event(db, claim, f"{claim.required_approver} approval required")
    return created


def notify(db: Session, claim: Claim, role: str, recipient: str, message: str) -> None:
    _guard(role, "send_notification", claim)
    t0 = time.perf_counter()
    send_notification(db, claim.claim_id, recipient, message)
    write_trace(db, claim, "send_notification", recipient, message, (time.perf_counter() - t0) * 1000)
    write_audit_event(db, claim, "Approval notification created")


def process_payment(db: Session, claim: Claim, role: str) -> bool:
    """Finance-only. Retries + circuit breaker. Idempotent."""
    _guard(role, "process_payment", claim)
    settings = get_settings()
    if payment_service.already_paid(claim.claim_id):
        write_audit_event(db, claim, "Payment skipped — already paid (idempotent)")
        claim.payment_status = "already_paid"
        return True

    max_attempts = settings.payment_retry_limit
    for attempt in range(1, max_attempts + 1):
        t0 = time.perf_counter()
        result = payment_service.process_payment(claim.claim_id, claim.total_amount)
        claim.retry_count = attempt
        db.add(
            PaymentAttempt(
                claim_pk=claim.id,
                attempt_no=attempt,
                status="success" if result.success else "failed",
                error=result.error,
            )
        )
        write_trace(
            db,
            claim,
            "process_payment",
            f"attempt={attempt} amount={claim.total_amount}",
            "PAYMENT_SUCCESS" if result.success else result.error,
            (time.perf_counter() - t0) * 1000,
            success=result.success,
            error=result.error,
        )
        if result.success:
            claim.payment_status = "success"
            claim.circuit_open = False
            write_audit_event(db, claim, "Payment initiated" if attempt == 1 else f"Payment succeeded after {attempt} attempts")
            return True
        write_audit_event(db, claim, f"Attempt {attempt} ❌ {result.error}", event_type="warn")
        if result.circuit_open:
            claim.circuit_open = True
            claim.payment_status = "circuit_open"
            write_audit_event(db, claim, "Circuit breaker opened", event_type="error")
            return False

    claim.payment_status = "failed"
    return False
