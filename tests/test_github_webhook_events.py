import unittest

from channel.web.github_webhook_events import (
    format_github_event_message,
    get_github_event_catalog,
    get_github_event_categories,
    github_event_is_enabled,
    normalize_github_event_actions,
    normalize_github_events,
    validate_github_event_config,
)


class GitHubWebhookEventsTest(unittest.TestCase):
    def test_repository_event_catalog_is_complete_and_unique(self):
        catalog = get_github_event_catalog()
        names = [item["name"] for item in catalog]

        self.assertEqual(53, len(names))
        self.assertEqual(53, len(set(names)))
        self.assertNotIn("ping", names)
        self.assertEqual(7, len(get_github_event_categories()))
        self.assertEqual(
            ["completed", "in_progress", "requested"],
            next(item for item in catalog if item["name"] == "workflow_run")["actions"],
        )
        self.assertTrue(next(item for item in catalog if item["name"] == "push")["high_volume"])
        self.assertTrue(
            next(item for item in catalog if item["name"] == "repository_vulnerability_alert")["legacy"]
        )

    def test_event_and_action_normalization_uses_official_catalog(self):
        self.assertEqual(
            ["push", "pull_request"],
            normalize_github_events(["push", "PULL_REQUEST", "push", "unknown"]),
        )
        self.assertEqual(
            {"pull_request": ["opened", "closed"]},
            normalize_github_event_actions({
                "pull_request": ["opened", "invalid", "closed", "opened"],
                "push": ["default"],
                "unknown": ["created"],
            }),
        )

    def test_strict_config_validation_rejects_unknown_values(self):
        with self.assertRaisesRegex(ValueError, "selected or all"):
            validate_github_event_config("invalid", ["push"], {})
        with self.assertRaisesRegex(ValueError, "Unsupported GitHub webhook events"):
            validate_github_event_config("selected", ["push", "future_event"], {})
        with self.assertRaisesRegex(ValueError, "Unsupported actions"):
            validate_github_event_config("selected", ["pull_request"], {
                "pull_request": ["opened", "future_action"],
            })
        with self.assertRaisesRegex(ValueError, "At least one"):
            validate_github_event_config("selected", [], {})
        with self.assertRaisesRegex(ValueError, "events must be an array"):
            validate_github_event_config("all", "push", {})
        with self.assertRaisesRegex(ValueError, "must be an array"):
            validate_github_event_config("selected", ["pull_request"], {
                "pull_request": "opened",
            })

    def test_selected_and_all_event_filtering(self):
        selected = {
            "github_commit_notify_event_mode": "selected",
            "github_commit_notify_events": ["push", "pull_request"],
            "github_commit_notify_event_actions": {"pull_request": ["opened"]},
        }
        self.assertEqual((True, ""), github_event_is_enabled(selected, "push"))
        self.assertEqual((True, ""), github_event_is_enabled(selected, "pull_request", "opened"))
        self.assertEqual(
            (False, "action_not_selected"),
            github_event_is_enabled(selected, "pull_request", "synchronize"),
        )
        self.assertEqual(
            (False, "event_not_selected"),
            github_event_is_enabled(selected, "issues", "opened"),
        )

        allow_all = {"github_commit_notify_event_mode": "all"}
        self.assertEqual((True, ""), github_event_is_enabled(allow_all, "future_event", "created"))

    def test_pull_request_message_uses_safe_summary_only(self):
        payload = {
            "action": "opened",
            "sender": {"login": "alice"},
            "repository": {
                "html_url": "https://github.com/owner/repository",
                "token": "repository-secret-canary",
            },
            "pull_request": {
                "number": 42,
                "title": "修复登录超时\n并补充回归测试",
                "body": "pull-request-body-secret-canary",
                "html_url": "https://github.com/owner/repository/pull/42",
            },
        }

        message = format_github_event_message("pull_request", payload, "owner/repository")

        self.assertIn("[GitHub Pull Request] owner/repository", message)
        self.assertIn("动作：opened", message)
        self.assertIn("操作者：alice", message)
        self.assertIn("PR #42 修复登录超时 并补充回归测试", message)
        self.assertIn("https://github.com/owner/repository/pull/42", message)
        self.assertNotIn("pull-request-body-secret-canary", message)
        self.assertNotIn("repository-secret-canary", message)

    def test_comment_and_security_payloads_do_not_leak_sensitive_content(self):
        comment_payload = {
            "action": "created",
            "sender": {"login": "reviewer"},
            "issue": {
                "number": 7,
                "title": "登录失败",
                "html_url": "https://github.com/owner/repository/issues/7",
            },
            "comment": {"body": "comment-body-secret-canary"},
        }
        comment_message = format_github_event_message(
            "issue_comment", comment_payload, "owner/repository"
        )
        self.assertIn("Issue #7 登录失败", comment_message)
        self.assertNotIn("comment-body-secret-canary", comment_message)

        security_payload = {
            "action": "created",
            "sender": {"login": "github-advanced-security"},
            "alert": {
                "number": 9,
                "state": "open",
                "secret": "ghp_sensitive_canary",
                "html_url": "https://github.com/owner/repository/security/secret-scanning/9",
            },
            "location": {"details": "sensitive-location-canary"},
        }
        security_message = format_github_event_message(
            "secret_scanning_alert_location", security_payload, "owner/repository"
        )
        self.assertIn("告警 #9", security_message)
        self.assertIn("状态：open", security_message)
        self.assertNotIn("ghp_sensitive_canary", security_message)
        self.assertNotIn("sensitive-location-canary", security_message)

        advisory_message = format_github_event_message(
            "repository_advisory",
            {
                "action": "reported",
                "repository_advisory": {"summary": "private-advisory-secret-canary"},
            },
            "owner/repository",
        )
        self.assertIn("内容：仓库安全公告", advisory_message)
        self.assertNotIn("private-advisory-secret-canary", advisory_message)

    def test_unknown_event_uses_minimal_summary_and_github_links_only(self):
        payload = {
            "action": "created",
            "sender": {"login": "ghost"},
            "repository": {
                "html_url": "https://github.com/owner/repository",
                "private_value": "unknown-payload-secret-canary",
            },
            "thing": {
                "title": "must not be traversed",
                "html_url": "https://attacker.example/item",
            },
        }

        message = format_github_event_message("future_event", payload, "owner/repository")

        self.assertIn("[GitHub future_event] owner/repository", message)
        self.assertIn("操作者：系统", message)
        self.assertIn("https://github.com/owner/repository", message)
        self.assertNotIn("unknown-payload-secret-canary", message)
        self.assertNotIn("must not be traversed", message)
        self.assertNotIn("attacker.example", message)

    def test_nested_scalar_fields_and_credentialed_urls_are_not_serialized(self):
        payload = {
            "action": {"secret": "nested-action-secret-canary"},
            "sender": {
                "login": {"secret": "nested-login-secret-canary"},
            },
            "repository": {
                "html_url": (
                    "https://github.com/owner/repository"
                    "?token=url-query-secret-canary#url-fragment-secret-canary"
                ),
            },
            "issue": {
                "number": 7,
                "title": {"secret": "nested-title-secret-canary"},
                "html_url": "https://userinfo-secret-canary@github.com/owner/repository/issues/7",
            },
        }

        message = format_github_event_message("issues", payload, "owner/repository")

        self.assertIn("操作者：系统", message)
        self.assertIn("内容：Issue #7", message)
        self.assertIn("查看详情：https://github.com/owner/repository", message)
        self.assertNotIn("secret-canary", message)

    def test_message_length_is_bounded(self):
        payload = {
            "action": "opened",
            "sender": {"login": "alice"},
            "issue": {"number": 1, "title": "x" * 1000},
        }
        message = format_github_event_message("issues", payload, "owner/repository", max_chars=200)
        self.assertLessEqual(len(message), 200)


if __name__ == "__main__":
    unittest.main()
