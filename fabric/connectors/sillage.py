"""Sillage connector: buying intent, hiring, champion tracking, job changes,
competitor engagement, all landing in signals with strength in [0, 1]."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fabric import schema as S
from fabric.connectors.base import FixtureConnector
from fabric.protocol import RawRecord


class SillageConnector(FixtureConnector):
    name = "sillage"
    fixture_file = "signals.json"
    record_kind = "signal"
    live_env_keys = ("SILLAGE_API_KEY",)

    def signals_for(self, company: str) -> list[dict[str, Any]]:
        """All fixture signals for a company domain."""
        if self.mode() == "live":
            raise NotImplementedError("sillage live: verify endpoint in config/apis.yaml")
        return [p for p in self._load_fixture() if p["company_domain"] == company.lower()]

    def normalize(self, raw: RawRecord) -> list[S.Entity]:
        p = raw.payload
        return [
            S.Signal(
                id=f"signal:{p['id']}",
                company_id=S.company_id(p["company_domain"]),
                person_id=S.person_id(p["person_email"]) if p.get("person_email") else None,
                source="sillage",
                kind=p["kind"],
                payload_json=p.get("payload", {}),
                ts=datetime.fromisoformat(p["ts"]),
                strength=float(p["strength"]),
            )
        ]
