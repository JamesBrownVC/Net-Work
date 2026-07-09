"""Google Calendar connector: events become interactions (kind=meeting).

Fixture events carry `offset_days` relative to runtime so the demo meeting
tomorrow never rots. Also exposes `upcoming(days)` as a Phase 3 trigger hook."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fabric import schema as S
from fabric.connectors.base import FixtureConnector
from fabric.protocol import RawRecord


class GcalConnector(FixtureConnector):
    name = "gcal"
    fixture_file = "events.json"
    record_kind = "meeting"
    live_env_keys = ("GOOGLE_TOKEN_PATH",)

    @staticmethod
    def _resolve_ts(payload: dict[str, Any]) -> datetime:
        if "ts" in payload:
            return datetime.fromisoformat(payload["ts"])
        base = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        return base + timedelta(days=int(payload["offset_days"]))

    def pull(self, since: datetime | None = None) -> list[RawRecord]:
        if self.mode() == "live":
            return self._pull_live(since)
        records = []
        for payload in self._load_fixture():
            ts = self._resolve_ts(payload)
            if since is not None and ts < since:
                continue
            payload = {**payload, "ts": ts.isoformat(timespec="seconds")}
            records.append(RawRecord(source=self.name, kind=self.record_kind, payload=payload))
        return records

    def upcoming(self, days: int = 7) -> list[dict[str, Any]]:
        """Future meetings within `days`, for agent triggers."""
        now = datetime.now()
        horizon = now + timedelta(days=days)
        out = []
        for rec in self.pull(since=None):
            ts = datetime.fromisoformat(rec.payload["ts"])
            if now <= ts <= horizon:
                out.append(rec.payload)
        return out

    def normalize(self, raw: RawRecord) -> list[S.Entity]:
        p = raw.payload
        cid = S.company_id(p["company_domain"])
        external = next(
            (a for a in p["attendees"] if not a.endswith("@atlasrev.io")), None
        )
        entities: list[S.Entity] = []
        if external is not None:
            entities.append(
                S.Person(
                    id=S.person_id(external),
                    company_id=cid,
                    full_name=external.split("@")[0].replace(".", " ").title(),
                    email=external,
                    source="gcal",
                )
            )
        entities.append(
            S.Interaction(
                id=f"interaction:{p['id']}",
                person_id=S.person_id(external) if external else None,
                company_id=cid,
                kind="meeting",
                direction="outbound",
                ts=datetime.fromisoformat(p["ts"]),
                summary=p.get("title", ""),
                source_ref=p["id"],
            )
        )
        return entities

    def _pull_live(self, since: datetime | None) -> list[RawRecord]:
        raise NotImplementedError(
            "gcal live: reuse GOOGLE_TOKEN_PATH, implement events.list on "
            "GOOGLE_CALENDAR_ID here"
        )
