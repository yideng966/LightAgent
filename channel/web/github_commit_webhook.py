import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import time
from contextlib import closing
from typing import Callable, Dict, Optional

from common.log import logger
from common.utils import expand_path
from config import conf


MAX_GITHUB_WEBHOOK_PAYLOAD_BYTES = 25 * 1024 * 1024
GITHUB_WEBHOOK_SECRET_ENV = "LIGHTAGENT_GITHUB_WEBHOOK_SECRET"
_DELIVERY_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class GitHubWebhookRequestError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = int(status_code)
        self.code = str(code)
        self.message = str(message)


def verify_github_webhook_signature(raw_body: bytes, secret: str, signature: str) -> bool:
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest("sha256=" + digest, signature)


class GitHubWebhookDeliveryStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self._default_db_path()
        self._lock = threading.RLock()
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._initialize()

    @staticmethod
    def _default_db_path() -> str:
        workspace = expand_path(conf().get("agent_workspace", "~/lightagent"))
        return os.path.join(workspace, "github", "webhook_deliveries.db")

    def get(self, delivery_id: str) -> Optional[dict]:
        with self._lock, closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM github_webhook_deliveries WHERE delivery_id = ?",
                (str(delivery_id),),
            ).fetchone()
            return dict(row) if row else None

    def record_queued(
        self,
        delivery_id: str,
        task_id: str,
        repository: str,
        ref: str,
        now: Optional[float] = None,
    ) -> None:
        timestamp = float(now if now is not None else time.time())
        with self._lock, closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE github_webhook_deliveries
                SET task_id = ?,
                    repository = ?,
                    ref = ?,
                    status = 'queued',
                    updated_at = ?
                WHERE delivery_id = ? AND status != 'delivered'
                """,
                (
                    str(task_id),
                    str(repository),
                    str(ref),
                    timestamp,
                    str(delivery_id),
                ),
            )
            if cursor.rowcount == 0:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO github_webhook_deliveries (
                        delivery_id, task_id, repository, ref, status,
                        received_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'queued', ?, ?)
                    """,
                    (
                        str(delivery_id),
                        str(task_id),
                        str(repository),
                        str(ref),
                        timestamp,
                        timestamp,
                    ),
                )
            conn.commit()

    def mark_delivered(self, delivery_id: str, now: Optional[float] = None) -> bool:
        timestamp = float(now if now is not None else time.time())
        with self._lock, closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE github_webhook_deliveries
                SET status = 'delivered', updated_at = ?
                WHERE delivery_id = ?
                """,
                (timestamp, str(delivery_id)),
            )
            conn.commit()
            return cursor.rowcount > 0

    def cleanup(self, retention_days: int, now: Optional[float] = None) -> int:
        days = max(int(retention_days or 0), 1)
        cutoff = float(now if now is not None else time.time()) - days * 86400
        with self._lock, closing(self._connect()) as conn:
            cursor = conn.execute(
                "DELETE FROM github_webhook_deliveries WHERE updated_at < ?",
                (cutoff,),
            )
            conn.commit()
            return int(cursor.rowcount or 0)

    def _initialize(self) -> None:
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS github_webhook_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    ref TEXT NOT NULL,
                    status TEXT NOT NULL,
                    received_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_github_webhook_deliveries_updated
                ON github_webhook_deliveries(updated_at)
                """
            )
            conn.commit()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn


class GitHubCommitWebhookService:
    def __init__(
        self,
        config_getter: Callable[[], Dict] = conf,
        secret_getter: Optional[Callable[[], str]] = None,
        delivery_store: Optional[GitHubWebhookDeliveryStore] = None,
        enqueue_func: Optional[Callable[..., str]] = None,
        now_func: Callable[[], float] = time.time,
    ):
        self._config_getter = config_getter
        self._secret_getter = secret_getter or self._default_secret_getter
        self._delivery_store = delivery_store
        self._enqueue_func = enqueue_func
        self._now_func = now_func
        self._lock = threading.Lock()

    @staticmethod
    def _default_secret_getter() -> str:
        return str(
            os.environ.get(GITHUB_WEBHOOK_SECRET_ENV)
            or conf().get("github_commit_notify_webhook_secret")
            or ""
        )

    @property
    def delivery_store(self) -> GitHubWebhookDeliveryStore:
        if self._delivery_store is None:
            self._delivery_store = GitHubWebhookDeliveryStore()
        return self._delivery_store

    def handle(self, raw_body: bytes, headers: Dict[str, str], content_type: str = "") -> dict:
        config = self._config_getter()
        if not config.get("github_commit_notify_enabled", False):
            raise GitHubWebhookRequestError(404, "webhook_disabled", "GitHub webhook is disabled")

        if not isinstance(raw_body, bytes):
            raise GitHubWebhookRequestError(400, "invalid_body", "Webhook body must be bytes")
        if len(raw_body) > MAX_GITHUB_WEBHOOK_PAYLOAD_BYTES:
            raise GitHubWebhookRequestError(413, "payload_too_large", "Webhook payload is too large")

        normalized_headers = {
            str(key).lower(): str(value or "") for key, value in (headers or {}).items()
        }
        secret = self._secret_getter()
        if not secret:
            raise GitHubWebhookRequestError(503, "secret_missing", "GitHub webhook secret is not configured")
        if not verify_github_webhook_signature(
            raw_body,
            secret,
            normalized_headers.get("x-hub-signature-256", ""),
        ):
            raise GitHubWebhookRequestError(403, "invalid_signature", "Webhook signature is invalid")

        if content_type and not content_type.lower().startswith("application/json"):
            raise GitHubWebhookRequestError(415, "unsupported_media_type", "Content-Type must be application/json")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise GitHubWebhookRequestError(400, "invalid_json", "Webhook body is not valid UTF-8 JSON")
        if not isinstance(payload, dict):
            raise GitHubWebhookRequestError(400, "invalid_payload", "Webhook payload must be an object")

        event = normalized_headers.get("x-github-event", "").strip().lower()
        if event == "ping":
            return {"status": "accepted", "event": "ping"}
        if event != "push":
            return {"status": "ignored", "reason": "unsupported_event", "event": event}

        delivery_id = normalized_headers.get("x-github-delivery", "").strip()
        if not _DELIVERY_ID_PATTERN.fullmatch(delivery_id):
            raise GitHubWebhookRequestError(400, "invalid_delivery_id", "X-GitHub-Delivery is missing or invalid")

        expected_repository = str(config.get("github_commit_notify_repository") or "").strip()
        stable_room_id = str(config.get("github_commit_notify_stable_room_id") or "").strip()
        if not expected_repository or not stable_room_id:
            raise GitHubWebhookRequestError(
                503,
                "notification_config_incomplete",
                "GitHub repository or target stable room is not configured",
            )
        selected_stable_rooms = _normalize_string_list(
            config.get("wechat_group_stable_room_ids", [])
        )
        if stable_room_id not in selected_stable_rooms:
            raise GitHubWebhookRequestError(
                503,
                "target_room_not_selected",
                "GitHub notification target must be a selected stable WeChat group",
            )

        repository = str((payload.get("repository") or {}).get("full_name") or "").strip()
        if repository.lower() != expected_repository.lower():
            return {"status": "ignored", "reason": "repository_not_allowed"}

        ref = str(payload.get("ref") or "").strip()
        if not ref.startswith("refs/heads/"):
            return {"status": "ignored", "reason": "non_branch_push"}
        if payload.get("deleted") is True:
            return {"status": "ignored", "reason": "branch_deleted"}

        branch = ref[len("refs/heads/"):]
        allowed_branches = _normalize_string_list(
            config.get("github_commit_notify_branches", ["main"])
        )
        if allowed_branches and branch not in allowed_branches:
            return {"status": "ignored", "reason": "branch_not_allowed", "branch": branch}

        commits = [item for item in (payload.get("commits") or []) if isinstance(item, dict)]
        if not commits and isinstance(payload.get("head_commit"), dict):
            commits = [payload["head_commit"]]
            payload = dict(payload)
            payload["commits"] = commits
        if not commits:
            return {"status": "ignored", "reason": "no_commits", "branch": branch}

        max_commits = _bounded_int(config.get("github_commit_notify_max_commits", 8), 1, 20, 8)
        max_chars = _bounded_int(
            config.get("wechat_group_response_cleanup_max_chars", 800),
            200,
            4000,
            800,
        )
        content = format_github_push_message(
            payload,
            repository=repository,
            branch=branch,
            max_commits=max_commits,
            max_chars=max_chars,
        )
        retry_hours = _bounded_int(
            config.get("github_commit_notify_retry_hours", 72),
            1,
            24 * 30,
            72,
        )
        retention_days = _bounded_int(
            config.get("github_commit_notify_delivery_retention_days", 30),
            1,
            365,
            30,
        )
        task_id = "github-" + hashlib.sha256(delivery_id.encode("utf-8")).hexdigest()[:24]

        with self._lock:
            existing_delivery = self.delivery_store.get(delivery_id)
            if existing_delivery and existing_delivery.get("status") == "delivered":
                return {"status": "duplicate", "delivery_id": delivery_id}

            enqueue_func = self._enqueue_func
            if enqueue_func is None:
                from agent.tools.scheduler.integration import enqueue_wechat_group_message

                enqueue_func = enqueue_wechat_group_message

            enqueue_status = enqueue_func(
                task_id=task_id,
                name="GitHub {} {} 提交通知".format(repository, branch),
                content=content,
                stable_receiver=stable_room_id,
                max_lateness_seconds=retry_hours * 3600,
                metadata={
                    "source": "github_webhook",
                    "external_delivery_id": delivery_id,
                    "repository": repository,
                    "ref": ref,
                },
            )
            self.delivery_store.record_queued(
                delivery_id,
                task_id,
                repository,
                ref,
                now=self._now_func(),
            )
            try:
                self.delivery_store.cleanup(retention_days, now=self._now_func())
            except Exception as e:
                logger.warning("[GitHubWebhook] Failed to clean delivery records: %s", e)

        if enqueue_status == "existing":
            return {"status": "duplicate", "delivery_id": delivery_id}
        logger.info(
            "[GitHubWebhook] Queued delivery %s for %s %s",
            delivery_id,
            repository,
            branch,
        )
        return {
            "status": "accepted",
            "event": "push",
            "delivery_id": delivery_id,
            "task_id": task_id,
        }


def format_github_push_message(
    payload: dict,
    repository: str,
    branch: str,
    max_commits: int = 8,
    max_chars: int = 800,
) -> str:
    commits = [item for item in (payload.get("commits") or []) if isinstance(item, dict)]
    total = _bounded_int(payload.get("size", len(commits)), 0, 1000000, len(commits))
    total = max(total, len(commits))
    pusher = _clean_text(
        (payload.get("pusher") or {}).get("name")
        or (payload.get("sender") or {}).get("login")
        or "unknown",
        80,
    )
    header_lines = [
        "[GitHub 提交] {}".format(_clean_text(repository, 200)),
        "分支：{}".format(_clean_text(branch, 160)),
        "推送者：{}".format(pusher),
        "提交：{} 个".format(total),
        "",
    ]

    commit_lines = []
    for commit in commits[:max(int(max_commits), 1)]:
        commit_id = _clean_text(commit.get("id") or "", 40)[:7] or "unknown"
        message = _clean_text(commit.get("message") or "(无提交说明)", 160)
        commit_lines.append("{} {}".format(commit_id, message))

    compare_url = _clean_url(payload.get("compare"))
    if not compare_url and commits:
        compare_url = _clean_url(commits[-1].get("url"))

    limit = max(int(max_chars or 800), 200)
    while True:
        omitted = max(total - len(commit_lines), 0)
        footer_lines = []
        if omitted:
            footer_lines.append("另有 {} 个提交未展开".format(omitted))
        if compare_url:
            footer_lines.append("查看变更：{}".format(compare_url))
        message = "\n".join(header_lines + commit_lines + ([""] if footer_lines else []) + footer_lines).strip()
        if len(message) <= limit or not commit_lines:
            return message[:limit].rstrip()
        commit_lines.pop()


_default_service = None
_default_service_lock = threading.Lock()


def get_github_commit_webhook_service() -> GitHubCommitWebhookService:
    global _default_service
    if _default_service is None:
        with _default_service_lock:
            if _default_service is None:
                _default_service = GitHubCommitWebhookService()
    return _default_service


def mark_github_delivery_delivered(delivery_id: str) -> bool:
    if not delivery_id:
        return False
    return get_github_commit_webhook_service().delivery_store.mark_delivered(delivery_id)


def _normalize_string_list(value) -> list:
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = []
    result = []
    for item in values:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _bounded_int(value, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(int(minimum), min(int(maximum), parsed))


def _clean_text(value, max_length: int) -> str:
    text = str(value or "")
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max(int(max_length), 1)]


def _clean_url(value) -> str:
    url = _clean_text(value, 500)
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return ""
