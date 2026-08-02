# encoding:utf-8

"""深度思考配置的统一语义与 OpenAI-compatible 协议转换。"""

VALID_REASONING_EFFORTS = ("low", "medium", "high", "max")
VALID_THINKING_PROTOCOLS = (
    "none",
    "thinking_object",
    "deepseek",
    "enable_thinking",
    "openai_reasoning",
)


def normalize_reasoning_effort(value, default="low"):
    effort = str(value or "").strip().lower()
    if effort in VALID_REASONING_EFFORTS:
        return effort
    fallback = str(default or "low").strip().lower()
    return fallback if fallback in VALID_REASONING_EFFORTS else "low"


def normalize_thinking_protocol(value, default="none"):
    protocol = str(value or "").strip().lower()
    if protocol in VALID_THINKING_PROTOCOLS:
        return protocol
    fallback = str(default or "none").strip().lower()
    return fallback if fallback in VALID_THINKING_PROTOCOLS else "none"


def thinking_is_enabled(thinking):
    return isinstance(thinking, dict) and thinking.get("type") == "enabled"


def map_reasoning_effort(value, mapping=None):
    effort = normalize_reasoning_effort(value)
    return (mapping or {}).get(effort, effort)


def openai_thinking_protocol_for_model(model_name):
    """只对明确的 OpenAI GPT-5 推理模型发送 reasoning_effort。"""
    model = str(model_name or "").strip().lower()
    return "openai_reasoning" if model.startswith("gpt-5") else "none"


def apply_openai_compatible_thinking(request_params, protocol, thinking, effort):
    """按显式协议把统一思考意图写入 OpenAI-compatible 请求体。"""
    protocol = normalize_thinking_protocol(protocol)
    enabled = thinking_is_enabled(thinking)
    effort = normalize_reasoning_effort(effort)

    if protocol == "none":
        return
    if protocol == "thinking_object":
        request_params["thinking"] = {"type": "enabled" if enabled else "disabled"}
        return
    if protocol == "deepseek":
        request_params["thinking"] = {"type": "enabled" if enabled else "disabled"}
        if enabled:
            request_params["reasoning_effort"] = map_reasoning_effort(
                effort,
                {"low": "high", "medium": "high", "high": "high", "max": "max"},
            )
        return
    if protocol == "enable_thinking":
        request_params["enable_thinking"] = enabled
        return
    if protocol == "openai_reasoning":
        request_params["reasoning_effort"] = effort if enabled else "none"
