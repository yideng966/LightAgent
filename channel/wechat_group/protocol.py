"""JSON Lines protocol models for the WeChat group sidecar."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class SidecarEventType:
    STATUS = "status"
    QR = "qr"
    ROOMS = "rooms"
    ROOM_MEMBERS = "room_members"
    MESSAGE = "message"
    SEND_RESULT = "send_result"
    ERROR = "error"


class SidecarCommandType:
    START = "start"
    STOP = "stop"
    LIST_ROOMS = "list_rooms"
    LIST_ROOM_MEMBERS = "list_room_members"
    SEND_TEXT = "send_text"
    SEND_FILE = "send_file"
    SEND_IMAGE = "send_image"
    SEND_AUDIO = "send_audio"


MESSAGE_IDENTITY_FIELDS = (
    "runtime_room_id",
    "runtime_sender_id",
    "runtime_self_id",
    "account_fingerprint",
    "room_fingerprint",
    "member_fingerprint",
)


@dataclass
class SidecarEvent:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)


@dataclass
class SidecarCommand:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        data = {"type": self.type}
        data.update(self.payload)
        return data


def parse_sidecar_event(data: Dict[str, Any]) -> SidecarEvent:
    event_type = data.get("type")
    if not event_type:
        raise ValueError("sidecar event missing type")
    payload = dict(data)
    payload.pop("type", None)
    return SidecarEvent(event_type, payload)


def build_send_text_command(
    room_id: str,
    text: str,
    mention_ids: Optional[List[str]] = None,
    alias_sync_cooldown_minutes: Optional[int] = None,
) -> SidecarCommand:
    payload = {
        "room_id": room_id,
        "text": text,
        "mention_ids": mention_ids or [],
    }
    if alias_sync_cooldown_minutes is not None:
        payload["alias_sync_cooldown_minutes"] = alias_sync_cooldown_minutes
    return SidecarCommand(
        SidecarCommandType.SEND_TEXT,
        payload,
    )
