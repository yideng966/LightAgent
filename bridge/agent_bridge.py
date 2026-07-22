"""
Agent Bridge - Integrates Agent system with existing LightAgent bridge
"""

import os
import re
import threading
import time
import types
from typing import Optional, List

from agent.protocol import Agent, LLMModel, LLMRequest, get_cancel_registry
from bridge.agent_event_handler import AgentEventHandler
from bridge.agent_initializer import AgentInitializer
from bridge.bridge import Bridge
from bridge.context import Context
from bridge.reply import Reply, ReplyType
from common import const
from common.log import logger
from common.utils import expand_path
from config import conf
from models.openai_compatible_bot import OpenAICompatibleBot


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


_MODEL_FAILOVER_STATE_INIT_LOCK = threading.Lock()


class AgentLLMModel(LLMModel):
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

    def __init__(self, bridge: Bridge, bot_type: str = "chat", failover_state=None):
        super().__init__(model=conf().get("model", const.GPT_41))
        self.bridge = bridge
        self.bot_type = bot_type
        self._bot = None
        self._bot_model = None
        self._candidate_bots = {}
        self._failover_state = failover_state or self._shared_failover_state(bridge)

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

    def _configure_custom_candidate_bot(self, bot, candidate):
        bot_type = candidate.get("bot_type") or ""
        try:
            from models.custom_provider import get_custom_providers, parse_custom_bot_type
            is_custom, provider_id = parse_custom_bot_type(bot_type)
            if not is_custom or not provider_id:
                return bot

            provider = None
            for item in get_custom_providers():
                if item.get("id") == provider_id:
                    provider = item
                    break
            if not provider:
                return bot

            api_key = provider.get("api_key", "")
            api_base = provider.get("api_base") or None
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
            try:
                from models.openai.openai_http_client import OpenAIHTTPClient
                bot._http_client = OpenAIHTTPClient(
                    api_key=api_key,
                    api_base=api_base,
                    proxy=proxy,
                )
            except Exception as e:
                logger.warning(f"[AgentLLMModel] failed to prepare custom fallback http client: {e}")

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
        except Exception as e:
            logger.warning(f"[AgentLLMModel] failed to configure custom fallback bot: {e}")
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
        }
        if request.max_tokens is not None:
            kwargs['max_tokens'] = request.max_tokens

        system_prompt = getattr(request, 'system', None)
        if system_prompt:
            kwargs['system'] = system_prompt

        channel_type = getattr(self, 'channel_type', None) or ''
        if channel_type:
            kwargs['channel_type'] = channel_type
        session_id = getattr(self, 'session_id', None)
        if session_id:
            kwargs['session_id'] = session_id

        thinking_enabled = bool(conf().get("enable_thinking", False))
        kwargs['thinking'] = (
            {"type": "enabled"} if thinking_enabled
            else {"type": "disabled"}
        )
        if thinking_enabled:
            effort = conf().get("reasoning_effort", "high")
            if effort in ("high", "max"):
                kwargs['reasoning_effort'] = effort
        return kwargs

    def _call_candidate(self, request: LLMRequest, candidate, stream: bool):
        bot = self._get_bot_for_candidate(candidate)
        if not hasattr(bot, 'call_with_tools'):
            bot_type = type(bot).__name__
            raise NotImplementedError(f"Bot {bot_type} does not support call_with_tools. Please add the method.")
        return bot.call_with_tools(**self._build_call_kwargs(request, candidate, stream))

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

    @staticmethod
    def _mark_fallback_exhausted(payload):
        if not isinstance(payload, dict):
            return payload
        marked = dict(payload)
        marked["model_fallback_exhausted"] = True
        return marked

    def call(self, request: LLMRequest):
        """
        Call the model using LightAgent's bot infrastructure
        """
        try:
            candidates = self._build_model_candidates()
            last_response = None
            for index, candidate in enumerate(candidates):
                try:
                    response = self._call_candidate(request, candidate, stream=False)
                    response = self._format_response(response)
                    is_transient = self._is_transient_model_error_payload(response)
                    if is_transient:
                        self._record_primary_transient_failure(candidate, candidates)
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
                    if is_transient and candidate.get("source") == "fallback":
                        return self._mark_fallback_exhausted(response)
                    return response
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
                        raise exhausted_error from e
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
            candidates = self._build_model_candidates()
            last_error_chunk = None
            for index, candidate in enumerate(candidates):
                yielded_any = False
                retry_next = False
                primary_health_recorded = False
                try:
                    stream = self._call_candidate(request, candidate, stream=True)
                    for chunk in stream:
                        is_error = isinstance(chunk, dict) and bool(chunk.get("error"))
                        is_transient = is_error and self._is_transient_model_error_payload(chunk)
                        if candidate.get("source") == "primary" and is_error:
                            if is_transient:
                                self._record_primary_transient_failure(candidate, candidates)
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
                            self._log_model_fallback(candidate, next_candidate, chunk)
                            last_error_chunk = chunk
                            retry_next = True
                            break
                        if is_transient and candidate.get("source") == "fallback":
                            chunk = self._mark_fallback_exhausted(chunk)
                        if candidate.get("source") == "primary" and not primary_health_recorded:
                            self._record_primary_healthy(candidate)
                            primary_health_recorded = True
                        yielded_any = True
                        yield self._format_stream_chunk(chunk)
                    if retry_next:
                        continue
                    if candidate.get("source") == "primary" and not primary_health_recorded:
                        self._record_primary_healthy(candidate)
                    return
                except Exception as e:
                    is_transient = self._is_transient_model_error_text(str(e))
                    if candidate.get("source") == "primary":
                        if is_transient:
                            self._record_primary_transient_failure(candidate, candidates)
                        else:
                            self._record_primary_healthy(candidate)
                    if (
                        not yielded_any
                        and is_transient
                        and index + 1 < len(candidates)
                    ):
                        next_candidate = candidates[index + 1]
                        self._log_model_fallback(candidate, next_candidate, e)
                        continue
                    if is_transient and candidate.get("source") == "fallback":
                        exhausted_error = RuntimeError(str(e))
                        exhausted_error.model_fallback_exhausted = True
                        raise exhausted_error from e
                    raise
            if last_error_chunk is not None:
                yield self._format_stream_chunk(last_error_chunk)
                
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


class AgentBridge:
    """
    Bridge class that integrates super Agent with LightAgent
    Manages multiple agent instances per session for conversation isolation
    """
    
    def __init__(self, bridge: Bridge):
        self.bridge = bridge
        self.agents = {}  # session_id -> Agent instance mapping
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
    
    def get_agent(self, session_id: str = None) -> Optional[Agent]:
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
        if session_id not in self.agents:
            self._init_agent_for_session(session_id)
        
        return self.agents[session_id]
    
    def _init_default_agent(self):
        """Initialize default super agent"""
        agent = self.initializer.initialize_agent(session_id=None)
        self.default_agent = agent
    
    def _init_agent_for_session(self, session_id: str):
        """Initialize agent for a specific session"""
        agent = self.initializer.initialize_agent(session_id=session_id)
        self.agents[session_id] = agent

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
        if not session_id or session_id not in self.agents:
            return -1
        agent = self.agents[session_id]
        if not (hasattr(agent, "messages") and hasattr(agent, "messages_lock")):
            return -1
        try:
            from agent.memory import get_conversation_store
            store = get_conversation_store()
            # No turn cap here: we want a faithful mirror of what the store
            # has for this session after deletion.
            remaining = store.load_messages(session_id, max_turns=10**6)
        except Exception as e:
            logger.warning(
                f"[AgentBridge] Failed to load messages for sync (session={session_id}): {e}"
            )
            return -1
        with agent.messages_lock:
            agent.messages.clear()
            for msg in remaining:
                agent.messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })
            count = len(agent.messages)
        logger.info(
            f"[AgentBridge] Synced agent memory for session={session_id}, messages={count}"
        )
        return count

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
        agent = None
        request_id = None
        cancel_event = None
        try:
            # Extract session_id from context for user isolation
            if context:
                session_id = context.kwargs.get("session_id") or context.get("session_id")
                request_id = context.kwargs.get("request_id") or context.get("request_id")

            # Register a cancel token. Prefer per-turn request_id (web),
            # fall back to session_id (IM channels). The Event is polled by
            # AgentStreamExecutor at safe checkpoints.
            registry = get_cancel_registry()
            token_key = request_id or session_id
            if token_key:
                cancel_event = registry.register(token_key, session_id=session_id)

            # Get agent for this session (will auto-initialize if needed)
            agent = self.get_agent(session_id=session_id)
            if not agent:
                return Reply(ReplyType.ERROR, "Failed to initialize super agent")
            
            # Create event handler for logging and channel communication
            event_handler = AgentEventHandler(context=context, original_callback=on_event)
            
            # Filter tools based on context
            original_tools = agent.tools
            original_extra_system_suffix = getattr(agent, "extra_system_suffix", "")
            filtered_tools = original_tools
            tools_modified = False
            suffix_modified = False
            
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
                agent.extra_system_suffix = (
                    f"{original_extra_system_suffix}\n\n{suffix}".strip()
                    if original_extra_system_suffix else suffix
                )
                suffix_modified = True
            
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
            pre_persisted = self._pre_persist_user_message(
                session_id, persisted_user_query, context, clear_history
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
                    cancel_event=cancel_event,
                    context=context,
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

            # Persist new messages generated during this run
            if session_id:
                channel_type = (context.get("channel_type") or "") if context else ""
                if persisted_user_query != query:
                    self._sanitize_wechat_group_runtime_messages(agent, query, persisted_user_query)
                new_messages = list(getattr(agent, '_last_run_new_messages', []))
                # The leading user turn was already persisted eagerly above;
                # drop it here so it isn't stored twice.
                if pre_persisted and new_messages and new_messages[0].get("role") == "user":
                    new_messages = new_messages[1:]
                if new_messages:
                    self._persist_messages(session_id, list(new_messages), channel_type)
                elif hasattr(agent, "messages") and hasattr(agent, "messages_lock"):
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
            ):
                try:
                    from agent.evolution.trigger import note_user_turn
                    ch = (context.get("channel_type") or "") if context else ""
                    rcv = (context.get("receiver") or "") if context else ""
                    is_group = bool(context.get("isgroup")) if context else False
                    # Only enable proactive push for single chats (group push is
                    # noisy); group sessions still evolve, just without notify.
                    note_user_turn(agent, channel_type=ch, receiver=(rcv if not is_group else ""))
                except Exception:
                    pass

            # Post-message hot-reload: detect edits to ~/lightagent/mcp.json and
            # sync any new/removed MCP tools into the live agent in the
            # background. Off the critical path so user latency is unaffected;
            # changes take effect on the user's next message.
            self._schedule_mcp_hot_reload(agent)

            # Check if there are files to send (from send/read tool)
            if hasattr(agent, 'stream_executor') and hasattr(agent.stream_executor, 'files_to_send'):
                files_to_send = agent.stream_executor.files_to_send
                if files_to_send:
                    # Send the first file (for now, handle one file at a time)
                    file_info = files_to_send[0]
                    logger.info(f"[AgentBridge] Sending file: {file_info.get('path')}")
                    
                    # Clear files_to_send for next request
                    agent.stream_executor.files_to_send = []
                    
                    # Return file reply based on file type
                    return self._create_file_reply(file_info, response, context)
            
            return Reply(ReplyType.TEXT, response)
            
        except Exception as e:
            logger.error(f"Agent reply error: {e}")
            # If the agent cleared its messages due to format error / overflow,
            # also purge the DB so the next request starts clean.
            if session_id and agent:
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
            from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
            from channel.wechat_group.wechat_group_sticker_service import WechatGroupStickerService
            from channel.wechat_group.wechat_group_sticker_tools import create_wechat_group_sticker_tools

            return create_wechat_group_memory_tools(
                knowledge_service=WechatGroupKnowledgeService(),
                profile_service=WechatGroupProfileService(
                    identity_service=WechatGroupIdentityService(),
                ),
                room_id=room_id,
                sender_id=sender_id,
                bot_sender_id=context.get("wechat_group_bot_sender_id") or "",
            ) + create_wechat_group_sticker_tools(
                sticker_service=WechatGroupStickerService(),
                room_id=room_id,
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
            "- For current group member roles, preferences, expertise, interaction "
            "style, boundaries, or profile facts, prefer calling "
            "`wechat_group_profile_get` before answering.\n"
            "- When a sticker reply fits better than plain text, prefer calling "
            "`wechat_group_sticker_search` first and then `wechat_group_sticker_send` "
            "with an exact sticker_id or online_id from the search result. Prefer "
            "local stickers; use online candidates only when local stickers are "
            "missing or unsuitable. Do not expose or invent raw sticker URLs.\n"
            "- These tools are bound to the current WeChat group by the server. "
            "Do not treat them as global memory or cross-group search tools."
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
    
    def _pre_persist_user_message(
        self, session_id: str, query: str, context: Context, clear_history: bool
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
            store.append_messages(session_id, [user_msg], channel_type=channel_type)
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
            if not conf().get("wechat_group_context_persist_raw_user_only", True):
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
        self, session_id: str, new_messages: list, channel_type: str = ""
    ) -> None:
        """
        Persist new messages to the conversation store after each agent run.

        Failures are logged but never propagate — they must not interrupt replies.
        """
        if not new_messages:
            return
        try:
            from config import conf
            if not conf().get("conversation_persistence", True):
                return
            # When deep-thinking display is disabled, strip "thinking" content
            # blocks before persisting so they don't resurface on history reload.
            # The in-memory message list keeps them intact for this run's
            # multi-turn LLM context.
            thinking_enabled = bool(conf().get("enable_thinking", False))
        except Exception:
            thinking_enabled = False

        messages_to_store = new_messages
        if not thinking_enabled:
            messages_to_store = self._strip_thinking_blocks(new_messages)

        try:
            from agent.memory import get_conversation_store
            get_conversation_store().append_messages(
                session_id, messages_to_store, channel_type=channel_type
            )
        except Exception as e:
            logger.warning(
                f"[AgentBridge] Failed to persist messages for session={session_id}: {e}"
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
        if session_id in self.agents:
            logger.info(f"[AgentBridge] Clearing session: {session_id}")
            del self.agents[session_id]
    
    def clear_all_sessions(self):
        """Clear all agent sessions"""
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
        for session_id, agent in self.agents.items():
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
