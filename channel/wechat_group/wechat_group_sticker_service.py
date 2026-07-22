"""Runtime helpers for WeChat group stickers."""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.request import Request, urlopen

from agent.tools.send.send import Send
from channel.wechat_group.wechat_group_sticker_online import (
    DEFAULT_ALLOWED_DOMAINS,
    is_allowed_meme_url,
    public_image_file_name_for_url,
    search_online_memes,
)
from channel.wechat_group.wechat_group_sticker_store import WechatGroupStickerStore
from channel.wechat_group.wechat_group_sticker_labeling import (
    inspect_labeling_candidates,
    is_opaque_sticker_description,
    is_pending_sticker_description,
    is_sticker_transport_description,
    normalize_manual_description,
    run_labeling,
    vision_label,
)
from common.log import logger
from config import conf


class WechatGroupStickerService:
    def __init__(self, store: Optional[WechatGroupStickerStore] = None):
        self.store = store or WechatGroupStickerStore()
        self._online_candidates = {}
        self._last_online_send_at = {}
        self._description_job_lock = threading.RLock()
        self._description_job = None

    def collect_from_message(
        self,
        room_id: str,
        media_path: str,
        source_message_id: str = "",
        description: str = "",
        now=None,
    ) -> Dict:
        room_text = str(room_id or "").strip()
        path_text = str(media_path or "").strip()
        if not room_text or not path_text or not os.path.isfile(path_text):
            return {}
        if os.path.getsize(path_text) <= 0:
            return {}
        if self._is_too_large(path_text):
            return {}
        file_hash = _hash_file(path_text)
        normalized_description = _normalize_description(description, path_text)
        existing = self.store.get_sticker_by_hash(room_text, file_hash)
        if existing and not is_pending_sticker_description(existing.get("description")):
            normalized_description = ""
        return self.store.upsert_sticker(
            room_id=room_text,
            file_hash=file_hash,
            media_path=path_text,
            description=normalized_description,
            source_message_id=str(source_message_id or "").strip(),
            status="active",
            created_at=now,
            updated_at=now,
        )

    def search_stickers(self, room_id: str, query: str = "", limit: int = 20, status: str = "active") -> List[Dict]:
        return self.store.list_stickers(room_id, query=query, status=status, limit=limit)

    def search_online_stickers(
        self,
        room_id: str,
        query: str = "",
        limit: int = 5,
        seed: str = "",
        opener=None,
    ) -> List[Dict]:
        if not conf().get("wechat_group_sticker_online_search_enabled", True):
            return []
        result = search_online_memes(
            query=query,
            provider=str(conf().get("wechat_group_sticker_online_provider", "xiaoapi") or "xiaoapi"),
            count=limit,
            seed=seed or "{}:{}".format(room_id, query),
            config=_online_config(),
            opener=opener,
        )
        if not result.get("ok"):
            return []
        rows = []
        for idx, item in enumerate(result.get("items") or [], 1):
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            online_id = _build_online_id(room_id, url)
            row = {
                "source": "online",
                "online_id": online_id,
                "description": result.get("query") or query or "表情包",
                "provider": result.get("provider") or item.get("source") or "xiaoapi",
                "width": item.get("width") or 0,
                "height": item.get("height") or 0,
                "size": item.get("size") or 0,
                "type": item.get("type") or "image",
                "_url": url,
                "_rank": idx,
            }
            rows.append(row)
            self._online_candidates[(str(room_id or "").strip(), online_id)] = dict(row)
        return rows

    def search_mixed_stickers(
        self,
        room_id: str,
        query: str = "",
        limit: int = 5,
        seed: str = "",
        online_opener=None,
    ) -> List[Dict]:
        max_results = min(max(int(limit or 5), 1), 40)
        local_rows = []
        for row in self.search_stickers(room_id, query=query, limit=max_results):
            item = dict(row)
            item["source"] = "local"
            local_rows.append(item)
        if len(local_rows) >= max_results:
            return local_rows[:max_results]
        online_rows = self.search_online_stickers(
            room_id,
            query=query,
            limit=max_results - len(local_rows),
            seed=seed,
            opener=online_opener,
        )
        return (local_rows + online_rows)[:max_results]

    def list_stickers(self, room_id: str, query: str = "", limit: int = 20, status: str = "") -> List[Dict]:
        return self.store.list_stickers(room_id, query=query, status=status, limit=limit)

    def disable_sticker(self, room_id: str, sticker_id: str) -> Dict:
        return self.store.update_status(room_id, sticker_id, status="disabled")

    def update_description(
        self,
        room_id: str,
        sticker_id: str,
        description: str,
        expected_description: Optional[str] = None,
    ) -> Dict:
        room_text = str(room_id or "").strip()
        sticker_text = str(sticker_id or "").strip()
        if not room_text or not sticker_text:
            raise ValueError("room_id and sticker_id are required")
        existing = self.store.get_sticker(room_text, sticker_text)
        if not existing:
            raise ValueError("sticker_id is not found in this room")
        description_text = normalize_manual_description(description)
        expected_text = (
            str(existing.get("description") or "")
            if expected_description is None
            else str(expected_description)
        )
        updated = self.store.update_description(
            room_text,
            sticker_text,
            description_text,
            expected_description=expected_text,
        )
        if not updated:
            raise ValueError("sticker description changed; refresh and try again")
        return updated

    def get_description_status(self, room_id: str) -> Dict:
        room_text = str(room_id or "").strip()
        if not room_text:
            raise ValueError("room_id is required")
        status = inspect_labeling_candidates(
            self.store.db_path,
            room_id=room_text,
            description_type="pending",
        )
        status["job"] = self.get_description_job_status(room_text)
        return status

    def get_description_job_status(self, room_id: str) -> Dict:
        room_text = str(room_id or "").strip()
        with self._description_job_lock:
            job = dict(self._description_job or {})
        if not job:
            return _empty_description_job()
        if job.get("room_id") != room_text:
            if job.get("status") == "running":
                return {**_empty_description_job(), "status": "busy"}
            return _empty_description_job()
        job.pop("room_id", None)
        job.pop("backup_path", None)
        return job

    def start_description_labeling(
        self,
        room_id: str,
        workers: int = 2,
        labeler: Callable[[str], str] = vision_label,
    ) -> Dict:
        room_text = str(room_id or "").strip()
        if not room_text:
            raise ValueError("room_id is required")
        with self._description_job_lock:
            if self._description_job and self._description_job.get("status") == "running":
                raise ValueError("another sticker description job is already running")
        candidate_status = inspect_labeling_candidates(
            self.store.db_path,
            room_id=room_text,
            description_type="pending",
        )
        if int(candidate_status.get("processable") or 0) <= 0:
            raise ValueError("no processable sticker descriptions")
        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "room_id": room_text,
            "status": "running",
            "total": int(candidate_status.get("processable") or 0),
            "processed": 0,
            "updated": 0,
            "failed": 0,
            "missing_files": int(candidate_status.get("missing_files") or 0),
            "empty_files": int(candidate_status.get("empty_files") or 0),
            "skipped_changed": 0,
            "backup_created": False,
            "started_at": int(time.time()),
            "finished_at": 0,
        }
        with self._description_job_lock:
            if self._description_job and self._description_job.get("status") == "running":
                raise ValueError("another sticker description job is already running")
            self._description_job = job

        thread = threading.Thread(
            target=self._run_description_labeling_job,
            args=(job_id, room_text, min(max(int(workers or 2), 1), 4), labeler),
            name="wechat-sticker-description-labeling",
            daemon=True,
        )
        try:
            thread.start()
        except Exception:
            self._update_description_job(
                job_id,
                status="failed",
                finished_at=int(time.time()),
            )
            raise
        return self.get_description_job_status(room_text)

    def _run_description_labeling_job(self, job_id, room_id, workers, labeler):
        def on_progress(report):
            self._update_description_job(
                job_id,
                total=int(report.get("processable") or 0),
                processed=int(report.get("processed") or 0),
                updated=int(report.get("updated") or 0),
                failed=int(report.get("failed") or 0),
                missing_files=int(report.get("missing_files") or 0),
                empty_files=int(report.get("empty_files") or 0),
                skipped_changed=int(report.get("skipped_changed") or 0),
                backup_created=bool(report.get("backup_path")),
            )

        try:
            report = run_labeling(
                self.store.db_path,
                apply=True,
                delay_seconds=0,
                description_type="pending",
                workers=workers,
                labeler=labeler,
                room_id=room_id,
                progress_callback=on_progress,
                progress_output=False,
            )
            has_failures = any(int(report.get(key) or 0) > 0 for key in (
                "failed",
                "missing_files",
                "empty_files",
            ))
            self._update_description_job(
                job_id,
                status="partial_failed" if has_failures else "completed",
                finished_at=int(time.time()),
                total=int(report.get("processable") or 0),
                processed=int(report.get("processed") or 0),
                updated=int(report.get("updated") or 0),
                failed=int(report.get("failed") or 0),
                missing_files=int(report.get("missing_files") or 0),
                empty_files=int(report.get("empty_files") or 0),
                skipped_changed=int(report.get("skipped_changed") or 0),
                backup_created=bool(report.get("backup_path")),
            )
        except Exception:
            logger.error("[wechat_group] sticker description labeling failed", exc_info=True)
            self._update_description_job(
                job_id,
                status="failed",
                finished_at=int(time.time()),
            )

    def _update_description_job(self, job_id, **updates):
        with self._description_job_lock:
            if not self._description_job or self._description_job.get("job_id") != job_id:
                return
            self._description_job.update(updates)

    def prepare_send_result(self, room_id: str, sticker_id: str, message: str = "", now=None) -> Dict:
        row = self.store.get_sticker(room_id, sticker_id)
        if not row:
            raise ValueError("sticker_id is not found in this room")
        if str(row.get("status") or "") != "active":
            raise ValueError("sticker is disabled")
        path_text = str(row.get("media_path") or "").strip()
        if not path_text or not os.path.isfile(path_text):
            raise ValueError("sticker file is missing")
        daily_limit = max(int(conf().get("wechat_group_sticker_daily_send_limit", 20) or 20), 1)
        if self.store.count_usage(str(room_id or "").strip(), _start_of_day(now)) >= daily_limit:
            raise ValueError("sticker daily limit reached")
        result = Send().execute({
            "path": path_text,
            "message": message or _default_send_message(path_text),
        })
        if getattr(result, "status", "") != "success":
            raise ValueError(str(getattr(result, "result", "") or "sticker send failed"))
        payload = dict(getattr(result, "result", {}) or {})
        payload["sticker_id"] = row.get("sticker_id") or ""
        payload["room_id"] = row.get("room_id") or ""
        payload["description"] = row.get("description") or ""
        return payload

    def prepare_online_send_result(
        self,
        room_id: str,
        item: Dict,
        message: str = "",
        now=None,
        opener=None,
    ) -> Dict:
        room_text = str(room_id or "").strip()
        online_id = str((item or {}).get("online_id") or "").strip()
        candidate = dict(item or {})
        if online_id and not candidate.get("_url"):
            candidate.update(self._online_candidates.get((room_text, online_id), {}))
        url = str(candidate.get("_url") or candidate.get("url") or "").strip()
        if not room_text or not online_id or not url:
            raise ValueError("room_id, online_id and url are required")
        if not is_allowed_meme_url(url, _online_config()):
            raise ValueError("online sticker url is not allowed")
        self._check_send_limits(room_text, now=now, online=True)
        cache_path = self._download_online_sticker(url, room_text, opener=opener)
        result = Send().execute({
            "path": cache_path,
            "message": message or _default_send_message(cache_path),
        })
        if getattr(result, "status", "") != "success":
            raise ValueError(str(getattr(result, "result", "") or "online sticker send failed"))
        payload = dict(getattr(result, "result", {}) or {})
        payload.pop("url", None)
        payload["online_id"] = online_id
        payload["room_id"] = room_text
        payload["description"] = candidate.get("description") or ""
        payload["wechat_group_sticker_source"] = "online"
        sent_at = int(now) if now is not None else int(time.time())
        self.store.record_usage(room_text, online_id, created_at=sent_at)
        self._last_online_send_at[room_text] = sent_at
        return payload

    def record_sent(self, room_id: str, sticker_id: str, now=None) -> Dict:
        return self.store.record_usage(room_id, sticker_id, created_at=now)

    def _check_send_limits(self, room_id: str, now=None, online: bool = False):
        daily_limit = max(int(conf().get("wechat_group_sticker_daily_send_limit", 20) or 20), 1)
        if self.store.count_usage(str(room_id or "").strip(), _start_of_day(now)) >= daily_limit:
            raise ValueError("sticker daily limit reached")
        if online:
            cooldown = max(int(conf().get("wechat_group_sticker_cooldown_seconds", 30) or 30), 0)
            current = int(now) if now is not None else int(time.time())
            previous = int(self._last_online_send_at.get(str(room_id or "").strip()) or 0)
            if cooldown > 0 and previous and current - previous < cooldown:
                raise ValueError("sticker cooldown not elapsed")

    def _download_online_sticker(self, url: str, room_id: str, opener=None) -> str:
        cache_dir = _online_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)
        digest = hashlib.sha1("{}|{}".format(room_id, url).encode("utf-8")).hexdigest()[:16]
        file_name = "{}_{}".format(digest, public_image_file_name_for_url(url))
        target = os.path.join(cache_dir, file_name)
        if os.path.isfile(target) and os.path.getsize(target) > 0 and not self._is_too_large(target):
            return target
        request = Request(url, headers={"User-Agent": "LightAgent/WechatGroupMemeDownload"})
        opener = opener or urlopen
        with opener(request, timeout=12) as response:
            data = response.read()
        max_bytes = max(int(conf().get("wechat_group_sticker_max_size_mb", 2) or 2), 1) * 1024 * 1024
        if len(data) <= 0:
            raise ValueError("online sticker file is empty")
        if len(data) > max_bytes:
            raise ValueError("online sticker file is too large")
        with open(target, "wb") as f:
            f.write(data)
        return target

    @staticmethod
    def _is_too_large(path_text: str) -> bool:
        max_mb = max(int(conf().get("wechat_group_sticker_max_size_mb", 2) or 2), 1)
        return os.path.getsize(path_text) > max_mb * 1024 * 1024


def _hash_file(path_text: str) -> str:
    digest = hashlib.sha1()
    with open(path_text, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_description(description: str, path_text: str) -> str:
    value = str(description or "").strip()
    if value and not is_sticker_transport_description(value) and not is_opaque_sticker_description(value):
        return value[:200]
    path_stem = Path(path_text).stem.strip()
    if path_stem and not is_sticker_transport_description(path_stem) and not is_opaque_sticker_description(path_stem):
        return path_stem[:200]
    return "群聊表情包"


def _default_send_message(path_text: str) -> str:
    return f"发送表情包 {os.path.basename(path_text)}"


def _start_of_day(now=None) -> int:
    ts = int(now) if now is not None else int(time.time())
    return ts - (ts % 86400)


def _online_config() -> Dict:
    return {
        "enabled": conf().get("wechat_group_sticker_online_search_enabled", True),
        "provider": str(conf().get("wechat_group_sticker_online_provider", "xiaoapi") or "xiaoapi"),
        "endpoint": str(conf().get("wechat_group_sticker_online_endpoint", "https://api.suol.cc/v1/meme.php") or ""),
        "allowed_domains": conf().get(
            "wechat_group_sticker_online_allowed_domains",
            DEFAULT_ALLOWED_DOMAINS,
        ) or DEFAULT_ALLOWED_DOMAINS,
        "allow_gif": conf().get("wechat_group_sticker_online_allow_gif", True),
        "search_count": conf().get("wechat_group_sticker_online_search_count", 10),
    }


def _online_cache_dir() -> str:
    root = str(conf().get("wechat_group_sticker_storage_dir") or "").strip()
    if not root:
        data_root = os.environ.get("LIGHTAGENT_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".lightagent")
        root = os.path.join(os.path.expanduser(data_root), "wechat_group", "stickers")
    return os.path.join(os.path.expanduser(root), "online")


def _build_online_id(room_id: str, url: str) -> str:
    return "online-" + hashlib.sha1("{}|{}".format(room_id, url).encode("utf-8")).hexdigest()[:16]


def _empty_description_job():
    return {
        "job_id": "",
        "status": "idle",
        "total": 0,
        "processed": 0,
        "updated": 0,
        "failed": 0,
        "missing_files": 0,
        "empty_files": 0,
        "skipped_changed": 0,
        "backup_created": False,
        "started_at": 0,
        "finished_at": 0,
    }
