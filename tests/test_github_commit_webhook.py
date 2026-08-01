import hashlib
import hmac
import json
import os
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from channel.web.github_commit_webhook import (
    GITHUB_WEBHOOK_SECRET_ENV,
    GitHubCommitWebhookService,
    GitHubWebhookDeliveryStore,
    GitHubWebhookRequestError,
    MAX_GITHUB_WEBHOOK_PAYLOAD_BYTES,
    format_github_push_message,
    verify_github_webhook_signature,
)


class FakeDeliveryStore:
    def __init__(self):
        self.records = {}
        self.cleanup_calls = []

    def get(self, delivery_id):
        record = self.records.get(delivery_id)
        return dict(record) if record else None

    def record_queued(self, delivery_id, task_id, repository, ref, now=None):
        self.records[delivery_id] = {
            "delivery_id": delivery_id,
            "task_id": task_id,
            "repository": repository,
            "ref": ref,
            "status": "queued",
            "updated_at": now,
        }

    def mark_delivered(self, delivery_id, now=None):
        if delivery_id not in self.records:
            return False
        self.records[delivery_id]["status"] = "delivered"
        self.records[delivery_id]["updated_at"] = now
        return True

    def cleanup(self, retention_days, now=None):
        self.cleanup_calls.append((retention_days, now))
        return 0


class GitHubCommitWebhookServiceTest(unittest.TestCase):
    secret = "test-webhook-secret"

    def setUp(self):
        self.config = {
            "github_commit_notify_enabled": True,
            "github_commit_notify_repository": "owner/repository",
            "github_commit_notify_branches": ["main"],
            "github_commit_notify_event_mode": "selected",
            "github_commit_notify_events": ["push"],
            "github_commit_notify_event_actions": {},
            "github_commit_notify_stable_room_id": "wgr_target",
            "github_commit_notify_max_commits": 8,
            "github_commit_notify_retry_hours": 72,
            "github_commit_notify_delivery_retention_days": 30,
            "wechat_group_stable_room_ids": ["wgr_target"],
            "wechat_group_response_cleanup_max_chars": 800,
        }
        self.store = FakeDeliveryStore()
        self.enqueued = []

    def _enqueue(self, **kwargs):
        self.enqueued.append(kwargs)
        return "enqueued"

    def _service(self, enqueue_func=None):
        return GitHubCommitWebhookService(
            config_getter=lambda: self.config,
            secret_getter=lambda: self.secret,
            delivery_store=self.store,
            enqueue_func=enqueue_func or self._enqueue,
            now_func=lambda: 1234.0,
        )

    def _payload(self, **updates):
        payload = {
            "ref": "refs/heads/main",
            "deleted": False,
            "size": 2,
            "compare": "https://github.com/owner/repository/compare/a...b",
            "repository": {
                "full_name": "owner/repository",
                "html_url": "https://github.com/owner/repository",
            },
            "pusher": {"name": "alice"},
            "sender": {"login": "alice-login"},
            "commits": [
                {
                    "id": "1234567890abcdef",
                    "message": "fix login\nwith regression coverage",
                    "url": "https://github.com/owner/repository/commit/1234567",
                },
                {
                    "id": "abcdef1234567890",
                    "message": "update docs",
                    "url": "https://github.com/owner/repository/commit/abcdef1",
                },
            ],
        }
        payload.update(updates)
        return payload

    def _request(self, service, payload=None, event="push", delivery_id="delivery-1"):
        raw_body = json.dumps(payload if payload is not None else self._payload()).encode("utf-8")
        signature = "sha256=" + hmac.new(
            self.secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return service.handle(
            raw_body,
            {
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": event,
                "X-GitHub-Delivery": delivery_id,
            },
            content_type="application/json; charset=utf-8",
        )

    def test_official_github_signature_vector(self):
        self.assertTrue(verify_github_webhook_signature(
            b"Hello, World!",
            "It's a Secret to Everybody",
            "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17",
        ))

    def test_invalid_signature_is_rejected_before_json_processing(self):
        with self.assertRaises(GitHubWebhookRequestError) as raised:
            self._service().handle(
                b"not-json",
                {
                    "X-Hub-Signature-256": "sha256=invalid",
                    "X-GitHub-Event": "push",
                },
                content_type="application/json",
            )
        self.assertEqual(403, raised.exception.status_code)
        self.assertEqual("invalid_signature", raised.exception.code)

    def test_disabled_or_missing_secret_is_rejected(self):
        self.config["github_commit_notify_enabled"] = False
        with self.assertRaises(GitHubWebhookRequestError) as disabled:
            self._service().handle(b"{}", {}, content_type="application/json")
        self.assertEqual(404, disabled.exception.status_code)

        self.config["github_commit_notify_enabled"] = True
        service = GitHubCommitWebhookService(
            config_getter=lambda: self.config,
            secret_getter=lambda: "",
            delivery_store=self.store,
            enqueue_func=self._enqueue,
        )
        with self.assertRaises(GitHubWebhookRequestError) as missing_secret:
            service.handle(b"{}", {}, content_type="application/json")
        self.assertEqual(503, missing_secret.exception.status_code)

    def test_default_secret_getter_prefers_environment_and_falls_back_to_config(self):
        with patch.dict(os.environ, {GITHUB_WEBHOOK_SECRET_ENV: ""}), \
                patch(
                    "channel.web.github_commit_webhook.conf",
                    return_value={"github_commit_notify_webhook_secret": "config-secret"},
                ):
            self.assertEqual(
                "config-secret",
                GitHubCommitWebhookService._default_secret_getter(),
            )

        with patch.dict(os.environ, {GITHUB_WEBHOOK_SECRET_ENV: "environment-secret"}), \
                patch(
                    "channel.web.github_commit_webhook.conf",
                    return_value={"github_commit_notify_webhook_secret": "config-secret"},
                ):
            self.assertEqual(
                "environment-secret",
                GitHubCommitWebhookService._default_secret_getter(),
            )

    def test_signed_invalid_json_and_content_type_are_rejected(self):
        raw_body = b"{"
        signature = "sha256=" + hmac.new(
            self.secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        headers = {
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "invalid-body",
        }

        with self.assertRaises(GitHubWebhookRequestError) as invalid_type:
            self._service().handle(raw_body, headers, content_type="text/plain")
        self.assertEqual(415, invalid_type.exception.status_code)

        with self.assertRaises(GitHubWebhookRequestError) as invalid_json:
            self._service().handle(raw_body, headers, content_type="application/json")
        self.assertEqual(400, invalid_json.exception.status_code)

    def test_ping_is_accepted_without_creating_task(self):
        result = self._request(self._service(), payload={"zen": "Keep it logically awesome"}, event="ping")
        self.assertEqual({"status": "accepted", "event": "ping"}, result)
        self.assertEqual([], self.enqueued)

    def test_push_is_formatted_and_queued_for_stable_room(self):
        result = self._request(self._service())

        self.assertEqual("accepted", result["status"])
        self.assertEqual(1, len(self.enqueued))
        task = self.enqueued[0]
        self.assertEqual("wgr_target", task["stable_receiver"])
        self.assertEqual(72 * 3600, task["max_lateness_seconds"])
        self.assertEqual("github_webhook", task["metadata"]["source"])
        self.assertEqual("delivery-1", task["metadata"]["external_delivery_id"])
        self.assertIn("[GitHub 提交] owner/repository", task["content"])
        self.assertIn("1234567 fix login with regression coverage", task["content"])
        self.assertEqual("queued", self.store.records["delivery-1"]["status"])

    def test_selected_pull_request_action_is_safely_formatted_and_queued(self):
        self.config["github_commit_notify_events"] = ["push", "pull_request"]
        self.config["github_commit_notify_event_actions"] = {
            "pull_request": ["opened"],
        }
        payload = {
            "action": "opened",
            "repository": {
                "full_name": "owner/repository",
                "html_url": "https://github.com/owner/repository",
            },
            "sender": {"login": "alice"},
            "pull_request": {
                "number": 42,
                "title": "Add webhook event filtering",
                "body": "pull-request-body-secret-canary",
                "html_url": "https://github.com/owner/repository/pull/42",
                "base": {"ref": "main"},
            },
        }

        result = self._request(
            self._service(),
            payload=payload,
            event="pull_request",
            delivery_id="delivery-pr",
        )

        self.assertEqual("accepted", result["status"])
        self.assertEqual("opened", result["action"])
        task = self.enqueued[0]
        self.assertIn("PR #42 Add webhook event filtering", task["content"])
        self.assertNotIn("pull-request-body-secret-canary", task["content"])
        self.assertEqual("pull_request", task["metadata"]["github_event"])
        self.assertEqual("opened", task["metadata"]["github_action"])
        self.assertEqual("main", task["metadata"]["ref"])

    def test_selected_release_queues_release_body(self):
        self.config["github_commit_notify_events"] = ["release"]
        self.config["github_commit_notify_event_actions"] = {
            "release": ["released"],
        }
        payload = {
            "action": "released",
            "repository": {
                "full_name": "owner/repository",
                "html_url": "https://github.com/owner/repository",
            },
            "sender": {"login": "github-actions[bot]"},
            "release": {
                "name": "LightAgent 2.2.2",
                "body": "本版本修复移动端问题。\n\n## Bug 修复\n\n- 保持侧边栏入口可见。",
                "html_url": "https://github.com/owner/repository/releases/tag/v2.2.2",
            },
        }

        result = self._request(
            self._service(),
            payload=payload,
            event="release",
            delivery_id="delivery-release",
        )

        self.assertEqual("accepted", result["status"])
        task = self.enqueued[0]
        self.assertIn("内容：LightAgent 2.2.2", task["content"])
        self.assertIn("本版本修复移动端问题。", task["content"])
        self.assertIn("Bug 修复", task["content"])
        self.assertNotIn("## Bug 修复", task["content"])
        self.assertEqual("release", task["metadata"]["github_event"])
        self.assertEqual("released", task["metadata"]["github_action"])

    def test_action_filter_and_selected_event_are_ignored_without_queueing(self):
        self.config["github_commit_notify_events"] = ["pull_request"]
        self.config["github_commit_notify_event_actions"] = {
            "pull_request": ["opened"],
        }
        payload = {
            "action": "synchronize",
            "repository": {"full_name": "owner/repository"},
            "sender": {"login": "alice"},
            "pull_request": {"number": 42, "title": "Update"},
        }

        result = self._request(
            self._service(),
            payload=payload,
            event="pull_request",
            delivery_id="delivery-pr-filtered",
        )

        self.assertEqual("ignored", result["status"])
        self.assertEqual("action_not_selected", result["reason"])
        self.assertEqual([], self.enqueued)

    def test_all_mode_accepts_unknown_repository_event_with_minimal_summary(self):
        self.config["github_commit_notify_event_mode"] = "all"
        payload = {
            "action": "created",
            "repository": {
                "full_name": "owner/repository",
                "html_url": "https://github.com/owner/repository",
            },
            "sender": {"login": "alice"},
            "unknown": {"secret": "unknown-event-secret-canary"},
        }

        result = self._request(
            self._service(),
            payload=payload,
            event="future_event",
            delivery_id="delivery-future",
        )

        self.assertEqual("accepted", result["status"])
        task = self.enqueued[0]
        self.assertIn("[GitHub future_event] owner/repository", task["content"])
        self.assertNotIn("unknown-event-secret-canary", task["content"])
        self.assertEqual("future_event", task["metadata"]["github_event"])

    def test_malformed_nested_action_is_not_serialized_or_persisted(self):
        self.config["github_commit_notify_event_mode"] = "all"
        payload = {
            "action": {"secret": "nested-action-secret-canary"},
            "repository": {
                "full_name": "owner/repository",
                "html_url": "https://github.com/owner/repository",
            },
            "sender": {"login": {"secret": "nested-sender-secret-canary"}},
        }

        result = self._request(
            self._service(),
            payload=payload,
            event="future_event",
            delivery_id="delivery-nested-action",
        )

        self.assertEqual("accepted", result["status"])
        self.assertEqual("", result["action"])
        task = self.enqueued[0]
        self.assertEqual("", task["metadata"]["github_action"])
        self.assertNotIn("secret-canary", task["content"])

    def test_missing_repository_is_ignored_before_target_group_validation(self):
        self.config["github_commit_notify_event_mode"] = "all"
        self.config["github_commit_notify_stable_room_id"] = ""

        result = self._request(
            self._service(),
            payload={"action": "created", "sender": {"login": "alice"}},
            event="organization",
            delivery_id="delivery-org",
        )

        self.assertEqual("ignored", result["status"])
        self.assertEqual("repository_missing", result["reason"])
        self.assertEqual([], self.enqueued)

        malformed = self._request(
            self._service(),
            payload={"repository": ["not", "an", "object"]},
            event="issues",
            delivery_id="delivery-malformed-repository",
        )
        self.assertEqual("repository_missing", malformed["reason"])

    def test_invalid_event_header_is_rejected(self):
        with self.assertRaises(GitHubWebhookRequestError) as raised:
            self._request(
                self._service(),
                event="invalid event",
                delivery_id="delivery-invalid-event",
            )

        self.assertEqual(400, raised.exception.status_code)
        self.assertEqual("invalid_event", raised.exception.code)

    def test_delivered_delivery_is_idempotent(self):
        self.store.record_queued(
            "delivery-1",
            "github-task",
            "owner/repository",
            "refs/heads/main",
        )
        self.store.mark_delivered("delivery-1")

        result = self._request(self._service())

        self.assertEqual("duplicate", result["status"])
        self.assertEqual([], self.enqueued)

    def test_queued_delivery_with_existing_task_is_idempotent(self):
        self.store.record_queued(
            "delivery-1",
            "github-task",
            "owner/repository",
            "refs/heads/main",
        )
        calls = []

        def existing_task(**kwargs):
            calls.append(kwargs)
            return "existing"

        result = self._request(self._service(enqueue_func=existing_task))

        self.assertEqual("duplicate", result["status"])
        self.assertEqual(1, len(calls))

    def test_non_target_events_and_pushes_are_ignored(self):
        cases = [
            ("issues", self._payload(), "event_not_selected"),
            ("push", self._payload(repository={"full_name": "other/repository"}), "repository_not_allowed"),
            ("push", self._payload(ref="refs/tags/v1.0.0"), "non_branch_push"),
            ("push", self._payload(deleted=True), "branch_deleted"),
            ("push", self._payload(ref="refs/heads/dev"), "branch_not_allowed"),
            ("push", self._payload(commits=[], head_commit=None), "no_commits"),
            (
                "push",
                self._payload(
                    commits={"message": "malformed-commits-secret-canary"},
                    head_commit=None,
                ),
                "no_commits",
            ),
        ]
        for index, (event, payload, reason) in enumerate(cases):
            with self.subTest(reason=reason):
                result = self._request(
                    self._service(),
                    payload=payload,
                    event=event,
                    delivery_id="filtered-{}".format(index),
                )
                self.assertEqual("ignored", result["status"])
                self.assertEqual(reason, result["reason"])
        self.assertEqual([], self.enqueued)

    def test_message_caps_commit_count_and_total_characters(self):
        commits = [
            {"id": str(index) * 16, "message": "message-{} ".format(index) + "x" * 160}
            for index in range(10)
        ]
        message = format_github_push_message(
            self._payload(size=10, commits=commits),
            repository="owner/repository",
            branch="main",
            max_commits=2,
            max_chars=240,
        )

        self.assertLessEqual(len(message), 240)
        self.assertIn("另有", message)
        self.assertNotIn("message-2", message)

    def test_push_formatter_does_not_serialize_nested_scalar_fields(self):
        message = format_github_push_message(
            self._payload(
                pusher={"name": {"secret": "nested-pusher-secret-canary"}},
                sender={"login": {"secret": "nested-sender-secret-canary"}},
                compare={"secret": "nested-url-secret-canary"},
                commits=[{
                    "id": {"secret": "nested-id-secret-canary"},
                    "message": {"secret": "nested-message-secret-canary"},
                    "url": {"secret": "nested-commit-url-secret-canary"},
                }],
                size=1,
            ),
            repository="owner/repository",
            branch="main",
        )

        self.assertIn("推送者：unknown", message)
        self.assertIn("unknown (无提交说明)", message)
        self.assertNotIn("secret-canary", message)

    def test_target_room_must_be_selected_in_wechat_group_config(self):
        self.config["wechat_group_stable_room_ids"] = ["wgr_other"]

        with self.assertRaises(GitHubWebhookRequestError) as raised:
            self._request(self._service())

        self.assertEqual(503, raised.exception.status_code)
        self.assertEqual("target_room_not_selected", raised.exception.code)
        self.assertEqual([], self.enqueued)

    def test_sqlite_delivery_store_persists_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "deliveries.db")
            store = GitHubWebhookDeliveryStore(db_path)
            store.record_queued("delivery-db", "task-db", "owner/repository", "refs/heads/main", now=100.0)
            self.assertEqual("queued", store.get("delivery-db")["status"])
            self.assertTrue(store.mark_delivered("delivery-db", now=200.0))
            self.assertEqual("delivered", store.get("delivery-db")["status"])
            store.record_queued(
                "delivery-db",
                "task-replayed",
                "owner/repository",
                "refs/heads/main",
                now=300.0,
            )
            self.assertEqual("delivered", store.get("delivery-db")["status"])
            self.assertEqual(1, store.cleanup(1, now=200.0 + 86401))
            self.assertIsNone(store.get("delivery-db"))


class GitHubWebhookHandlerTest(unittest.TestCase):
    def test_handler_returns_202_for_accepted_delivery(self):
        from channel.web.web_channel import GitHubWebhookHandler

        raw_body = b"{}"
        ctx = types.SimpleNamespace(env={
            "CONTENT_LENGTH": str(len(raw_body)),
            "CONTENT_TYPE": "application/json",
            "HTTP_X_HUB_SIGNATURE_256": "sha256=test",
            "HTTP_X_GITHUB_EVENT": "ping",
            "HTTP_X_GITHUB_DELIVERY": "delivery-handler",
        }, status="")
        service = Mock()
        service.handle.return_value = {"status": "accepted", "event": "ping"}

        with patch("channel.web.web_channel.web.ctx", ctx, create=True), \
                patch("channel.web.web_channel.web.data", return_value=raw_body), \
                patch("channel.web.web_channel.web.header"), \
                patch("channel.web.github_commit_webhook.get_github_commit_webhook_service", return_value=service):
            result = json.loads(GitHubWebhookHandler().POST())

        self.assertEqual("202 Accepted", ctx.status)
        self.assertEqual("accepted", result["status"])
        service.handle.assert_called_once()

    def test_handler_maps_request_error_status(self):
        from channel.web.web_channel import GitHubWebhookHandler

        ctx = types.SimpleNamespace(env={"CONTENT_LENGTH": "2"}, status="")
        service = Mock()
        service.handle.side_effect = GitHubWebhookRequestError(
            403, "invalid_signature", "Webhook signature is invalid"
        )

        with patch("channel.web.web_channel.web.ctx", ctx, create=True), \
                patch("channel.web.web_channel.web.data", return_value=b"{}"), \
                patch("channel.web.web_channel.web.header"), \
                patch("channel.web.github_commit_webhook.get_github_commit_webhook_service", return_value=service):
            result = json.loads(GitHubWebhookHandler().POST())

        self.assertEqual("403 Forbidden", ctx.status)
        self.assertEqual("invalid_signature", result["code"])

    def test_handler_rejects_oversized_request_before_reading_body(self):
        from channel.web.web_channel import GitHubWebhookHandler

        ctx = types.SimpleNamespace(env={
            "CONTENT_LENGTH": str(MAX_GITHUB_WEBHOOK_PAYLOAD_BYTES + 1),
        }, status="")
        with patch("channel.web.web_channel.web.ctx", ctx, create=True), \
                patch("channel.web.web_channel.web.data") as read_body, \
                patch("channel.web.web_channel.web.header"):
            result = json.loads(GitHubWebhookHandler().POST())

        self.assertEqual("413 Payload Too Large", ctx.status)
        self.assertEqual("payload_too_large", result["code"])
        read_body.assert_not_called()


if __name__ == "__main__":
    unittest.main()
