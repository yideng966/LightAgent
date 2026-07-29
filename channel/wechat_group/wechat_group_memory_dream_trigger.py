"""Idle trigger for automatic room-scoped group memory Dream."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, Optional

from common.log import logger
from config import conf

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_context import sanitize_wechat_group_prompt_text
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
        self._running_rooms = set()
        self._lock = threading.RLock()
        self._started = False

    def note_message(self, stable_room_id: str, archive_row_id: int = 0, now: Optional[int] = None) -> None:
        room_id = str(stable_room_id or "").strip()
        row_id = max(int(archive_row_id or 0), 0)
        if not room_id or row_id <= 0:
            return
        now_ts = int(now or time.time())
        scheduler = self.knowledge_store.get_scheduler_state(room_id)
        latest = max(int(scheduler.get("latest_observed_row_id") or 0), row_id)
        self.knowledge_store.update_scheduler_state(
            room_id,
            latest_observed_row_id=latest,
            last_signal_at=now_ts,
        )
        with self._lock:
            self._signals[room_id] = {
                "latest_observed_row_id": latest,
                "last_signal_at": now_ts,
            }

    def scan_once(self, now: Optional[int] = None) -> None:
        if not self._cfg_bool("wechat_group_learning_enabled", False):
            return
        now_ts = int(now or time.time())
        rooms = self._candidate_rooms()
        for room_id in rooms:
            if not self._ensure_initialized(room_id, now_ts):
                continue
            scheduler = self.knowledge_store.get_scheduler_state(room_id)
            with self._lock:
                if room_id in self._running_rooms:
                    continue
            if now_ts < int(scheduler.get("next_retry_at") or 0):
                continue
            latest = max(
                int(scheduler.get("latest_observed_row_id") or 0),
                self.archive.get_max_row_id(room_id),
            )
            cursor = int(self.knowledge_store.get_cursor(room_id).get("last_archive_row_id") or 0)
            if latest <= cursor:
                continue
            idle_seconds = self._cfg_int("wechat_group_learning_idle_minutes", 10) * 60
            last_signal_at = int(scheduler.get("last_signal_at") or 0)
            if last_signal_at and now_ts - last_signal_at < idle_seconds:
                continue
            should_run, force, _ = self._run_decision(room_id, now_ts)
            if not should_run:
                continue
            if not _GLOBAL_DREAM_LOCK.acquire(blocking=False):
                continue
            with self._lock:
                self._running_rooms.add(room_id)
            try:
                self.knowledge_store.update_scheduler_state(room_id, last_attempt_at=now_ts)
                result = self.dream_service.run_once(
                    room_id,
                    trigger_source="idle",
                    force=force,
                )
                if str((result or {}).get("status") or "") == "success":
                    self.knowledge_store.update_scheduler_state(
                        room_id,
                        latest_observed_row_id=max(
                            latest,
                            int((result or {}).get("cursor_after") or 0),
                        ),
                        last_success_at=now_ts,
                        next_retry_at=0,
                        consecutive_failures=0,
                        last_failed_reason_code="",
                    )
                else:
                    self._record_failure(room_id, result or {}, now_ts, idle_seconds)
                    logger.warning(
                        "[wechat_group] group memory Dream deferred for "
                        "room=%s run=%s status=%s summary=%s dream=%s "
                        "transient=%s http=%s reason=%s",
                        room_id,
                        _bounded_log_value((result or {}).get("run_id")),
                        _bounded_log_value((result or {}).get("status")),
                        _bounded_log_value((result or {}).get("summary_status")),
                        _bounded_log_value((result or {}).get("dream_status")),
                        bool((result or {}).get("transient", False)),
                        (result or {}).get("llm_status_code") or "-",
                        _bounded_log_value((result or {}).get("message"), limit=300),
                    )
            except Exception as exc:
                self._record_failure(
                    room_id,
                    {"status": "failed", "message": type(exc).__name__},
                    now_ts,
                    idle_seconds,
                )
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
        scheduler = self.knowledge_store.get_scheduler_state(room_id) if room_id else {}
        backfill = self.knowledge_store.get_backfill_state(room_id) if room_id else {}
        with self._lock:
            running = room_id in self._running_rooms
        pending = 0
        batch = None
        oldest = {}
        high_watermark = 0
        if room_id:
            try:
                batch = self._pending_batch(room_id)
                pending = self.archive.count_text_messages_after_row_id(
                    room_id, int(cursor.get("last_archive_row_id") or 0)
                )
                oldest = self.archive.get_oldest_text_message_after_row_id(
                    room_id, int(cursor.get("last_archive_row_id") or 0)
                )
                high_watermark = self.archive.get_max_row_id(room_id)
            except Exception:
                pending = 0
        now_ts = int(time.time())
        reason = self._blocking_reason(room_id, now_ts, running=running) if room_id else "no_data"
        return {
            "room_id": room_id,
            "initialization_mode": str(scheduler.get("initialization_mode") or ""),
            "initialized_at": int(scheduler.get("initialized_at") or 0),
            "last_archive_row_id": int(cursor.get("last_archive_row_id") or 0),
            "incremental_cursor": int(cursor.get("last_archive_row_id") or 0),
            "archive_high_watermark": high_watermark,
            "latest_observed_row_id": max(
                int(scheduler.get("latest_observed_row_id") or 0), high_watermark
            ),
            "last_signal_at": int(scheduler.get("last_signal_at") or 0),
            "pending_text_count": pending,
            "next_window_scanned_count": int(getattr(batch, "scanned_count", 0) or 0),
            "next_window_eligible_count": int(getattr(batch, "eligible_count", 0) or 0),
            "next_window_filtered_count": int(getattr(batch, "filtered_count", 0) or 0),
            "oldest_pending_at": int(oldest.get("created_at") or 0),
            "running": running,
            "blocking_reason": reason,
            "next_retry_at": int(scheduler.get("next_retry_at") or 0),
            "backoff_until": int(scheduler.get("next_retry_at") or 0),
            "consecutive_failures": int(scheduler.get("consecutive_failures") or 0),
            "last_failed_reason_code": str(scheduler.get("last_failed_reason_code") or ""),
            "last_attempt_at": int(scheduler.get("last_attempt_at") or 0),
            "last_success_at": int(scheduler.get("last_success_at") or 0),
            "backfill": backfill,
        }

    def start(self) -> None:
        if self._started:
            return
        self.knowledge_store.interrupt_running_learning_runs()
        self._started = True
        thread = threading.Thread(
            target=self._scan_loop,
            name="wechat-group-memory-dream-trigger",
            daemon=True,
        )
        thread.start()

    def _scan_loop(self) -> None:
        while True:
            try:
                self.scan_once()
            except Exception as exc:
                logger.warning(
                    "[wechat_group] group memory Dream scan failed: %s",
                    type(exc).__name__,
                )
            time.sleep(_SCAN_INTERVAL_SECONDS)

    def _run_decision(self, room_id: str, now_ts: int) -> tuple[bool, bool, str]:
        batch = self._pending_batch(room_id)
        eligible = len(batch.messages)
        if eligible <= 0:
            if batch.scanned_count:
                return True, True, "filtered"
            return False, False, "no_data"
        min_messages = self._cfg_int("wechat_group_learning_group_memory_min_messages", 20)
        if eligible >= min_messages:
            return True, False, "ready"
        cursor = self.knowledge_store.get_cursor(room_id)
        total_pending = self.archive.count_text_messages_after_row_id(
            room_id, int(cursor.get("last_archive_row_id") or 0)
        )
        if total_pending >= min_messages:
            return True, True, "sparse_window"
        max_interval = self._cfg_int("wechat_group_learning_max_interval_minutes", 1440) * 60
        oldest = self.archive.get_oldest_text_message_after_row_id(
            room_id, int(cursor.get("last_archive_row_id") or 0)
        )
        oldest_at = int(oldest.get("created_at") or 0)
        if oldest_at and now_ts - oldest_at >= max_interval:
            return True, True, "max_interval"
        return False, False, "below_threshold"

    def _should_run(self, room_id: str, now_ts: int) -> tuple[bool, bool]:
        should_run, force, _ = self._run_decision(room_id, now_ts)
        return should_run, force

    def _pending_batch(self, room_id: str):
        cursor = self.knowledge_store.get_cursor(room_id)
        return self.material_builder.build(
            room_id,
            after_row_id=int(cursor.get("last_archive_row_id") or 0),
            limit=self._cfg_int("wechat_group_learning_batch_message_limit", 200),
            window_minutes=self._cfg_int("wechat_group_learning_group_memory_window_minutes", 120),
        )

    def _candidate_rooms(self) -> list[str]:
        configured = self.config_getter("wechat_group_stable_room_ids", []) or []
        if not isinstance(configured, (list, tuple, set)):
            configured = []
        result = []
        for value in configured:
            room_id = str(value or "").strip()
            if room_id and room_id not in result:
                result.append(room_id)
        return result

    def _ensure_initialized(self, room_id: str, now_ts: int) -> bool:
        scheduler = self.knowledge_store.get_scheduler_state(room_id)
        if int(scheduler.get("initialized_at") or 0):
            return True
        cursor = self.knowledge_store.get_cursor(room_id)
        if int(cursor.get("updated_at") or 0):
            mode = "from_history" if int(cursor.get("last_archive_row_id") or 0) == 0 else "existing_cursor"
            high_watermark = self.archive.get_max_row_id(room_id)
        else:
            mode = "from_now"
            high_watermark = self.archive.get_max_row_id(room_id)
            self.knowledge_store.update_cursor(room_id, high_watermark)
        self.knowledge_store.update_scheduler_state(
            room_id,
            initialized_at=now_ts,
            initialization_mode=mode,
            latest_observed_row_id=high_watermark,
        )
        return mode != "from_now"

    def _record_failure(
        self, room_id: str, result: Dict[str, Any], now_ts: int, idle_seconds: int
    ) -> None:
        state = self.knowledge_store.get_scheduler_state(room_id)
        failures = int(state.get("consecutive_failures") or 0) + 1
        base = max(idle_seconds, 60)
        delay = min(base * (2 ** min(failures - 1, 5)), 6 * 60 * 60)
        code = _failure_reason_code(result)
        self.knowledge_store.update_scheduler_state(
            room_id,
            next_retry_at=now_ts + delay,
            consecutive_failures=failures,
            last_failed_reason_code=code,
        )

    def _blocking_reason(self, room_id: str, now_ts: int, *, running: bool) -> str:
        if running:
            return "running"
        state = self.knowledge_store.get_scheduler_state(room_id)
        if now_ts < int(state.get("next_retry_at") or 0):
            return "backoff"
        cursor = int(self.knowledge_store.get_cursor(room_id).get("last_archive_row_id") or 0)
        if self.archive.get_max_row_id(room_id) <= cursor:
            return "no_data"
        last_signal_at = int(state.get("last_signal_at") or 0)
        idle_seconds = self._cfg_int("wechat_group_learning_idle_minutes", 10) * 60
        if last_signal_at and now_ts - last_signal_at < idle_seconds:
            return "idle_wait"
        should_run, _, reason = self._run_decision(room_id, now_ts)
        return "ready" if should_run else reason

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


def _bounded_log_value(value: Any, limit: int = 120) -> str:
    text = sanitize_wechat_group_prompt_text(value, max_length=limit)
    return text or "-"


def _failure_reason_code(result: Dict[str, Any]) -> str:
    status_code = int(result.get("llm_status_code") or 0)
    if status_code:
        return f"http_{status_code}"
    if result.get("transient"):
        return "transient_model_error"
    phase = str(result.get("dream_status") or result.get("summary_status") or "failed")
    return phase if phase not in {"", "not_run"} else "failed"


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
