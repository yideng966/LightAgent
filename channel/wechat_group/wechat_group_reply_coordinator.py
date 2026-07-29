"""Per-room priority and single-flight coordinator for WeChat group replies."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class _RoomState:
    condition: threading.Condition = field(
        default_factory=lambda: threading.Condition(threading.Lock())
    )
    queue: List[tuple] = field(default_factory=list)
    active: bool = False
    sequence: int = 0


class WechatGroupReplyCoordinator:
    def __init__(self):
        self._states: Dict[str, _RoomState] = {}
        self._states_lock = threading.Lock()

    def _state(self, room_id: str) -> _RoomState:
        key = str(room_id or "").strip() or "__unknown_room__"
        with self._states_lock:
            state = self._states.get(key)
            if state is None:
                state = _RoomState()
                self._states[key] = state
            return state

    @contextmanager
    def turn(self, room_id: str, priority: int = 10):
        state = self._state(room_id)
        token = object()
        with state.condition:
            state.sequence += 1
            entry = (int(priority), state.sequence, token)
            state.queue.append(entry)
            while state.active or min(state.queue, key=lambda item: (item[0], item[1]))[2] is not token:
                state.condition.wait()
            state.queue.remove(entry)
            state.active = True
        try:
            yield
        finally:
            with state.condition:
                state.active = False
                state.condition.notify_all()

    def status(self, room_id: str = "") -> dict:
        if room_id:
            state = self._state(room_id)
            with state.condition:
                return {"active": state.active, "pending": len(state.queue)}
        with self._states_lock:
            items = list(self._states.items())
        active = 0
        pending = 0
        for _, state in items:
            with state.condition:
                active += 1 if state.active else 0
                pending += len(state.queue)
        return {"rooms": len(items), "active": active, "pending": pending}
