"""Explicit claim workflow states."""

from __future__ import annotations

from enum import Enum


class ClaimState(str, Enum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    VALIDATING = "VALIDATING"
    CLASSIFYING = "CLASSIFYING"
    POLICY_CHECK = "POLICY_CHECK"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVED = "APPROVED"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXCEPTION = "EXCEPTION"
    REJECTED = "REJECTED"


PIPELINE = (
    ClaimState.UPLOADED,
    ClaimState.EXTRACTING,
    ClaimState.VALIDATING,
    ClaimState.CLASSIFYING,
    ClaimState.POLICY_CHECK,
    ClaimState.APPROVAL_REQUIRED,
    ClaimState.APPROVED,
    ClaimState.PAYMENT_PROCESSING,
    ClaimState.COMPLETED,
)

ALLOWED: dict[ClaimState, set[ClaimState]] = {
    ClaimState.UPLOADED: {ClaimState.EXTRACTING, ClaimState.FAILED},
    ClaimState.EXTRACTING: {ClaimState.VALIDATING, ClaimState.FAILED, ClaimState.EXCEPTION},
    ClaimState.VALIDATING: {
        ClaimState.CLASSIFYING,
        ClaimState.FAILED,
        ClaimState.EXCEPTION,
        ClaimState.VALIDATING,
    },
    ClaimState.CLASSIFYING: {ClaimState.POLICY_CHECK, ClaimState.FAILED, ClaimState.EXCEPTION},
    ClaimState.POLICY_CHECK: {ClaimState.APPROVAL_REQUIRED, ClaimState.FAILED, ClaimState.EXCEPTION},
    ClaimState.APPROVAL_REQUIRED: {ClaimState.APPROVED, ClaimState.REJECTED, ClaimState.EXCEPTION},
    ClaimState.APPROVED: {ClaimState.PAYMENT_PROCESSING, ClaimState.EXCEPTION},
    ClaimState.PAYMENT_PROCESSING: {
        ClaimState.COMPLETED,
        ClaimState.EXCEPTION,
        ClaimState.FAILED,
        ClaimState.PAYMENT_PROCESSING,
    },
    ClaimState.COMPLETED: set(),
    ClaimState.FAILED: set(),
    ClaimState.EXCEPTION: set(),
    ClaimState.REJECTED: set(),
}


def can_transition(current: str, nxt: str) -> bool:
    try:
        return ClaimState(nxt) in ALLOWED[ClaimState(current)]
    except ValueError:
        return False
