"""Gmail connector: threads become interactions (kind=email), participants
are resolved or created in people. Live adapter uses the Google API with the
gmail.readonly scope and a token path from GOOGLE_TOKEN_PATH."""

from __future__ import annotations

from datetime import datetime

from fabric import schema as S
from fabric.connectors.base import FixtureConnector
from fabric.protocol import RawRecord


class GmailConnector(FixtureConnector):
    name = "gmail"
    fixture_file = "threads.json"
    record_kind = "email"
    live_env_keys = ("GOOGLE_TOKEN_PATH",)

    def normalize(self, raw: RawRecord) -> list[S.Entity]:
        p = raw.payload
        cid = S.company_id(p["company_domain"])
        external = p["from"] if p["direction"] == "inbound" else p["to"][0]
        entities: list[S.Entity] = [
            S.Person(
                id=S.person_id(external),
                company_id=cid,
                full_name=external.split("@")[0].replace(".", " ").title(),
                email=external,
                source="gmail",
            ),
            S.Interaction(
                id=f"interaction:{p['id']}",
                person_id=S.person_id(external),
                company_id=cid,
                kind="email",
                direction=p["direction"],
                ts=datetime.fromisoformat(p["ts"]),
                latency_hours=p.get("latency_hours"),
                sentiment=p.get("sentiment"),
                summary=(p.get("subject", "") + (" - " + p["body"] if p.get("body") else "")),
                source_ref=p["id"],
            ),
        ]
        return entities

    def _pull_live(self, since: datetime | None) -> list[RawRecord]:
        raise NotImplementedError(
            "gmail live: authorize a gmail.readonly token, set GOOGLE_TOKEN_PATH, "
            "then implement users.messages.list paging here"
        )
