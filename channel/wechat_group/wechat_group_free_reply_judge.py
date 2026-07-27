"""LLM JSON decision helper for WeChat group free replies."""

import json

from bridge.bridge import Bridge
from channel.wechat_group.wechat_group_free_reply_context import build_safe_free_reply_timeline
from channel.wechat_group.wechat_group_context import sanitize_wechat_group_prompt_text


def _empty_decision(error="", reason="") -> dict:
    return {
        "approved": False,
        "should_reply": False,
        "confidence": 0.0,
        "reason": reason,
        "tone": "",
        "error": error,
    }


def parse_free_reply_judge_reply(text, min_confidence) -> dict:
    try:
        data = json.loads(str(text or "").strip())
    except Exception:
        return _empty_decision("invalid_json")

    should_reply = bool(data.get("should_reply"))
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    reason = str(data.get("reason") or "")
    tone = str(data.get("tone") or "")

    if should_reply and confidence < float(min_confidence):
        return {
            "approved": False,
            "should_reply": should_reply,
            "confidence": confidence,
            "reason": reason,
            "tone": tone,
            "error": "low_confidence",
        }
    return {
        "approved": should_reply and confidence >= float(min_confidence),
        "should_reply": should_reply,
        "confidence": confidence,
        "reason": reason,
        "tone": tone,
        "error": "" if should_reply else "rejected",
    }


def build_free_reply_judge_prompt(task) -> str:
    local_decision = task.get("local_decision") or {}
    msg = task.get("msg")
    current = {
        "message_id": getattr(msg, "msg_id", "") if msg is not None else "",
        "created_at": getattr(msg, "create_time", None) if msg is not None else None,
        "sender_id": task.get("sender_id") or "",
        "runtime_sender_id": task.get("runtime_sender_id") or "",
        "bot_sender_id": getattr(msg, "stable_self_id", "") if msg is not None else "",
        "runtime_bot_sender_id": getattr(msg, "to_user_id", "") if msg is not None else "",
        "text": task.get("text") or "",
    }
    recent = build_safe_free_reply_timeline(
        current,
        task.get("recent_messages") or [],
        limit=5,
    )
    current_text = recent[-1].get("text", "") if recent else ""
    return """你是 LightAgent 微信群自由回复的轻量判定器。

只判断是否适合接话，不要生成最终回复。
只返回 JSON，不要返回 Markdown。
不要调用工具，不要写入记忆，不要发送消息。
如果是明确求助、明显玩梗/吐槽/笑点、明确表情包/梗图/斗图请求，且不会打断群聊，可以返回 should_reply=true。
如果明显是 A 对 B 说话、请求群友做事、催某个群友回应，或是两个人私聊语境，默认返回 should_reply=false；除非文本明确在请求机器人能力。
如果当前短问句自然承接上一名群友，必须返回 should_reply=false；“有用吗”本身不能证明在问机器人。
只有明确指向机器人或明确面向全群的开放问题，才考虑返回 should_reply=true。
如果只是纯表情或纯笑声、敏感、隐私、危险、两人私聊、刷屏场景，返回 should_reply=false。

返回格式：
{{"should_reply": true, "confidence": 0.82, "reason": "一句话原因", "tone": "natural"}}

群名：{room_name}
文本：{text}
安全近场上下文：{recent_context}
确定性收件人特征：{addressee}
本地得分：{score}
本地阈值：{threshold}
加分原因：{reasons}
抑制原因：{suppressions}
""".format(
        room_name=sanitize_wechat_group_prompt_text(task.get("room_name", ""), 120),
        text=current_text,
        recent_context=json.dumps(recent, ensure_ascii=False, separators=(",", ":")),
        addressee=json.dumps(local_decision.get("addressee") or {}, ensure_ascii=False, separators=(",", ":")),
        score=local_decision.get("score", 0),
        threshold=local_decision.get("threshold", 0),
        reasons=", ".join(local_decision.get("reasons") or []),
        suppressions=", ".join(local_decision.get("suppressions") or []),
    )


class WechatGroupFreeReplyJudge:
    def __init__(self, bridge=None, scorer=None):
        self.bridge = bridge or Bridge()
        self.scorer = scorer

    def judge(self, task, config) -> dict:
        if config.get("scorer_enabled") and self.scorer is not None:
            local_decision = task.get("local_decision") or {}
            if "force_keyword_match" in (local_decision.get("reasons") or []):
                return {
                    "approved": True,
                    "should_reply": True,
                    "reply_mode": "direct",
                    "confidence": 1.0,
                    "reason": "force_keyword_match",
                    "tone": "natural",
                    "error": "",
                    "source": "local",
                }
            try:
                scorer_decision = self.scorer.score(task, config)
            except Exception as e:
                scorer_decision = {
                    "approved": False,
                    "error": "exception",
                    "reason": type(e).__name__,
                    "fallback_to_rules": bool(config.get("scorer_fallback_to_rules", True)),
                    "source": "scorer",
                }
            if not scorer_decision.get("fallback_to_rules"):
                return scorer_decision
            if not config.get("llm_judge_enabled", True):
                approved = bool(local_decision.get("local_rule_triggered", False))
                return {
                    "approved": approved,
                    "should_reply": approved,
                    "confidence": 1.0 if approved else 0.0,
                    "reason": "local_rules_fallback",
                    "tone": "natural" if approved else "",
                    "error": "" if approved else str(scorer_decision.get("error") or "rejected"),
                    "source": "local_fallback",
                }
        if not config.get("llm_judge_enabled", True):
            return {
                "approved": True,
                "should_reply": True,
                "confidence": 1.0,
                "reason": "llm_judge_disabled",
                "tone": "natural",
                "error": "",
            }
        try:
            prompt = build_free_reply_judge_prompt(task)
            result = self.bridge.complete_text(
                [{"role": "user", "content": prompt}],
                purpose="wechat_group_free_reply_judge",
            )
            if not result.get("success"):
                return _empty_decision("model_error", result.get("content", ""))
            text = result.get("content", "")
            return parse_free_reply_judge_reply(text, config.get("llm_judge_min_confidence", 0.6))
        except Exception as e:
            return _empty_decision("exception", str(e))
