"""Mock CRM connector.

Unlike every other Phase 1 connector, mockcrm has no live counterpart: the
fixture IS the source of truth. scripts/seed.py writes
fixtures/mockcrm/accounts.json deterministically (seed 42); this connector
just reads it, wraps each account as a RawRecord, and normalizes it into a
Company plus its current Deal.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

from fabric.protocol import RawRecord, Status
from fabric.schema import Company, Deal, Entity

DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "mockcrm" / "accounts.json"


def _fixture_path() -> Path:
    override = os.environ.get("MOCKCRM_FIXTURE_PATH")
    return Path(override) if override else DEFAULT_FIXTURE_PATH


class MockCRMConnector:
    name = "mockcrm"

    def __init__(self, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path or _fixture_path()

    def health(self) -> Status:
        return Status.MOCK if self.fixture_path.exists() else Status.RED

    def pull(self, since: datetime | None = None) -> list[RawRecord]:
        if not self.fixture_path.exists():
            return []

        accounts = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        return [
            RawRecord(source=self.name, source_id=account["domain"], payload=account)
            for account in accounts
        ]

    def normalize(self, raw: RawRecord) -> list[Entity]:
        account = raw.payload
        company_id = account["id"]

        company = Company(
            id=company_id,
            name=account["name"],
            domain=account["domain"],
            industry=account.get("industry"),
            size=account.get("size"),
            is_customer=True,
            arr=account["arr"],
            renewal_date=date.fromisoformat(account["renewal_date"]),
        )

        deal = Deal(
            id=f"deal-{company_id}",
            company_id=company_id,
            stage=account["deal"]["stage"],
            amount=account["deal"]["amount"],
            products_json=account["deal"]["products"],
            opened_at=date.fromisoformat(account["deal"]["opened_at"]),
            closed_at=date.fromisoformat(account["deal"]["closed_at"]) if account["deal"].get("closed_at") else None,
        )

        return [company, deal]
