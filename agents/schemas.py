"""Pydantic output schemas the agents are forced to return."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WarmNode(BaseModel):
    name: str
    title: str = ""
    warmth: float = 0.0
    why: str = ""


class NetworkReport(BaseModel):
    target: str
    warm_nodes: list[WarmNode]
    power_centers: list[str]
    champion_notes: list[str] = Field(default_factory=list)
    summary: str


class RetentionRisk(BaseModel):
    account: str
    arr_eur: float
    risk: str
    evidence: list[str] = Field(default_factory=list)


class RelationshipReport(BaseModel):
    risks: list[RetentionRisk]
    summary: str


class ConquestStep(BaseModel):
    from_person: str
    to_person: str
    ask: str
    p: float


class ConquestPlay(BaseModel):
    steps: list[ConquestStep]
    reliability: float
    ev_eur: float
    timing_signal: str = ""


class ConquestReport(BaseModel):
    target: str
    objective: str
    primary_play: ConquestPlay
    fallback_play: ConquestPlay | None = None
    objections: list[str] = Field(default_factory=list)
    summary: str


class BattlePlan(BaseModel):
    """Unified Battle Plan. Section names are our own until ACR_PRD.md lands."""

    executive_summary: str
    conquest: ConquestReport
    network: NetworkReport
    allocation: list[dict]
    retention_risks: list[RetentionRisk] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            "# Unified Battle Plan",
            "",
            "## Executive Summary",
            self.executive_summary,
            "",
            f"## Conquest: {self.conquest.target} ({self.conquest.objective})",
            self.conquest.summary,
            "",
        ]
        for i, step in enumerate(self.conquest.primary_play.steps, 1):
            lines.append(
                f"{i}. {step.from_person} -> {step.to_person}: {step.ask} (p={step.p})"
            )
        lines += ["", "## Network Map", self.network.summary, ""]
        for node in self.network.warm_nodes:
            lines.append(f"- {node.name} ({node.title}) warmth={node.warmth}: {node.why}")
        lines += ["", "## This Week's Allocation"]
        for item in self.allocation:
            lines.append(f"- {item['account']}: {item['action']} (EUR {item['U_eur']})")
        if self.retention_risks:
            lines += ["", "## Retention Risks"]
            for r in self.retention_risks:
                lines.append(f"- {r.account} (EUR {r.arr_eur:,.0f}): {r.risk}")
        lines += ["", "## Next Steps"]
        lines += [f"- {s}" for s in self.next_steps]
        return "\n".join(lines)
