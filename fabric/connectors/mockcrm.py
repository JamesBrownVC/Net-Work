"""Mock CRM connector: the fixture IS the source. 25 customer accounts with
ARR, products, renewal dates, deal stages, plus our own seller org."""

from __future__ import annotations

import json
from datetime import datetime

from fabric import schema as S
from fabric.connectors.base import FixtureConnector
from fabric.protocol import FIXTURES_DIR, RawRecord


class MockCrmConnector(FixtureConnector):
    name = "mockcrm"
    fixture_file = "companies.json"
    record_kind = "crm"
    live_env_keys = ()

    def pull(self, since: datetime | None) -> list[RawRecord]:
        records: list[RawRecord] = []
        for kind, filename in (
            ("company", "companies.json"),
            ("contact", "contacts.json"),
            ("deal", "deals.json"),
            ("seller", "sellers.json"),
        ):
            path = FIXTURES_DIR / self.name / filename
            if not path.exists():
                continue
            for payload in json.loads(path.read_text(encoding="utf-8")):
                records.append(RawRecord(source=self.name, kind=kind, payload=payload))
        return records

    def normalize(self, raw: RawRecord) -> list[S.Entity]:
        p = raw.payload
        if raw.kind == "company":
            return [
                S.Company(
                    id=p["id"],
                    name=p["name"],
                    domain=p["domain"],
                    industry=p["industry"],
                    size=p["size"],
                    is_customer=p["is_customer"],
                    arr=p["arr"],
                    renewal_date=datetime.fromisoformat(p["renewal_date"]),
                )
            ]
        if raw.kind == "contact":
            return [
                S.Person(
                    id=p["id"],
                    company_id=S.company_id(p["company_domain"]),
                    full_name=p["full_name"],
                    title=p["title"],
                    dept=p["dept"],
                    seniority_level=p["seniority_level"],
                    email=p["email"],
                    source="mockcrm",
                )
            ]
        if raw.kind == "seller":
            return [
                S.Person(
                    id=p["id"],
                    company_id="company:atlasrev.io",
                    full_name=p["full_name"],
                    title=p["title"],
                    dept=p["dept"],
                    seniority_level=p["seniority_level"],
                    email=p["email"],
                    source="mockcrm",
                )
            ]
        return [
            S.Deal(
                id=p["id"],
                company_id=S.company_id(p["company_domain"]),
                stage=p["stage"],
                amount=p["amount"],
                products_json=p["products"],
                opened_at=datetime.fromisoformat(p["opened_at"]),
                closed_at=datetime.fromisoformat(p["closed_at"]) if p["closed_at"] else None,
            )
        ]
