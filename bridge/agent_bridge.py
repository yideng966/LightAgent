"""
Agent Bridge - Integrates Agent system with existing LightAgent bridge
"""

import os
import re
import html
import copy
import json
import threading
import time
import types
from collections import OrderedDict
from html.parser import HTMLParser
from typing import Optional, List
from uuid import uuid4

from agent.protocol import (
    AGENT_FINISH_TOOL_NAME,
    Agent,
    AgentCancelledError,
    LLMModel,
    LLMRequest,
    LLMRequestSourceSnapshot,
    get_cancel_registry,
)
from bridge.agent_event_handler import AgentEventHandler
from bridge.agent_initializer import AgentInitializer
from bridge.bridge import Bridge
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType
from common import const
from common.log import logger
from common.utils import expand_path
from config import conf, load_config
from models.openai_compatible_bot import OpenAICompatibleBot


_WECHAT_GROUP_FINAL_ONLY_PROMPT = """
这是即时通讯群聊请求。不要输出、解释或复述内部分析、思考步骤或回答计划，只输出面向用户的最终答复。
需要调用工具时只返回原生 tool_calls，不要先输出过程说明，也不要把 tool_calls 写成文本标签。
可以直接回答时输出纯文本最终答复，不要添加 XML、JSON、send、message、analysis 或 thinking 标签。
工具执行后，如果工具列表中出现 `{finish_tool}`：信息充分时必须调用它提交完整、自包含的最终正文；信息不足时继续调用所需工具，不要输出“让我继续看看”等进度说明。
""".strip().format(finish_tool=AGENT_FINISH_TOOL_NAME)


class _WechatSendAttributeParser(HTMLParser):
    """只解析兼容 `<send message="...">` 所需的确定性属性。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.start_count = 0
        self.end_count = 0
        self.message = None

    def handle_starttag(self, tag, attrs):
        if str(tag or "").lower() != "send":
            return
        self.start_count += 1
        if self.start_count == 1:
            values = {str(key or "").lower(): value for key, value in attrs}
            self.message = values.get("message")

    def handle_startendtag(self, tag, attrs):
        if str(tag or "").lower() != "send":
            return
        self.handle_starttag(tag, attrs)
        self.end_count += 1

    def handle_endtag(self, tag):
        if str(tag or "").lower() == "send":
            self.end_count += 1


def add_openai_compatible_support(bot_instance):
    """
    Dynamically add OpenAI-compatible tool calling support to a bot instance.
    
    This allows any bot to gain tool calling capability without modifying its code,
    as long as it uses OpenAI-compatible API format.
    
    Note: Some bots like ZHIPUAIBot have native tool calling support and don't need enhancement.
    """
    if hasattr(bot_instance, 'call_with_tools'):
        # Bot already has tool calling support (e.g., ZHIPUAIBot)
        logger.debug(f"[AgentBridge] {type(bot_instance).__name__} already has native tool calling support")
        return bot_instance

    # Create a temporary mixin class that combines the bot with OpenAI compatibility
    class EnhancedBot(bot_instance.__class__, OpenAICompatibleBot):
        """Dynamically enhanced bot with OpenAI-compatible tool calling"""

        def get_api_config(self):
            """
            Infer API config from common configuration patterns.
            Most OpenAI-compatible bots use similar configuration.
            """
            from config import conf

            return {
                'api_key': conf().get("open_ai_api_key"),
                'api_base': conf().get("open_ai_api_base"),
                'model': conf().get("model", "gpt-3.5-turbo"),
                'default_temperature': conf().get("temperature", 0.9),
                'default_top_p': conf().get("top_p", 1.0),
                'default_frequency_penalty': conf().get("frequency_penalty", 0.0),
                'default_presence_penalty': conf().get("presence_penalty", 0.0),
            }

    # Change the bot's class to the enhanced version
    bot_instance.__class__ = EnhancedBot
    logger.info(
        f"[AgentBridge] Enhanced {bot_instance.__class__.__bases__[0].__name__} with OpenAI-compatible tool calling")

    return bot_instance


class _ModelFailoverState:
    """Thread-safe runtime circuit state shared by Agent model instances."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._routes = {}

    def route_mode(self, route_key):
        with self._lock:
            state = self._routes.get(route_key)
            if not state or not state.get("open_until"):
                return self.CLOSED

            now = self._clock()
            if now < state["open_until"] or state.get("probe_in_flight"):
                return self.OPEN

            state["probe_in_flight"] = True
            return self.HALF_OPEN

    def record_transient_failure(self, route_key, threshold, cooldown_seconds):
        with self._lock:
            state = self._routes.setdefault(route_key, {
                "failures": 0,
                "open_until": 0,
                "probe_in_flight": False,
            })
            state["failures"] += 1
            should_open = state.get("probe_in_flight") or state["failures"] >= threshold
            if should_open:
                state["open_until"] = self._clock() + cooldown_seconds
                state["probe_in_flight"] = False
            return state["failures"], bool(should_open)

    def record_healthy(self, route_key):
        with self._lock:
            state = self._routes.pop(route_key, None)
            return bool(state and (
                state.get("failures")
                or state.get("open_until")
                or state.get("probe_in_flight")
            ))

    def record_unusable_probe(self, route_key, cooldown_seconds):
        """释放半开探测并重新冷却，不改变临时故障计数。"""
        with self._lock:
            state = self._routes.get(route_key)
            if not state or not state.get("probe_in_flight"):
                return False
            state["open_until"] = self._clock() + cooldown_seconds
            state["probe_in_flight"] = False
            return True


_MODEL_FAILOVER_STATE_INIT_LOCK = threading.Lock()


class _CanonicalTextSession:
    """Provider-neutral conversation state used by legacy chat mode."""

    def __init__(self, session_id, system_prompt=""):
        self.session_id = session_id
        self.system_prompt = system_prompt or ""
        self.messages = []
        if self.system_prompt:
            self.messages.append({"role": "system", "content": self.system_prompt})

    def set_system_prompt(self, system_prompt):
        self.system_prompt = system_prompt or ""
        self.messages = []
        if self.system_prompt:
            self.messages.append({"role": "system", "content": self.system_prompt})


class _CanonicalTextSessionStore:
    """Thread-safe canonical history; failed candidates never mutate it."""

    def __init__(self):
        self._sessions = {}
        self._locks = {}
        self._lock = threading.RLock()

    def session_lock(self, session_id):
        key = session_id or "__stateless__"
        with self._lock:
            return self._locks.setdefault(key, threading.RLock())

    def build_session(self, session_id, system_prompt=None):
        with self._lock:
            if session_id not in self._sessions:
                prompt = conf().get("character_desc", "") if system_prompt is None else system_prompt
                self._sessions[session_id] = _CanonicalTextSession(session_id, prompt)
            elif system_prompt is not None and self._sessions[session_id].system_prompt != system_prompt:
                self._sessions[session_id] = _CanonicalTextSession(session_id, system_prompt)
            return self._sessions[session_id]

    def snapshot_with_query(self, session_id, query):
        session = self.build_session(session_id)
        messages = [dict(item) for item in session.messages]
        messages.append({"role": "user", "content": query})
        return messages

    def commit_exchange(self, session_id, query, reply):
        session = self.build_session(session_id)
        session.messages.extend([
            {"role": "user", "content": query},
            {"role": "assistant", "content": reply},
        ])
        self._trim(session)

    @staticmethod
    def _trim(session):
        try:
            limit = max(1, int(conf().get("conversation_max_tokens", 1000)))
        except (TypeError, ValueError):
            limit = 1000
        # Provider-independent conservative estimate. Keep the system prompt and
        # remove complete user/assistant turns so history remains well formed.
        def size():
            return sum(len(str(item.get("content", ""))) for item in session.messages)

        start = 1 if session.messages and session.messages[0].get("role") == "system" else 0
        while size() > limit and len(session.messages) - start > 2:
            del session.messages[start:start + 2]

    def clear_session(self, session_id):
        with self._lock:
            self._sessions.pop(session_id, None)
            self._locks.pop(session_id or "__stateless__", None)

    def clear_all_session(self):
        with self._lock:
            self._sessions.clear()
            self._locks.clear()

    # Compatibility for plugins that only need to append/read canonical history.
    def session_query(self, query, session_id):
        session = self.build_session(session_id)
        session.messages.append({"role": "user", "content": query})
        self._trim(session)
        return session

    def session_reply(self, reply, session_id, total_tokens=None):
        session = self.build_session(session_id)
        session.messages.append({"role": "assistant", "content": reply})
        self._trim(session)
        return session


class TextModelRouter(LLMModel):
    """
    LLM Model adapter that uses LightAgent's existing bot infrastructure
    """

    _MODEL_BOT_TYPE_MAP = {
        "wenxin": const.BAIDU, "wenxin-4": const.BAIDU,
        "xunfei": const.XUNFEI, const.QWEN: const.QWEN_DASHSCOPE,
        const.QIANFAN: const.QIANFAN,
        const.MODELSCOPE: const.MODELSCOPE,
    }
    _MODEL_PREFIX_MAP = [
        ("qwen", const.QWEN_DASHSCOPE), ("qwq", const.QWEN_DASHSCOPE), ("qvq", const.QWEN_DASHSCOPE),
        ("gemini", const.GEMINI), ("glm", const.ZHIPU_AI), ("claude", const.CLAUDEAPI),
        ("moonshot", const.MOONSHOT), ("kimi", const.MOONSHOT),
        ("doubao", const.DOUBAO), ("deepseek", const.DEEPSEEK),
        ("ernie", const.QIANFAN),
        ("mimo-", const.MIMO),
    ]
    _TRANSIENT_MODEL_STATUS_CODES = {408, 429, 500, 502, 503, 504}
    _TRANSIENT_MODEL_ERROR_KEYWORDS = (
        "rate limit",
        "freeusagelimiterror",
        "too many requests",
        "insufficient_quota",
        "quota exceeded",
        "token limit",
        "no token",
        "timeout",
        "timed out",
        "temporarily unavailable",
        "temporary unavailable",
        "overloaded",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
    )
    _TRANSIENT_MODEL_STATUS_PATTERN = re.compile(r"(?<!\d)(?:408|429|500|502|503|504)(?!\d)")
    _NON_FALLBACK_EMPTY_FINISH_REASONS = {
        "blocked",
        "content-filter",
        "content_filter",
        "moderation",
        "prohibited",
        "safety",
    }
    _WECHAT_GROUP_MAX_BUFFERED_CHUNKS = 8192

    def __init__(self, bridge: Bridge, bot_type: str = "chat", failover_state=None):
        super().__init__(model=conf().get("model", const.GPT_41))
        self.bridge = bridge
        self.bot_type = bot_type
        self._bot = None
        self._bot_model = None
        self._candidate_bots = {}
        self._failover_state = failover_state or self._shared_failover_state(bridge)
        self.sessions = (
            bridge._text_model_sessions
            if bridge is not None and getattr(bridge, "_text_model_sessions", None) is not None
            else _CanonicalTextSessionStore()
        )
        if bridge is not None:
            bridge._text_model_sessions = self.sessions

    @staticmethod
    def _shared_failover_state(bridge):
        if bridge is None:
            return _ModelFailoverState()
        state = getattr(bridge, "_agent_model_failover_state", None)
        if state is not None:
            return state
        with _MODEL_FAILOVER_STATE_INIT_LOCK:
            state = getattr(bridge, "_agent_model_failover_state", None)
            if state is None:
                state = _ModelFailoverState()
                bridge._agent_model_failover_state = state
            return state

    @staticmethod
    def _positive_int_config(key, default):
        try:
            return max(1, int(conf().get(key, default)))
        except (TypeError, ValueError):
            return default

    def _failover_policy(self):
        return (
            self._positive_int_config("model_failover_failure_threshold", 3),
            self._positive_int_config("model_failover_cooldown_seconds", 300),
        )

    @staticmethod
    def _route_key(candidate):
        return candidate.get("bot_type") or "", candidate.get("model") or ""

    @property
    def model(self):
        return conf().get("model", const.GPT_41)

    @model.setter
    def model(self, value):
        pass

    def _resolve_bot_type(self, model_name: str) -> str:
        """Resolve bot type from model name, matching Bridge.__init__ logic."""
        if conf().get("use_linkai", False) and conf().get("linkai_api_key"):
            return const.LINKAI
        # Support custom bot type configuration
        configured_bot_type = conf().get("bot_type")
        if configured_bot_type:
            return configured_bot_type
        return self._infer_bot_type_from_model_name(model_name)

    def _infer_bot_type_from_model_name(self, model_name: str) -> str:
        """Infer bot type from model name without reading configured bot_type."""
        if not model_name or not isinstance(model_name, str):
            return const.OPENAI
        if model_name in self._MODEL_BOT_TYPE_MAP:
            return self._MODEL_BOT_TYPE_MAP[model_name]
        if model_name.lower().startswith("minimax") or model_name in ["abab6.5-chat"]:
            return const.MiniMax
        if model_name in [const.QWEN_TURBO, const.QWEN_PLUS, const.QWEN_MAX]:
            return const.QWEN_DASHSCOPE
        if model_name in [const.MOONSHOT, "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]:
            return const.MOONSHOT
        if model_name == const.MODELSCOPE:
            return const.MODELSCOPE
        lowered_model = model_name.lower()
        for prefix, btype in self._MODEL_PREFIX_MAP:
            if lowered_model.startswith(prefix):
                return btype
        return const.OPENAI

    @property
    def bot(self):
        """Lazy load the bot, re-create when model or bot_type changes"""
        from models.bot_factory import create_bot
        cur_model = self.model
        cur_bot_type = self._resolve_bot_type(cur_model)
        if self._bot is None or self._bot_model != cur_model or getattr(self, '_bot_type', None) != cur_bot_type:
            self._bot = create_bot(cur_bot_type)
            self._bot = add_openai_compatible_support(self._bot)
            self._bot_model = cur_model
            self._bot_type = cur_bot_type
        return self._bot

    def _resolve_custom_provider_model(self, bot_type: str) -> str:
        try:
            from models.custom_provider import get_custom_providers, parse_custom_bot_type
            is_custom, provider_id = parse_custom_bot_type(bot_type)
            if not is_custom or not provider_id:
                return ""
            for provider in get_custom_providers():
                if provider.get("id") == provider_id:
                    return provider.get("model") or ""
        except Exception as e:
            logger.warning(f"[AgentLLMModel] failed to resolve custom provider model: {e}")
        return ""

    def _build_model_candidates(self):
        current_model = self.model
        current_bot_type = self._resolve_bot_type(current_model)
        candidates = [{
            "bot_type": current_bot_type,
            "model": current_model,
            "source": "primary",
        }]

        raw_fallbacks = conf().get("model_fallbacks", []) or []
        if not isinstance(raw_fallbacks, list):
            raw_fallbacks = []

        for item in raw_fallbacks:
            if isinstance(item, str):
                bot_type = ""
                model_name = item.strip()
            elif isinstance(item, dict):
                bot_type = (
                    item.get("bot_type")
                    or item.get("provider")
                    or item.get("type")
                    or ""
                ).strip()
                model_name = (item.get("model") or "").strip()
            else:
                continue

            if not model_name and bot_type:
                model_name = self._resolve_custom_provider_model(bot_type)
            if not model_name:
                model_name = current_model
            if not bot_type:
                bot_type = self._infer_bot_type_from_model_name(model_name)
            if not bot_type:
                continue

            candidates.append({
                "bot_type": bot_type,
                "model": model_name,
                "source": "fallback",
            })

        deduped = []
        seen = set()
        for candidate in candidates:
            key = (candidate.get("bot_type") or "", candidate.get("model") or "")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)

        if len(deduped) > 1:
            primary = deduped[0]
            route_mode = self._failover_state.route_mode(self._route_key(primary))
            if route_mode == _ModelFailoverState.OPEN:
                logger.info(
                    "[AgentLLMModel] primary circuit open, starting with fallback: "
                    f"primary={primary.get('bot_type')}/{primary.get('model')}"
                )
                return [candidate for candidate in deduped if candidate.get("source") != "primary"]
            if route_mode == _ModelFailoverState.HALF_OPEN:
                logger.info(
                    "[AgentLLMModel] primary circuit half-open, allowing one probe: "
                    f"primary={primary.get('bot_type')}/{primary.get('model')}"
                )
        return deduped

    @staticmethod
    def _build_override_candidates(provider=None, model=None):
        if provider is None and model is None:
            return None
        provider_id = str(provider or "").strip()
        model_name = str(model or "").strip()
        if not provider_id or not model_name:
            raise ValueError("provider and model are required for a model override")
        return [{
            "bot_type": "chatGPT" if provider_id == "openai" else provider_id,
            "model": model_name,
            "source": "override",
        }]

    def _configure_custom_candidate_bot(self, bot, candidate):
        bot_type = candidate.get("bot_type") or ""
        from models.custom_provider import get_custom_providers, parse_custom_bot_type

        is_custom, provider_id = parse_custom_bot_type(bot_type)
        if not is_custom:
            return bot

        if provider_id:
            provider = next(
                (item for item in get_custom_providers() if item.get("id") == provider_id),
                None,
            )
            if provider is None:
                raise ValueError(f"custom provider not found: {provider_id}")
        else:
            provider = {
                "api_key": conf().get("custom_api_key", ""),
                "api_base": conf().get("custom_api_base") or None,
                "model": "",
            }

        api_key = provider.get("api_key", "")
        api_base = provider.get("api_base") or None
        if not api_base:
            provider_label = provider_id or "legacy"
            raise ValueError(f"custom provider api_base is required: {provider_label}")

        model_name = candidate.get("model") or provider.get("model") or self.model
        proxy = conf().get("proxy") or None

        if hasattr(bot, "_api_key"):
            bot._api_key = api_key
        if hasattr(bot, "_api_base"):
            bot._api_base = api_base
        if hasattr(bot, "args") and isinstance(bot.args, dict):
            bot.args["model"] = model_name
        if hasattr(bot, "sessions") and hasattr(bot.sessions, "model"):
            bot.sessions.model = model_name

        from models.openai.openai_http_client import OpenAIHTTPClient
        bot._http_client = OpenAIHTTPClient(
            api_key=api_key,
            api_base=api_base,
            proxy=proxy,
        )

        def get_api_config(instance):
            return {
                "api_key": api_key,
                "api_base": api_base,
                "model": model_name,
                "default_temperature": conf().get("temperature", 0.9),
                "default_top_p": conf().get("top_p", 1.0),
                "default_frequency_penalty": conf().get("frequency_penalty", 0.0),
                "default_presence_penalty": conf().get("presence_penalty", 0.0),
            }

        bot.get_api_config = types.MethodType(get_api_config, bot)
        return bot

    def _get_bot_for_candidate(self, candidate):
        if candidate.get("source") == "primary":
            return self.bot

        from models.bot_factory import create_bot
        bot_type = candidate.get("bot_type") or self._resolve_bot_type(candidate.get("model"))
        model_name = candidate.get("model") or self.model
        cache_key = (bot_type, model_name)
        if cache_key not in self._candidate_bots:
            bot = create_bot(bot_type)
            bot = add_openai_compatible_support(bot)
            bot = self._configure_custom_candidate_bot(bot, candidate)
            self._candidate_bots[cache_key] = bot
        return self._candidate_bots[cache_key]

    def _build_call_kwargs(self, request: LLMRequest, candidate, stream: bool):
        kwargs = {
            'messages': request.messages,
            'tools': getattr(request, 'tools', None),
            'stream': stream,
            'model': candidate.get("model") or self.model,
            'provider_type': candidate.get("bot_type") or "",
        }
        if request.max_tokens is not None:
            kwargs['max_tokens'] = request.max_tokens
        explicit_temperature = getattr(request, "_explicit_temperature", None)
        if explicit_temperature is not None:
            kwargs['temperature'] = explicit_temperature
        request_options = getattr(request, 'request_options', None)
        if not isinstance(request_options, dict):
            request_options = {}
        if request_options:
            kwargs['request_options'] = dict(request_options)

        channel_type = getattr(self, 'channel_type', None) or ''
        system_prompt = getattr(request, 'system', None)
        if channel_type == const.WECHAT_GROUP:
            system_prompt = "{}\n\n{}".format(
                str(system_prompt or "").strip(),
                _WECHAT_GROUP_FINAL_ONLY_PROMPT,
            ).strip()
        if system_prompt:
            kwargs['system'] = system_prompt

        if channel_type:
            kwargs['channel_type'] = channel_type
        session_id = getattr(self, 'session_id', None)
        if session_id:
            kwargs['session_id'] = session_id

        request_disables_thinking = request_options.get("reasoning_effort") == "none"
        thinking_enabled = bool(conf().get("enable_thinking", False))
        if request_disables_thinking:
            thinking_enabled = False
        kwargs['thinking'] = (
            {"type": "enabled"} if thinking_enabled
            else {"type": "disabled"}
        )
        if thinking_enabled:
            effort = conf().get("reasoning_effort", "high")
            if effort in ("high", "max"):
                kwargs['reasoning_effort'] = effort
        return kwargs

    def _get_provider_continuation_store(self):
        store = getattr(self, "_provider_continuation_store", None)
        if store is None:
            from channel.wechat_group.wechat_group_provider_continuation import (
                ProviderContinuationStore,
            )

            store = ProviderContinuationStore()
            self._provider_continuation_store = store
        return store

    @staticmethod
    def _request_has_tool_history(request: LLMRequest) -> bool:
        for message in getattr(request, "messages", None) or []:
            if not isinstance(message, dict):
                continue
            if message.get("role") == "tool" or message.get("tool_calls"):
                return True
            content = message.get("content")
            if isinstance(content, list) and any(
                isinstance(block, dict)
                and block.get("type") in {"tool_use", "tool_result"}
                for block in content
            ):
                return True
        return False

    @staticmethod
    def _payload_has_tool_call(payload) -> bool:
        if not isinstance(payload, dict):
            return False
        choices = payload.get("choices") or []
        for choice in choices if isinstance(choices, list) else []:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message") or choice.get("delta") or {}
            if isinstance(message, dict) and message.get("tool_calls"):
                return True
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list) and any(
                isinstance(block, dict) and block.get("type") == "tool_use"
                for block in content
            ):
                return True
        content = payload.get("content")
        return isinstance(content, list) and any(
            isinstance(block, dict) and block.get("type") == "tool_use"
            for block in content
        )

    def _prepare_provider_continuation(
        self,
        request: LLMRequest,
        candidate,
        bot,
        kwargs,
    ):
        if not conf().get("wechat_group_provider_continuation_enabled", False):
            return kwargs, None
        context = getattr(request, "provider_continuation_context", None)
        if not isinstance(context, dict) or self._request_has_tool_history(request):
            return kwargs, None
        action = str(context.get("thread_action") or "").strip()
        if action not in {"new_thread", "resume_thread"}:
            return kwargs, None
        capability_getter = getattr(
            bot, "get_provider_continuation_capability", None
        )
        request_builder = getattr(
            bot, "build_provider_continuation_request", None
        )
        anchor_extractor = getattr(
            bot, "extract_provider_continuation_anchor", None
        )
        if not all(callable(item) for item in (
            capability_getter, request_builder, anchor_extractor
        )):
            return kwargs, None
        provider_key = str(candidate.get("bot_type") or "").strip()
        model_name = str(candidate.get("model") or self.model).strip()
        try:
            from channel.wechat_group.wechat_group_provider_continuation import (
                ProviderContinuationScope,
                endpoint_fingerprint,
                normalize_capability,
                permission_fingerprint,
            )

            api_config = bot.get_api_config() if hasattr(bot, "get_api_config") else {}
            api_base = (
                api_config.get("api_base")
                if isinstance(api_config, dict)
                else ""
            )
            fingerprint = endpoint_fingerprint(provider_key, api_base or "")
            capability = normalize_capability(
                capability_getter(model=model_name),
                provider_key,
                model_name,
                fingerprint,
            )
            if not capability.supported:
                return kwargs, None
            scope = ProviderContinuationScope(
                stable_account_scope=str(
                    context.get("stable_account_scope") or ""
                ).strip(),
                stable_room_id=str(context.get("stable_room_id") or "").strip(),
                stable_member_id=str(context.get("stable_member_id") or "").strip(),
                owner_session_id=str(context.get("owner_session_id") or "").strip(),
                thread_id=str(context.get("thread_id") or "").strip(),
                provider_key=provider_key,
                model=model_name,
                endpoint_fingerprint=fingerprint,
                permission_fingerprint=permission_fingerprint(context),
            )
            request_id = str(context.get("request_id") or "").strip()
            if not scope.valid() or not request_id:
                return kwargs, None
            store = self._get_provider_continuation_store()
            committed = None
            if (
                action == "resume_thread"
                and getattr(request, "_provider_continuation_skip_anchor", False)
                is not True
            ):
                committed = store.get_committed(scope)
            prepared = request_builder(
                request_kwargs=copy.deepcopy(kwargs),
                committed_anchor=(committed.anchor_value if committed else ""),
                capability=capability.to_dict(),
            )
            if not isinstance(prepared, dict):
                raise TypeError(
                    "provider continuation request builder must return a dict"
                )
        except Exception as exc:
            logger.warning(
                "[ProviderContinuation] optional adapter disabled for request: "
                "provider=%s model=%s error_type=%s",
                provider_key,
                model_name,
                type(exc).__name__,
            )
            return kwargs, None
        runtime = {
            "bot": bot,
            "capability": capability,
            "scope": scope,
            "store": store,
            "request_id": request_id,
            "ttl_seconds": min(
                max(int(context.get("ttl_seconds") or 900), 60),
                24 * 60 * 60,
            ),
            "committed": committed,
            "candidate_anchor": "",
            "candidate_anchor_type": capability.anchor_type,
            "saw_tool_call": False,
            "saw_error": False,
        }
        return prepared, runtime

    def _observe_provider_continuation(self, request: LLMRequest, payload) -> None:
        runtime = getattr(request, "_provider_continuation_runtime", None)
        if not isinstance(runtime, dict):
            return
        if isinstance(payload, dict) and payload.get("error"):
            runtime["saw_error"] = True
        if self._payload_has_tool_call(payload):
            runtime["saw_tool_call"] = True
        try:
            candidate = runtime["bot"].extract_provider_continuation_anchor(
                payload=payload,
                capability=runtime["capability"].to_dict(),
            )
        except Exception as exc:
            logger.warning(
                "[ProviderContinuation] candidate extraction failed: "
                "provider=%s error_type=%s",
                runtime["capability"].provider_key,
                type(exc).__name__,
            )
            return
        if isinstance(candidate, dict):
            anchor_value = str(candidate.get("anchor_value") or "").strip()
            anchor_type = str(
                candidate.get("anchor_type")
                or runtime["capability"].anchor_type
            ).strip()
        else:
            anchor_value = str(candidate or "").strip()
            anchor_type = runtime["capability"].anchor_type
        if anchor_value:
            runtime["candidate_anchor"] = anchor_value
            runtime["candidate_anchor_type"] = anchor_type

    def _stage_provider_continuation(self, request: LLMRequest) -> bool:
        runtime = getattr(request, "_provider_continuation_runtime", None)
        if not isinstance(runtime, dict):
            return False
        if runtime.get("saw_error") or runtime.get("saw_tool_call"):
            return False
        anchor_value = str(runtime.get("candidate_anchor") or "").strip()
        if not anchor_value:
            return False
        committed = runtime.get("committed")
        try:
            staged = runtime["store"].stage(
                runtime["scope"],
                str(runtime.get("candidate_anchor_type") or ""),
                anchor_value,
                runtime["request_id"],
                runtime["ttl_seconds"],
                parent_anchor_value=(committed.anchor_value if committed else ""),
            )
        except Exception as exc:
            logger.warning(
                "[ProviderContinuation] candidate staging failed: "
                "provider=%s model=%s error_type=%s",
                runtime["capability"].provider_key,
                runtime["capability"].model,
                type(exc).__name__,
            )
            return False
        if not staged:
            return False
        logger.debug(
            "[ProviderContinuation] staged provider=%s model=%s anchor=%s request=%s",
            staged.scope.provider_key,
            staged.scope.model,
            staged.hash_prefix,
            staged.request_id,
        )
        return True

    @staticmethod
    def _provider_anchor_error(request: LLMRequest, error) -> bool:
        runtime = getattr(request, "_provider_continuation_runtime", None)
        if not isinstance(runtime, dict) or runtime.get("committed") is None:
            return False
        classifier = getattr(
            runtime.get("bot"), "classify_provider_continuation_error", None
        )
        if not callable(classifier):
            return False
        try:
            classification = classifier(
                error=error,
                capability=runtime["capability"].to_dict(),
            )
        except Exception:
            return False
        return str(classification or "").strip().lower() in {
            "expired", "not_found"
        }

    @staticmethod
    def _expire_provider_anchor(request: LLMRequest) -> None:
        runtime = getattr(request, "_provider_continuation_runtime", None)
        if not isinstance(runtime, dict):
            return
        committed = runtime.get("committed")
        if committed is not None:
            try:
                runtime["store"].expire(committed.row_id)
            except Exception as exc:
                logger.warning(
                    "[ProviderContinuation] committed anchor expiration failed: "
                    "provider=%s model=%s error_type=%s",
                    runtime["capability"].provider_key,
                    runtime["capability"].model,
                    type(exc).__name__,
                )

    def _call_candidate(self, request: LLMRequest, candidate, stream: bool):
        bot = self._get_bot_for_candidate(candidate)
        if not hasattr(bot, 'call_with_tools'):
            bot_type = type(bot).__name__
            raise NotImplementedError(f"Bot {bot_type} does not support call_with_tools. Please add the method.")
        kwargs = self._build_call_kwargs(request, candidate, stream)
        kwargs, runtime = self._prepare_provider_continuation(
            request,
            candidate,
            bot,
            kwargs,
        )
        request._provider_continuation_runtime = runtime
        return bot.call_with_tools(**kwargs)

    @staticmethod
    def _request_source_snapshot(request: LLMRequest) -> LLMRequestSourceSnapshot:
        """取得候选循环唯一、不可变的规范化请求源。"""
        source = getattr(request, "_source_snapshot", None)
        if isinstance(source, LLMRequestSourceSnapshot):
            return source
        return LLMRequestSourceSnapshot.from_request(request)

    @classmethod
    def _candidate_request(cls, request_source: LLMRequestSourceSnapshot) -> LLMRequest:
        """每个候选都从同一源重新创建完整请求。"""
        return request_source.build_request()

    @staticmethod
    def _request_tool_names(request: LLMRequest):
        names = set()
        for tool in getattr(request, "tools", None) or []:
            if not isinstance(tool, dict):
                continue
            name = tool.get("name")
            if not name and isinstance(tool.get("function"), dict):
                name = tool["function"].get("name")
            name = str(name or "").strip()
            if name:
                names.add(name)
        return names

    @staticmethod
    def _stream_delta_text(delta) -> str:
        if not isinstance(delta, dict):
            return ""
        content = delta.get("content")
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""
        return "".join(
            str(block.get("text") or "")
            for block in content
            if isinstance(block, dict) and block.get("type") in (None, "text")
        )

    @staticmethod
    def _single_protocol_block(text, open_tag, close_tag):
        open_count = text.count(open_tag)
        close_count = text.count(close_tag)
        if open_count == 0 and close_count == 0:
            return None, ""
        if open_count != 1 or close_count != 1:
            return None, "malformed {} protocol block".format(open_tag)
        start = text.find(open_tag)
        end = text.find(close_tag, start + len(open_tag))
        if start < 0 or end < 0:
            return None, "malformed {} protocol block".format(open_tag)
        return text[start + len(open_tag):end], ""

    @staticmethod
    def _single_send_attribute_message(text):
        parser = _WechatSendAttributeParser()
        try:
            parser.feed(str(text or ""))
            parser.close()
        except Exception:
            return None, "malformed send attribute protocol"
        if parser.start_count == 0 and parser.end_count == 0:
            return None, ""
        if parser.start_count != 1 or parser.end_count != 1:
            return None, "malformed send attribute protocol"
        if not isinstance(parser.message, str) or not parser.message.strip():
            return None, "send attribute protocol requires string message"
        return parser.message.strip(), ""

    @staticmethod
    def _strip_wechat_group_protocol_residue(content):
        """从已缓冲候选中移除确定性的 Provider 控制块和标签。"""
        result = str(content or "")
        block_tags = {
            "analysis",
            "arg_value",
            "function_calls",
            "function_calls_output",
            "think",
            "thinking",
            "tool_calls",
            "wechat-sticker-copied",
        }
        tag_pattern = re.compile(
            r"<\s*(/?)\s*(analysis|arg_value|function_calls(?:_output)?|"
            r"think|thinking|tool_calls|wechat-sticker-copied|s)\b[^>]*>",
            flags=re.I,
        )
        visible_parts = []
        open_blocks = []
        cursor = 0
        for match in tag_pattern.finditer(result):
            if not open_blocks:
                visible_parts.append(result[cursor:match.start()])
            tag_name = match.group(2).lower()
            is_closing = bool(match.group(1))
            is_self_closing = match.group(0).rstrip().endswith("/>")
            if tag_name in block_tags:
                if is_closing:
                    if tag_name in open_blocks:
                        while open_blocks:
                            if open_blocks.pop() == tag_name:
                                break
                elif not is_self_closing:
                    open_blocks.append(tag_name)
            cursor = match.end()
        if not open_blocks:
            visible_parts.append(result[cursor:])
        result = "".join(visible_parts)
        for marker in ("<|endoftext|>", "<|end_of_text|>", "<|eot_id|>"):
            result = result.replace(marker, "")
        return result.strip()

    @classmethod
    def _extract_wechat_group_final_content(cls, content):
        final_payload, final_error = cls._single_protocol_block(
            content,
            "<final_response>",
            "</final_response>",
        )
        if final_error:
            return "", final_error, ""
        send_payload, send_error = cls._single_protocol_block(
            content,
            "<send>",
            "</send>",
        )
        send_attribute_message = None
        if send_payload is None:
            send_attribute_message, attribute_error = (
                cls._single_send_attribute_message(content)
            )
            if send_attribute_message is not None:
                send_error = ""
            elif attribute_error and not send_error:
                send_error = attribute_error
        if send_error:
            return "", send_error, ""
        if final_payload is not None and (
            send_payload is not None or send_attribute_message is not None
        ):
            return "", "multiple final response protocol blocks", ""

        protocol_kind = ""
        if final_payload is not None:
            final_text = str(final_payload).strip()
            protocol_kind = "final_response"
        elif send_attribute_message is not None:
            final_text = send_attribute_message
            protocol_kind = "send_attribute"
        elif send_payload is not None:
            message_payload, message_error = cls._single_protocol_block(
                send_payload,
                "<message>",
                "</message>",
            )
            if message_error:
                return "", message_error, ""
            if message_payload is not None:
                message_block = "<message>{}</message>".format(message_payload)
                if send_payload.replace(message_block, "", 1).strip():
                    return "", "unexpected content inside send protocol", ""
                final_text = str(message_payload).strip()
                protocol_kind = "send_message"
            else:
                try:
                    send_data = json.loads(str(send_payload or "").strip())
                except (TypeError, ValueError):
                    return "", "invalid JSON send protocol", ""
                if not isinstance(send_data, dict):
                    return "", "JSON send protocol must be an object", ""
                message = send_data.get("message")
                if not isinstance(message, str):
                    return "", "JSON send protocol requires string message", ""
                final_text = message.strip()
                protocol_kind = "send_json"
        else:
            final_text = str(content or "").strip()
            protocol_kind = "plain_text"

        normalized_text = cls._strip_wechat_group_protocol_residue(final_text)
        if normalized_text != final_text:
            protocol_kind = "{}_normalized".format(protocol_kind)
        final_text = normalized_text
        if not final_text:
            return "", "empty final response", ""
        return final_text, "", protocol_kind

    @staticmethod
    def _normalized_wechat_group_text_chunk(content, finish_reason="stop"):
        return {
            "choices": [{
                "delta": {"content": content},
                "finish_reason": finish_reason or "stop",
            }],
        }

    @classmethod
    def _normalize_wechat_group_candidate(cls, request, chunks):
        content_parts = []
        tool_calls = {}
        safety_finish_reason = ""
        final_finish_reason = "stop"

        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            choices = chunk.get("choices") or []
            if not isinstance(choices, list):
                return "invalid stream choices payload", "", [], ""
            if len(choices) > 1:
                return "multiple stream choices are not supported", "", [], ""
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                finish_reason = str(choice.get("finish_reason") or "").lower()
                if finish_reason in cls._NON_FALLBACK_EMPTY_FINISH_REASONS:
                    safety_finish_reason = finish_reason
                elif finish_reason:
                    final_finish_reason = finish_reason
                delta = choice.get("delta") or choice.get("message") or {}
                content_parts.append(cls._stream_delta_text(delta))
                for tool_delta in delta.get("tool_calls") or []:
                    if not isinstance(tool_delta, dict):
                        return "invalid tool call payload", "", [], ""
                    index = tool_delta.get("index", 0)
                    item = tool_calls.setdefault(index, {"name": "", "arguments": ""})
                    function = tool_delta.get("function") or {}
                    if not isinstance(function, dict):
                        return "invalid tool function payload", "", [], ""
                    if function.get("name") is not None:
                        item["name"] = str(function.get("name") or "")
                    arguments = function.get("arguments")
                    if arguments is not None:
                        if not isinstance(arguments, str):
                            return "tool arguments must be JSON text", "", [], ""
                        item["arguments"] += arguments

        content = "".join(content_parts)
        if safety_finish_reason:
            return "", safety_finish_reason, [], "safety"

        allowed_tool_names = cls._request_tool_names(request)
        for item in tool_calls.values():
            name = str(item.get("name") or "").strip()
            if not name:
                return "empty tool name", "", [], ""
            if name not in allowed_tool_names:
                return f"unknown tool name: {name}", "", [], ""
            arguments_text = str(item.get("arguments") or "").strip() or "{}"
            try:
                arguments = json.loads(arguments_text)
            except (TypeError, ValueError):
                return f"invalid JSON arguments for tool: {name}", "", [], ""
            if not isinstance(arguments, dict):
                return f"tool arguments must be an object: {name}", "", [], ""

        if tool_calls:
            return "", "", list(chunks), "tool_calls"

        if not content.strip():
            return "empty response", "", [], ""
        final_text, protocol_reason, protocol_kind = (
            cls._extract_wechat_group_final_content(content)
        )
        if protocol_reason:
            return protocol_reason, "", [], ""
        normalized = cls._normalized_wechat_group_text_chunk(
            final_text,
            final_finish_reason,
        )
        return "", "", [normalized], protocol_kind

    @staticmethod
    def _wechat_group_safety_chunk(finish_reason: str):
        return {
            "choices": [{
                "delta": {"content": "抱歉，我无法协助处理这个请求。"},
                "finish_reason": finish_reason or "content_filter",
            }],
        }

    def _wechat_group_protocol_error_chunk(self, candidate, attempt_count, reason):
        logger.error(
            "[AgentLLMModel] all available candidates returned invalid protocol: "
            "candidate=%s/%s reason=%s",
            candidate.get("bot_type"),
            candidate.get("model"),
            reason,
        )
        return self._with_route_metadata({
            "error": True,
            "message": "模型返回了无法安全处理的响应，请稍后重试。",
            "status_code": 422,
            "model_fallback_exhausted": True,
            "protocol_error": True,
        }, candidate, attempt_count)

    @staticmethod
    def _wechat_group_thinking_control_rejected(candidate, error) -> bool:
        provider_type = str(candidate.get("bot_type") or "").lower()
        if not provider_type.startswith("custom"):
            return False

        status_code = None
        parts = []
        if isinstance(error, dict):
            status_code = error.get("status_code") or error.get("status")
            parts.extend((error.get("message"), error.get("code"), error.get("type")))
            error_data = error.get("error")
            if isinstance(error_data, dict):
                parts.extend((
                    error_data.get("message"),
                    error_data.get("code"),
                    error_data.get("type"),
                ))
            elif error_data is not None:
                parts.append(error_data)
        else:
            status_code = getattr(error, "status_code", None)
            parts.extend((str(error), getattr(error, "message", None)))
            body = getattr(error, "body", None)
            if body is not None:
                parts.append(body)

        try:
            if int(status_code) not in (400, 422):
                return False
        except (TypeError, ValueError):
            return False

        message = " ".join(str(part or "") for part in parts).lower()
        rejection_markers = (
            "unknown",
            "unsupported",
            "unrecognized",
            "not supported",
            "not allowed",
            "unexpected",
            "extra fields",
            "additional properties",
            "invalid parameter",
        )
        return "thinking" in message and any(
            marker in message for marker in rejection_markers
        )

    def _call_wechat_group_stream(self, request_source, candidates, cancel_event=None):
        for index, candidate in enumerate(candidates):
            retry_next = False
            for anchor_attempt in range(2):
                candidate_request = self._candidate_request(request_source)
                if anchor_attempt:
                    candidate_request._provider_continuation_skip_anchor = True
                buffered_chunks = []
                transient_error = None
                terminal_error = None
                protocol_reason = ""
                protocol_kind = ""
                normalized_chunks = []
                retry_anchor = False
                try:
                    if cancel_event is not None and cancel_event.is_set():
                        raise AgentCancelledError("cancelled before model candidate")
                    stream = self._call_candidate(
                        candidate_request,
                        candidate,
                        stream=True,
                    )

                    for chunk in stream:
                        if cancel_event is not None and cancel_event.is_set():
                            raise AgentCancelledError("cancelled during model candidate")
                        if len(buffered_chunks) >= self._WECHAT_GROUP_MAX_BUFFERED_CHUNKS:
                            protocol_reason = "stream chunk limit exceeded"
                            break
                        if (
                            anchor_attempt == 0
                            and not buffered_chunks
                            and self._provider_anchor_error(candidate_request, chunk)
                        ):
                            self._expire_provider_anchor(candidate_request)
                            retry_anchor = True
                            break
                        self._observe_provider_continuation(
                            candidate_request,
                            chunk,
                        )
                        is_error = isinstance(chunk, dict) and bool(chunk.get("error"))
                        if is_error:
                            if self._is_transient_model_error_payload(chunk):
                                transient_error = chunk
                            else:
                                terminal_error = chunk
                            break
                        buffered_chunks.append(self._format_stream_chunk(chunk))

                    if retry_anchor:
                        continue

                    if transient_error is not None:
                        self._record_primary_transient_failure(candidate, candidates)
                        if index + 1 < len(candidates):
                            next_candidate = candidates[index + 1]
                            self._log_model_fallback(
                                candidate,
                                next_candidate,
                                transient_error,
                            )
                            retry_next = True
                            break
                        if candidate.get("source") == "fallback":
                            transient_error = self._mark_fallback_exhausted(
                                transient_error
                            )
                        yield self._format_stream_chunk(transient_error)
                        return

                    if terminal_error is not None:
                        if self._wechat_group_thinking_control_rejected(
                            candidate,
                            terminal_error,
                        ):
                            protocol_reason = "provider rejected thinking control"
                        else:
                            self._record_primary_healthy(candidate)
                            yield self._format_stream_chunk(terminal_error)
                            return

                    if not protocol_reason:
                        (
                            protocol_reason,
                            safety_reason,
                            normalized_chunks,
                            protocol_kind,
                        ) = (
                            self._normalize_wechat_group_candidate(
                                candidate_request,
                                buffered_chunks,
                            )
                        )
                        if safety_reason:
                            self._record_primary_healthy(candidate)
                            yield self._wechat_group_safety_chunk(safety_reason)
                            return

                    if protocol_reason:
                        self._record_primary_unusable_probe(candidate, candidates)
                        if index + 1 < len(candidates):
                            next_candidate = candidates[index + 1]
                            self._log_unusable_model_fallback(
                                candidate,
                                next_candidate,
                                protocol_reason,
                            )
                            retry_next = True
                            break
                        yield self._wechat_group_protocol_error_chunk(
                            candidate,
                            index + 1,
                            protocol_reason,
                        )
                        return

                    self._record_primary_healthy(candidate)
                    logger.info(
                        "[AgentLLMModel] accepted wechat-group candidate: "
                        "candidate=%s/%s protocol=%s raw_chunks=%s normalized_chunks=%s",
                        candidate.get("bot_type"),
                        candidate.get("model"),
                        protocol_kind,
                        len(buffered_chunks),
                        len(normalized_chunks),
                    )
                    for chunk in normalized_chunks:
                        yield chunk
                    if not (
                        bool(getattr(candidate_request, "require_finish_tool", False))
                        and protocol_kind != "tool_calls"
                    ):
                        self._stage_provider_continuation(candidate_request)
                    return
                except Exception as exc:
                    if isinstance(exc, AgentCancelledError):
                        raise
                    if (
                        anchor_attempt == 0
                        and not buffered_chunks
                        and self._provider_anchor_error(candidate_request, exc)
                    ):
                        self._expire_provider_anchor(candidate_request)
                        continue
                    if self._wechat_group_thinking_control_rejected(candidate, exc):
                        protocol_reason = "provider rejected thinking control"
                        self._record_primary_unusable_probe(candidate, candidates)
                        if index + 1 < len(candidates):
                            next_candidate = candidates[index + 1]
                            self._log_unusable_model_fallback(
                                candidate,
                                next_candidate,
                                protocol_reason,
                            )
                            retry_next = True
                            break
                        yield self._wechat_group_protocol_error_chunk(
                            candidate,
                            index + 1,
                            protocol_reason,
                        )
                        return
                    is_transient = self._is_transient_model_error_text(str(exc))
                    if is_transient:
                        self._record_primary_transient_failure(candidate, candidates)
                    else:
                        self._record_primary_healthy(candidate)
                    if is_transient and index + 1 < len(candidates):
                        next_candidate = candidates[index + 1]
                        self._log_model_fallback(candidate, next_candidate, exc)
                        retry_next = True
                        break
                    if is_transient and candidate.get("source") == "fallback":
                        exhausted_error = RuntimeError(str(exc))
                        exhausted_error.model_fallback_exhausted = True
                        raise self._with_route_exception_metadata(
                            exhausted_error,
                            candidate,
                            index + 1,
                        ) from exc
                    self._with_route_exception_metadata(exc, candidate, index + 1)
                    raise
            if retry_next:
                continue

    def _is_transient_model_error_text(self, text) -> bool:
        error_text = str(text or "").lower()
        if not error_text:
            return False
        return (
            any(keyword in error_text for keyword in self._TRANSIENT_MODEL_ERROR_KEYWORDS)
            or bool(self._TRANSIENT_MODEL_STATUS_PATTERN.search(error_text))
        )

    def _is_transient_model_error_payload(self, payload) -> bool:
        if isinstance(payload, dict):
            status_code = payload.get("status_code") or payload.get("status")
            try:
                if int(status_code) in self._TRANSIENT_MODEL_STATUS_CODES:
                    return True
            except Exception:
                pass

            parts = [
                payload.get("message"),
                payload.get("code"),
                payload.get("type"),
            ]
            error_data = payload.get("error")
            if isinstance(error_data, dict):
                parts.extend([
                    error_data.get("message"),
                    error_data.get("code"),
                    error_data.get("type"),
                ])
            elif error_data not in (None, True, False):
                parts.append(error_data)
            return self._is_transient_model_error_text(" ".join(str(p or "") for p in parts))
        return self._is_transient_model_error_text(payload)

    @staticmethod
    def _bounded_diagnostic_value(value, limit=80):
        if not isinstance(value, (str, int, float)):
            return ""
        return " ".join(str(value).split())[:limit]

    @classmethod
    def _unusable_sync_text_reason(cls, request, response):
        """识别请求成功但没有可消费最终正文的同步响应。"""
        if getattr(request, "tools", None):
            return ""
        if isinstance(response, dict) and response.get("error"):
            return ""
        _, success = cls._extract_text_response(response)
        if success:
            return ""

        details = []
        if isinstance(response, dict):
            choices = response.get("choices") or []
            first = choices[0] if choices and isinstance(choices[0], dict) else {}
            finish_reason = cls._bounded_diagnostic_value(first.get("finish_reason"))
            if finish_reason.lower() in cls._NON_FALLBACK_EMPTY_FINISH_REASONS:
                return ""
            if finish_reason:
                details.append(f"finish_reason={finish_reason}")

            usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
            completion_tokens = cls._bounded_diagnostic_value(usage.get("completion_tokens"))
            if completion_tokens:
                details.append(f"completion_tokens={completion_tokens}")
            token_details = (
                usage.get("completion_tokens_details")
                if isinstance(usage.get("completion_tokens_details"), dict)
                else {}
            )
            reasoning_tokens = cls._bounded_diagnostic_value(token_details.get("reasoning_tokens"))
            if reasoning_tokens:
                details.append(f"reasoning_tokens={reasoning_tokens}")

        suffix = f" ({', '.join(details)})" if details else ""
        return f"unusable empty text response{suffix}"

    def _log_model_fallback(self, candidate, next_candidate, reason):
        logger.warning(
            "[AgentLLMModel] transient model error, switching candidate: "
            "from={}/{} to={}/{} reason={}".format(
                candidate.get("bot_type"),
                candidate.get("model"),
                next_candidate.get("bot_type"),
                next_candidate.get("model"),
                str(reason)[:160],
            )
        )

    def _record_primary_transient_failure(self, candidate, candidates):
        if candidate.get("source") != "primary":
            return
        if not any(item.get("source") == "fallback" for item in candidates):
            return
        threshold, cooldown_seconds = self._failover_policy()
        failures, opened = self._failover_state.record_transient_failure(
            self._route_key(candidate),
            threshold,
            cooldown_seconds,
        )
        if opened:
            logger.warning(
                "[AgentLLMModel] primary circuit opened: "
                f"primary={candidate.get('bot_type')}/{candidate.get('model')} "
                f"failures={failures} threshold={threshold} "
                f"cooldown_seconds={cooldown_seconds}"
            )

    def _record_primary_healthy(self, candidate):
        if candidate.get("source") != "primary":
            return
        if self._failover_state.record_healthy(self._route_key(candidate)):
            logger.info(
                "[AgentLLMModel] primary circuit recovered: "
                f"primary={candidate.get('bot_type')}/{candidate.get('model')}"
            )

    def _record_primary_unusable_probe(self, candidate, candidates):
        if candidate.get("source") != "primary":
            return
        if not any(item.get("source") == "fallback" for item in candidates):
            return
        _, cooldown_seconds = self._failover_policy()
        if self._failover_state.record_unusable_probe(
            self._route_key(candidate),
            cooldown_seconds,
        ):
            logger.warning(
                "[AgentLLMModel] primary half-open probe returned unusable text; "
                f"reopening circuit: primary={candidate.get('bot_type')}/{candidate.get('model')} "
                f"cooldown_seconds={cooldown_seconds}"
            )

    @staticmethod
    def _log_unusable_model_fallback(candidate, next_candidate, reason):
        logger.warning(
            "[AgentLLMModel] unusable text response, switching candidate: "
            "from={}/{} to={}/{} reason={}".format(
                candidate.get("bot_type"),
                candidate.get("model"),
                next_candidate.get("bot_type"),
                next_candidate.get("model"),
                str(reason)[:240],
            )
        )

    @staticmethod
    def _mark_fallback_exhausted(payload):
        if not isinstance(payload, dict):
            return payload
        marked = dict(payload)
        marked["model_fallback_exhausted"] = True
        return marked

    @staticmethod
    def _with_route_metadata(payload, candidate, attempt_count):
        if not isinstance(payload, dict):
            return payload
        payload["_lightagent_route_source"] = str(candidate.get("source") or "primary")
        payload["_lightagent_route_attempt_count"] = max(int(attempt_count or 1), 1)
        return payload

    @staticmethod
    def _with_route_exception_metadata(exc, candidate, attempt_count):
        try:
            exc._lightagent_route_source = str(candidate.get("source") or "primary")
            exc._lightagent_route_attempt_count = max(int(attempt_count or 1), 1)
        except Exception:
            pass
        return exc

    def _call_sync_candidate_with_anchor_retry(self, request_source, candidate):
        candidate_request = self._candidate_request(request_source)
        try:
            response = self._call_candidate(
                candidate_request, candidate, stream=False
            )
        except Exception as exc:
            if not self._provider_anchor_error(candidate_request, exc):
                raise
            self._expire_provider_anchor(candidate_request)
            candidate_request = self._candidate_request(request_source)
            candidate_request._provider_continuation_skip_anchor = True
            response = self._call_candidate(
                candidate_request, candidate, stream=False
            )
        else:
            if self._provider_anchor_error(candidate_request, response):
                self._expire_provider_anchor(candidate_request)
                candidate_request = self._candidate_request(request_source)
                candidate_request._provider_continuation_skip_anchor = True
                response = self._call_candidate(
                    candidate_request, candidate, stream=False
                )
        self._observe_provider_continuation(candidate_request, response)
        return response, candidate_request

    def call(self, request: LLMRequest, model=None, provider=None):
        """
        Call the model using LightAgent's bot infrastructure
        """
        try:
            request_source = self._request_source_snapshot(request)
            candidates = (
                self._build_override_candidates(provider, model)
                or self._build_model_candidates()
            )
            last_response = None
            for index, candidate in enumerate(candidates):
                try:
                    response, candidate_request = (
                        self._call_sync_candidate_with_anchor_retry(
                            request_source,
                            candidate,
                        )
                    )
                    response = self._format_response(response)
                    is_transient = self._is_transient_model_error_payload(response)
                    unusable_reason = (
                        ""
                        if is_transient
                        else self._unusable_sync_text_reason(candidate_request, response)
                    )
                    if is_transient:
                        self._record_primary_transient_failure(candidate, candidates)
                    elif unusable_reason:
                        self._record_primary_unusable_probe(candidate, candidates)
                    else:
                        self._record_primary_healthy(candidate)
                    if (
                        is_transient
                        and index + 1 < len(candidates)
                    ):
                        next_candidate = candidates[index + 1]
                        self._log_model_fallback(candidate, next_candidate, response)
                        last_response = response
                        continue
                    if unusable_reason and index + 1 < len(candidates):
                        next_candidate = candidates[index + 1]
                        self._log_unusable_model_fallback(
                            candidate,
                            next_candidate,
                            unusable_reason,
                        )
                        last_response = response
                        continue
                    if is_transient and candidate.get("source") == "fallback":
                        response = self._mark_fallback_exhausted(response)
                    if not is_transient and not unusable_reason:
                        self._stage_provider_continuation(candidate_request)
                    return self._with_route_metadata(response, candidate, index + 1)
                except Exception as e:
                    is_transient = self._is_transient_model_error_text(str(e))
                    if is_transient:
                        self._record_primary_transient_failure(candidate, candidates)
                    else:
                        self._record_primary_healthy(candidate)
                    if (
                        is_transient
                        and index + 1 < len(candidates)
                    ):
                        next_candidate = candidates[index + 1]
                        self._log_model_fallback(candidate, next_candidate, e)
                        continue
                    if is_transient and candidate.get("source") == "fallback":
                        exhausted_error = RuntimeError(str(e))
                        exhausted_error.model_fallback_exhausted = True
                        raise self._with_route_exception_metadata(
                            exhausted_error, candidate, index + 1
                        ) from e
                    self._with_route_exception_metadata(e, candidate, index + 1)
                    raise
            return last_response
                
        except Exception as e:
            logger.error(f"AgentLLMModel call error: {e}")
            raise
    
    def call_stream(self, request: LLMRequest):
        """
        Call the model with streaming using LightAgent's bot infrastructure
        """
        try:
            request_source = self._request_source_snapshot(request)
            candidates = self._build_model_candidates()
            if (getattr(self, "channel_type", None) or "") == const.WECHAT_GROUP:
                yield from self._call_wechat_group_stream(
                    request_source,
                    candidates,
                    cancel_event=getattr(request, "_cancel_event", None),
                )
                return
            last_error_chunk = None
            for index, candidate in enumerate(candidates):
                retry_next = False
                for anchor_attempt in range(2):
                    yielded_any = False
                    retry_anchor = False
                    primary_health_recorded = False
                    candidate_request = self._candidate_request(request_source)
                    if anchor_attempt:
                        candidate_request._provider_continuation_skip_anchor = True
                    try:
                        stream = self._call_candidate(
                            candidate_request, candidate, stream=True
                        )
                        for chunk in stream:
                            if (
                                anchor_attempt == 0
                                and not yielded_any
                                and self._provider_anchor_error(
                                    candidate_request, chunk
                                )
                            ):
                                self._expire_provider_anchor(candidate_request)
                                retry_anchor = True
                                break
                            self._observe_provider_continuation(
                                candidate_request, chunk
                            )
                            is_error = (
                                isinstance(chunk, dict)
                                and bool(chunk.get("error"))
                            )
                            is_transient = (
                                is_error
                                and self._is_transient_model_error_payload(chunk)
                            )
                            if candidate.get("source") == "primary" and is_error:
                                if is_transient:
                                    self._record_primary_transient_failure(
                                        candidate, candidates
                                    )
                                else:
                                    self._record_primary_healthy(candidate)
                                primary_health_recorded = True
                            if (
                                is_error
                                and not yielded_any
                                and is_transient
                                and index + 1 < len(candidates)
                            ):
                                next_candidate = candidates[index + 1]
                                self._log_model_fallback(
                                    candidate, next_candidate, chunk
                                )
                                last_error_chunk = chunk
                                retry_next = True
                                break
                            if (
                                is_transient
                                and candidate.get("source") == "fallback"
                            ):
                                chunk = self._mark_fallback_exhausted(chunk)
                            if (
                                candidate.get("source") == "primary"
                                and not primary_health_recorded
                            ):
                                self._record_primary_healthy(candidate)
                                primary_health_recorded = True
                            yielded_any = True
                            yield self._format_stream_chunk(chunk)
                        if retry_anchor:
                            continue
                        if retry_next:
                            break
                        if (
                            candidate.get("source") == "primary"
                            and not primary_health_recorded
                        ):
                            self._record_primary_healthy(candidate)
                        self._stage_provider_continuation(candidate_request)
                        return
                    except Exception as e:
                        if (
                            anchor_attempt == 0
                            and not yielded_any
                            and self._provider_anchor_error(
                                candidate_request, e
                            )
                        ):
                            self._expire_provider_anchor(candidate_request)
                            continue
                        is_transient = self._is_transient_model_error_text(str(e))
                        if candidate.get("source") == "primary":
                            if is_transient:
                                self._record_primary_transient_failure(
                                    candidate, candidates
                                )
                            else:
                                self._record_primary_healthy(candidate)
                        if (
                            not yielded_any
                            and is_transient
                            and index + 1 < len(candidates)
                        ):
                            next_candidate = candidates[index + 1]
                            self._log_model_fallback(
                                candidate, next_candidate, e
                            )
                            retry_next = True
                            break
                        if (
                            is_transient
                            and candidate.get("source") == "fallback"
                        ):
                            exhausted_error = RuntimeError(str(e))
                            exhausted_error.model_fallback_exhausted = True
                            raise exhausted_error from e
                        raise
                if retry_next:
                    continue
            if last_error_chunk is not None:
                yield self._format_stream_chunk(last_error_chunk)
                
        except AgentCancelledError:
            raise
        except Exception as e:
            logger.error(f"AgentLLMModel call_stream error: {e}", exc_info=True)
            raise
    
    def _format_response(self, response):
        """Format Claude response to our expected format"""
        # This would need to be implemented based on Claude's response format
        return response
    
    def _format_stream_chunk(self, chunk):
        """Format Claude stream chunk to our expected format"""
        # This would need to be implemented based on Claude's stream format
        return chunk


    @staticmethod
    def _extract_text_response(response):
        """Return (text, success) from OpenAI/Claude-compatible payloads."""
        if not isinstance(response, dict):
            text = str(response or "")
            return text, bool(text.strip())
        if response.get("error"):
            error = response.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or response.get("message") or ""), False
            return str(response.get("message") or error or ""), False
        choices = response.get("choices") or []
        if choices:
            first = choices[0] or {}
            message = first.get("message") or {}
            content = message.get("content")
            if content is None:
                content = first.get("text")
            if isinstance(content, list):
                content = "".join(
                    str(block.get("text", "")) if isinstance(block, dict) else str(block)
                    for block in content
                )
            text = str(content or "")
            return text, bool(text.strip())
        content = response.get("content")
        if isinstance(content, list):
            content = "".join(
                str(block.get("text", "")) if isinstance(block, dict) else str(block)
                for block in content
            )
        text = str(content or response.get("message") or "")
        return text, bool(text.strip())

    def complete(
        self,
        messages,
        purpose="text",
        system="",
        max_tokens=None,
        temperature=None,
        model=None,
        provider=None,
        request_options=None,
    ):
        """Run a stateless text completion through the shared fallback chain."""
        request_source = LLMRequestSourceSnapshot(
            messages=[dict(item) for item in (messages or [])],
            tools=[],
            system=system or "",
            max_tokens=max_tokens,
            stream=False,
            request_options=dict(request_options or {}),
            _explicit_temperature=temperature,
        )
        request = request_source.build_request()
        request._source_snapshot = request_source
        response = self.call(request, model=model, provider=provider)
        text, success = self._extract_text_response(response)
        logger.debug(
            "[TextModelRouter] completion finished: purpose=%s success=%s",
            purpose,
            success,
        )
        return {
            "content": text,
            "completion_tokens": 1 if success else 0,
            "total_tokens": 0,
            "success": success,
            "raw": response,
        }

    def reply(self, query, context=None):
        """Provider-neutral legacy chat entry point with atomic history commit."""
        if context is None or context.type != ContextType.TEXT:
            return self.bridge.get_bot("chat").reply(query, context)

        session_id = context.get("session_id")
        clear_commands = conf().get("clear_memory_commands", ["#清除记忆"])
        if query in clear_commands:
            self.sessions.clear_session(session_id)
            return Reply(ReplyType.INFO, "记忆已清除")
        if query == "#清除所有":
            self.sessions.clear_all_session()
            return Reply(ReplyType.INFO, "所有人记忆已清除")
        if query == "#更新配置":
            load_config()
            return Reply(ReplyType.INFO, "配置已更新")

        lock = self.sessions.session_lock(session_id)
        with lock:
            messages = self.sessions.snapshot_with_query(session_id, query)
            result = self.complete(messages, purpose="legacy_chat")
            if not result.get("success"):
                return Reply(ReplyType.ERROR, result.get("content") or "模型调用失败")
            content = result.get("content") or ""
            self.sessions.commit_exchange(session_id, query, content)
            return Reply(ReplyType.TEXT, content)


class AgentLLMModel(TextModelRouter):
    """Backward-compatible Agent protocol adapter for the shared text router."""

    pass


class AgentBridge:
    """
    Bridge class that integrates super Agent with LightAgent
    Manages multiple agent instances per session for conversation isolation
    """
    
    def __init__(self, bridge: Bridge):
        self.bridge = bridge
        self.agents = OrderedDict()  # owner session or (owner session, thread)
        self._agents_lock = threading.RLock()
        self._active_agent_cache_keys = set()
        self.default_agent = None  # For backward compatibility (no session_id)
        self.agent: Optional[Agent] = None
        self.scheduler_initialized = False
        
        # Create helper instances
        self.initializer = AgentInitializer(bridge, self)

        # Eager-start the scheduler so cron tasks fire without waiting
        # for the first user message. init_scheduler is idempotent.
        try:
            from agent.tools.scheduler.integration import init_scheduler
            if init_scheduler(self):
                self.scheduler_initialized = True
        except Exception as e:
            logger.warning(f"[AgentBridge] Eager scheduler init failed: {e}")

        # Start the self-evolution idle trigger (idempotent, daemon thread).
        try:
            from agent.evolution.trigger import start_evolution_trigger
            start_evolution_trigger(self)
        except Exception as e:
            logger.warning(f"[AgentBridge] Evolution trigger init failed: {e}")

    def create_agent(self, system_prompt: str, tools: List = None, **kwargs) -> Agent:
        """
        Create the super agent with LightAgent integration
        
        Args:
            system_prompt: System prompt
            tools: List of tools (optional)
            **kwargs: Additional agent parameters
            
        Returns:
            Agent instance
        """
        # Create LLM model that uses LightAgent's bot infrastructure
        model = AgentLLMModel(self.bridge)
        
        # Default tools if none provided
        if tools is None:
            # Use ToolManager to load all available tools
            from agent.tools import ToolManager
            tool_manager = ToolManager()
            tool_manager.load_tools()
            
            tools = []
            workspace_dir = kwargs.get("workspace_dir")
            for tool_name in tool_manager.tool_classes.keys():
                try:
                    tool = tool_manager.create_tool(tool_name)
                    if tool:
                        if workspace_dir and hasattr(tool, 'cwd'):
                            tool.cwd = workspace_dir
                        tools.append(tool)
                except Exception as e:
                    logger.warning(f"[AgentBridge] Failed to load tool {tool_name}: {e}")
        
        # Create agent instance
        agent = Agent(
            system_prompt=system_prompt,
            description=kwargs.get("description", "AI Super Agent"),
            model=model,
            tools=tools,
            max_steps=kwargs.get("max_steps", 15),
            output_mode=kwargs.get("output_mode", "logger"),
            workspace_dir=kwargs.get("workspace_dir"),
            skill_manager=kwargs.get("skill_manager"),
            enable_skills=kwargs.get("enable_skills", True),
            memory_manager=kwargs.get("memory_manager"),
            max_context_tokens=kwargs.get("max_context_tokens"),
            context_reserve_tokens=kwargs.get("context_reserve_tokens"),
            runtime_info=kwargs.get("runtime_info"),
        )

        # Log skill loading details
        if agent.skill_manager:
            logger.debug(f"[AgentBridge] SkillManager initialized with {len(agent.skill_manager.skills)} skills")

        return agent
    
    @staticmethod
    def _agent_cache_key(session_id: str, thread_id: Optional[str] = None):
        return (session_id, str(thread_id)) if thread_id else session_id

    def _agent_cache_lock(self):
        if not hasattr(self, "agents"):
            self.agents = OrderedDict()
        lock = getattr(self, "_agents_lock", None)
        if lock is None:
            lock = threading.RLock()
            self._agents_lock = lock
        return lock

    def _touch_agent_cache_key(self, cache_key) -> None:
        move_to_end = getattr(self.agents, "move_to_end", None)
        if callable(move_to_end):
            move_to_end(cache_key)
            return
        agent = self.agents.pop(cache_key)
        self.agents[cache_key] = agent

    def _enforce_thread_agent_cache_limit(self) -> None:
        try:
            limit = int(
                conf().get("wechat_group_thread_agent_cache_max_entries", 128)
                or 128
            )
        except (TypeError, ValueError):
            limit = 128
        limit = min(max(limit, 8), 1024)
        active_keys = getattr(self, "_active_agent_cache_keys", set())
        thread_keys = [
            key
            for key in self.agents
            if isinstance(key, tuple) and key not in active_keys
        ]
        total_thread_entries = sum(
            1 for key in self.agents if isinstance(key, tuple)
        )
        while total_thread_entries > limit and thread_keys:
            evicted = thread_keys.pop(0)
            self.agents.pop(evicted, None)
            total_thread_entries -= 1
            logger.debug(
                "[AgentBridge] Evicted inactive WeChat group thread agent: %s",
                evicted,
            )

    def agent_items_snapshot(self):
        with self._agent_cache_lock():
            return list(self.agents.items())

    def get_agent(
        self,
        session_id: str = None,
        thread_id: Optional[str] = None,
    ) -> Optional[Agent]:
        """
        Get agent instance for the given session
        
        Args:
            session_id: Session identifier (e.g., user_id). If None, returns default agent.
        
        Returns:
            Agent instance for this session
        """
        # If no session_id, use default agent (backward compatibility)
        if session_id is None:
            if self.default_agent is None:
                self._init_default_agent()
            return self.default_agent
        
        # Check if agent exists for this session
        cache_key = self._agent_cache_key(session_id, thread_id)
        with self._agent_cache_lock():
            if cache_key not in self.agents:
                self._init_agent_for_session(session_id, thread_id=thread_id)
                self._enforce_thread_agent_cache_limit()
            else:
                self._touch_agent_cache_key(cache_key)
            return self.agents[cache_key]
    
    def _init_default_agent(self):
        """Initialize default super agent"""
        agent = self.initializer.initialize_agent(session_id=None)
        self.default_agent = agent
    
    def _init_agent_for_session(
        self,
        session_id: str,
        thread_id: Optional[str] = None,
    ):
        """Initialize agent for a specific session"""
        if thread_id:
            agent = self.initializer.initialize_agent(
                session_id=session_id,
                history_thread_id=thread_id,
            )
        else:
            agent = self.initializer.initialize_agent(session_id=session_id)
        self.agents[self._agent_cache_key(session_id, thread_id)] = agent

    def sync_session_messages_from_store(self, session_id: str) -> int:
        """Reload an agent's in-memory ``messages`` list from the persistent
        conversation store.

        Used after an external mutation (e.g. user edits / deletes a message
        via the web console) so the agent's next turn sees the same history
        as the database. The operation is a no-op when the agent has not been
        instantiated yet for the session.

        Returns:
            Number of messages now held in the agent's memory. Returns -1 if
            the agent does not exist or has no compatible ``messages`` attr.
        """
        if not session_id:
            return -1
        targets = []
        for cache_key, agent in self.agent_items_snapshot():
            owner = cache_key[0] if isinstance(cache_key, tuple) else cache_key
            if owner == session_id:
                thread_id = cache_key[1] if isinstance(cache_key, tuple) else None
                targets.append((agent, thread_id))
        if not targets:
            return -1
        count = 0
        from agent.memory import get_conversation_store
        store = get_conversation_store()
        for agent, thread_id in targets:
            if not (hasattr(agent, "messages") and hasattr(agent, "messages_lock")):
                continue
            try:
                remaining = store.load_messages(
                    session_id,
                    max_turns=10**6,
                    thread_id=thread_id,
                )
            except Exception as e:
                logger.warning(
                    f"[AgentBridge] Failed to load messages for sync "
                    f"(session={session_id}, thread={thread_id or 'legacy'}): {e}"
                )
                continue
            with agent.messages_lock:
                agent.messages.clear()
                for msg in remaining:
                    agent.messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                    })
                count += len(agent.messages)
        logger.info(
            f"[AgentBridge] Synced agent memory for session={session_id}, messages={count}"
        )
        return count

    def sync_thread_messages_from_store(
        self,
        session_id: str,
        thread_id: str,
    ) -> int:
        """Reload one cached thread from its committed text-only history."""
        if not session_id or not thread_id:
            return -1
        cache_key = self._agent_cache_key(session_id, thread_id)
        with self._agent_cache_lock():
            agent = self.agents.get(cache_key)
        if agent is None:
            return -1
        return self._reload_thread_agent_from_store(
            agent,
            session_id,
            thread_id,
        )

    def agent_reply(self, query: str, context: Context = None, 
                   on_event=None, clear_history: bool = False) -> Reply:
        """
        Use super agent to reply to a query
        
        Args:
            query: User query
            context: LightAgent context (optional, contains session_id for user isolation)
            on_event: Event callback (optional)
            clear_history: Whether to clear conversation history
            
        Returns:
            Reply object
        """
        session_id = None
        history_thread_id = None
        session_action = ""
        agent = None
        request_id = None
        cancel_event = None
        execution_lock = None
        execution_lock_acquired = False
        history_mode = "interactive_session"
        history_snapshot = None
        history_snapshot_restored = False
        run_stream_executor = None
        observed_messages = []
        agent_cache_key = None
        memory_route = None
        registry = None
        token_key = None
        try:
            # Extract session_id from context for user isolation
            if context:
                session_id = context.kwargs.get("session_id") or context.get("session_id")
                request_id = context.kwargs.get("request_id") or context.get("request_id")
                session_action = str(
                    context.get("wechat_group_session_action") or ""
                ).strip()
                if session_action in {"new_thread", "resume_thread"}:
                    history_thread_id = str(
                        context.get("wechat_group_thread_id") or ""
                    ).strip() or None
                if history_thread_id and not request_id:
                    request_id = uuid4().hex
                    context["request_id"] = request_id

            # Get agent for this session (will auto-initialize if needed)
            if history_thread_id:
                agent = self.get_agent(
                    session_id=session_id,
                    thread_id=history_thread_id,
                )
            else:
                agent = self.get_agent(session_id=session_id)
            if not agent:
                return Reply(ReplyType.ERROR, "Failed to initialize super agent")
            agent_cache_key = self._agent_cache_key(session_id, history_thread_id)
            with self._agent_cache_lock():
                active_keys = getattr(self, "_active_agent_cache_keys", None)
                if active_keys is None:
                    active_keys = set()
                    self._active_agent_cache_keys = active_keys
                active_keys.add(agent_cache_key)

            from agent.memory.routing import resolve_memory_route
            memory_route = resolve_memory_route(
                context=context,
                agent=agent,
                session_id=session_id or "",
            )
            agent._memory_route = memory_route
            if getattr(agent, "memory_manager", None) is not None:
                agent.memory_manager._memory_route = memory_route

            execution_lock = getattr(agent, "execution_lock", None)
            if execution_lock is None:
                execution_lock = threading.RLock()
                agent.execution_lock = execution_lock
            execution_lock.acquire()
            execution_lock_acquired = True

            # Register after acquiring the per-session execution lock so a
            # queued IM request cannot replace the active request's token.
            registry = get_cancel_registry()
            token_key = request_id or session_id
            if token_key:
                cancel_event = registry.register(token_key, session_id=session_id)

            history_mode = self._resolve_agent_history_mode(context)
            preparation_mode = (
                "interactive_session"
                if history_thread_id and session_action in {"new_thread", "resume_thread"}
                else history_mode
            )
            history_snapshot = self._prepare_agent_history_for_mode(agent, preparation_mode)
            
            # Create event handler for logging and channel communication
            event_handler = AgentEventHandler(context=context, original_callback=on_event)
            
            # Filter tools based on context
            original_tools = agent.tools
            original_extra_system_suffix = getattr(agent, "extra_system_suffix", "")
            filtered_tools = original_tools
            tools_modified = False
            suffix_modified = False
            skill_filter = None
            
            # If this is a scheduled task execution, exclude scheduler tool to prevent recursion
            if context and context.get("is_scheduled_task"):
                filtered_tools = [tool for tool in agent.tools if tool.name != "scheduler"]
                agent.tools = filtered_tools
                tools_modified = True
                logger.info(f"[AgentBridge] Scheduled task execution: excluded scheduler tool ({len(filtered_tools)}/{len(original_tools)} tools)")
            else:
                # Attach context to scheduler tool if present
                if context and agent.tools:
                    for tool in agent.tools:
                        if tool.name == "scheduler":
                            try:
                                from agent.tools.scheduler.integration import attach_scheduler_to_tool
                                attach_scheduler_to_tool(tool, context)
                            except Exception as e:
                                logger.warning(f"[AgentBridge] Failed to attach context to scheduler: {e}")
                            break

            if context and context.get("channel_type") == "wechat_group":
                try:
                    from channel.wechat_group.wechat_group_permissions import filter_wechat_group_tools_for_permissions

                    scoped_filtered = filter_wechat_group_tools_for_permissions(
                        filtered_tools,
                        room_id=(
                            context.get("wechat_group_stable_room_id")
                            or context.get("wechat_group_room_id")
                            or context.get("receiver")
                            or ""
                        ),
                        sender_id=(
                            ""
                            if context.get("wechat_group_identity_requires_confirmation") is True
                            else (
                                context.get("wechat_group_stable_member_id")
                                or context.get("wechat_group_sender_id")
                                or ""
                            )
                        ),
                    )
                    if len(scoped_filtered) != len(filtered_tools):
                        filtered_tools = scoped_filtered
                        agent.tools = filtered_tools
                        tools_modified = True
                        logger.info(
                            "[AgentBridge] WeChat group permission tool filter applied: {}/{} tools".format(
                                len(filtered_tools),
                                len(original_tools),
                            )
                        )
                except Exception as e:
                    logger.warning(f"[AgentBridge] WeChat group permission tool filter failed: {e}")

                try:
                    from channel.wechat_group.wechat_group_skill_access import (
                        DENIAL_TEXT,
                        get_wechat_group_skill_access_service,
                    )

                    skill_manager = getattr(agent, "skill_manager", None)
                    if skill_manager:
                        stable_room_id = (
                            context.get("wechat_group_stable_room_id") or ""
                        )
                        stable_member_id = (
                            ""
                            if context.get("wechat_group_identity_requires_confirmation") is True
                            else context.get("wechat_group_stable_member_id") or ""
                        )
                        access_service = get_wechat_group_skill_access_service()
                        skill_filter = access_service.allowed_skill_names(
                            skill_manager,
                            stable_room_id,
                            stable_member_id,
                            request_id=request_id or "",
                        )
                        allowed = set(skill_filter)
                        denied_entries = [
                            entry
                            for entry in skill_manager.list_skills()
                            if entry.skill.name not in allowed
                            and skill_manager.is_skill_enabled(entry.skill.name)
                        ]
                        context["wechat_group_skill_access_enabled"] = True
                        context["wechat_group_allowed_skill_names"] = list(skill_filter)
                        context["wechat_group_denied_skill_names"] = [
                            entry.skill.name for entry in denied_entries
                        ]
                        context["wechat_group_skill_roots"] = {
                            entry.skill.name: os.path.realpath(entry.skill.base_dir)
                            for entry in skill_manager.list_skills()
                        }
                        context["wechat_group_active_skill_key"] = ""
                        if denied_entries:
                            denied_prompt = [
                                "<wechat_group_restricted_skills>",
                                "These skills are installed but unavailable to the current member.",
                                "If the request clearly requires one of them, reply with exactly the denial text below and do not call any tool.",
                            ]
                            for entry in denied_entries:
                                denied_prompt.append(
                                    "  <skill><name>{}</name><description>{}</description>"
                                    "<denial>{}</denial></skill>".format(
                                        html.escape(entry.skill.name),
                                        html.escape(entry.skill.description),
                                        html.escape(DENIAL_TEXT.format(
                                            skill_name=entry.skill.name
                                        )),
                                    )
                                )
                            denied_prompt.append("</wechat_group_restricted_skills>")
                            suffix = "\n".join(denied_prompt)
                            agent.extra_system_suffix = (
                                f"{original_extra_system_suffix}\n\n{suffix}".strip()
                                if original_extra_system_suffix
                                else suffix
                            )
                            suffix_modified = True
                        logger.info(
                            "[AgentBridge] WeChat group skill ACL applied: %s/%s skills",
                            len(skill_filter),
                            len(skill_manager.skills),
                        )
                except Exception as e:
                    # Fail closed for the WeChat group channel. Other channels
                    # keep their original unrestricted semantics.
                    skill_filter = []
                    context["wechat_group_skill_access_enabled"] = True
                    context["wechat_group_allowed_skill_names"] = []
                    logger.error(
                        f"[AgentBridge] WeChat group skill ACL failed closed: {e}"
                    )

            wechat_group_tools = self._create_wechat_group_memory_tools(agent, context)
            if wechat_group_tools:
                existing_names = {tool.name for tool in filtered_tools}
                scoped_tools = [
                    tool for tool in wechat_group_tools
                    if tool.name not in existing_names
                ]
                if scoped_tools:
                    agent.tools = list(filtered_tools) + scoped_tools
                    tools_modified = True
                suffix = self._build_wechat_group_memory_tool_prompt()
                current_suffix = getattr(agent, "extra_system_suffix", "") or ""
                agent.extra_system_suffix = (
                    f"{current_suffix}\n\n{suffix}".strip()
                    if current_suffix else suffix
                )
                suffix_modified = True

            if context and context.get("channel_type") == const.WECHAT_GROUP:
                suggested_tool_names = context.get("wechat_group_suggested_tool_names")
                if isinstance(suggested_tool_names, list) and suggested_tool_names:
                    allowed_names = {
                        str(name or "").strip()
                        for name in suggested_tool_names
                        if str(name or "").strip()
                    }
                    current_tools = list(agent.tools)
                    agent.tools = [
                        tool for tool in current_tools
                        if str(getattr(tool, "name", "") or "") in allowed_names
                    ]
                    tools_modified = True
                    context["wechat_group_route_tool_count"] = len(agent.tools)
                    logger.info(
                        "[AgentBridge] WeChat group route narrowed tools: "
                        "route=%s tools=%s/%s",
                        context.get("wechat_group_intent_route") or "unknown",
                        len(agent.tools),
                        len(current_tools),
                    )
            
            # Pass context metadata to model for downstream API requests
            if context and hasattr(agent, 'model'):
                agent.model.channel_type = context.get("channel_type", "")
                agent.model.session_id = session_id or ""

            # Store session_id on agent so executor can clear DB on fatal errors
            agent._current_session_id = session_id

            # Bound the in-memory context for scheduler sessions before each run.
            # Scheduler sessions are stable per-task and append every trigger,
            # so without trimming they would grow unbounded across runs and
            # blow up prompt cost. Regular user chats are not touched here —
            # the agent's own context manager handles that path.
            if session_id and session_id.startswith("scheduler_"):
                from config import conf
                scheduler_keep_turns = max(
                    1, int(conf().get("agent_max_context_turns", 20)) // 5
                )
                self._trim_in_memory_to_turns(agent, scheduler_keep_turns)

            # Eagerly persist the user message BEFORE running the agent so the
            # session and the user's bubble are immediately visible — even if
            # the user switches away or refreshes before the reply finishes.
            # The reply (assistant/tool messages) is appended once the run
            # completes; the final persist skips this already-stored user turn.
            persisted_user_query = self._select_persisted_user_query(query, context)
            if history_mode == "fresh" and not history_thread_id:
                self._start_fresh_persistent_context(session_id, context)
            if history_thread_id:
                # V2 thread turns are staged as one pending user/assistant pair
                # after generation. This avoids exposing or committing a
                # half-written turn before WeChat confirms the actual send.
                pre_persisted = False
            else:
                pre_persisted = self._pre_persist_user_message(
                    session_id,
                    persisted_user_query,
                    context,
                    clear_history and history_mode != "observe_only",
                )

            # Mark this session as mid-run so the self-evolution idle scan does
            # not fire concurrently when a single turn runs longer than
            # idle_minutes.
            try:
                from agent.evolution.trigger import mark_run_active
                mark_run_active(agent, True)
            except Exception:
                pass

            try:
                # Use agent's run_stream method with event handler
                response = agent.run_stream(
                    user_message=query,
                    on_event=event_handler.handle_event,
                    clear_history=clear_history,
                    skill_filter=skill_filter,
                    cancel_event=cancel_event,
                    context=context,
                )
                run_stream_executor = getattr(agent, "stream_executor", None)
                if history_mode == "observe_only":
                    if persisted_user_query != query:
                        self._sanitize_wechat_group_runtime_messages(
                            agent,
                            query,
                            persisted_user_query,
                        )
                    observed_messages = self._build_observed_exchange(
                        persisted_user_query,
                        response,
                    )
            finally:
                # Clear the mid-run flag so idle scans can review this session.
                try:
                    from agent.evolution.trigger import mark_run_active
                    mark_run_active(agent, False)
                except Exception:
                    pass

                # Restore original per-turn tool/prompt mutations.
                if tools_modified:
                    agent.tools = original_tools
                if suffix_modified:
                    agent.extra_system_suffix = original_extra_system_suffix

                # Log execution summary
                event_handler.log_summary()

                # Release cancel token; keep registry bounded.
                if token_key:
                    try:
                        registry.unregister(token_key)
                    except Exception:
                        pass

                if history_mode == "observe_only" and history_snapshot is not None:
                    self._restore_agent_history_snapshot(agent, history_snapshot)
                    history_snapshot_restored = True

            # Persist new messages generated during this run
            if session_id:
                channel_type = (context.get("channel_type") or "") if context else ""
                if history_mode == "observe_only":
                    self._persist_observe_only_assistant(
                        session_id,
                        response,
                        context,
                    )
                elif persisted_user_query != query:
                    self._sanitize_wechat_group_runtime_messages(agent, query, persisted_user_query)
                new_messages = (
                    []
                    if history_mode == "observe_only"
                    else list(getattr(agent, '_last_run_new_messages', []))
                )
                # The leading user turn was already persisted eagerly above;
                # drop it here so it isn't stored twice.
                if pre_persisted and new_messages and new_messages[0].get("role") == "user":
                    new_messages = new_messages[1:]
                messages_to_persist = list(new_messages)
                if history_thread_id:
                    # Agent context trimming can make _last_run_new_messages
                    # incomplete. Build an explicit turn envelope so confirmed
                    # delivery always has a recoverable user/final pair.
                    messages_to_persist = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": persisted_user_query}
                            ],
                        },
                        *messages_to_persist,
                        {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": str(response or "")}
                            ],
                        },
                    ]
                if messages_to_persist:
                    persisted = self._persist_messages(
                        session_id,
                        messages_to_persist,
                        channel_type,
                        thread_id=history_thread_id or "",
                        delivery_request_id=(request_id or "") if history_thread_id else "",
                        inbound_source_event_id=(
                            "inbound:{}".format(
                                int(context.get("wechat_group_inbound_archive_row_id") or 0)
                            )
                            if history_thread_id
                            and context
                            and context.get("wechat_group_inbound_archive_row_id")
                            else ""
                        ),
                    )
                    if history_thread_id and persisted and context is not None:
                        self._stage_wechat_group_delivery(
                            session_id,
                            history_thread_id,
                            session_action,
                            request_id or "",
                            list(new_messages),
                            context,
                        )
                elif (
                    history_mode != "observe_only"
                    and not history_thread_id
                    and hasattr(agent, "messages")
                    and hasattr(agent, "messages_lock")
                ):
                    with agent.messages_lock:
                        msg_count = len(agent.messages)
                    if msg_count == 0:
                        try:
                            from agent.memory import get_conversation_store
                            get_conversation_store().clear_session(session_id)
                            logger.info(f"[AgentBridge] Cleared DB for recovered session: {session_id}")
                        except Exception as e:
                            logger.warning(f"[AgentBridge] Failed to clear DB after recovery: {e}")
            
            # Record this user turn for the self-evolution idle trigger. Skip
            # scheduler-injected / scheduled-task sessions so internal runs do
            # not count as user activity.
            if session_id and not session_id.startswith("scheduler_") and not (
                context and context.get("is_scheduled_task")
            ) and (memory_route is None or memory_route.allow_shared_evolution):
                try:
                    from agent.evolution.trigger import note_user_turn
                    ch = (context.get("channel_type") or "") if context else ""
                    rcv = (context.get("receiver") or "") if context else ""
                    is_group = bool(context.get("isgroup")) if context else False
                    # Only enable proactive push for single chats. WeChat group
                    # sessions are rejected by MemoryRoute before this point.
                    note_user_turn(
                        agent,
                        channel_type=ch,
                        receiver=(rcv if not is_group else ""),
                        observed_messages=(observed_messages if history_mode == "observe_only" else None),
                        stable_room_id=(context.get("wechat_group_stable_room_id") or "") if context else "",
                        stable_member_id=(context.get("wechat_group_stable_member_id") or "") if context else "",
                    )
                except Exception:
                    pass

            # Post-message hot-reload: detect edits to ~/lightagent/mcp.json and
            # sync any new/removed MCP tools into the live agent in the
            # background. Off the critical path so user latency is unaffected;
            # changes take effect on the user's next message.
            self._schedule_mcp_hot_reload(agent)

            # Check if there are files to send (from send/read tool)
            active_executor = run_stream_executor or getattr(agent, "stream_executor", None)
            if active_executor is not None and hasattr(active_executor, 'files_to_send'):
                files_to_send = active_executor.files_to_send
                if files_to_send:
                    # Send the first file (for now, handle one file at a time)
                    file_info = files_to_send[0]
                    logger.info(f"[AgentBridge] Sending file: {file_info.get('path')}")
                    
                    # Clear files_to_send for next request
                    active_executor.files_to_send = []
                    
                    # Return file reply based on file type
                    return self._create_file_reply(file_info, response, context)
            
            return Reply(ReplyType.TEXT, response)
            
        except Exception as e:
            logger.error(f"Agent reply error: {e}")
            if session_id and history_thread_id:
                self._discard_pending_thread_turn(
                    session_id,
                    history_thread_id,
                    request_id or "",
                    agent=agent,
                )
                if context is not None:
                    context.pop("wechat_group_pending_agent_delivery", None)
            # If the agent cleared its messages due to format error / overflow,
            # also purge the DB so the next request starts clean.
            if session_id and agent and history_mode != "observe_only" and not history_thread_id:
                try:
                    if hasattr(agent, "messages") and hasattr(agent, "messages_lock"):
                        with agent.messages_lock:
                            msg_count = len(agent.messages)
                        if msg_count == 0:
                            from agent.memory import get_conversation_store
                            get_conversation_store().clear_session(session_id)
                            logger.info(f"[AgentBridge] Cleared DB for session after error: {session_id}")
                except Exception as db_err:
                    logger.warning(f"[AgentBridge] Failed to clear DB after error: {db_err}")
            # Release cancel token on error path too (idempotent).
            if cancel_event is not None and (request_id or session_id):
                try:
                    get_cancel_registry().unregister(request_id or session_id)
                except Exception:
                    pass
            return Reply(ReplyType.ERROR, f"Agent error: {str(e)}")
        finally:
            if (
                history_mode == "observe_only"
                and history_snapshot is not None
                and not history_snapshot_restored
                and agent is not None
            ):
                self._restore_agent_history_snapshot(agent, history_snapshot)
            if execution_lock_acquired and execution_lock is not None:
                execution_lock.release()
            if agent_cache_key is not None:
                with self._agent_cache_lock():
                    getattr(self, "_active_agent_cache_keys", set()).discard(
                        agent_cache_key
                    )
                    self._enforce_thread_agent_cache_limit()

    def _create_wechat_group_memory_tools(self, agent, context: Context = None):
        if not context or context.get("channel_type") != "wechat_group":
            return []
        room_id = (
            context.get("wechat_group_stable_room_id")
            or context.get("wechat_group_room_id")
            or ""
        ).strip()
        sender_id = (
            context.get("wechat_group_stable_member_id")
            or context.get("wechat_group_sender_id")
            or ""
        ).strip()
        if not room_id or not sender_id:
            return []
        memory_manager = getattr(agent, "memory_manager", None)
        try:
            from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
            from channel.wechat_group.wechat_group_identity_service import WechatGroupIdentityService
            from channel.wechat_group.wechat_group_memory_tools import create_wechat_group_memory_tools
            from channel.wechat_group.wechat_group_permissions import is_wechat_group_admin
            from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
            from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
            from channel.wechat_group.wechat_group_sticker_tools import create_wechat_group_sticker_tools
            from channel.wechat_group.wechat_group_report_tools import create_wechat_group_report_tools

            stable_room_id = str(context.get("wechat_group_stable_room_id") or "").strip()
            stable_member_id = str(context.get("wechat_group_stable_member_id") or "").strip()
            allow_memory_write = bool(
                stable_room_id
                and stable_member_id
                and context.get("wechat_group_identity_requires_confirmation") is not True
                and is_wechat_group_admin(stable_room_id, stable_member_id)
            )
            return create_wechat_group_memory_tools(
                knowledge_service=WechatGroupKnowledgeService(),
                profile_service=WechatGroupProfileService(
                    identity_service=WechatGroupIdentityService(),
                ),
                room_id=room_id,
                sender_id=sender_id,
                bot_sender_id=context.get("wechat_group_bot_sender_id") or "",
                allow_write=allow_memory_write,
            ) + create_wechat_group_sticker_tools(
                sticker_service=WechatGroupStickerService(),
                room_id=room_id,
            ) + create_wechat_group_report_tools(
                stable_room_id=context.get("wechat_group_stable_room_id") or "",
                stable_member_id=context.get("wechat_group_stable_member_id") or "",
                identity_confirmed=context.get("wechat_group_identity_requires_confirmation") is not True,
            )
        except Exception as e:
            logger.warning(f"[AgentBridge] Failed to create WeChat group memory tools: {e}")
            return []

    @staticmethod
    def _build_wechat_group_memory_tool_prompt() -> str:
        return (
            "## WeChat Group Scoped Memory\n\n"
            "- For current group rules, group preferences, historical agreements, "
            "project facts, or recurring decisions, prefer calling "
            "`wechat_group_memory_search` before answering.\n"
            "- When the current-room administrator explicitly asks to remember or "
            "disable a group memory, use `wechat_group_memory_write` or "
            "`wechat_group_memory_disable` when those tools are available.\n"
            "- Group memory tool scope is bound by the server; never invent or ask "
            "for another room ID.\n"
            "- For current group member roles, preferences, expertise, interaction "
            "style, boundaries, or profile facts, prefer calling "
            "`wechat_group_profile_get` before answering.\n"
            "- When a sticker reply fits better than plain text, prefer calling "
            "`wechat_group_sticker_search` first and then `wechat_group_sticker_send` "
            "with an exact sticker_id or online_id from the search result. Prefer "
            "local stickers; use online candidates only when local stickers are "
            "missing or unsuitable. Do not expose or invent raw sticker URLs.\n"
            "- These tools are bound to the current WeChat group by the server. "
            "Do not treat them as global memory or cross-group search tools.\n"
            "- `wechat_group_report` can only generate or inspect a report for the current "
            "stable group scope. Do not invent report job ids or ask it to target another group."
        )
    
    def _schedule_mcp_hot_reload(self, agent):
        """
        Fire-and-forget: detect mcp.json edits and reconcile the agent's
        tool dict in the background. Runs after the user's reply is sent,
        so any cost (file stat, hash, server boot) never adds to user latency.
        Failures are isolated and never raise into the message pipeline.
        """
        import threading
        from agent.tools import ToolManager

        def _run():
            try:
                tm = ToolManager()
                tm.refresh_mcp_if_changed()
                added, removed = tm.sync_mcp_into_agent(agent)
                if added or removed:
                    logger.info(
                        f"[AgentBridge] Agent tools synced — "
                        f"added={added}, removed={removed}"
                    )
            except Exception as e:
                logger.warning(f"[AgentBridge] MCP hot-reload failed (non-fatal): {e}")

        threading.Thread(target=_run, daemon=True, name="mcp-hot-reload").start()

    def _create_file_reply(self, file_info: dict, text_response: str, context: Context = None) -> Reply:
        """
        Create a reply for sending files
        
        Args:
            file_info: File metadata from read tool
            text_response: Text response from agent
            context: Context object
            
        Returns:
            Reply object for file sending
        """
        file_type = file_info.get("file_type", "file")
        file_path = file_info.get("path")
        is_wechat_group_sticker = bool(
            context
            and context.get("channel_type") == "wechat_group"
            and (file_info.get("sticker_id") or file_info.get("online_id"))
        )
        
        # For images, use IMAGE_URL type (channel will handle upload)
        if file_type == "image":
            # Convert local path to file:// URL for channel processing
            file_url = f"file://{file_path}"
            logger.info(f"[AgentBridge] Sending image: {file_url}")
            reply = Reply(ReplyType.IMAGE_URL, file_url)
            # Attach text message if present (for channels that support text+image)
            if text_response and not is_wechat_group_sticker:
                reply.text_content = text_response  # Store accompanying text
            reply.wechat_group_sticker_id = file_info.get("sticker_id") or ""
            reply.wechat_group_sticker_online_id = file_info.get("online_id") or ""
            reply.wechat_group_sticker_source = file_info.get("wechat_group_sticker_source") or ""
            return reply
        
        # For all file types (document, video, audio), use FILE type
        if file_type in ["document", "video", "audio"]:
            file_url = f"file://{file_path}"
            logger.info(f"[AgentBridge] Sending {file_type}: {file_url}")
            reply = Reply(ReplyType.FILE, file_url)
            reply.file_name = file_info.get("file_name", os.path.basename(file_path))
            # Attach text message if present
            if text_response:
                reply.text_content = text_response
            reply.wechat_group_sticker_id = file_info.get("sticker_id") or ""
            reply.wechat_group_sticker_online_id = file_info.get("online_id") or ""
            reply.wechat_group_sticker_source = file_info.get("wechat_group_sticker_source") or ""
            return reply
        
        # For all other file types (tar.gz, zip, etc.), also use FILE type
        file_url = f"file://{file_path}"
        logger.info(f"[AgentBridge] Sending generic file: {file_url}")
        reply = Reply(ReplyType.FILE, file_url)
        reply.file_name = file_info.get("file_name", os.path.basename(file_path))
        if text_response:
            reply.text_content = text_response
        return reply
    
    def _migrate_config_to_env(self, workspace_root: str):
        """
        Sync API keys from config.json to .env file.
        Adds new keys and updates changed values on each startup.

        Args:
            workspace_root: Workspace directory path (not used, kept for compatibility)
        """
        from config import conf
        import os
        
        key_mapping = {
            "open_ai_api_key": "OPENAI_API_KEY",
            "open_ai_api_base": "OPENAI_API_BASE",
            "gemini_api_key": "GEMINI_API_KEY",
            "claude_api_key": "CLAUDE_API_KEY",
            "linkai_api_key": "LINKAI_API_KEY",
        }
        
        env_file = expand_path("~/.lightagent/.env")
        
        # Read existing env vars (key -> value)
        existing_env_vars = {}
        if os.path.exists(env_file):
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, val = line.split('=', 1)
                            existing_env_vars[key.strip()] = val.strip()
            except Exception as e:
                logger.warning(f"[AgentBridge] Failed to read .env file: {e}")
        
        # Sync config.json values into .env (add/update/remove)
        updated = False
        for config_key, env_key in key_mapping.items():
            raw = conf().get(config_key, "")
            value = raw.strip() if raw else ""
            old_value = existing_env_vars.get(env_key)

            if value:
                if old_value == value:
                    continue
                existing_env_vars[env_key] = value
                os.environ[env_key] = value
                updated = True
            else:
                if old_value is None:
                    continue
                existing_env_vars.pop(env_key, None)
                os.environ.pop(env_key, None)
                updated = True
            updated = True

        if updated:
            try:
                env_dir = os.path.dirname(env_file)
                os.makedirs(env_dir, exist_ok=True)

                with open(env_file, 'w', encoding='utf-8') as f:
                    f.write('# Environment variables for agent\n')
                    f.write('# Auto-managed - synced from config.json on startup\n\n')
                    for key, value in sorted(existing_env_vars.items()):
                        f.write(f'{key}={value}\n')

                logger.info(f"[AgentBridge] Synced API keys from config.json to .env")
            except Exception as e:
                logger.warning(f"[AgentBridge] Failed to sync API keys: {e}")
    
    @staticmethod
    def _resolve_agent_history_mode(context: Context) -> str:
        if not context or context.get("channel_type") != const.WECHAT_GROUP:
            return "interactive_session"
        mode = str(context.get("wechat_group_agent_history_mode") or "").strip()
        if mode in {"fresh", "interactive_session", "observe_only"}:
            return mode
        return "interactive_session"

    @staticmethod
    def _prepare_agent_history_for_mode(agent, history_mode: str):
        if history_mode not in {"fresh", "observe_only"}:
            return None
        snapshot = None
        if history_mode == "observe_only":
            with agent.messages_lock:
                snapshot = {
                    "messages": copy.deepcopy(list(agent.messages)),
                    "last_run_new_messages": copy.deepcopy(
                        list(getattr(agent, "_last_run_new_messages", []) or [])
                    ),
                    "stream_executor": getattr(agent, "stream_executor", None),
                }
                agent.messages = []
                agent._last_run_new_messages = []
            return snapshot
        with agent.messages_lock:
            agent.messages = []
            agent._last_run_new_messages = []
        return None

    @staticmethod
    def _restore_agent_history_snapshot(agent, snapshot) -> None:
        if not agent or not isinstance(snapshot, dict):
            return
        with agent.messages_lock:
            agent.messages = copy.deepcopy(list(snapshot.get("messages") or []))
            agent._last_run_new_messages = copy.deepcopy(
                list(snapshot.get("last_run_new_messages") or [])
            )
            previous_executor = snapshot.get("stream_executor")
            if previous_executor is None:
                try:
                    delattr(agent, "stream_executor")
                except AttributeError:
                    pass
            else:
                agent.stream_executor = previous_executor

    @staticmethod
    def _history_visibility_extras(context: Context, visibility: str) -> dict:
        if visibility != "observe_only":
            return {}
        extras = {
            "history_visibility": "observe_only",
            "channel_type": const.WECHAT_GROUP,
        }
        if context:
            room_id = str(context.get("wechat_group_stable_room_id") or "").strip()
            member_id = str(context.get("wechat_group_stable_member_id") or "").strip()
            if room_id:
                extras["stable_room_id"] = room_id
            if member_id:
                extras["stable_member_id"] = member_id
        return extras

    @staticmethod
    def _build_observed_exchange(user_text: str, assistant_text: str) -> list:
        messages = []
        if str(user_text or "").strip():
            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": str(user_text)}],
            })
        if str(assistant_text or "").strip():
            messages.append({
                "role": "assistant",
                "content": [{"type": "text", "text": str(assistant_text)}],
            })
        return messages

    def _start_fresh_persistent_context(self, session_id: str, context: Context) -> None:
        if not session_id or not context or context.get("channel_type") != const.WECHAT_GROUP:
            return
        try:
            if not conf().get("conversation_persistence", True):
                return
            from agent.memory import get_conversation_store
            get_conversation_store().clear_context(session_id)
        except Exception as e:
            logger.warning(
                f"[AgentBridge] Failed to start fresh context for session={session_id}: {e}"
            )

    @staticmethod
    def _reload_thread_agent_from_store(
        agent,
        session_id: str,
        thread_id: str,
    ) -> int:
        if not agent or not session_id or not thread_id:
            return -1
        if not (hasattr(agent, "messages") and hasattr(agent, "messages_lock")):
            return -1
        try:
            from agent.memory import get_conversation_store

            saved = get_conversation_store().load_messages(
                session_id,
                max_turns=10**6,
                thread_id=thread_id,
            )
            with agent.messages_lock:
                agent.messages = [
                    {"role": item["role"], "content": item["content"]}
                    for item in saved
                ]
                if hasattr(agent, "_last_run_new_messages"):
                    agent._last_run_new_messages = []
            return len(saved)
        except Exception as e:
            logger.warning(
                "[AgentBridge] Failed to reload thread after delivery: "
                "session=%s thread=%s error=%s",
                session_id,
                thread_id,
                e,
            )
            return -1

    def _discard_pending_thread_turn(
        self,
        session_id: str,
        thread_id: str,
        request_id: str,
        agent=None,
    ) -> int:
        removed = 0
        if session_id and thread_id and request_id:
            try:
                from agent.memory import get_conversation_store

                removed = get_conversation_store().discard_pending_thread_turn(
                    session_id,
                    thread_id,
                    request_id,
                )
            except Exception as e:
                logger.warning(
                    "[AgentBridge] Failed to discard pending thread turn: "
                    "session=%s thread=%s request=%s error=%s",
                    session_id,
                    thread_id,
                    request_id,
                    e,
                )
        target = agent
        if target is None:
            cache_key = self._agent_cache_key(session_id, thread_id)
            with self._agent_cache_lock():
                target = self.agents.get(cache_key)
        if target is not None:
            self._reload_thread_agent_from_store(target, session_id, thread_id)
        return removed

    def _persist_observe_only_assistant(
        self,
        session_id: str,
        response: str,
        context: Context,
    ) -> None:
        if not session_id or not str(response or "").strip():
            return
        try:
            if not conf().get("conversation_persistence", True):
                return
            from agent.memory import get_conversation_store
            extras = self._history_visibility_extras(context, "observe_only")
            get_conversation_store().append_messages(
                session_id,
                [{
                    "role": "assistant",
                    "content": [{"type": "text", "text": str(response)}],
                    "extras": extras,
                }],
                channel_type=(context.get("channel_type") or "") if context else "",
            )
        except Exception as e:
            logger.warning(
                f"[AgentBridge] Failed to persist observe-only assistant for session={session_id}: {e}"
            )

    def _pre_persist_user_message(
        self,
        session_id: str,
        query: str,
        context: Context,
        clear_history: bool,
        thread_id: str = "",
    ) -> bool:
        """Persist the user's message before the agent runs.

        This makes a brand-new session (and the user's bubble) visible even if
        the reply hasn't finished — switching away or refreshing no longer
        loses the in-flight session. Returns True when the user turn was
        stored, so the caller can skip it in the post-run persist.

        Best-effort: any failure is swallowed and reported as not-persisted.
        """
        if not session_id or not query:
            return False
        # Only real user turns: skip scheduler-injected / scheduled-task runs.
        if session_id.startswith("scheduler_") or (
            context and context.get("is_scheduled_task")
        ):
            return False
        try:
            from config import conf
            if not conf().get("conversation_persistence", True):
                return False
            from agent.memory import get_conversation_store
            store = get_conversation_store()
            # clear_history starts a fresh transcript: wipe the store first so
            # the eager user turn becomes seq 0, matching in-memory state.
            if clear_history:
                store.clear_session(session_id)
            channel_type = (context.get("channel_type") or "") if context else ""
            user_msg = {
                "role": "user",
                "content": [{"type": "text", "text": query}],
            }
            if context and context.get("wechat_group_inbound_archive_row_id"):
                user_msg["extras"] = {
                    "source_event_id": "inbound:{}".format(
                        int(context.get("wechat_group_inbound_archive_row_id") or 0)
                    )
                }
            if self._resolve_agent_history_mode(context) == "observe_only":
                extras = dict(user_msg.get("extras") or {})
                extras.update(self._history_visibility_extras(context, "observe_only"))
                user_msg["extras"] = extras
            store.append_messages(
                session_id,
                [user_msg],
                channel_type=channel_type,
                thread_id=thread_id,
            )
            return True
        except Exception as e:
            logger.warning(
                f"[AgentBridge] Failed to pre-persist user message for session={session_id}: {e}"
            )
            return False

    def _select_persisted_user_query(self, query: str, context: Context) -> str:
        if not context:
            return query
        try:
            if context.get("channel_type") != const.WECHAT_GROUP:
                return query
            raw = context.get("wechat_group_user_content")
            if isinstance(raw, str) and raw.strip():
                return raw
        except Exception:
            return query
        return query

    def _sanitize_wechat_group_runtime_messages(self, agent, enhanced_query: str, raw_query: str) -> bool:
        if not agent or not enhanced_query or not raw_query or enhanced_query == raw_query:
            return False
        if not (hasattr(agent, "messages") and hasattr(agent, "messages_lock")):
            return False
        changed = False
        with agent.messages_lock:
            for message in reversed(agent.messages):
                if self._message_text_equals(message, enhanced_query):
                    changed = self._replace_message_text(message, raw_query) or changed
                    break
            new_messages = getattr(agent, "_last_run_new_messages", None)
            if isinstance(new_messages, list):
                for message in new_messages:
                    if self._message_text_equals(message, enhanced_query):
                        changed = self._replace_message_text(message, raw_query) or changed
                        break
        return changed

    @staticmethod
    def _message_text_equals(message, expected: str) -> bool:
        if not isinstance(message, dict) or message.get("role") != "user":
            return False
        content = message.get("content")
        if isinstance(content, str):
            return content == expected
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text") == expected
        return False

    @staticmethod
    def _replace_message_text(message, value: str) -> bool:
        content = message.get("content")
        if isinstance(content, str):
            message["content"] = value
            return True
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    block["text"] = value
                    return True
        return False

    def _persist_messages(
        self,
        session_id: str,
        new_messages: list,
        channel_type: str = "",
        thread_id: str = "",
        delivery_request_id: str = "",
        inbound_source_event_id: str = "",
    ) -> bool:
        """
        Persist new messages to the conversation store after each agent run.

        Failures are logged but never propagate — they must not interrupt replies.
        """
        if not new_messages:
            return False
        try:
            from config import conf
            if not conf().get("conversation_persistence", True):
                return False
            # When deep-thinking display is disabled, strip "thinking" content
            # blocks before persisting so they don't resurface on history reload.
            # The in-memory message list keeps them intact for this run's
            # multi-turn LLM context.
            thinking_enabled = bool(conf().get("enable_thinking", False))
        except Exception:
            thinking_enabled = False

        messages_to_store = new_messages
        if not thinking_enabled or channel_type == const.WECHAT_GROUP:
            messages_to_store = self._strip_thinking_blocks(new_messages)
        if thread_id:
            messages_to_store = self._thread_text_only_messages(messages_to_store)
            roles = {str(item.get("role") or "") for item in messages_to_store}
            if roles != {"user", "assistant"}:
                logger.warning(
                    "[AgentBridge] Skip incomplete WeChat group thread turn: "
                    "session=%s thread=%s roles=%s",
                    session_id,
                    thread_id,
                    sorted(roles),
                )
                return False
        if thread_id and delivery_request_id:
            staged_messages = []
            for message in messages_to_store:
                staged = dict(message)
                extras = dict(staged.get("extras") or {})
                extras.update({
                    "delivery_state": "pending",
                    "delivery_request_id": str(delivery_request_id),
                })
                if staged.get("role") == "user" and inbound_source_event_id:
                    extras["source_event_id"] = str(inbound_source_event_id)
                staged["extras"] = extras
                staged_messages.append(staged)
            messages_to_store = staged_messages

        if not messages_to_store:
            return False

        try:
            from agent.memory import get_conversation_store
            get_conversation_store().append_messages(
                session_id,
                messages_to_store,
                channel_type=channel_type,
                thread_id=thread_id,
            )
            return True
        except Exception as e:
            logger.warning(
                f"[AgentBridge] Failed to persist messages for session={session_id}: {e}"
            )
            return False

    @staticmethod
    def _thread_text_only_messages(messages: list) -> list:
        """Keep the first real user text and the final assistant text only."""
        first_user = None
        last_assistant = None
        for message in messages or []:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "")
            if role not in {"user", "assistant"}:
                continue
            content = message.get("content")
            if isinstance(content, str):
                text_blocks = (
                    [{"type": "text", "text": content}]
                    if content.strip()
                    else []
                )
            elif isinstance(content, list):
                text_blocks = [
                    dict(block)
                    for block in content
                    if isinstance(block, dict)
                    and block.get("type") == "text"
                    and str(block.get("text") or "").strip()
                ]
            else:
                text_blocks = []
            if not text_blocks:
                continue
            cleaned = dict(message)
            cleaned["content"] = text_blocks
            if role == "user" and first_user is None:
                first_user = cleaned
            elif role == "assistant":
                last_assistant = cleaned
        return [item for item in (first_user, last_assistant) if item is not None]

    @staticmethod
    def _stage_wechat_group_delivery(
        session_id: str,
        thread_id: str,
        action: str,
        request_id: str,
        messages: list,
        context: Context,
    ) -> None:
        if not context or context.get("channel_type") != const.WECHAT_GROUP:
            return
        msg = context.get("msg")
        try:
            ttl_seconds = max(
                int(context.get("wechat_group_thread_ttl_seconds") or 900),
                60,
            )
        except (TypeError, ValueError):
            ttl_seconds = 900
        pending = {
            "state": "pending",
            "owner_session_id": str(session_id or ""),
            "thread_id": str(thread_id or ""),
            "request_id": str(request_id or ""),
            "action": str(action or "new_thread"),
            "stable_room_id": str(
                context.get("wechat_group_stable_room_id") or ""
            ),
            "stable_member_id": str(
                context.get("wechat_group_stable_member_id") or ""
            ),
            "message_id": str(getattr(msg, "msg_id", "") or ""),
            "ttl_seconds": ttl_seconds,
            "reason": str(context.get("wechat_group_session_reason") or ""),
        }
        context["wechat_group_pending_agent_delivery"] = pending
        tool_continuation_enabled = conf().get(
            "wechat_group_tool_continuation_enabled",
            False,
        )
        if not tool_continuation_enabled:
            return
        try:
            from channel.wechat_group.wechat_group_continuation_store import (
                build_safe_continuation_capsule,
            )

            capsule = build_safe_continuation_capsule(messages)
            if capsule:
                pending["continuation_capsule"] = capsule
                pending["continuation_ttl_seconds"] = min(ttl_seconds, 15 * 60)
        except Exception as e:
            logger.warning(
                "[AgentBridge] Failed to stage WeChat group continuation: %s",
                e,
            )

    # Marker used to identify scheduler-injected user messages so we can apply
    # a sliding window without touching real user turns. The legacy prefix
    # "Scheduled task" (written by the v2 PR) is also recognised when pruning,
    # so old data can be aged out instead of leaking forever.
    _SCHEDULED_MARKER = "[SCHEDULED]"
    _SCHEDULED_LEGACY_MARKERS = ("Scheduled task",)

    def remember_scheduled_output(
        self,
        session_id: str,
        content: str,
        channel_type: str = "",
        task_description: str = "",
    ) -> None:
        """Add the visible output of a scheduled task to the receiver's session.

        Scheduled task execution uses an isolated session so internal planning and
        tool calls do not leak into the user's chat. The final message is still
        part of the conversation from the user's point of view, so keep a small
        visible turn in the receiver session for follow-up questions.

        Configuration:
            scheduler_inject_to_session (bool, default True):
                Master switch. When False, this method is a no-op.
            scheduler_inject_max_per_session (int, default 3):
                Maximum scheduler-injected user/assistant pairs retained per
                session. Older injections are pruned automatically.

        Content is truncated to 2000 chars to prevent a single high-volume task
        from bloating one entry.
        """
        from config import conf
        if not conf().get("scheduler_inject_to_session", True):
            return
        if not session_id or not content:
            return

        max_len = 2000
        if len(content) > max_len:
            content = content[:max_len] + "..."

        user_text = self._SCHEDULED_MARKER
        if task_description:
            user_text = f"{self._SCHEDULED_MARKER} {task_description}"

        messages = [
            {"role": "user", "content": [{"type": "text", "text": user_text}]},
            {"role": "assistant", "content": [{"type": "text", "text": content}]},
        ]

        # Persist first so the new pair gets a stable seq, then prune old
        # scheduler pairs in DB, then sync the in-memory agent.messages buffer.
        self._persist_messages(session_id, messages, channel_type)

        keep_last_n = max(int(conf().get("scheduler_inject_max_per_session", 3) or 0), 0)
        try:
            from agent.memory import get_conversation_store
            deleted = get_conversation_store().prune_scheduled_messages(
                session_id, keep_last_n=keep_last_n
            )
            if deleted:
                logger.debug(
                    f"[AgentBridge] Pruned {deleted} old scheduler messages "
                    f"for session={session_id} (keep_last_n={keep_last_n})"
                )
        except Exception as e:
            logger.warning(
                f"[AgentBridge] Failed to prune scheduled messages "
                f"for session={session_id}: {e}"
            )

        agent = self.agents.get(session_id)
        if agent:
            try:
                with agent.messages_lock:
                    agent.messages.extend(messages)
                    self._prune_scheduled_in_memory(agent, keep_last_n)
            except Exception as e:
                logger.warning(
                    f"[AgentBridge] Failed to update in-memory scheduled output "
                    f"for session={session_id}: {e}"
                )

    @staticmethod
    def _trim_in_memory_to_turns(agent, keep_turns: int) -> None:
        """Bound ``agent.messages`` to the most recent ``keep_turns`` real
        user/assistant turns, dropping older history together with any
        intermediate tool_use/tool_result blocks that belonged to it.

        A "real" user message is any user message whose content is not solely a
        tool_result block — matches the heuristic used elsewhere when filtering
        history (see ``AgentInitializer._filter_text_only_messages``).

        No-op when the session is already within budget. Caller does not need
        to hold the lock; this method acquires it itself.
        """
        if not (hasattr(agent, "messages") and hasattr(agent, "messages_lock")):
            return
        if keep_turns <= 0:
            return

        def _is_real_user(msg) -> bool:
            if not isinstance(msg, dict) or msg.get("role") != "user":
                return False
            content = msg.get("content")
            if isinstance(content, list):
                if any(
                    isinstance(b, dict) and b.get("type") == "tool_result"
                    for b in content
                ):
                    return False
                return any(
                    isinstance(b, dict) and b.get("type") == "text" and b.get("text")
                    for b in content
                )
            if isinstance(content, str):
                return bool(content.strip())
            return False

        with agent.messages_lock:
            msgs = agent.messages
            real_user_indices = [i for i, m in enumerate(msgs) if _is_real_user(m)]
            if len(real_user_indices) <= keep_turns:
                return

            # Cut at the (k-th from the end) real user message; keep everything
            # from there onwards so the surviving slice is still a valid
            # user/assistant sequence.
            cut_idx = real_user_indices[-keep_turns]
            if cut_idx == 0:
                return

            kept = msgs[cut_idx:]
            msgs.clear()
            msgs.extend(kept)
            logger.debug(
                f"[AgentBridge] Trimmed in-memory messages to last "
                f"{keep_turns} turns ({len(kept)} messages remain)"
            )

    @classmethod
    def _prune_scheduled_in_memory(cls, agent, keep_last_n: int) -> None:
        """Mirror conversation_store.prune_scheduled_messages on agent.messages.

        Caller must hold ``agent.messages_lock``.
        """
        if keep_last_n < 0:
            keep_last_n = 0

        markers = (cls._SCHEDULED_MARKER,) + cls._SCHEDULED_LEGACY_MARKERS

        def _is_marker_user(msg) -> bool:
            if not isinstance(msg, dict) or msg.get("role") != "user":
                return False
            content = msg.get("content")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        break
            return any(text.startswith(m) for m in markers)

        msgs = agent.messages
        pair_indices = []  # list of (user_idx, assistant_idx_or_None)
        for idx, msg in enumerate(msgs):
            if not _is_marker_user(msg):
                continue
            assistant_idx = None
            if idx + 1 < len(msgs):
                nxt = msgs[idx + 1]
                if isinstance(nxt, dict) and nxt.get("role") == "assistant":
                    assistant_idx = idx + 1
            pair_indices.append((idx, assistant_idx))

        if len(pair_indices) <= keep_last_n:
            return

        to_drop = pair_indices[: len(pair_indices) - keep_last_n]
        drop_set = set()
        for u_idx, a_idx in to_drop:
            drop_set.add(u_idx)
            if a_idx is not None:
                drop_set.add(a_idx)

        # Rebuild the list in place to keep external references stable.
        kept = [m for i, m in enumerate(msgs) if i not in drop_set]
        msgs.clear()
        msgs.extend(kept)

    @staticmethod
    def _strip_thinking_blocks(messages: list) -> list:
        """Return a shallow copy of messages with assistant "thinking" blocks removed."""
        cleaned = []
        for msg in messages:
            if not isinstance(msg, dict):
                cleaned.append(msg)
                continue
            if msg.get("role") != "assistant":
                cleaned.append(msg)
                continue
            content = msg.get("content")
            if not isinstance(content, list):
                cleaned.append(msg)
                continue
            filtered_blocks = [
                b for b in content
                if not (isinstance(b, dict) and b.get("type") == "thinking")
            ]
            if len(filtered_blocks) == len(content):
                cleaned.append(msg)
            else:
                new_msg = dict(msg)
                new_msg["content"] = filtered_blocks
                cleaned.append(new_msg)
        return cleaned

    def clear_session(self, session_id: str):
        """
        Clear a specific session's agent and conversation history
        
        Args:
            session_id: Session identifier to clear
        """
        with self._agent_cache_lock():
            keys = [
                key for key in self.agents
                if (key[0] if isinstance(key, tuple) else key) == session_id
            ]
            if keys:
                logger.info(f"[AgentBridge] Clearing session: {session_id}")
                for key in keys:
                    del self.agents[key]
    
    def clear_all_sessions(self):
        """Clear all agent sessions"""
        with self._agent_cache_lock():
            logger.info(f"[AgentBridge] Clearing all sessions ({len(self.agents)} total)")
            self.agents.clear()
            self.default_agent = None
    
    def refresh_all_skills(self) -> int:
        """
        Refresh skills and conditional tools in all agent instances after
        environment variable changes. This allows hot-reload without restarting.

        Returns:
            Number of agent instances refreshed
        """
        import os
        from dotenv import load_dotenv
        from config import conf

        # Reload environment variables from .env file
        workspace_root = expand_path(conf().get("agent_workspace", "~/lightagent"))
        env_file = os.path.join(workspace_root, '.env')

        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
            logger.info(f"[AgentBridge] Reloaded environment variables from {env_file}")

        refreshed_count = 0

        # Collect all agent instances to refresh
        agents_to_refresh = []
        if self.default_agent:
            agents_to_refresh.append(("default", self.default_agent))
        for session_id, agent in self.agent_items_snapshot():
            agents_to_refresh.append((session_id, agent))

        for label, agent in agents_to_refresh:
            # Refresh skills
            if hasattr(agent, 'skill_manager') and agent.skill_manager:
                agent.skill_manager.refresh_skills()

            # Refresh conditional tools (e.g. web_search depends on API keys)
            self._refresh_conditional_tools(agent)

            refreshed_count += 1

        if refreshed_count > 0:
            logger.info(f"[AgentBridge] Refreshed skills & tools in {refreshed_count} agent instance(s)")

        return refreshed_count

    @staticmethod
    def _refresh_conditional_tools(agent):
        """
        Add or remove conditional tools based on current environment variables.
        For example, web_search should only be present when BOCHA_API_KEY or
        LINKAI_API_KEY is set.
        """
        try:
            from agent.tools.web_search.web_search import WebSearch

            has_tool = any(t.name == "web_search" for t in agent.tools)
            available = WebSearch.is_available()

            if available and not has_tool:
                # API key was added - inject the tool
                tool = WebSearch()
                tool.model = agent.model
                agent.tools.append(tool)
                logger.info("[AgentBridge] web_search tool added (API key now available)")
            elif not available and has_tool:
                # API key was removed - remove the tool
                agent.tools = [t for t in agent.tools if t.name != "web_search"]
                logger.info("[AgentBridge] web_search tool removed (API key no longer available)")
        except Exception as e:
            logger.debug(f"[AgentBridge] Failed to refresh conditional tools: {e}")
