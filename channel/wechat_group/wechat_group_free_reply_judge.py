"""LLM JSON decision helper for WeChat group free replies."""

import json

from bridge.bridge import Bridge
from bridge.context import Context, ContextType


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
    return """你是 LightAgent 微信群自由回复的轻量判定器。

只判断是否适合接话，不要生成最终回复。
只返回 JSON，不要返回 Markdown。
不要调用工具，不要写入记忆，不要发送消息。
如果是明确求助、明显玩梗/吐槽/笑点、明确表情包/梗图/斗图请求，且不会打断群聊，可以返回 should_reply=true。
如果明显是 A 对 B 说话、请求群友做事、催某个群友回应，或是两个人私聊语境，默认返回 should_reply=false；除非文本明确在请求机器人能力。
如果只是纯表情或纯笑声、敏感、隐私、危险、两人私聊、刷屏场景，返回 should_reply=false。

返回格式：
{{"should_reply": true, "confidence": 0.82, "reason": "一句话原因", "tone": "natural"}}

群名：{room_name}
发送者：{sender_name}
文本：{text}
本地得分：{score}
本地阈值：{threshold}
加分原因：{reasons}
抑制原因：{suppressions}
""".format(
        room_name=task.get("room_name", ""),
        sender_name=task.get("sender_name", ""),
        text=task.get("text", ""),
        score=local_decision.get("score", 0),
        threshold=local_decision.get("threshold", 0),
        reasons=", ".join(local_decision.get("reasons") or []),
        suppressions=", ".join(local_decision.get("suppressions") or []),
    )


class WechatGroupFreeReplyJudge:
    def __init__(self, bridge=None):
        self.bridge = bridge or Bridge()

    def judge(self, task, config) -> dict:
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
            context = Context(
                ContextType.TEXT,
                prompt,
                {
                    "session_id": "wechat_group_free_reply:{}".format(task.get("room_id", "")),
                    "receiver": task.get("room_id", ""),
                    "wechat_group_free_reply_judge": True,
                    "free_reply_judge_timeout_seconds": config.get("llm_judge_timeout_seconds", 8),
                },
            )
            reply = self.bridge.fetch_reply_content(prompt, context)
            text = getattr(reply, "content", reply)
            return parse_free_reply_judge_reply(text, config.get("llm_judge_min_confidence", 0.6))
        except Exception as e:
            return _empty_decision("exception", str(e))
