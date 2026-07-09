"""Shared fixture-backed connector behavior. Live adapters are per-connector."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from fabric.protocol import FIXTURES_DIR, RawRecord, Status, mock_mode


class FixtureConnector:
    """Base for all connectors: mock-first, deterministic, credential-optional.

    Subclasses set `name`, `fixture_file`, `record_kind`, `live_env_keys` and
    implement `normalize`. `pull` reads the fixture in mock mode; live mode
    delegates to `_pull_live`, which subclasses override when an adapter
    exists and is verified.
    """

    name: str = ""
    fixture_file: str = ""
    record_kind: str = "record"
    live_env_keys: tuple[str, ...] = ()

    def _fixture_path(self) -> Any:
        return FIXTURES_DIR / self.name / self.fixture_file

    def _load_fixture(self) -> list[dict[str, Any]]:
        path = self._fixture_path()
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else [data]

    def _has_creds(self) -> bool:
        return all(os.getenv(k) for k in self.live_env_keys)

    def health(self) -> Status:
        if mock_mode() or not self._has_creds():
            return Status.MOCK if self._fixture_path().exists() else Status.RED
        return Status.GREEN

    def mode(self) -> str:
        return "mock" if (mock_mode() or not self._has_creds()) else "live"

    @staticmethod
    def _ts_of(payload: dict[str, Any]) -> datetime | None:
        raw = payload.get("ts") or payload.get("call_ts")
        return datetime.fromisoformat(raw) if isinstance(raw, str) else None

    def pull(self, since: datetime | None = None) -> list[RawRecord]:
        if self.mode() == "live":
            return self._pull_live(since)
        records = []
        for payload in self._load_fixture():
            ts = self._ts_of(payload)
            if since is not None and ts is not None and ts < since:
                continue
            records.append(RawRecord(source=self.name, kind=self.record_kind, payload=payload))
        return records

    def _pull_live(self, since: datetime | None) -> list[RawRecord]:
        raise NotImplementedError(
            f"{self.name}: live adapter not verified yet, see config/apis.yaml"
        )
