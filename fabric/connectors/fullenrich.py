"""FullEnrich connector: contact enrichment plus org hints.

Tools: enrich_company(domain) and lookalikes(domains, n). The live adapter is
implemented against the fixture shapes only until config/apis.yaml flips
verified: true after a human checks the official docs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fabric import schema as S
from fabric.connectors.base import FixtureConnector
from fabric.protocol import FIXTURES_DIR, RawRecord


class FullEnrichConnector(FixtureConnector):
    name = "fullenrich"
    fixture_file = "novapay.json"
    record_kind = "enrichment"
    live_env_keys = ("FULLENRICH_API_KEY",)

    def enrich_company(self, domain: str) -> dict[str, Any]:
        """People with titles and org hints for a company domain."""
        if self.mode() == "live":
            raise NotImplementedError("fullenrich live: verify endpoint in config/apis.yaml")
        data = self._load_fixture()
        for block in data:
            if block.get("company", {}).get("domain") == domain.lower():
                return block
        return {"company": {"domain": domain}, "people": [], "warm_nodes": []}

    def lookalikes(self, domains: list[str], n: int = 5) -> list[str]:
        """ICP reverse search: companies similar to the given domains."""
        path = FIXTURES_DIR / self.name / "lookalikes.json"
        table: dict[str, list[str]] = json.loads(path.read_text(encoding="utf-8"))
        out: list[str] = []
        for d in domains:
            out.extend(table.get(d.lower(), []))
        return out[:n]

    def normalize(self, raw: RawRecord) -> list[S.Entity]:
        block = raw.payload
        comp = block["company"]
        entities: list[S.Entity] = [
            S.Company(
                id=comp["id"],
                name=comp["name"],
                domain=comp["domain"],
                industry=comp.get("industry", ""),
                size=comp.get("size", 0),
                is_customer=comp.get("is_customer", False),
            )
        ]
        now = datetime.now()
        for p in block["people"]:
            entities.append(
                S.Person(
                    id=p["id"],
                    company_id=comp["id"],
                    full_name=p["full_name"],
                    title=p["title"],
                    dept=p["dept"],
                    seniority_level=p["seniority_level"],
                    email=p["email"],
                    source="fullenrich",
                    enriched_at=now,
                )
            )
        entities.append(
            S.Signal(
                id=f"signal:orgstructure:{comp['domain']}",
                company_id=comp["id"],
                source="fullenrich",
                kind="org_structure",
                payload_json={
                    "reporting_lines": [
                        {"person": p["email"], "manager": p["manager_email"]}
                        for p in block["people"]
                    ],
                    "warm_nodes": block.get("warm_nodes", []),
                },
                ts=now,
                strength=1.0,
            )
        )
        return entities
