"""Structured receipt extraction output. AI must return this shape."""

from typing import Literal

from pydantic import BaseModel, Field


ExpenseType = Literal["hotel", "travel", "meal", "flight", "other"]


class ExtractedExpense(BaseModel):
    """Validated structured output from receipt extraction."""

    vendor: str = Field(..., min_length=1)
    expense_type: ExpenseType
    amount: float = Field(..., ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=8)
    date: str = Field(default="")
    invoice_number: str = Field(default="")
    confidence: float = Field(default=0.9, ge=0, le=1)
    filename: str = Field(default="")
    raw_text: str = Field(default="")
    injection_flag: bool = False
