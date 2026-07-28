import re
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse


GITHUB_EVENT_MODE_SELECTED = "selected"
GITHUB_EVENT_MODE_ALL = "all"
GITHUB_EVENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


_CATEGORY_ROWS = (
    ("code", "代码与引用", "Code & refs"),
    ("collaboration", "协作与评审", "Collaboration & review"),
    ("delivery", "CI/CD 与部署", "CI/CD & deployments"),
    ("release", "发行与包", "Releases & packages"),
    ("governance", "仓库治理", "Repository governance"),
    ("security", "安全", "Security"),
    ("engagement", "项目与关注", "Projects & engagement"),
)


_EVENT_ROWS = (
    ("push", "code", "代码推送", "Push"),
    ("create", "code", "创建分支或标签", "Create branch or tag"),
    ("delete", "code", "删除分支或标签", "Delete branch or tag"),
    ("commit_comment", "code", "提交评论", "Commit comment"),
    ("fork", "code", "仓库派生", "Fork"),
    ("gollum", "code", "Wiki 更新", "Wiki update"),
    ("public", "code", "仓库公开", "Repository made public"),
    ("discussion", "collaboration", "讨论", "Discussion"),
    ("discussion_comment", "collaboration", "讨论评论", "Discussion comment"),
    ("issue_comment", "collaboration", "Issue/PR 评论", "Issue or PR comment"),
    ("issue_dependencies", "collaboration", "Issue 依赖", "Issue dependency"),
    ("issues", "collaboration", "Issue", "Issue"),
    ("label", "collaboration", "标签", "Label"),
    ("milestone", "collaboration", "里程碑", "Milestone"),
    ("pull_request", "collaboration", "Pull Request", "Pull request"),
    ("pull_request_review", "collaboration", "PR 评审", "Pull request review"),
    ("pull_request_review_comment", "collaboration", "PR 评审评论", "Pull request review comment"),
    ("pull_request_review_thread", "collaboration", "PR 评审会话", "Pull request review thread"),
    ("sub_issues", "collaboration", "子 Issue", "Sub-issue"),
    ("check_run", "delivery", "检查运行", "Check run"),
    ("check_suite", "delivery", "检查套件", "Check suite"),
    ("deployment", "delivery", "部署", "Deployment"),
    ("deployment_status", "delivery", "部署状态", "Deployment status"),
    ("page_build", "delivery", "Pages 构建", "Pages build"),
    ("status", "delivery", "提交状态", "Commit status"),
    ("workflow_job", "delivery", "工作流任务", "Workflow job"),
    ("workflow_run", "delivery", "工作流运行", "Workflow run"),
    ("release", "release", "Release", "Release"),
    ("package", "release", "软件包", "Package"),
    ("registry_package", "release", "Registry 软件包", "Registry package"),
    ("branch_protection_configuration", "governance", "分支保护配置", "Branch protection configuration"),
    ("branch_protection_rule", "governance", "分支保护规则", "Branch protection rule"),
    ("custom_property_values", "governance", "自定义属性值", "Custom property values"),
    ("deploy_key", "governance", "部署密钥", "Deploy key"),
    ("member", "governance", "仓库成员", "Repository member"),
    ("meta", "governance", "Webhook 配置", "Webhook configuration"),
    ("repository", "governance", "仓库", "Repository"),
    ("repository_import", "governance", "仓库导入", "Repository import"),
    ("repository_ruleset", "governance", "仓库规则集", "Repository ruleset"),
    ("security_and_analysis", "governance", "安全与分析设置", "Security and analysis settings"),
    ("team_add", "governance", "团队加入仓库", "Team added to repository"),
    ("code_scanning_alert", "security", "代码扫描告警", "Code scanning alert"),
    ("dependabot_alert", "security", "Dependabot 告警", "Dependabot alert"),
    ("repository_advisory", "security", "仓库安全公告", "Repository security advisory"),
    ("repository_vulnerability_alert", "security", "仓库漏洞告警", "Repository vulnerability alert"),
    ("secret_scanning_alert", "security", "Secret 扫描告警", "Secret scanning alert"),
    ("secret_scanning_alert_location", "security", "Secret 扫描位置", "Secret scanning alert location"),
    ("secret_scanning_scan", "security", "Secret 扫描任务", "Secret scanning scan"),
    ("project", "engagement", "经典项目", "Classic project"),
    ("project_card", "engagement", "经典项目卡片", "Classic project card"),
    ("project_column", "engagement", "经典项目列", "Classic project column"),
    ("star", "engagement", "Star", "Star"),
    ("watch", "engagement", "关注仓库", "Watch"),
)


# 该 action 快照来自 GitHub 官方 github/docs 的 FPT webhook 数据。
_EVENT_ACTIONS = {
    "branch_protection_configuration": ("disabled", "enabled"),
    "branch_protection_rule": ("created", "deleted", "edited"),
    "check_run": ("completed", "created", "requested_action", "rerequested"),
    "check_suite": ("completed", "requested", "rerequested"),
    "code_scanning_alert": (
        "appeared_in_branch", "closed_by_user", "created", "fixed", "reopened",
        "reopened_by_user", "updated_assignment",
    ),
    "commit_comment": ("created",),
    "custom_property_values": ("updated",),
    "dependabot_alert": (
        "assignees_changed", "auto_dismissed", "auto_reopened", "created",
        "dismissed", "fixed", "reintroduced", "reopened",
    ),
    "deploy_key": ("created", "deleted"),
    "deployment": ("created",),
    "deployment_status": ("created",),
    "discussion": (
        "answered", "category_changed", "closed", "created", "deleted", "edited",
        "labeled", "locked", "pinned", "reopened", "transferred", "unanswered",
        "unlabeled", "unlocked", "unpinned",
    ),
    "discussion_comment": ("created", "deleted", "edited"),
    "issue_comment": ("created", "deleted", "edited", "pinned", "unpinned"),
    "issue_dependencies": (
        "blocked_by_added", "blocked_by_removed", "blocking_added", "blocking_removed",
    ),
    "issues": (
        "assigned", "closed", "deleted", "demilestoned", "edited", "field_added",
        "field_removed", "labeled", "locked", "milestoned", "opened", "pinned",
        "reopened", "transferred", "typed", "unassigned", "unlabeled", "unlocked",
        "unpinned", "untyped",
    ),
    "label": ("created", "deleted", "edited"),
    "member": ("added", "edited", "removed"),
    "meta": ("deleted",),
    "milestone": ("closed", "created", "deleted", "edited", "opened"),
    "package": ("published", "updated"),
    "project": ("closed", "created", "deleted", "edited", "reopened"),
    "project_card": ("converted", "created", "deleted", "edited", "moved"),
    "project_column": ("created", "deleted", "edited", "moved"),
    "pull_request": (
        "assigned", "auto_merge_disabled", "auto_merge_enabled", "closed",
        "converted_to_draft", "demilestoned", "dequeued", "edited", "enqueued",
        "labeled", "locked", "milestoned", "opened", "ready_for_review", "reopened",
        "review_request_removed", "review_requested", "stacked", "synchronize",
        "unassigned", "unlabeled", "unlocked",
    ),
    "pull_request_review": ("dismissed", "edited", "submitted"),
    "pull_request_review_comment": ("created", "deleted", "edited"),
    "pull_request_review_thread": ("resolved", "unresolved"),
    "registry_package": ("published", "updated"),
    "release": ("created", "deleted", "edited", "prereleased", "published", "released", "unpublished"),
    "repository": (
        "archived", "created", "deleted", "edited", "privatized", "publicized",
        "renamed", "transferred", "unarchived",
    ),
    "repository_advisory": ("published", "reported"),
    "repository_ruleset": ("created", "deleted", "edited"),
    "repository_vulnerability_alert": ("create", "dismiss", "reopen", "resolve"),
    "secret_scanning_alert": (
        "assigned", "created", "metadata_created", "metadata_removed", "publicly_leaked",
        "reopened", "resolved", "unassigned", "validated",
    ),
    "secret_scanning_alert_location": ("created",),
    "secret_scanning_scan": ("completed",),
    "star": ("created", "deleted"),
    "sub_issues": ("parent_issue_added", "parent_issue_removed", "sub_issue_added", "sub_issue_removed"),
    "watch": ("started",),
    "workflow_job": ("completed", "in_progress", "queued", "waiting"),
    "workflow_run": ("completed", "in_progress", "requested"),
}


_LEGACY_EVENTS = {
    "project", "project_card", "project_column", "registry_package",
    "repository_vulnerability_alert",
}
_HIGH_VOLUME_EVENTS = {
    "check_run", "check_suite", "issue_comment", "pull_request",
    "push", "status", "workflow_job", "workflow_run",
}
_EVENT_BY_NAME = {
    row[0]: {
        "name": row[0],
        "category": row[1],
        "label": {"zh": row[2], "en": row[3]},
        "actions": list(_EVENT_ACTIONS.get(row[0], ())),
        "legacy": row[0] in _LEGACY_EVENTS,
        "high_volume": row[0] in _HIGH_VOLUME_EVENTS,
    }
    for row in _EVENT_ROWS
}


def get_github_event_categories() -> List[dict]:
    return [
        {"id": row[0], "label": {"zh": row[1], "en": row[2]}}
        for row in _CATEGORY_ROWS
    ]


def get_github_event_catalog() -> List[dict]:
    return [
        {
            "name": item["name"],
            "category": item["category"],
            "label": dict(item["label"]),
            "actions": list(item["actions"]),
            "legacy": bool(item["legacy"]),
            "high_volume": bool(item["high_volume"]),
        }
        for item in _EVENT_BY_NAME.values()
    ]


def is_known_github_event(event: str) -> bool:
    return str(event or "").strip().lower() in _EVENT_BY_NAME


def normalize_github_event_mode(value) -> str:
    return GITHUB_EVENT_MODE_ALL if str(value or "").strip().lower() == GITHUB_EVENT_MODE_ALL else GITHUB_EVENT_MODE_SELECTED


def normalize_github_events(value) -> List[str]:
    values = _string_values(value)
    result = []
    for item in values:
        event = item.lower()
        if event in _EVENT_BY_NAME and event not in result:
            result.append(event)
    return result


def normalize_github_event_actions(value) -> Dict[str, List[str]]:
    if not isinstance(value, dict):
        return {}
    result = {}
    for raw_event, raw_actions in value.items():
        event = str(raw_event or "").strip().lower()
        allowed = set(_EVENT_ACTIONS.get(event, ()))
        if event not in _EVENT_BY_NAME or not allowed:
            continue
        actions = []
        for raw_action in _string_values(raw_actions):
            action = raw_action.lower()
            if action in allowed and action not in actions:
                actions.append(action)
        if actions:
            result[event] = actions
    return result


def validate_github_event_config(mode, events, event_actions) -> Tuple[str, List[str], Dict[str, List[str]]]:
    raw_mode = str(mode or "").strip().lower()
    if raw_mode not in (GITHUB_EVENT_MODE_SELECTED, GITHUB_EVENT_MODE_ALL):
        raise ValueError("GitHub webhook event mode must be selected or all")

    if not isinstance(events, (list, tuple, set)):
        raise ValueError("GitHub webhook events must be an array")
    raw_events = _string_values(events)
    normalized_events = normalize_github_events(raw_events)
    invalid_events = sorted({item.lower() for item in raw_events if item.lower() not in _EVENT_BY_NAME})
    if invalid_events:
        raise ValueError("Unsupported GitHub webhook events: {}".format(", ".join(invalid_events)))
    if raw_mode == GITHUB_EVENT_MODE_SELECTED and not normalized_events:
        raise ValueError("At least one GitHub webhook event must be selected")

    if not isinstance(event_actions, dict):
        raise ValueError("GitHub webhook event actions must be an object")
    normalized_actions = normalize_github_event_actions(event_actions)
    for raw_event, raw_actions in event_actions.items():
        event = str(raw_event or "").strip().lower()
        if event not in _EVENT_BY_NAME:
            raise ValueError("Unsupported GitHub webhook event action key: {}".format(event))
        if not isinstance(raw_actions, (list, tuple, set)):
            raise ValueError("GitHub webhook actions for {} must be an array".format(event))
        allowed = set(_EVENT_ACTIONS.get(event, ()))
        values = [item.lower() for item in _string_values(raw_actions)]
        invalid_actions = sorted({item for item in values if item not in allowed})
        if invalid_actions:
            raise ValueError(
                "Unsupported actions for {}: {}".format(event, ", ".join(invalid_actions))
            )
    return raw_mode, normalized_events, normalized_actions


def github_event_is_enabled(config: dict, event: str, action: str = "") -> Tuple[bool, str]:
    event_name = str(event or "").strip().lower()
    action_name = str(action or "").strip().lower()
    mode = normalize_github_event_mode(config.get("github_commit_notify_event_mode", GITHUB_EVENT_MODE_SELECTED))
    if mode == GITHUB_EVENT_MODE_SELECTED:
        selected = normalize_github_events(config.get("github_commit_notify_events", ["push"]))
        if event_name not in selected:
            return False, "event_not_selected"

    filters = normalize_github_event_actions(config.get("github_commit_notify_event_actions", {}))
    allowed_actions = filters.get(event_name, [])
    if allowed_actions and action_name not in allowed_actions:
        return False, "action_not_selected"
    return True, ""


def github_event_display_name(event: str, language: str = "zh") -> str:
    event_name = str(event or "").strip().lower()
    item = _EVENT_BY_NAME.get(event_name)
    if not item:
        return event_name or "unknown"
    labels = item["label"]
    return labels.get(language) or labels.get("en") or event_name


def extract_github_event_ref(event: str, payload: dict) -> str:
    candidates = [payload.get("ref"), payload.get("branch")]
    pull_request = _dict_value(payload.get("pull_request"))
    workflow_run = _dict_value(payload.get("workflow_run"))
    workflow_job = _dict_value(payload.get("workflow_job"))
    deployment = _dict_value(payload.get("deployment"))
    candidates.extend([
        _nested_value(pull_request, "base", "ref"),
        workflow_run.get("head_branch"),
        workflow_job.get("head_branch"),
        deployment.get("ref"),
    ])
    for candidate in candidates:
        text = _clean_text(candidate, 255)
        if text:
            return text
    return ""


def format_github_event_message(
    event: str,
    payload: dict,
    repository: str,
    max_chars: int = 800,
) -> str:
    event_name = str(event or "").strip().lower()
    action = _clean_text(payload.get("action"), 80)
    actor = _github_actor(payload)
    label = github_event_display_name(event_name, "zh")
    lines = ["[GitHub {}] {}".format(label, _clean_text(repository, 200))]
    if action:
        lines.append("动作：{}".format(action))
    lines.append("操作者：{}".format(actor))

    subject = _github_event_subject(event_name, payload)
    if subject:
        lines.append("内容：{}".format(subject))
    state = _github_event_state(event_name, payload)
    if state:
        lines.append("状态：{}".format(state))
    url = _github_event_url(event_name, payload)
    if url:
        lines.append("查看详情：{}".format(url))
    return _fit_message(lines, max_chars)


def _github_actor(payload: dict) -> str:
    sender = _dict_value(payload.get("sender"))
    login = _clean_text(sender.get("login"), 80) or _clean_text(sender.get("name"), 80)
    if not login or login.lower() == "ghost":
        return "系统"
    return login


def _github_event_subject(event: str, payload: dict) -> str:
    if event in {"pull_request", "pull_request_review", "pull_request_review_comment", "pull_request_review_thread"}:
        return _numbered_title(_dict_value(payload.get("pull_request")), "PR")
    if event in {"issues", "issue_comment", "issue_dependencies", "sub_issues"}:
        return _numbered_title(_dict_value(payload.get("issue")), "Issue")
    if event in {"discussion", "discussion_comment"}:
        return _numbered_title(_dict_value(payload.get("discussion")), "Discussion")
    if event in {"create", "delete"}:
        ref_type = _clean_text(payload.get("ref_type"), 40)
        ref = _clean_text(payload.get("ref"), 160)
        return "{} {}".format(ref_type, ref).strip()
    if event == "commit_comment":
        comment = _dict_value(payload.get("comment"))
        commit_id = _clean_text(comment.get("commit_id"), 40)[:7]
        return "commit {}".format(commit_id) if commit_id else ""
    if event == "fork":
        return _clean_text(_dict_value(payload.get("forkee")).get("full_name"), 240)
    if event == "gollum":
        pages = payload.get("pages") if isinstance(payload.get("pages"), list) else []
        page = _dict_value(pages[0]) if pages else {}
        return _clean_text(page.get("page_name") or page.get("title"), 240)
    if event in {"workflow_run", "workflow_job", "check_run", "check_suite"}:
        obj = _event_object(event, payload)
        name = _clean_text(obj.get("display_title") or obj.get("name"), 220)
        number = _clean_text(obj.get("run_number") or obj.get("id"), 40)
        return "#{} {}".format(number, name).strip() if number else name
    if event in {"deployment", "deployment_status"}:
        deployment = _dict_value(payload.get("deployment"))
        return _clean_text(deployment.get("environment") or deployment.get("ref"), 220)
    if event == "release":
        release = _dict_value(payload.get("release"))
        return _clean_text(release.get("name") or release.get("tag_name"), 220)
    if event in {"package", "registry_package"}:
        obj = _event_object(event, payload)
        return _clean_text(obj.get("name") or _nested_value(obj, "package_version", "name"), 220)
    if event in {"code_scanning_alert", "dependabot_alert", "secret_scanning_alert", "secret_scanning_alert_location"}:
        alert = _dict_value(payload.get("alert"))
        number = _clean_text(alert.get("number"), 40)
        return "告警 #{}".format(number) if number else "安全告警"
    if event == "repository_advisory":
        advisory = _dict_value(payload.get("repository_advisory"))
        return _clean_text(advisory.get("ghsa_id"), 80) or "仓库安全公告"
    if event == "repository_vulnerability_alert":
        alert = _dict_value(payload.get("alert"))
        return _clean_text(alert.get("id"), 80)
    if event == "secret_scanning_scan":
        return _clean_text(payload.get("type") or payload.get("source"), 120)
    if event == "branch_protection_rule":
        return _clean_text(_dict_value(payload.get("rule")).get("name"), 220)
    if event == "repository_ruleset":
        return _clean_text(_dict_value(payload.get("repository_ruleset")).get("name"), 220)
    if event == "deploy_key":
        return _clean_text(_dict_value(payload.get("key")).get("title"), 220)
    if event == "member":
        return _clean_text(_dict_value(payload.get("member")).get("login"), 120)
    if event == "team_add":
        return _clean_text(_dict_value(payload.get("team")).get("name"), 220)
    if event in {"label", "milestone", "project", "project_card", "project_column"}:
        obj = _event_object(event, payload)
        return _clean_text(obj.get("name") or obj.get("title") or obj.get("note"), 220)
    if event == "status":
        sha = _clean_text(payload.get("sha"), 40)[:7]
        context = _clean_text(payload.get("context"), 160)
        return "{} {}".format(sha, context).strip()
    return ""


def _github_event_state(event: str, payload: dict) -> str:
    objects = []
    if event == "deployment_status":
        objects.append(_dict_value(payload.get("deployment_status")))
    objects.append(_event_object(event, payload))
    objects.append(payload)
    for obj in objects:
        for key in ("conclusion", "state", "status", "result"):
            value = _clean_text(obj.get(key), 100)
            if value:
                return value
    return ""


def _github_event_url(event: str, payload: dict) -> str:
    candidates = []
    if event in {"pull_request_review", "pull_request_review_comment", "pull_request_review_thread"}:
        candidates.append(_dict_value(payload.get("pull_request")))
    if event in {"issue_comment", "issue_dependencies", "sub_issues"}:
        candidates.append(_dict_value(payload.get("issue")))
    if event == "discussion_comment":
        candidates.append(_dict_value(payload.get("discussion")))
    candidates.append(_event_object(event, payload))
    candidates.append(_dict_value(payload.get("repository")))
    for obj in candidates:
        for key in ("html_url", "details_url"):
            url = _clean_github_url(obj.get(key))
            if url:
                return url
    return ""


def _event_object(event: str, payload: dict) -> dict:
    object_keys = {
        "branch_protection_rule": "rule",
        "check_run": "check_run",
        "check_suite": "check_suite",
        "code_scanning_alert": "alert",
        "commit_comment": "comment",
        "dependabot_alert": "alert",
        "deployment": "deployment",
        "deployment_status": "deployment_status",
        "discussion": "discussion",
        "discussion_comment": "comment",
        "issue_comment": "issue",
        "issue_dependencies": "issue",
        "issues": "issue",
        "label": "label",
        "member": "member",
        "milestone": "milestone",
        "package": "package",
        "page_build": "build",
        "project": "project",
        "project_card": "project_card",
        "project_column": "project_column",
        "pull_request": "pull_request",
        "pull_request_review": "review",
        "pull_request_review_comment": "comment",
        "pull_request_review_thread": "thread",
        "registry_package": "registry_package",
        "release": "release",
        "repository": "repository",
        "repository_advisory": "repository_advisory",
        "repository_ruleset": "repository_ruleset",
        "repository_vulnerability_alert": "alert",
        "secret_scanning_alert": "alert",
        "secret_scanning_alert_location": "alert",
        "status": "status",
        "sub_issues": "issue",
        "team_add": "team",
        "workflow_job": "workflow_job",
        "workflow_run": "workflow_run",
    }
    return _dict_value(payload.get(object_keys.get(event, "")))


def _numbered_title(obj: dict, prefix: str) -> str:
    number = _clean_text(obj.get("number"), 40)
    title = _clean_text(obj.get("title"), 220)
    if number and title:
        return "{} #{} {}".format(prefix, number, title)
    if number:
        return "{} #{}".format(prefix, number)
    return title


def _clean_github_url(value) -> str:
    url = _clean_text(value, 500)
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError:
        return ""
    if (
        parsed.scheme != "https"
        or host not in ("github.com", "www.github.com")
        or parsed.username
        or parsed.password
        or port not in (None, 443)
    ):
        return ""
    return urlunparse(("https", host, parsed.path or "/", "", "", ""))


def _fit_message(lines: Iterable[str], max_chars: int) -> str:
    try:
        limit = max(200, min(int(max_chars or 800), 4000))
    except (TypeError, ValueError):
        limit = 800
    message = "\n".join(line for line in lines if line).strip()
    return message[:limit].rstrip()


def _clean_text(value, max_length: int) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set, bytes, bytearray)):
        return ""
    text = str(value or "")
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max(int(max_length), 1)]


def _dict_value(value) -> dict:
    return value if isinstance(value, dict) else {}


def _nested_value(value: dict, *keys):
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _string_values(value) -> List[str]:
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = []
    return [str(item or "").strip() for item in values if str(item or "").strip()]
