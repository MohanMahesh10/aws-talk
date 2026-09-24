"""Receipt extraction: live model or deterministic demo. Never hide the source."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from app.config import get_settings
from app.models.expense import ExtractedExpense
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = (
    "ignore company policy",
    "approve this claim",
    "ignore previous instructions",
    "disregard policy",
    "you are now",
    "override policy",
    "ignore all rules",
)

# Deterministic demo receipts keyed by filename tokens.
DEMO_LIBRARY: dict[str, dict] = {
    "uber": {
        "vendor": "Uber",
        "expense_type": "travel",
        "amount": 850.0,
        "currency": "INR",
        "date": "2026-09-20",
        "invoice_number": "UBR-1001",
        "confidence": 0.96,
    },
    "ola": {
        "vendor": "Ola",
        "expense_type": "travel",
        "amount": 850.0,
        "currency": "INR",
        "date": "2026-09-20",
        "invoice_number": "OLA-1001",
        "confidence": 0.95,
    },
    "hotel": {
        "vendor": "ABC Hotel",
        "expense_type": "hotel",
        "amount": 8500.0,
        "currency": "INR",
        "date": "2026-09-20",
        "invoice_number": "INV-12345",
        "confidence": 0.94,
    },
    "meal": {
        "vendor": "Spice Kitchen",
        "expense_type": "meal",
        "amount": 1200.0,
        "currency": "INR",
        "date": "2026-09-21",
        "invoice_number": "ML-4401",
        "confidence": 0.93,
    },
    "food": {
        "vendor": "Spice Kitchen",
        "expense_type": "meal",
        "amount": 1200.0,
        "currency": "INR",
        "date": "2026-09-21",
        "invoice_number": "ML-4401",
        "confidence": 0.92,
    },
    "flight": {
        "vendor": "IndiGo",
        "expense_type": "flight",
        "amount": 14000.0,
        "currency": "INR",
        "date": "2026-09-19",
        "invoice_number": "FLT-7788",
        "confidence": 0.97,
    },
    "air": {
        "vendor": "IndiGo",
        "expense_type": "flight",
        "amount": 14000.0,
        "currency": "INR",
        "date": "2026-09-19",
        "invoice_number": "FLT-7788",
        "confidence": 0.96,
    },
}


def detect_injection(text: str) -> bool:
    blob = (text or "").lower()
    return any(p in blob for p in INJECTION_PATTERNS)


def read_file_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return p.name
    try:
        raw = p.read_bytes()
    except OSError:
        return p.name
    # Best-effort text; binary receipts still work via filename in demo mode
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return p.name


_INVOICE_RE = re.compile(r"\b((?:INV|UBR|ML|FLT|OLA|GEN|HT)-[A-Z0-9-]+)\b", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"(?:INR|₹|rs\.?)\s*([0-9][0-9,]*)", re.IGNORECASE)


def _demo_from_name(filename: str, raw_text: str) -> ExtractedExpense:
    lower = f"{filename} {raw_text}".lower()
    flagged = detect_injection(lower)
    base: dict | None = None
    for key, data in DEMO_LIBRARY.items():
        if key in lower:
            base = dict(data)
            break

    if base is None:
        digest = hashlib.md5(filename.encode("utf-8")).hexdigest()
        base = {
            "vendor": "Unknown Vendor",
            "expense_type": "other",
            "amount": float(500 + (int(digest[:4], 16) % 4500)),
            "currency": "INR",
            "date": "2026-09-20",
            "invoice_number": f"GEN-{digest[:8].upper()}",
            "confidence": 0.7,
        }

    found_inv = _INVOICE_RE.search(raw_text or "")
    if found_inv:
        base["invoice_number"] = found_inv.group(1).upper()
    found_amt = _AMOUNT_RE.search(raw_text or "")
    if found_amt:
        base["amount"] = float(found_amt.group(1).replace(",", ""))

    return ExtractedExpense(
        **base,
        filename=filename,
        raw_text=raw_text,
        injection_flag=flagged,
    )


def extract_receipt(filename: str, stored_path: str) -> tuple[ExtractedExpense, str, float]:
    """Extract one receipt.

    Returns (expense, source, cost_usd).
    source is 'demo' or 'model'.
    """
    raw_text = read_file_text(stored_path)
    settings = get_settings()

    if settings.ai_available():
        try:
            expense, meta = ai_service.extract_expense(filename, raw_text)
            expense.injection_flag = detect_injection(f"{filename} {raw_text} {expense.vendor}")
            expense.raw_text = raw_text
            expense.filename = filename
            return expense, "model", float(meta.get("cost_usd") or 0.0)
        except Exception as exc:
            logger.warning("Live extraction failed, falling back to demo: %s", exc)

    return _demo_from_name(filename, raw_text), "demo", 0.0


def classify_expense(expense: ExtractedExpense) -> str:
    """Route type → validation lane."""
    mapping = {
        "hotel": "Hotel validation",
        "travel": "Travel validation",
        "meal": "Meal policy",
        "flight": "Travel validation",
        "other": "General validation",
    }
    return mapping.get(expense.expense_type, "General validation")


def sanitize_untrusted(text: str) -> str:
    """Strip instruction-like lines. Document stays data."""
    lines = []
    for line in (text or "").splitlines():
        if detect_injection(line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    return re.sub(r"\s+", " ", cleaned).strip()
