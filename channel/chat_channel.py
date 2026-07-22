import os
import re
import shutil
import tempfile
import threading
import time
from asyncio import CancelledError
from concurrent.futures import Future, ThreadPoolExecutor

from bridge.context import *
from bridge.reply import *
from channel.channel import Channel
from common.dequeue import Dequeue
from common import memory
from common.i18n import t as _t
from plugins import *

DEFAULT_IMAGE_CREATE_PREFIX = ["画"]

handler_pool = ThreadPoolExecutor(max_workers=8)  # 处理消息的线程池


# 抽象类, 它包含了与消息通道无关的通用处理逻辑
class ChatChannel(Channel):
    name = None  # 登录的用户名
    user_id = None  # 登录的用户id

    def __init__(self):
        super().__init__()
        # Instance-level attributes so each channel subclass has its own
        # independent session queue and lock. Previously these were class-level,
        # which caused contexts from one channel (e.g. Feishu) to be consumed
        # by another channel's consume() thread (e.g. Web), leading to errors
        # like "No request_id found in context".
        self.futures = {}
        self.sessions = {}
        self.lock = threading.Lock()
        _thread = threading.Thread(target=self.consume)
        _thread.daemon = True
        _thread.start()

    # 根据消息构造context，消息内容相关的触发项写在这里
    def _compose_context(self, ctype: ContextType, content, **kwargs):
        context = Context(ctype, content)
        context.kwargs = kwargs
        if "channel_type" not in context:
            context["channel_type"] = self.channel_type
        if "origin_ctype" not in context:
            context["origin_ctype"] = ctype
        # context首次传入时，receiver是None，根据类型设置receiver
        first_in = "receiver" not in context
        # 群名匹配过程，设置session_id和receiver
        if first_in:  # context首次传入时，receiver是None，根据类型设置receiver
            config = conf()
            cmsg = context["msg"]
            user_data = conf().get_user_data(cmsg.from_user_id)
            context["openai_api_key"] = user_data.get("openai_api_key")
            context["gpt_model"] = user_data.get("gpt_model")
            if context.get("isgroup", False):
                group_name = cmsg.other_user_nickname
                group_id = cmsg.other_user_id

                group_name_white_list = config.get("group_name_white_list", [])
                group_name_keyword_white_list = config.get("group_name_keyword_white_list", [])
                stable_group_id = context.get("wechat_group_stable_room_id") or ""
                stable_member_id = context.get("wechat_group_stable_member_id") or ""
                wechat_group_stable_room_ids = config.get("wechat_group_stable_room_ids", [])
                wechat_group_room_ids = config.get("wechat_group_room_ids", [])
                matched_wechat_group_room_id = (
                    context.get("channel_type") == "wechat_group"
                    and (
                        (stable_group_id and stable_group_id in wechat_group_stable_room_ids)
                        or group_id in wechat_group_room_ids
                    )
                )
                if any(
                    [
                        group_name in group_name_white_list,
                        "ALL_GROUP" in group_name_white_list,
                        check_contain(group_name, group_name_keyword_white_list),
                        matched_wechat_group_room_id,
                    ]
                ):
                    # Check global group_shared_session config first
                    group_shared_session = conf().get("group_shared_session", True)
                    if context.get("channel_type") == "wechat_group" and stable_group_id:
                        if group_shared_session:
                            session_id = f"wechat_group:{stable_group_id}"
                        else:
                            session_member = stable_member_id or cmsg.actual_user_id
                            session_id = f"wechat_group:{stable_group_id}:{session_member}"
                    elif group_shared_session:
                        # All users in the group share the same session
                        session_id = group_id
                    else:
                        # Check group-specific whitelist (legacy behavior)
                        group_chat_in_one_session = conf().get("group_chat_in_one_session", [])
                        session_id = cmsg.actual_user_id
                        if any(
                            [
                                group_name in group_chat_in_one_session,
                                "ALL_GROUP" in group_chat_in_one_session,
                            ]
                        ):
                            session_id = group_id
                else:
                    logger.debug(f"No need reply, groupName not in whitelist, group_name={group_name}")
                    return None
                context["session_id"] = session_id
                context["receiver"] = group_id
            else:
                context["session_id"] = cmsg.other_user_id
                context["receiver"] = cmsg.other_user_id
            e_context = PluginManager().emit_event(EventContext(Event.ON_RECEIVE_MESSAGE, {"channel": self, "context": context}))
            context = e_context["context"]
            if e_context.is_pass() or context is None:
                return context
            if cmsg.from_user_id == self.user_id and not config.get("trigger_by_self", True):
                logger.debug("[chat_channel]self message skipped")
                return None

        # 消息内容匹配过程，并处理content
        if ctype == ContextType.TEXT:
            if first_in and "」\n- - - - - - -" in content and not context.get("wechat_group_force_reply", False):  # 初次匹配 过滤引用消息
                logger.debug(content)
                logger.debug("[chat_channel]reference query skipped")
                return None

            nick_name_black_list = conf().get("nick_name_black_list", [])
            if context.get("isgroup", False):  # 群聊
                # 校验关键字
                match_prefix = check_prefix(content, conf().get("group_chat_prefix"))
                match_contain = check_contain(content, conf().get("group_chat_keyword"))
                flag = bool(context.get("wechat_group_force_reply", False))
                if context["msg"].to_user_id != context["msg"].actual_user_id:
                    if match_prefix is not None or match_contain is not None:
                        flag = True
                        if match_prefix:
                            content = content.replace(match_prefix, "", 1).strip()
                    if context["msg"].is_at:
                        nick_name = context["msg"].actual_user_nickname
                        if nick_name and nick_name in nick_name_black_list:
                            # 黑名单过滤
                            logger.warning(f"[chat_channel] Nickname {nick_name} in In BlackList, ignore")
                            return None

                        logger.info("[chat_channel]receive group at")
                        if not conf().get("group_at_off", False):
                            flag = True
                        self.name = self.name if self.name is not None else ""  # 部分渠道self.name可能没有赋值
                        pattern = f"@{re.escape(self.name)}(\u2005|\u0020)"
                        subtract_res = re.sub(pattern, r"", content)
                        if isinstance(context["msg"].at_list, list):
                            for at in context["msg"].at_list:
                                pattern = f"@{re.escape(at)}(\u2005|\u0020)"
                                subtract_res = re.sub(pattern, r"", subtract_res)
                        if subtract_res == content and context["msg"].self_display_name:
                            # 前缀移除后没有变化，使用群昵称再次移除
                            pattern = f"@{re.escape(context['msg'].self_display_name)}(\u2005|\u0020)"
                            subtract_res = re.sub(pattern, r"", content)
                        content = subtract_res
                if not flag:
                    if context["origin_ctype"] == ContextType.VOICE:
                        logger.info("[chat_channel]receive group voice, but checkprefix didn't match")
                    return None
            else:  # 单聊
                nick_name = context["msg"].from_user_nickname
                if nick_name and nick_name in nick_name_black_list:
                    # 黑名单过滤
                    logger.warning(f"[chat_channel] Nickname '{nick_name}' in In BlackList, ignore")
                    return None

                match_prefix = check_prefix(content, conf().get("single_chat_prefix", [""]))
                if match_prefix is not None:  # 判断如果匹配到自定义前缀，则返回过滤掉前缀+空格后的内容
                    content = content.replace(match_prefix, "", 1).strip()
                elif context["origin_ctype"] == ContextType.VOICE:  # 如果源消息是私聊的语音消息，允许不匹配前缀，放宽条件
                    pass
                else:
                    logger.info("[chat_channel]receive single chat msg, but checkprefix didn't match")
                    return None
            content = content.strip()
            img_match_prefix = check_prefix(content, conf().get("image_create_prefix", DEFAULT_IMAGE_CREATE_PREFIX))
            if img_match_prefix:
                content = content.replace(img_match_prefix, "", 1)
                context.type = ContextType.IMAGE_CREATE
            else:
                context.type = ContextType.TEXT
            context.content = content.strip()
            if "desire_rtype" not in context and conf().get("always_reply_voice") and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                context["desire_rtype"] = ReplyType.VOICE
        elif context.type == ContextType.VOICE:
            # Voice input replies with voice when either voice_reply_voice
            # (mirror voice) or the global always_reply_voice toggle is on.
            if (
                "desire_rtype" not in context
                and (conf().get("voice_reply_voice") or conf().get("always_reply_voice"))
                and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE
            ):
                context["desire_rtype"] = ReplyType.VOICE
        return context

    def _handle(self, context: Context):
        if context is None or not context.content:
            return
        if context.type == ContextType.IMAGE_CREATE:
            logger.info(
                "[chat_channel] image-create handling: session_id=%s, content=%s",
                context.get("session_id"),
                str(context.content)[:120],
            )
        logger.debug("[chat_channel] handling context: {}".format(context))
        # reply的构建步骤
        reply = self._generate_reply(context)

        logger.debug("[chat_channel] decorating reply: {}".format(reply))

        # reply的包装步骤
        if reply and reply.content:
            reply = self._decorate_reply(context, reply)

            # reply的发送步骤
            self._send_reply(context, reply)

    def _generate_reply(self, context: Context, reply: Reply = Reply()) -> Reply:
        e_context = PluginManager().emit_event(
            EventContext(
                Event.ON_HANDLE_CONTEXT,
                {"channel": self, "context": context, "reply": reply},
            )
        )
        reply = e_context["reply"]
        if not e_context.is_pass():
            logger.debug("[chat_channel] type={}, content={}".format(context.type, context.content))
            if context.type == ContextType.TEXT or context.type == ContextType.IMAGE_CREATE:  # 文字和图片消息
                context["channel"] = e_context["channel"]
                reply = super().build_reply_content(context.content, context)
            elif context.type == ContextType.VOICE:  # 语音消息
                cmsg = context["msg"]
                cmsg.prepare()
                file_path = context.content
                generated_wav_path = os.path.splitext(file_path)[0] + ".wav"
                asr_path = generated_wav_path
                detected_audio_format = ""
                try:
                    from voice.audio_convert import sniff_audio_format
                    detected_audio_format = sniff_audio_format(file_path)
                except Exception:
                    detected_audio_format = ""
                is_silk = str(file_path).lower().endswith((".sil", ".silk", ".slk")) and detected_audio_format in ("", "silk")
                asr_alias_path = ""
                try:
                    try:
                        from voice.audio_convert import any_to_wav
                        any_to_wav(file_path, generated_wav_path)
                    except Exception as e:
                        if is_silk:
                            missing_pysilk = (
                                isinstance(e, ImportError)
                                and "pysilk-mod" in str(e).lower()
                            )
                            logger.warning(
                                "[chat_channel] silk to wav conversion failed; "
                                "asr skipped, error_type=%s detected_format=%s",
                                type(e).__name__,
                                detected_audio_format or "unknown",
                            )
                            if missing_pysilk:
                                error_content = (
                                    "Silk 语音转换依赖缺失，请安装 "
                                    "pysilk-mod>=1.6.4 后重试。"
                                )
                            else:
                                error_content = (
                                    "Silk 语音转换失败，无法进行语音识别，"
                                    "请稍后重试。"
                                )
                            return Reply(
                                ReplyType.ERROR,
                                error_content,
                            )
                        # Some ASR providers can accept formats such as MP3 directly.
                        logger.warning(
                            "[chat_channel] audio to wav conversion failed; "
                            "using raw audio, error_type=%s detected_format=%s",
                            type(e).__name__,
                            detected_audio_format or "unknown",
                        )
                        asr_alias_path = _build_audio_alias_for_asr(file_path, detected_audio_format)
                        if asr_alias_path:
                            try:
                                shutil.copy2(file_path, asr_alias_path)
                                asr_path = asr_alias_path
                            except Exception:
                                asr_path = file_path
                        else:
                            asr_path = file_path
                    # 语音识别
                    reply = super().build_voice_to_text(asr_path)
                finally:
                    # 删除临时文件
                    cleanup_paths = []
                    if not _should_preserve_voice_input(context, file_path):
                        cleanup_paths.append(file_path)
                    if generated_wav_path != file_path:
                        cleanup_paths.append(generated_wav_path)
                    if asr_alias_path:
                        cleanup_paths.append(asr_alias_path)
                    seen_cleanup_paths = set()
                    for cleanup_path in cleanup_paths:
                        if cleanup_path in seen_cleanup_paths:
                            continue
                        seen_cleanup_paths.add(cleanup_path)
                        try:
                            os.remove(cleanup_path)
                        except Exception:
                            pass

                if reply.type == ReplyType.TEXT:
                    new_context = self._handle_voice_transcription(context, reply.content)
                    if new_context:
                        reply = self._generate_reply(new_context)
                    else:
                        return
            elif context.type == ContextType.IMAGE:  # 图片消息，当前仅做下载保存到本地的逻辑
                memory.USER_IMAGE_CACHE[context["session_id"]] = {
                    "path": context.content,
                    "msg": context.get("msg")
                }
            elif context.type == ContextType.SHARING:  # 分享信息，当前无默认逻辑
                pass
            elif context.type == ContextType.FUNCTION or context.type == ContextType.FILE:  # 文件消息及函数调用等，当前无默认逻辑
                pass
            else:
                logger.warning("[chat_channel] unknown context type: {}".format(context.type))
                return
        return reply

    def _handle_voice_transcription(self, context: Context, transcription: str):
        return self._compose_context(ContextType.TEXT, transcription, **context.kwargs)

    def _decorate_reply(self, context: Context, reply: Reply) -> Reply:
        if reply and reply.type:
            e_context = PluginManager().emit_event(
                EventContext(
                    Event.ON_DECORATE_REPLY,
                    {"channel": self, "context": context, "reply": reply},
                )
            )
            reply = e_context["reply"]
            desire_rtype = context.get("desire_rtype")
            if not e_context.is_pass() and reply and reply.type:
                if reply.type in self.NOT_SUPPORT_REPLYTYPE:
                    logger.error("[chat_channel]reply type not support: " + str(reply.type))
                    reply.type = ReplyType.ERROR
                    reply.content = _t("不支持发送的消息类型: ", "Unsupported message type: ") + str(reply.type)

                if reply.type == ReplyType.TEXT:
                    reply_text = reply.content
                    if desire_rtype == ReplyType.VOICE and ReplyType.VOICE not in self.NOT_SUPPORT_REPLYTYPE:
                        # Preserve original text for the "text-then-voice" pattern in _send_reply.
                        context["voice_reply_text"] = reply.content
                        reply = super().build_text_to_voice(reply.content)
                        return self._decorate_reply(context, reply)
                    if context.get("isgroup", False):
                        if not context.get("no_need_at", False):
                            reply_text = "@" + context["msg"].actual_user_nickname + "\n" + reply_text.strip()
                        reply_text = conf().get("group_chat_reply_prefix", "") + reply_text + conf().get("group_chat_reply_suffix", "")
                    else:
                        reply_text = conf().get("single_chat_reply_prefix", "") + reply_text + conf().get("single_chat_reply_suffix", "")
                    reply.content = reply_text
                elif reply.type == ReplyType.ERROR or reply.type == ReplyType.INFO:
                    reply.content = "[" + str(reply.type) + "]\n" + reply.content
                elif reply.type == ReplyType.IMAGE_URL or reply.type == ReplyType.VOICE or reply.type == ReplyType.IMAGE or reply.type == ReplyType.FILE or reply.type == ReplyType.VIDEO or reply.type == ReplyType.VIDEO_URL:
                    pass
                else:
                    logger.error("[chat_channel] unknown reply type: {}".format(reply.type))
                    return
            if desire_rtype and desire_rtype != reply.type and reply.type not in [ReplyType.ERROR, ReplyType.INFO]:
                logger.warning("[chat_channel] desire_rtype: {}, but reply type: {}".format(context.get("desire_rtype"), reply.type))
            return reply

    def _send_reply(self, context: Context, reply: Reply):
        if reply and reply.type:
            e_context = PluginManager().emit_event(
                EventContext(
                    Event.ON_SEND_REPLY,
                    {"channel": self, "context": context, "reply": reply},
                )
            )
            reply = e_context["reply"]
            if not e_context.is_pass() and reply and reply.type:
                logger.debug("[chat_channel] sending reply: {}, context: {}".format(reply, context))
                
                # 如果是文本回复，尝试提取并发送图片
                # Web channel renders images/videos inline via renderMarkdown,
                # so skip the extract-and-send step to avoid duplicate media.
                if reply.type == ReplyType.TEXT and context.get("channel_type") != "web":
                    self._extract_and_send_images(reply, context)
                elif reply.type == ReplyType.TEXT:
                    self._send(reply, context)
                # 如果是图片回复但带有文本内容，先发文本再发图片
                elif reply.type == ReplyType.IMAGE_URL and hasattr(reply, 'text_content') and reply.text_content:
                    # 先发送文本
                    text_reply = Reply(ReplyType.TEXT, reply.text_content)
                    self._send(text_reply, context)
                    # 短暂延迟后发送图片
                    time.sleep(0.3)
                    self._send(reply, context)
                # Send text bubble before voice, unless channel already streamed
                # the text (feishu) or natively renders STT under the voice (wechatcom).
                elif reply.type == ReplyType.VOICE and context.get("voice_reply_text") \
                        and not context.get("feishu_streamed") \
                        and context.get("channel_type") not in ("wechatcom_app",):
                    text_reply = Reply(ReplyType.TEXT, context.get("voice_reply_text"))
                    self._send(text_reply, context)
                    time.sleep(0.3)
                    self._send(reply, context)
                else:
                    self._send(reply, context)
    
    def _extract_and_send_images(self, reply: Reply, context: Context):
        """
        从文本回复中提取图片/视频URL并单独发送
        支持格式：[图片: /path/to/image.png], [视频: /path/to/video.mp4], ![](url), <img src="url">
        最多发送5个媒体文件
        """
        content = reply.content
        media_items = []  # [(url, type), ...]
        
        # 正则提取各种格式的媒体URL
        patterns = [
            (r'\[图片:\s*([^\]]+)\]', 'image'),   # [图片: /path/to/image.png]
            (r'\[视频:\s*([^\]]+)\]', 'video'),   # [视频: /path/to/video.mp4]
            (r'!\[.*?\]\(([^\)]+)\)', 'image'),   # ![alt](url) - 默认图片
            (r'<img[^>]+src=["\']([^"\']+)["\']', 'image'),  # <img src="url">
            (r'<video[^>]+src=["\']([^"\']+)["\']', 'video'),  # <video src="url">
            (r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp)', 'image'),  # 直接的图片URL
            (r'https?://[^\s]+\.(?:mp4|avi|mov|wmv|flv)', 'video'),  # 直接的视频URL
        ]
        
        for pattern, media_type in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                media_items.append((match, media_type))
        
        # 去重（保持顺序）并限制最多5个
        seen = set()
        unique_items = []
        for url, mtype in media_items:
            if url not in seen:
                seen.add(url)
                unique_items.append((url, mtype))
        media_items = unique_items[:5]
        
        if media_items:
            logger.info(f"[chat_channel] Extracted {len(media_items)} media item(s) from reply")
            
            # Send text first (the frontend will embed video players via renderMarkdown).
            logger.info(f"[chat_channel] Sending text content before media: {reply.content[:100]}...")
            self._send(reply, context)
            logger.info(f"[chat_channel] Text sent, now sending {len(media_items)} media item(s)")
            
            for i, (url, media_type) in enumerate(media_items):
                try:
                    # Determine whether it is a remote URL or a local file.
                    if url.startswith(('http://', 'https://')):
                        if media_type == 'video':
                            media_reply = Reply(ReplyType.FILE, url)
                            media_reply.file_name = os.path.basename(url)
                        else:
                            media_reply = Reply(ReplyType.IMAGE_URL, url)
                    elif os.path.exists(url):
                        if media_type == 'video':
                            media_reply = Reply(ReplyType.FILE, f"file://{url}")
                            media_reply.file_name = os.path.basename(url)
                        else:
                            media_reply = Reply(ReplyType.IMAGE_URL, f"file://{url}")
                    else:
                        logger.warning(f"[chat_channel] Media file not found or invalid URL: {url}")
                        continue
                    
                    if i > 0:
                        time.sleep(0.5)
                    self._send(media_reply, context)
                    logger.info(f"[chat_channel] Sent {media_type} {i+1}/{len(media_items)}: {url[:50]}...")
                    
                except Exception as e:
                    logger.error(f"[chat_channel] Failed to send {media_type} {url}: {e}")
        else:
            # 没有媒体文件，正常发送文本
                self._send(reply, context)

    def _send(self, reply: Reply, context: Context, retry_cnt=0):
        try:
            self.send(reply, context)
        except Exception as e:
            logger.error("[chat_channel] sendMsg error: {}".format(str(e)))
            if isinstance(e, NotImplementedError):
                return
            logger.exception(e)
            if retry_cnt < 2:
                time.sleep(3 + 3 * retry_cnt)
                self._send(reply, context, retry_cnt + 1)

    def _success_callback(self, session_id, **kwargs):  # 线程正常结束时的回调函数
        logger.debug("Worker return success, session_id = {}".format(session_id))

    def _fail_callback(self, session_id, exception, **kwargs):  # 线程异常结束时的回调函数
        logger.exception("Worker return exception: {}".format(exception))

    def _thread_pool_callback(self, session_id, **kwargs):
        def func(worker: Future):
            try:
                worker_exception = worker.exception()
                if worker_exception:
                    self._fail_callback(session_id, exception=worker_exception, **kwargs)
                else:
                    self._success_callback(session_id, **kwargs)
            except CancelledError as e:
                logger.info("Worker cancelled, session_id = {}".format(session_id))
            except Exception as e:
                logger.exception("Worker raise exception: {}".format(e))
            with self.lock:
                self.sessions[session_id][1].release()

        return func

    # Chat commands that must bypass the per-session serial queue,
    # otherwise /cancel would queue behind the task it tries to cancel.
    # Use /cancel (not /stop) to avoid colliding with `lightagent stop` CLI.
    _BYPASS_QUEUE_COMMANDS = ("/cancel",)

    def produce(self, context: Context):
        session_id = context["session_id"]

        # Fast path: /cancel must not enter the queue.
        if context.type == ContextType.TEXT and context.content:
            stripped = context.content.strip().lower()
            if stripped in self._BYPASS_QUEUE_COMMANDS:
                self._handle_cancel_command(context, session_id)
                return

        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = [
                    Dequeue(),
                    threading.BoundedSemaphore(conf().get("concurrency_in_session", 1)),
                ]
            if context.type == ContextType.TEXT and context.content.startswith("#"):
                self.sessions[session_id][0].putleft(context)  # 优先处理管理命令
            else:
                self.sessions[session_id][0].put(context)
            if context.type == ContextType.IMAGE_CREATE:
                logger.info(
                    "[chat_channel] image-create enqueued: session_id=%s, queue_size=%s, content=%s",
                    session_id,
                    self.sessions[session_id][0].qsize(),
                    str(context.content)[:120],
                )

    def _handle_cancel_command(self, context: Context, session_id: str) -> None:
        """Cancel any in-flight agent run for *session_id* and reply inline.

        Runs synchronously on the caller's thread. Reply is sent through
        _send_reply so plugins (e.g. logging) still observe it.
        """
        try:
            from agent.protocol import get_cancel_registry
            from bridge.reply import Reply, ReplyType

            cancelled = get_cancel_registry().cancel_session(session_id)
            text = (
                _t("🛑 已中止", "🛑 Cancelled")
                if cancelled > 0
                else _t("当前没有可中止的任务。", "Nothing to cancel.")
            )
            logger.info(
                f"[chat_channel] /cancel fast-path: session={session_id}, cancelled={cancelled}"
            )
            self._send_reply(context, Reply(ReplyType.TEXT, text))
        except Exception as e:
            logger.warning(f"[chat_channel] /cancel fast-path failed: {e}")

    # Consumer loop: pull contexts from per-session queues and dispatch them.
    def consume(self):
        while True:
            try:
                with self.lock:
                    session_ids = list(self.sessions.keys())
                for session_id in session_ids:
                    semaphore_acquired = False
                    callback_registered = False
                    try:
                        with self.lock:
                            try:
                                session_state = self.sessions[session_id]
                            except KeyError:
                                logger.warning(
                                    "[chat_channel] consume skip missing session: session_id=%s",
                                    session_id,
                                )
                                continue
                        if not isinstance(session_state, (list, tuple)) or len(session_state) != 2:
                            logger.warning(
                                "[chat_channel] consume skip invalid session state: session_id=%s, state=%r",
                                session_id,
                                session_state,
                            )
                            continue
                        context_queue, semaphore = session_state
                        if semaphore.acquire(blocking=False):
                            semaphore_acquired = True
                            if not context_queue.empty():
                                context = context_queue.get()
                                logger.debug("[chat_channel] consume context: {}".format(context))
                                if context.type == ContextType.IMAGE_CREATE:
                                    logger.info(
                                        "[chat_channel] image-create dispatching: session_id=%s, content=%s",
                                        session_id,
                                        str(context.content)[:120],
                                    )
                                future: Future = handler_pool.submit(self._handle, context)
                                future.add_done_callback(self._thread_pool_callback(session_id, context=context))
                                callback_registered = True
                                with self.lock:
                                    if session_id not in self.futures:
                                        self.futures[session_id] = []
                                    self.futures[session_id].append(future)
                            elif semaphore._initial_value == semaphore._value + 1:
                                with self.lock:
                                    pending_futures = [t for t in self.futures.get(session_id, []) if not t.done()]
                                    self.futures[session_id] = pending_futures
                                    if pending_futures:
                                        logger.warning(
                                            "[chat_channel] consume keep session with pending futures: session_id=%s, count=%s",
                                            session_id,
                                            len(pending_futures),
                                        )
                                        semaphore.release()
                                        semaphore_acquired = False
                                        continue
                                    if session_id in self.sessions:
                                        del self.sessions[session_id]
                            else:
                                semaphore.release()
                                semaphore_acquired = False
                    except Exception as e:
                        logger.exception(
                            "[chat_channel] consume session error, skip: session_id=%s, error=%s",
                            session_id,
                            e,
                        )
                        if semaphore_acquired and not callback_registered:
                            try:
                                semaphore.release()
                            except Exception:
                                logger.exception(
                                    "[chat_channel] consume failed to release semaphore: session_id=%s",
                                    session_id,
                                )
            except Exception as e:
                logger.exception("[chat_channel] consume loop error: {}".format(e))
            time.sleep(0.2)

    # Cancel queued and not-yet-running tasks for the session.
    def cancel_session(self, session_id):
        with self.lock:
            if session_id in self.sessions:
                # futures[session_id] is only created in consume() when a task is
                # dispatched, so it may be absent if cancel happens right after
                # produce() but before the first dispatch. Default to [].
                for future in self.futures.get(session_id, []):
                    future.cancel()
                cnt = self.sessions[session_id][0].qsize()
                if cnt > 0:
                    logger.info("Cancel {} messages in session {}".format(cnt, session_id))
                self.sessions[session_id][0] = Dequeue()

    def cancel_all_session(self):
        with self.lock:
            for session_id in self.sessions:
                for future in self.futures.get(session_id, []):
                    future.cancel()
                cnt = self.sessions[session_id][0].qsize()
                if cnt > 0:
                    logger.info("Cancel {} messages in session {}".format(cnt, session_id))
                self.sessions[session_id][0] = Dequeue()


def check_prefix(content, prefix_list):
    if not prefix_list:
        return None
    for prefix in prefix_list:
        if content.startswith(prefix):
            return prefix
    return None


def check_contain(content, keyword_list):
    if not keyword_list:
        return None
    for ky in keyword_list:
        if content.find(ky) != -1:
            return True
    return None


def _should_preserve_voice_input(context, file_path):
    if context.get("channel_type") != "wechat_group":
        return False
    msg = context.get("msg")
    media_path = str(getattr(msg, "media_path", "") or "").strip()
    if not media_path:
        return False
    try:
        return os.path.samefile(media_path, file_path)
    except Exception:
        return os.path.normcase(os.path.abspath(media_path)) == os.path.normcase(os.path.abspath(file_path))


def _build_audio_alias_for_asr(file_path, detected_format):
    ext = ""
    try:
        from voice.audio_convert import audio_extension_for_format
        ext = audio_extension_for_format(detected_format)
    except Exception:
        ext = ""
    if not ext:
        return ""
    current_ext = os.path.splitext(str(file_path))[1].lower().lstrip(".")
    if current_ext == ext:
        return ""
    fd, alias_path = tempfile.mkstemp(prefix="lightagent-asr-", suffix="." + ext)
    os.close(fd)
    return alias_path
