"""Dedicated worker pool for WeChat group free reply candidates."""

import queue
import threading
import time

from common.log import logger


def _preview(text, limit=120) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return "{}...(+{} chars)".format(value[:limit], len(value) - limit)


def _local_repeater_decision(task) -> dict:
    local_decision = (task or {}).get("local_decision") or {}
    reasons = local_decision.get("reasons") or []
    suppressions = local_decision.get("suppressions") or []
    if (
        local_decision.get("triggered")
        and "repeater_message" in reasons
        and not suppressions
    ):
        return {
            "approved": True,
            "should_reply": True,
            "confidence": 1.0,
            "reason": "repeater_message",
            "tone": "natural",
            "error": "",
            "source": "local",
        }
    return {}


class WechatGroupFreeReplyWorkerPool:
    def __init__(self, judge, submit_callback, max_workers=2, queue_size=100, ttl_seconds=120, debounce_seconds=0):
        self.judge = judge
        self.submit_callback = submit_callback
        self.max_workers = max(1, int(max_workers or 1))
        self.queue_limit = max(1, int(queue_size or 1))
        self.ttl_seconds = max(1, int(ttl_seconds or 120))
        try:
            self.debounce_seconds = max(0.0, float(debounce_seconds or 0))
        except (TypeError, ValueError):
            self.debounce_seconds = 0.0
        self._queue = queue.Queue(maxsize=self.queue_limit)
        self._stop_event = threading.Event()
        self._threads = []
        self._lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending_by_room = {}
        self._active_workers = 0
        self._running = False
        self.submitted_total = 0
        self.dropped_total = 0
        self.expired_total = 0
        self.approved_total = 0
        self.rejected_total = 0
        self.coalesced_total = 0
        self.last_error = ""

    def start(self) -> None:
        if self._running:
            return
        self._stop_event.clear()
        self._running = True
        for idx in range(self.max_workers):
            thread = threading.Thread(target=self._run, name="wechat-free-reply-{}".format(idx), daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False
        with self._pending_lock:
            pending_entries = list(self._pending_by_room.values())
            self._pending_by_room = {}
        for entry in pending_entries:
            try:
                entry["timer"].cancel()
            except Exception:
                pass
        for _ in self._threads:
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
        for thread in self._threads:
            thread.join(timeout=1)
        self._threads = []

    def submit(self, task) -> bool:
        if self.debounce_seconds > 0:
            return self._submit_debounced(task)
        return self._enqueue_task(task)

    def _enqueue_task(self, task, count_submitted=True) -> bool:
        try:
            self._queue.put_nowait(task)
        except queue.Full:
            with self._lock:
                self.dropped_total += 1
            return False
        if count_submitted:
            with self._lock:
                self.submitted_total += 1
        return True

    def _submit_debounced(self, task) -> bool:
        room_id = str((task or {}).get("room_id") or "")
        if not room_id:
            return self._enqueue_task(task)
        token = object()
        timer = threading.Timer(self.debounce_seconds, self._flush_pending_room, args=(room_id, token))
        timer.daemon = True
        with self._pending_lock:
            existing = self._pending_by_room.get(room_id)
            if existing:
                try:
                    existing["timer"].cancel()
                except Exception:
                    pass
                with self._lock:
                    self.submitted_total += 1
                    self.coalesced_total += 1
            else:
                if len(self._pending_by_room) + self._queue.qsize() >= self.queue_limit:
                    with self._lock:
                        self.dropped_total += 1
                    return False
                with self._lock:
                    self.submitted_total += 1
            self._pending_by_room[room_id] = {
                "task": task,
                "timer": timer,
                "token": token,
            }
            timer.start()
        return True

    def _flush_pending_room(self, room_id, token) -> None:
        with self._pending_lock:
            entry = self._pending_by_room.get(room_id)
            if not entry or entry.get("token") is not token:
                return
            task = entry.get("task")
            self._pending_by_room.pop(room_id, None)
        if self._stop_event.is_set():
            return
        self._enqueue_task(task, count_submitted=False)

    def status(self) -> dict:
        with self._pending_lock:
            pending_count = len(self._pending_by_room)
        with self._lock:
            return {
                "running": self._running,
                "max_workers": self.max_workers,
                "queue_size": self._queue.qsize(),
                "queue_limit": self.queue_limit,
                "pending_count": pending_count,
                "active_workers": self._active_workers,
                "submitted_total": self.submitted_total,
                "dropped_total": self.dropped_total,
                "expired_total": self.expired_total,
                "approved_total": self.approved_total,
                "rejected_total": self.rejected_total,
                "coalesced_total": self.coalesced_total,
                "debounce_seconds": self.debounce_seconds,
                "last_error": self.last_error,
            }

    def _run(self):
        while not self._stop_event.is_set():
            try:
                task = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if task is None:
                    return
                self._process(task)
            finally:
                self._queue.task_done()

    def _process(self, task):
        queued_at = float(task.get("queued_at") or 0)
        if queued_at and time.time() - queued_at > self.ttl_seconds:
            with self._lock:
                self.expired_total += 1
            return
        with self._lock:
            self._active_workers += 1
        try:
            decision = _local_repeater_decision(task) or self.judge.judge(task, task.get("config") or {})
            if decision.get("approved"):
                decision_source = decision.get("source") or "llm"
                logger.info(
                    '[wechat_group] free reply {} approved: room="{}" sender="{}" confidence={} reason="{}" text="{}"'.format(
                        decision_source,
                        task.get("room_name", "") or task.get("room_id", ""),
                        task.get("sender_name", "") or task.get("sender_id", ""),
                        decision.get("confidence", 0),
                        _preview(decision.get("reason", ""), limit=80),
                        _preview(task.get("text", "")),
                    )
                )
                self.submit_callback(task, decision)
                with self._lock:
                    self.approved_total += 1
            else:
                logger.info(
                    '[wechat_group] free reply llm rejected: room="{}" sender="{}" confidence={} error="{}" reason="{}" text="{}"'.format(
                        task.get("room_name", "") or task.get("room_id", ""),
                        task.get("sender_name", "") or task.get("sender_id", ""),
                        decision.get("confidence", 0),
                        decision.get("error", ""),
                        _preview(decision.get("reason", ""), limit=80),
                        _preview(task.get("text", "")),
                    )
                )
                with self._lock:
                    self.rejected_total += 1
        except Exception as e:
            with self._lock:
                self.rejected_total += 1
                self.last_error = str(e)
        finally:
            with self._lock:
                self._active_workers -= 1
