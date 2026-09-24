"""Reem's state machine.

AI decides what requires intelligence.
Code decides what requires certainty.
Humans decide what requires authority.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.state import ClaimState, can_transition
from app.agent import tools
from app.config import get_settings
from app.db.models import Approval, Claim
from app.policy.engine import PolicyEngine
from app.security import Actor, can_approve_role
from app.services.memory import remember_claim

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self, db: Session, actor: Actor) -> None:
        self.db = db
        self.actor = actor
        self.settings = get_settings()

    def _claim(self, claim_id: str) -> Claim:
        claim = self.db.query(Claim).filter(Claim.claim_id == claim_id).one_or_none()
        if claim is None:
            raise ValueError(f"Unknown claim {claim_id}")
        return claim

    def transition(self, claim: Claim, nxt: ClaimState, message: str | None = None) -> None:
        if not can_transition(claim.state, nxt.value):
            raise ValueError(f"Illegal transition {claim.state} → {nxt.value}")
        claim.state = nxt.value
        claim.updated_at = datetime.utcnow()
        if message:
            tools.write_audit_event(self.db, claim, message)
        self.db.flush()

    def process(self, claim_id: str) -> Claim:
        """Run UPLOADED → APPROVAL_REQUIRED (or EXCEPTION)."""
        claim = self._claim(claim_id)
        role = self.actor.role
        try:
            return self._run_pipeline(claim, role)
        except tools.RateLimitError as exc:
            tools.write_audit_event(self.db, claim, str(exc), event_type="error")
            claim.exception_reason = str(exc)
            self.db.commit()
            return claim
        except Exception as exc:
            logger.exception("Agent failed on %s", claim_id)
            claim.state = ClaimState.FAILED.value
            claim.exception_reason = str(exc)
            tools.write_audit_event(self.db, claim, f"Agent failed: {exc}", event_type="error")
            self.db.commit()
            return claim

    def _run_pipeline(self, claim: Claim, role: str) -> Claim:
        if claim.state == ClaimState.UPLOADED.value:
            tools.write_audit_event(self.db, claim, "Claim uploaded")
            self.transition(claim, ClaimState.EXTRACTING)

        if claim.state == ClaimState.EXTRACTING.value:
            extracted = tools.extract_receipts_parallel(self.db, claim, role)
            tools.persist_expenses(self.db, claim, extracted)
            self.transition(claim, ClaimState.VALIDATING)

        if claim.state == ClaimState.VALIDATING.value:
            if claim.demo_scenario == "loop":
                self._simulate_loop(claim, role)
                if claim.loop_detected:
                    self.db.commit()
                    return claim
            self._validate_all(claim, role)
            live = [e for e in claim.expenses if not e.is_duplicate]
            if claim.duplicate_blocked and not live:
                claim.state = ClaimState.EXCEPTION.value
                claim.exception_reason = "Duplicate invoice + amount — already processed (idempotency)"
                tools.write_audit_event(self.db, claim, "Idempotency protection: duplicate invoice blocked", event_type="error")
                self.db.commit()
                return claim
            self.transition(claim, ClaimState.CLASSIFYING)

        if claim.state == ClaimState.CLASSIFYING.value:
            for exp in claim.expenses:
                if not exp.is_duplicate:
                    tools.classify_and_route(self.db, claim, exp, role)
            total = sum(e.amount for e in claim.expenses if not e.is_duplicate)
            claim.total_amount = total
            tools.write_audit_event(self.db, claim, f"Total calculated: ₹{total:,.0f}")
            self.transition(claim, ClaimState.POLICY_CHECK)

        if claim.state == ClaimState.POLICY_CHECK.value:
            decision = tools.check_policy(self.db, claim, role)
            claim.required_approver = decision.approver
            claim.policy_reason = decision.reason
            engine = PolicyEngine()
            roles = engine.required_roles(decision.approver)
            tools.write_trace(self.db, claim, "route_approval", decision.approver, ",".join(roles), 1.0)
            self.transition(claim, ClaimState.APPROVAL_REQUIRED, f"{decision.approver} approval required")
            tools.create_approval_request(self.db, claim, roles, role)
            tools.notify(
                self.db,
                claim,
                role,
                roles[0],
                f"Approval needed for {claim.claim_id} — ₹{claim.total_amount:,.0f}",
            )
            remember_claim(self.db, claim)

        self.db.commit()
        return claim

    def _validate_all(self, claim: Claim, role: str) -> None:
        kept = 0
        for exp in list(claim.expenses):
            tools.validate_receipt(self.db, claim, exp, role)
            if tools.check_duplicate_claim(self.db, claim, exp, role):
                claim.duplicate_blocked = True
                tools.write_audit_event(
                    self.db,
                    claim,
                    f"Duplicate blocked: {exp.invoice_number} ₹{exp.amount:,.0f}",
                    event_type="warn",
                )
            else:
                kept += 1
            if exp.injection_flag:
                tools.write_audit_event(
                    self.db,
                    claim,
                    "Suspicious instruction detected in document. Treating document content as data, not instructions.",
                    event_type="warn",
                )

    def _simulate_loop(self, claim: Claim, role: str) -> None:
        limit = self.settings.max_agent_loops
        for i in range(1, limit + 2):
            tools.write_audit_event(self.db, claim, "Trying to validate receipt...")
            tools.write_trace(self.db, claim, "validate_receipt", f"loop={i}", "retry", 8.0, success=False, error="loop")
            if i >= limit:
                claim.loop_detected = True
                claim.state = ClaimState.EXCEPTION.value
                claim.exception_reason = "Loop detected — agent stopped, escalated to human"
                tools.write_audit_event(self.db, claim, "Loop detected → Stop agent → Escalate to human", event_type="error")
                tools.write_trace(self.db, claim, "loop_detector", f"limit={limit}", "LOOP_DETECTED", 1.0, success=False)
                return

    def decide(self, claim_id: str, approve: bool, comment: str = "") -> Claim:
        claim = self._claim(claim_id)
        if claim.state != ClaimState.APPROVAL_REQUIRED.value:
            raise ValueError(f"Claim {claim_id} is not waiting for approval")

        pending = [a for a in claim.approvals if a.status == "PENDING"]
        if not pending:
            raise ValueError("No pending approval")

        target = next((a for a in pending if can_approve_role(self.actor.role, a.required_role)), None)
        if target is None:
            raise PermissionError(f"{self.actor.role} cannot approve this claim")

        target.status = "APPROVED" if approve else "REJECTED"
        target.decided_by = self.actor.name
        target.decided_at = datetime.utcnow()
        target.comment = comment

        if not approve:
            self.transition(claim, ClaimState.REJECTED, f"{self.actor.role} rejected")
            self.db.commit()
            return claim

        tools.write_audit_event(self.db, claim, f"{target.required_role} approved", actor=self.actor.name)
        still = [a for a in claim.approvals if a.status == "PENDING"]
        if still:
            tools.write_audit_event(self.db, claim, f"Still waiting on {still[0].required_role}")
            self.db.commit()
            return claim

        self.transition(claim, ClaimState.APPROVED, "Human authorized payment")
        self._pay(claim)
        self.db.commit()
        return claim

    def _pay(self, claim: Claim) -> None:
        self.transition(claim, ClaimState.PAYMENT_PROCESSING, "Payment processing")
        # Agent cannot pay. Finance tool only — ADMIN/FINANCE. For demo after CFO
        # approval, payment runs as a privileged finance job, not as the AI.
        payer = Actor(name="Finance Bot", role="FINANCE", employee_id="FIN-000")
        ok = tools.process_payment(self.db, claim, payer.role)
        if ok:
            self.transition(claim, ClaimState.COMPLETED, "Claim completed")
        else:
            claim.state = ClaimState.EXCEPTION.value
            claim.exception_reason = (
                "Circuit breaker opened — ask finance team"
                if claim.circuit_open
                else "Payment failed after retries"
            )
            tools.write_audit_event(self.db, claim, "Ask human/finance team to recover", event_type="error")

    def retry_payment(self, claim_id: str) -> Claim:
        claim = self._claim(claim_id)
        if self.actor.role not in ("FINANCE", "ADMIN"):
            raise PermissionError("Only finance can retry payment")
        if claim.state not in (ClaimState.EXCEPTION.value, ClaimState.PAYMENT_PROCESSING.value):
            raise ValueError("Claim is not in a payment-recovery state")
        claim.state = ClaimState.APPROVED.value
        claim.circuit_open = False
        claim.exception_reason = ""
        self._pay(claim)
        self.db.commit()
        return claim
