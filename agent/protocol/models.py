"""
Models module for agent system.
Provides basic model classes needed by tools and bridge integration.
"""

import copy
from typing import Any, Dict, List, Optional


class LLMRequest:
    """Request model for LLM operations"""
    
    def __init__(self, messages: List[Dict[str, str]] = None, model: Optional[str] = None,
                 temperature: float = 0.7, max_tokens: Optional[int] = None, 
                 stream: bool = False, tools: Optional[List] = None, **kwargs):
        self.messages = messages or []
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stream = stream
        self.tools = tools
        # Allow extra attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


class LLMRequestSourceSnapshot:
    """候选调用前冻结的 Provider 无关请求源。"""

    __slots__ = ("_request_state", "_source_metadata")

    def __init__(
        self,
        messages=None,
        model=None,
        temperature=0.7,
        max_tokens=None,
        stream=False,
        tools=None,
        source_metadata=None,
        **kwargs,
    ):
        state = {
            "messages": messages or [],
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "tools": tools,
            **kwargs,
        }
        object.__setattr__(self, "_request_state", copy.deepcopy(state))
        object.__setattr__(
            self,
            "_source_metadata",
            copy.deepcopy(source_metadata or {}),
        )

    def __setattr__(self, name, value):
        raise AttributeError("LLMRequestSourceSnapshot is immutable")

    @classmethod
    def from_request(cls, request: "LLMRequest") -> "LLMRequestSourceSnapshot":
        state = {
            key: value
            for key, value in vars(request).items()
            if key not in {"_source_snapshot", "_source_metadata", "_cancel_event"}
        }
        return cls(
            source_metadata=getattr(request, "_source_metadata", None),
            **state,
        )

    def build_request(self) -> LLMRequest:
        """从冻结源重新创建完整且嵌套对象独立的请求。"""
        return LLMRequest(**copy.deepcopy(self._request_state))

    def source_metadata(self) -> Dict[str, Any]:
        return copy.deepcopy(self._source_metadata)


class LLMModel:
    """Base class for LLM models"""
    
    def __init__(self, model: str = None, **kwargs):
        self.model = model
        self.config = kwargs
    
    def call(self, request: LLMRequest):
        """
        Call the model with a request.
        This is a placeholder implementation.
        """
        raise NotImplementedError("LLMModel.call not implemented in this context")
    
    def call_stream(self, request: LLMRequest):
        """
        Call the model with streaming.
        This is a placeholder implementation.
        """
        raise NotImplementedError("LLMModel.call_stream not implemented in this context")


class ModelFactory:
    """Factory for creating model instances"""

    @staticmethod
    def create_model(model_type: str, **kwargs):
        """
        Create a model instance based on type.
        This is a placeholder implementation.
        """
        raise NotImplementedError("ModelFactory.create_model not implemented in this context")
