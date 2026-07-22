"""Idle trigger for automatic WeChat group profile evolution."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from common.log import logger
from config import conf

from channel.wechat_group.wechat_group_profile_evolution_executor import (
    WechatGroupProfileEvolutionExecutor,
)
from channel.wechat_group.wechat_group_profile_evolution_store import (
    WechatGroupProfileEvolutionStore,
)
from channel.wechat_group.wechat_group_profile_llm_extractor import (
    WechatGroupProfileExtractionError,
)

_SCAN_INTERVAL_SECONDS = 60


class WechatGroupProfileEvolutionTrigger:
    def __init__(
        self,
        evolution_store: Optional[WechatGroupProfileEvolutionStore] = None,
        executor: Optional[Any] = None,
        config_getter: Optional[Callable[[str, Any], Any]] = None,
    ):
        self.evolution_store = evolution_store or WechatGroupProfileEvolutionStore()
        self.executor = executor or WechatGroupProfileEvolutionExecutor(evolution_store=self.evolution_store)
        self.config_getter = config_getter or (lambda key, default=None: conf().get(key, default))
        self._rooms = set()
        self._last_triggered_observed_row_ids = {}
        self._lock = threading.Lock()
        self._started = False

    def note_message(self, room_id: str, archive_row_id: int = 0, now: Optional[int] = None) -> None:
        room_text = str(room_id or "").strip()
        if not room_text:
            return
        ts = int(now or time.time())
        with self._lock:
            self._rooms.add(room_text)
        status = self.evolution_store.get_status(room_text)
        archive_row = int(archive_row_id or 0)
        if int(status.get("updated_at") or 0) == 0:
            self.evolution_store.update_status(
                room_text,
                last_archive_row_id=archive_row,
                latest_observed_row_id=archive_row,
                last_signal_at=ts,
            )
            return
        self.evolution_store.update_status(
            room_text,
            last_signal_at=ts,
            # Keep the processed cursor unchanged. archive_row_id is the latest
            # observed row and is used only to detect pending work in scan_once.
            latest_observed_row_id=max(
                int(status.get("latest_observed_row_id") or 0),
                archive_row,
            ),
        )

    def scan_once(self, now: Optional[int] = None) -> None:
        if not self._cfg_bool("wechat_group_profile_evolution_enabled", False):
            return
        now_ts = int(now or time.time())
        with self._lock:
            rooms = list(self._rooms)
        for room_id in rooms:
            status = self.evolution_store.get_status(room_id)
            if status.get("running"):
                continue
            if not self._should_run(status, now_ts):
                continue
            latest_observed = int(status.get("latest_observed_row_id") or 0)
            if latest_observed and self._last_triggered_observed_row_ids.get(room_id) == latest_observed:
                continue
            self.evolution_store.update_status(room_id, running=True)
            try:
                if hasattr(self.executor, "batch_message_limit"):
                    self.executor.batch_message_limit = max(
                        int(self.config_getter("wechat_group_profile_evolution_batch_message_limit", 200) or 200),
                        1,
                    )
                self.executor.run_once(room_id, trigger_source="idle")
                if latest_observed:
                    self._last_triggered_observed_row_ids[room_id] = latest_observed
            except WechatGroupProfileExtractionError as e:
                if getattr(e, "transient", False):
                    self.evolution_store.update_status(
                        room_id,
                        last_signal_at=now_ts,
                        last_failed_at=now_ts,
                        last_failed_reason=str(e),
                    )
                    logger.warning(
                        "[wechat_group] profile evolution deferred for room {}: {}".format(room_id, e)
                    )
                else:
                    logger.warning(
                        "[wechat_group] profile evolution trigger failed for room {}: {}".format(room_id, e)
                    )
            except Exception as e:
                logger.warning("[wechat_group] profile evolution trigger failed for room {}: {}".format(room_id, e))
            finally:
                self.evolution_store.update_status(room_id, running=False)

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        thread = threading.Thread(target=self._scan_loop, name="wechat-profile-evolution-trigger", daemon=True)
        thread.start()

    def _scan_loop(self) -> None:
        while True:
            time.sleep(_SCAN_INTERVAL_SECONDS)
            try:
                self.scan_once()
            except Exception as e:
                logger.warning("[wechat_group] profile evolution scan loop error: {}".format(e))

    def _should_run(self, status: dict, now_ts: int) -> bool:
        last_signal_at = int(status.get("last_signal_at") or 0)
        if not last_signal_at:
            return False
        idle_seconds = max(int(self.config_getter("wechat_group_profile_evolution_idle_minutes", 10) or 10), 1) * 60
        if now_ts - last_signal_at < idle_seconds:
            return False
        latest_observed = int(status.get("latest_observed_row_id") or 0)
        last_processed = int(status.get("last_archive_row_id") or 0)
        pending = max(latest_observed - last_processed, 0)
        min_messages = max(int(self.config_getter("wechat_group_profile_evolution_min_messages", 30) or 30), 1)
        if pending >= min_messages:
            return True
        max_interval_minutes = max(int(self.config_getter("wechat_group_profile_evolution_max_interval_minutes", 1440) or 1440), 1)
        last_success_at = int(status.get("last_success_at") or 0)
        return pending > 0 and last_success_at > 0 and now_ts - last_success_at >= max_interval_minutes * 60

    def _cfg_bool(self, key: str, default: bool) -> bool:
        value = self.config_getter(key, default)
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


_default_trigger = None
_default_lock = threading.Lock()


def get_wechat_group_profile_evolution_trigger() -> WechatGroupProfileEvolutionTrigger:
    global _default_trigger
    with _default_lock:
        if _default_trigger is None:
            from bridge.agent_bridge import AgentLLMModel
            from bridge.bridge import Bridge
            from channel.wechat_group.wechat_group_profile_llm_extractor import (
                WechatGroupProfileLlmExtractor,
            )

            store = WechatGroupProfileEvolutionStore()
            executor = WechatGroupProfileEvolutionExecutor(
                evolution_store=store,
                extractor=WechatGroupProfileLlmExtractor(model=AgentLLMModel(Bridge())),
                batch_message_limit=conf().get("wechat_group_profile_evolution_batch_message_limit", 200),
            )
            _default_trigger = WechatGroupProfileEvolutionTrigger(
                evolution_store=store,
                executor=executor,
            )
        return _default_trigger


def note_wechat_group_profile_signal(room_id: str, archive_row_id: int = 0) -> None:
    get_wechat_group_profile_evolution_trigger().note_message(room_id, archive_row_id=archive_row_id)
