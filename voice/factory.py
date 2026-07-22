"""
voice factory
"""


SUPPORTED_ASR_PROVIDERS = frozenset(
    {
        "baidu",
        "google",
        "openai",
        "azure",
        "linkai",
        "ali",
        "xunfei",
        "tencent",
        "dashscope",
        "zhipu",
        "zhipuai",
    }
)

SUPPORTED_TTS_PROVIDERS = frozenset(
    {
        "baidu",
        "google",
        "openai",
        "pytts",
        "azure",
        "elevenlabs",
        "linkai",
        "ali",
        "edge",
        "xunfei",
        "tencent",
        "minimax",
        "dashscope",
        "zhipu",
        "zhipuai",
        "mimo",
    }
)


class UnsupportedVoiceProviderError(ValueError):
    def __init__(self, voice_type):
        self.voice_type = voice_type
        super().__init__(f"Unsupported voice provider: {voice_type}")


def create_voice(voice_type, capability=None):
    """
    create a voice instance
    :param voice_type: voice type code
    :return: voice instance
    """
    if voice_type == "custom" or (
        isinstance(voice_type, str) and voice_type.startswith("custom:")
    ):
        if capability in ("voice_to_text", "text_to_voice"):
            from voice.custom.custom_voice import CustomVoice

            return CustomVoice(voice_type)
        raise UnsupportedVoiceProviderError(voice_type)
    if voice_type == "baidu":
        from voice.baidu.baidu_voice import BaiduVoice

        return BaiduVoice()
    elif voice_type == "google":
        from voice.google.google_voice import GoogleVoice

        return GoogleVoice()
    elif voice_type == "openai":
        from voice.openai.openai_voice import OpenaiVoice

        return OpenaiVoice()
    elif voice_type == "pytts":
        from voice.pytts.pytts_voice import PyttsVoice

        return PyttsVoice()
    elif voice_type == "azure":
        from voice.azure.azure_voice import AzureVoice

        return AzureVoice()
    elif voice_type == "elevenlabs":
        from voice.elevent.elevent_voice import ElevenLabsVoice

        return ElevenLabsVoice()

    elif voice_type == "linkai":
        from voice.linkai.linkai_voice import LinkAIVoice

        return LinkAIVoice()
    elif voice_type == "ali":
        from voice.ali.ali_voice import AliVoice

        return AliVoice()
    elif voice_type == "edge":
        from voice.edge.edge_voice import EdgeVoice

        return EdgeVoice()
    elif voice_type == "xunfei":
        from voice.xunfei.xunfei_voice import XunfeiVoice

        return XunfeiVoice()
    elif voice_type == "tencent":
        from voice.tencent.tencent_voice import TencentVoice

        return TencentVoice()
    elif voice_type == "minimax":
        from voice.minimax.minimax_voice import MinimaxVoice

        return MinimaxVoice()
    elif voice_type == "dashscope":
        from voice.dashscope.dashscope_voice import DashScopeVoice

        return DashScopeVoice()
    elif voice_type == "zhipu" or voice_type == "zhipuai":
        from voice.zhipuai.zhipuai_voice import ZhipuAIVoice

        return ZhipuAIVoice()
    elif voice_type == "mimo":
        from voice.mimo.mimo_voice import MimoVoice

        return MimoVoice()
    raise UnsupportedVoiceProviderError(voice_type)
