"""Schema for Claude's allocator uplift adjustments."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AccountAdjustment(BaseModel):
    factor: float = Field(ge=-0.4, le=0.4, description="Uplift multiplier delta in [-0.4, 0.4]")
    citations: list[str] = Field(
        default_factory=list,
        description="Interaction or signal row ids justifying the adjustment",
    )
    rationale: str = ""
