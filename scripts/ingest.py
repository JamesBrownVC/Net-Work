"""Pull -> normalize -> upsert for all connectors (or one)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy.orm import Session  # noqa: E402

from fabric import registry, store  # noqa: E402


def ingest(names: list[str] | None = None, since: datetime | None = None) -> dict[str, int]:
    engine = store.get_engine()
    results: dict[str, int] = {}
    with Session(engine) as session:
        for connector in registry.all_connectors():
            if names and connector.name not in names:
                continue
            raws = connector.pull(since)
            n = 0
            for raw in raws:
                n += store.upsert(session, connector.normalize(raw))
            store.record_ingest(session, connector.name, n, datetime.now())
            results[connector.name] = n
        session.commit()
    return results


if __name__ == "__main__":
    names = sys.argv[1:] or None
    for name, n in ingest(names).items():
        print(f"{name:12s} upserted {n} entities")
