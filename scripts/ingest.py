"""Pull -> normalize -> upsert for every registered connector.

Phase 1 scope registers mockcrm only. Adding a ninth connector later means
implementing fabric.protocol.Connector and appending it to CONNECTORS; the
upsert path in fabric.store already dispatches on entity type.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from fabric.connectors.mockcrm import MockCRMConnector
from fabric.protocol import Connector
from fabric.store import get_engine, init_db, session_scope, upsert_entity

CONNECTORS: list[Connector] = [MockCRMConnector()]


def run_ingest(since: datetime | None = None) -> Counter:
    engine = get_engine()
    init_db(engine)

    counts: Counter = Counter()
    with session_scope(engine) as session:
        for connector in CONNECTORS:
            raw_records = connector.pull(since=since)
            for raw in raw_records:
                entities = connector.normalize(raw)
                for entity in entities:
                    upsert_entity(session, entity)
                    counts[type(entity).__name__] += 1

    return counts


def main() -> None:
    counts = run_ingest()
    if not counts:
        print("No entities ingested. Run `make seed` first.")
        return

    print("Ingest complete:")
    for entity_name, count in sorted(counts.items()):
        print(f"  {entity_name}: {count}")


if __name__ == "__main__":
    main()
