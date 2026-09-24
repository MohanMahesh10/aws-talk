"""Claim request/response schemas."""

from datetime import date

from pydantic import BaseModel, Field


class ClaimCreate(BaseModel):
    employee_name: str = Field(..., min_length=1)
    employee_id: str = Field(..., min_length=1)
    trip_purpose: str = Field(..., min_length=1)
    trip_location: str = Field(..., min_length=1)
    trip_start: date
    trip_end: date


class CompactContext(BaseModel):
    """Compact claim context sent to the model — not full history."""

    claim_id: str
    employee: str
    trip: str
    total: float
    expenses: int
    policy_version: str
    current_state: str


class ClaimOut(BaseModel):
    claim_id: str
    employee_name: str
    employee_id: str
    trip_purpose: str
    trip_location: str
    trip_start: str
    trip_end: str
    total_amount: float
    currency: str
    state: str
    policy_version: str
    required_approver: str
    policy_reason: str
    demo_mode: bool
    extraction_source: str
    injection_detected: bool
    loop_detected: bool
    retry_count: int
    circuit_open: bool
    cache_hit: bool
    duplicate_blocked: bool
    exception_reason: str
    payment_status: str
    estimated_cost_usd: float

    class Config:
        from_attributes = True
