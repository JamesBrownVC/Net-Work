"""Connector discovery and health aggregation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from fabric.connectors.base import FixtureConnector
from fabric.connectors.fullenrich import FullEnrichConnector
from fabric.connectors.gcal import GcalConnector
from fabric.connectors.gmail import GmailConnector
from fabric.connectors.gradium import GradiumConnector
from fabric.connectors.mockcrm import MockCrmConnector
from fabric.connectors.notion import NotionConnector
from fabric.connectors.sillage import SillageConnector
from fabric.connectors.slack_source import SlackSourceConnector
from fabric.store import IngestStateRow

CONNECTOR_CLASSES: dict[str, type[FixtureConnector]] = {
    c.name: c
    for c in (
        GmailConnector,
        GcalConnector,
        SlackSourceConnector,
        NotionConnector,
        FullEnrichConnector,
        SillageConnector,
        GradiumConnector,
        MockCrmConnector,
    )
}

# Connector-specific methods exposed as extra MCP tools next to the generic ones.
EXTRA_TOOLS: dict[str, tuple[str, ...]] = {
    "gcal": ("upcoming",),
    "fullenrich": ("enrich_company", "lookalikes"),
    "sillage": ("signals_for",),
    "gradium": ("transcribe",),
}


def get(name: str) -> FixtureConnector:
    if name not in CONNECTOR_CLASSES:
        raise KeyError(f"unknown connector {name!r}; known: {sorted(CONNECTOR_CLASSES)}")
    return CONNECTOR_CLASSES[name]()


def all_connectors() -> list[FixtureConnector]:
    return [cls() for cls in CONNECTOR_CLASSES.values()]


def status_rows(session: Session) -> list[dict[str, str]]:
    """One row per connector: name, mode, health, last_pull, rows ingested."""
    state = {r.connector: r for r in session.query(IngestStateRow).all()}
    rows = []
    for connector in all_connectors():
        st = state.get(connector.name)
        rows.append(
            {
                "connector": connector.name,
                "mode": connector.mode(),
                "health": connector.health().value,
                "last_pull": st.last_pull.isoformat(timespec="seconds") if st and st.last_pull
                else "-",
                "rows": str(st.rows) if st else "0",
            }
        )
    return rows
