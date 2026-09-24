from pydantic import BaseModel, Field


class ApprovalDecision(BaseModel):
    comment: str = Field(default="")
