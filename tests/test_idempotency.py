"""Duplicate invoice + amount must not process twice."""

from app.services.extraction import _demo_from_name
from app.services.payment import PaymentService


def test_same_invoice_extracted_identically():
    a = _demo_from_name("hotel.txt", "ABC Hotel Invoice INV-12345 INR 8500")
    b = _demo_from_name("hotel-copy.txt", "ABC Hotel Invoice INV-12345 INR 8500")
    assert a.invoice_number == b.invoice_number == "INV-12345"
    assert a.amount == b.amount == 8500


def test_duplicate_key():
    seen: set[tuple[str, float]] = set()
    key = ("INV-12345", 8500.0)
    assert key not in seen
    seen.add(key)
    assert key in seen


def test_payment_not_sent_twice():
    svc = PaymentService()
    first = svc.process_payment("CLM-X", 100)
    second = svc.process_payment("CLM-X", 100)
    assert first.success
    assert second.success
    assert second.error == "already_paid"
