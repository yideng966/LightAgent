"""
Message sending channel abstract class
"""

import json
import os
import subprocess
import sys

from bridge.bridge import Bridge
from bridge.context import Context, ContextType
from bridge.reply import *
from common.log import logger
from config import conf


def _normalize_config_bool(value, default=False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off", ""):
        return False
    return default


class Channel(object):
    channel_type = ""
    NOT_SUPPORT_REPLYTYPE = [ReplyType.VOICE, ReplyType.IMAGE]

    def __init__(self):
        import threading
        self._startup_event = threading.Event()
        self._startup_error = None
        self.cloud_mode = False  # set to True by ChannelManager when running with cloud client

    def startup(self):
        """
        init channel
        """
        raise NotImplementedError

    def report_startup_success(self):
        self._startup_error = None
        self._startup_event.set()

    def report_startup_error(self, error: str):
        self._startup_error = error
        self._startup_event.set()

    def wait_startup(self, timeout: float = 3) -> (bool, str):
        """
        Wait for channel startup result.
        Returns (success: bool, error_msg: str).
        """
        ready = self._startup_event.wait(timeout=timeout)
        if not ready:
            return True, ""
        if self._startup_error:
            return False, self._startup_error
        return True, ""

    def stop(self):
        """
        stop channel gracefully, called before restart
        """
        pass

    def handle_text(self, msg):
        """
        process received msg
        :param msg: message object
        """
        raise NotImplementedError

    # 统一的发送函数，每个Channel自行实现，根据reply的type字段发送不同类型的消息
    def send(self, reply: Reply, context: Context):
        """
        send message to user
        :param msg: message content
        :param receiver: receiver channel account
        :return:
        """
        raise NotImplementedError

    def build_reply_content(self, query, context: Context = None) -> Reply:
        """
        Build reply content, using agent if enabled in config
        """
        # Check if agent mode is enabled
        use_agent = conf().get("agent", True)

        if use_agent:
            if context and context.type == ContextType.IMAGE_CREATE:
                return self._build_image_create_reply(query, context)

            try:
                logger.info("[Channel] Using agent mode")

                # Add channel_type to context if not present
                if context and "channel_type" not in context:
                    context["channel_type"] = self.channel_type

                # Read on_event callback injected by the channel (e.g. web SSE)
                on_event = context.get("on_event") if context else None

                # Use agent bridge to handle the query
                return Bridge().fetch_agent_reply(
                    query=query,
                    context=context,
                    on_event=on_event,
                    clear_history=False
                )
            except Exception as e:
                logger.error(f"[Channel] Agent mode failed, fallback to normal mode: {e}")
                # Fallback to normal mode if agent fails
                return Bridge().fetch_reply_content(query, context)
        else:
            # Normal mode
            return Bridge().fetch_reply_content(query, context)

    def _build_image_create_reply(self, query, context: Context = None) -> Reply:
        """Run the image-generation skill script deterministically.

        Image creation is already identified before this method is called via
        ContextType.IMAGE_CREATE, so do not ask the chat model to decide
        whether to use the skill. Passing argv as a list avoids Windows shell
        quote loss that breaks JSON arguments.
        """
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = os.path.join(project_root, "skills", "image-generation", "scripts", "generate.py")
        if not os.path.exists(script):
            return Reply(ReplyType.ERROR, "图像生成脚本不存在，请检查 skills/image-generation。")

        payload = {"prompt": str(query or "").strip()}
        skills_cfg = conf().get("skills") or conf().get("skill") or {}
        if isinstance(skills_cfg, dict):
            image_cfg = skills_cfg.get("image-generation") or {}
            if isinstance(image_cfg, dict):
                provider = (image_cfg.get("provider") or "").strip()
                model = (image_cfg.get("model") or "").strip()
                proxy_enabled = _normalize_config_bool(image_cfg.get("proxy_enabled"), False)
                proxy_domains = image_cfg.get("proxy_domains") or []
                if provider:
                    payload["provider"] = provider
                if model:
                    payload["model"] = model
                payload["proxy_enabled"] = proxy_enabled
                payload["proxy_domains"] = proxy_domains
        tools_cfg = conf().get("tools") or conf().get("tool") or {}
        if isinstance(tools_cfg, dict):
            web_fetch_cfg = tools_cfg.get("web_fetch") or {}
            if isinstance(web_fetch_cfg, dict):
                proxy = str(web_fetch_cfg.get("proxy") or "").strip()
                if proxy:
                    payload["proxy"] = proxy
        if not payload["prompt"]:
            return Reply(ReplyType.ERROR, "图像生成提示词为空。")

        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        try:
            completed = subprocess.run(
                [sys.executable, script, json.dumps(payload, ensure_ascii=False)],
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=child_env,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            return Reply(ReplyType.ERROR, "图像生成超时，请稍后再试。")
        except Exception as e:
            logger.warning("[Channel] image generation script failed to start: {}".format(e))
            return Reply(ReplyType.ERROR, "图像生成启动失败：{}".format(e))

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            err = stdout or stderr or "unknown error"
            try:
                err_obj = json.loads(stdout)
                err = err_obj.get("error") or err
            except Exception:
                pass
            logger.warning("[Channel] image generation failed: {}".format(err))
            return Reply(ReplyType.ERROR, "累了不想画了，你跪安吧。")

        try:
            result = json.loads(stdout)
        except Exception as e:
            logger.warning(
                "[Channel] invalid image generation output: error={} stdout={} stderr={}".format(
                    e, stdout[:300], stderr[:300],
                )
            )
            return Reply(ReplyType.ERROR, "图像生成返回格式错误。")

        if result.get("error"):
            logger.warning("[Channel] image generation returned error: {}".format(result.get("error")))
            return Reply(ReplyType.ERROR, "累了不想画了，你跪安吧。")

        images = result.get("images") or []
        if not images:
            return Reply(ReplyType.ERROR, "图像生成没有返回图片。")
        first = images[0] if isinstance(images[0], dict) else {}
        image_url = first.get("url") or ""
        if not image_url:
            return Reply(ReplyType.ERROR, "图像生成结果缺少图片地址。")
        if image_url.startswith(("http://", "https://", "file://")):
            return Reply(ReplyType.IMAGE_URL, image_url)
        return Reply(ReplyType.IMAGE, image_url)

    def build_voice_to_text(self, voice_file) -> Reply:
        return Bridge().fetch_voice_to_text(voice_file)

    def build_text_to_voice(self, text) -> Reply:
        return Bridge().fetch_text_to_voice(text)
