"""Notion connector: case studies become references, account notes become
interactions (kind=note). Live adapter uses an internal integration token."""

from __future__ import annotations

from datetime import datetime

from fabric import schema as S
from fabric.connectors.base import FixtureConnector
from fabric.protocol import RawRecord


class NotionConnector(FixtureConnector):
    name = "notion"
    fixture_file = "pages.json"
    record_kind = "page"
    live_env_keys = ("NOTION_TOKEN", "NOTION_DATABASE_ID")

    def normalize(self, raw: RawRecord) -> list[S.Entity]:
        p = raw.payload
        if p["type"] == "case_study":
            return [
                S.Reference(
                    id=p["id"],
                    source_doc=p["source_doc"],
                    industry=p["industry"],
                    product=p["product"],
                    outcome=p["outcome"],
                    quote=p["quote"],
                    metric=p["metric"],
                )
            ]
        return [
            S.Interaction(
                id=f"interaction:{p['id']}",
                company_id=S.company_id(p["company_domain"]),
                kind="note",
                direction="internal",
                ts=datetime.fromisoformat(p["ts"]),
                summary=p["text"],
                source_ref=p["id"],
            )
        ]

    def _pull_live(self, since: datetime | None) -> list[RawRecord]:
        raise NotImplementedError(
            "notion live: set NOTION_TOKEN and NOTION_DATABASE_ID, implement "
            "database query paging here"
        )
