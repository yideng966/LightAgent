"""Idle trigger for automatic room-scoped group memory Dream."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional

from common.log import logger
from config import conf

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_knowledge_store import WechatGroupKnowledgeStore
from channel.wechat_group.wechat_group_memory_dream import WechatGroupMemoryDreamService
from channel.wechat_group.wechat_group_memory_material import WechatGroupMemoryMaterialBuilder


_SCAN_INTERVAL_SECONDS = 60
_GLOBAL_DREAM_LOCK = threading.Lock()


class WechatGroupMemoryDreamTrigger:
    def __init__(
        self,
        archive: Optional[WechatGroupArchive] = None,
        knowledge_store: Optional[WechatGroupKnowledgeStore] = None,
        dream_service: Optional[WechatGroupMemoryDreamService] = None,
        config_getter: Optional[Callable[[str, Any], Any]] = None,
    ):
        self.archive = archive or WechatGroupArchive()
        self.knowledge_store = knowledge_store or WechatGroupKnowledgeStore()
        self.dream_service = dream_service or WechatGroupMemoryDreamService(archive=self.archive)
        self.config_getter = config_getter or (lambda key, default=None: conf().get(key, default))
        self.material_builder = WechatGroupMemoryMaterialBuilder(self.archive)
        self._signals: Dict[str, Dict[str, int]] = {}
        self._last_triggered_observed_row_ids: Dict[str, int] = {}
        self._backoff_until: Dict[str, int] = {}
        self._running_rooms = set()
        self._lock = threading.RLock()
        self._started = False

    def note_message(self, stable_room_id: str, archive_row_id: int = 0, now: Optional[int] = None) -> None:
        room_id = str(stable_room_id or "").strip()
        row_id = max(int(archive_row_id or 0), 0)
        if not room_id or row_id <= 0:
            return
        now_ts = int(now or time.time())
        cursor = self.knowledge_store.get_cursor(room_id)
        first_signal = int(cursor.get("updated_at") or 0) == 0
        if first_signal:
            self.knowledge_store.update_cursor(room_id, row_id)
        with self._lock:
            previous = self._signals.get(room_id, {})
            latest = max(int(previous.get("latest_observed_row_id") or 0), row_id)
            self._signals[room_id] = {
                "latest_observed_row_id": latest,
                "last_signal_at": now_ts,
            }
            if first_signal:
                self._last_triggered_observed_row_ids[room_id] = row_id

    def scan_once(self, now: Optional[int] = None) -> None:
        if not self._cfg_bool("wechat_group_learning_enabled", False):
            return
        now_ts = int(now or time.time())
        with self._lock:
            rooms = list(self._signals)
        for room_id in rooms:
            with self._lock:
                signal = dict(self._signals.get(room_id) or {})
                if room_id in self._running_rooms:
                    continue
                if now_ts < int(self._backoff_until.get(room_id) or 0):
                    continue
            latest = int(signal.get("latest_observed_row_id") or 0)
            if latest <= 0 or self._last_triggered_observed_row_ids.get(room_id) == latest:
                continue
            idle_seconds = self._cfg_int("wechat_group_learning_idle_minutes", 10) * 60
            if now_ts - int(signal.get("last_signal_at") or 0) < idle_seconds:
                continue
            should_run, force = self._should_run(room_id, now_ts)
            if not should_run:
                continue
            if not _GLOBAL_DREAM_LOCK.acquire(blocking=False):
                continue
            with self._lock:
                self._running_rooms.add(room_id)
            try:
                result = self.dream_service.run_once(
                    room_id,
                    trigger_source="idle",
                    force=force,
                )
                if str((result or {}).get("status") or "") == "success":
                    self._last_triggered_observed_row_ids[room_id] = latest
                    self._backoff_until.pop(room_id, None)
                else:
                    backoff = max(idle_seconds, 60)
                    self._backoff_until[room_id] = now_ts + backoff
                    logger.warning(
                        "[wechat_group] group memory Dream deferred for room=%s status=%s http=%s",
                        room_id,
                        (result or {}).get("status"),
                        (result or {}).get("llm_status_code") or 0,
                    )
            except Exception as exc:
                self._backoff_until[room_id] = now_ts + max(idle_seconds, 60)
                logger.warning(
                    "[wechat_group] group memory Dream trigger failed for room=%s: %s",
                    room_id,
                    type(exc).__name__,
                )
            finally:
                with self._lock:
                    self._running_rooms.discard(room_id)
                _GLOBAL_DREAM_LOCK.release()

    def get_status(self, stable_room_id: str) -> Dict[str, Any]:
        room_id = str(stable_room_id or "").strip()
        cursor = self.knowledge_store.get_cursor(room_id) if room_id else {}
        with self._lock:
            signal = dict(self._signals.get(room_id) or {})
            running = room_id in self._running_rooms
            backoff_until = int(self._backoff_until.get(room_id) or 0)
        pending = 0
        if room_id:
            try:
                batch = self._pending_batch(room_id)
                pending = len(batch.messages)
            except Exception:
                pending = 0
        return {
            "room_id": room_id,
            "last_archive_row_id": int(cursor.get("last_archive_row_id") or 0),
            "latest_observed_row_id": int(signal.get("latest_observed_row_id") or 0),
            "last_signal_at": int(signal.get("last_signal_at") or 0),
            "pending_text_count": pending,
            "running": running,
            "backoff_until": backoff_until,
        }

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        thread = threading.Thread(
            target=self._scan_loop,
            name="wechat-group-memory-dream-trigger",
            daemon=True,
        )
        thread.start()

    def _scan_loop(self) -> None:
        while True:
            time.sleep(_SCAN_INTERVAL_SECONDS)
            try:
                self.scan_once()
            except Exception as exc:
                logger.warning(
                    "[wechat_group] group memory Dream scan failed: %s",
                    type(exc).__name__,
                )

    def _should_run(self, room_id: str, now_ts: int) -> tuple[bool, bool]:
        batch = self._pending_batch(room_id)
        pending = len(batch.messages)
        if pending <= 0:
            return bool(batch.scanned_count), bool(batch.scanned_count)
        min_messages = self._cfg_int("wechat_group_learning_group_memory_min_messages", 20)
        if pending >= min_messages:
            return True, False
        cursor = self.knowledge_store.get_cursor(room_id)
        max_interval = self._cfg_int("wechat_group_learning_max_interval_minutes", 1440) * 60
        updated_at = int(cursor.get("updated_at") or 0)
        return bool(updated_at and now_ts - updated_at >= max_interval), True

    def _pending_batch(self, room_id: str):
        cursor = self.knowledge_store.get_cursor(room_id)
        return self.material_builder.build(
            room_id,
            after_row_id=int(cursor.get("last_archive_row_id") or 0),
            limit=self._cfg_int("wechat_group_learning_batch_message_limit", 200),
            window_minutes=self._cfg_int("wechat_group_learning_group_memory_window_minutes", 120),
        )

    def _cfg_int(self, key: str, default: int) -> int:
        try:
            return max(int(self.config_getter(key, default) or default), 1)
        except Exception:
            return default

    def _cfg_bool(self, key: str, default: bool) -> bool:
        value = self.config_getter(key, default)
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


_default_trigger: Optional[WechatGroupMemoryDreamTrigger] = None
_default_lock = threading.Lock()


def get_wechat_group_memory_dream_trigger() -> WechatGroupMemoryDreamTrigger:
    global _default_trigger
    with _default_lock:
        if _default_trigger is None:
            from bridge.bridge import Bridge
            from agent.memory.dream_engine import MemoryDreamEngine
            from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService

            archive = WechatGroupArchive()
            store = WechatGroupKnowledgeStore()
            service = WechatGroupKnowledgeService(store)
            dream_service = WechatGroupMemoryDreamService(
                archive=archive,
                knowledge_service=service,
                dream_engine=MemoryDreamEngine(Bridge().get_text_model_router()),
            )
            _default_trigger = WechatGroupMemoryDreamTrigger(
                archive=archive,
                knowledge_store=store,
                dream_service=dream_service,
            )
        return _default_trigger


def note_wechat_group_memory_signal(stable_room_id: str, archive_row_id: int = 0) -> None:
    get_wechat_group_memory_dream_trigger().note_message(
        stable_room_id,
        archive_row_id=archive_row_id,
    )
