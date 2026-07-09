"""In-process pub/sub event bus. Every agent action becomes a structured
event; Phase 4's Theater WebSocket feeds off this."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

Handler = Callable[["AgentEvent"], None]


@dataclass
class AgentEvent:
    agent: str
    kind: str  # moved_to | asks | receives | shares_with | done
    payload: dict[str, Any]
    ts: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_json(self) -> str:
        return json.dumps(self.__dict__, default=str)


class EventBus:
    def __init__(self) -> None:
        self._handlers: list[Handler] = []
        self.log: list[AgentEvent] = []
        self._queues: list[asyncio.Queue[AgentEvent]] = []

    def subscribe(self, handler: Handler) -> None:
        self._handlers.append(handler)

    def queue(self) -> asyncio.Queue[AgentEvent]:
        """A live queue for WebSocket consumers (Phase 4)."""
        q: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._queues.append(q)
        return q

    def emit(self, agent: str, kind: str, **payload: Any) -> None:
        event = AgentEvent(agent=agent, kind=kind, payload=payload)
        self.log.append(event)
        for handler in self._handlers:
            handler(event)
        for q in self._queues:
            q.put_nowait(event)

    # convenience emitters matching the required choreography vocabulary
    def moved_to(self, agent: str, station: str) -> None:
        self.emit(agent, "moved_to", station=station)

    def asks(self, agent: str, text: str) -> None:
        self.emit(agent, "asks", text=text)

    def receives(self, agent: str, summary: str) -> None:
        self.emit(agent, "receives", summary=summary)

    def shares_with(self, agent: str, other: str, text: str) -> None:
        self.emit(agent, "shares_with", other=other, text=text)
