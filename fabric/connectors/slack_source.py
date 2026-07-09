"""Slack as a data source: #acct-* dumps become interactions (kind=slack),
champion mentions become signals. Live adapter needs a bot token with
channels:history."""

from __future__ import annotations

from datetime import datetime

from fabric import schema as S
from fabric.connectors.base import FixtureConnector
from fabric.protocol import RawRecord


class SlackSourceConnector(FixtureConnector):
    name = "slack"
    fixture_file = "messages.json"
    record_kind = "slack_message"
    live_env_keys = ("SLACK_BOT_TOKEN",)

    def normalize(self, raw: RawRecord) -> list[S.Entity]:
        p = raw.payload
        cid = S.company_id(p["company_domain"])
        ts = datetime.fromisoformat(p["ts"])
        entities: list[S.Entity] = [
            S.Interaction(
                id=f"interaction:{p['id']}",
                company_id=cid,
                kind="slack",
                direction="internal",
                ts=ts,
                summary=f"{p['channel']}: {p['text']}",
                source_ref=p["id"],
            )
        ]
        if p.get("champion_mention"):
            entities.append(
                S.Signal(
                    id=f"signal:{p['id']}",
                    company_id=cid,
                    source="slack",
                    kind="champion_mention",
                    payload_json={"text": p["text"], "channel": p["channel"]},
                    ts=ts,
                    strength=0.6,
                )
            )
        return entities

    def _pull_live(self, since: datetime | None) -> list[RawRecord]:
        raise NotImplementedError(
            "slack live: set SLACK_BOT_TOKEN, implement conversations.history "
            "over #acct-* channels here"
        )
