"""Mocked payment API: retries + circuit breaker. Not a real bank."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CircuitBreaker:
    threshold: int = 3
    failures: int = 0
    open: bool = False

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.open = True

    def record_success(self) -> None:
        self.failures = 0
        self.open = False

    def reset(self) -> None:
        self.failures = 0
        self.open = False


@dataclass
class PaymentResult:
    success: bool
    attempt: int
    error: str = ""
    circuit_open: bool = False


@dataclass
class PaymentService:
    """In-memory mock. fail_remaining > 0 forces the next N attempts to fail."""

    fail_remaining: int = 0
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    paid_ids: set[str] = field(default_factory=set)

    def configure_failures(self, count: int) -> None:
        self.fail_remaining = count
        self.breaker.reset()

    def process_payment(self, claim_id: str, amount: float) -> PaymentResult:
        """Idempotent: already-paid claims succeed without a second transfer."""
        if claim_id in self.paid_ids:
            return PaymentResult(success=True, attempt=0, error="already_paid")

        if self.breaker.open:
            return PaymentResult(
                success=False,
                attempt=0,
                error="Circuit breaker open — payment service unavailable",
                circuit_open=True,
            )

        if self.fail_remaining > 0:
            self.fail_remaining -= 1
            self.breaker.record_failure()
            return PaymentResult(
                success=False,
                attempt=0,
                error="Payment API timeout",
                circuit_open=self.breaker.open,
            )

        self.breaker.record_success()
        self.paid_ids.add(claim_id)
        return PaymentResult(success=True, attempt=0)

    def already_paid(self, claim_id: str) -> bool:
        return claim_id in self.paid_ids


payment_service = PaymentService()
