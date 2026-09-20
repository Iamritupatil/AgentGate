"""The timeline. Every authority decision leaves a record here.

The UI renders these verbatim, so an event must never describe something that
did not happen. `TOOL_EXECUTED` is appended after the store returns a receipt,
never before.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any


class Actor(str, Enum):
    # OPERATOR exists so the timeline never credits a human-typed tool call to
    # the model. Until the Strands agent lands, every proposal is an OPERATOR.
    OPERATOR = "OPERATOR"
    AGENT = "AGENT"
    CEDAR = "CEDAR"
    HUMAN = "HUMAN"
    TOOL = "TOOL"


class EventType(str, Enum):
    TOOL_PROPOSED = "TOOL_PROPOSED"
    POLICY_CHECKED = "POLICY_CHECKED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    HUMAN_DECIDED = "HUMAN_DECIDED"
    TOOL_EXECUTED = "TOOL_EXECUTED"
    TOOL_BLOCKED = "TOOL_BLOCKED"
    TOOL_FAILED = "TOOL_FAILED"


@dataclass(frozen=True, slots=True)
class Event:
    sequence: int
    run_id: str
    actor: Actor
    type: EventType
    detail: dict[str, Any]
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventLog:
    """Append-only within a reset cycle. Nothing rewrites history."""

    def __init__(self) -> None:
        self._events: tuple[Event, ...] = ()
        self._lock = Lock()

    def append(self, run_id: str, actor: Actor, type: EventType, **detail: Any) -> Event:
        with self._lock:
            event = Event(len(self._events) + 1, run_id, actor, type, detail)
            self._events = (*self._events, event)
            return event

    def events(self, run_id: str | None = None) -> tuple[Event, ...]:
        with self._lock:
            if run_id is None:
                return self._events
            return tuple(event for event in self._events if event.run_id == run_id)

    def reset(self) -> None:
        with self._lock:
            self._events = ()
