"""
Integration module for scheduler with AgentBridge
"""

import os
import threading
from datetime import datetime, timedelta
from typing import Optional
from config import conf
from common.log import logger
from common.utils import expand_path
from bridge.context import Context, ContextType
from bridge.reply import Reply, ReplyType

# Global scheduler service instance
_scheduler_service = None
_task_store = None
# Module-level lock to guard idempotent initialization across threads
_init_lock = threading.Lock()
_task_store_lock = threading.Lock()
_enqueue_lock = threading.Lock()


def _get_or_create_task_store():
    global _task_store
    if _task_store is not None:
        return _task_store
    with _task_store_lock:
        if _task_store is None:
            from agent.tools.scheduler.task_store import TaskStore

            workspace_root = expand_path(conf().get("agent_workspace", "~/lightagent"))
            store_path = os.path.join(workspace_root, "scheduler", "tasks.json")
            _task_store = TaskStore(store_path)
            logger.debug(f"[Scheduler] Task store initialized: {store_path}")
    return _task_store


def init_scheduler(agent_bridge) -> bool:
    """
    Initialize scheduler service (idempotent).

    Safe to call multiple times and from multiple threads: only the first
    successful call creates the singleton ``SchedulerService`` + background
    scanning thread. Subsequent calls return immediately.

    Args:
        agent_bridge: AgentBridge instance

    Returns:
        True if scheduler is initialized (newly created or already running)
    """
    global _scheduler_service, _task_store

    # Fast path: already initialized and running
    if _scheduler_service is not None and getattr(_scheduler_service, "running", False):
        return True

    with _init_lock:
        # Re-check under the lock to avoid races where multiple threads
        # passed the fast-path check before any of them acquired the lock.
        if _scheduler_service is not None and getattr(_scheduler_service, "running", False):
            return True

        try:
            from agent.tools.scheduler.scheduler_service import SchedulerService

            _task_store = _get_or_create_task_store()

            # Create execute callback. Returns True on success, False to ask
            # the scheduler to retry on the next tick (e.g. channel not yet
            # ready right after process start).
            def execute_task_callback(task: dict):
                try:
                    action = task.get("action", {})
                    action_type = action.get("type")
                    channel_type = action.get("channel_type", "unknown")
                    receiver = action.get("receiver", "")

                    if not _is_channel_ready(channel_type, receiver):
                        logger.warning(
                            f"[Scheduler] Task {task.get('id')}: channel "
                            f"'{channel_type}' not ready for receiver={receiver} "
                            f"(no inbound msg cached since restart?); deferring"
                        )
                        return False

                    if action_type == "agent_task":
                        return _execute_agent_task(task, agent_bridge)
                    elif action_type == "send_message":
                        return _execute_send_message(task, agent_bridge)
                    elif action_type == "tool_call":
                        return _execute_tool_call(task, agent_bridge)
                    elif action_type == "skill_call":
                        return _execute_skill_call(task, agent_bridge)
                    else:
                        logger.warning(f"[Scheduler] Unknown action type: {action_type}")
                        return True
                except Exception as e:
                    logger.error(f"[Scheduler] Error executing task {task.get('id')}: {e}")
                    return False

            # Create scheduler service
            _scheduler_service = SchedulerService(_task_store, execute_task_callback)
            _scheduler_service.start()

            logger.info("[Scheduler] Service initialized and started")
            return True

        except Exception as e:
            logger.error(f"[Scheduler] Failed to initialize scheduler: {e}")
            return False


def _is_channel_ready(channel_type: str, receiver: str) -> bool:
    """Best-effort readiness probe for outbound channels.

    Returns False when we know the send will drop (e.g. weixin not yet
    logged in, web session has no polling queue), so the scheduler can
    defer instead of consuming the task. Unknown channels return True
    to preserve previous behaviour.
    """
    if not channel_type or channel_type == "unknown":
        return True
    try:
        if channel_type == "wechat_group":
            channel = _get_running_channel(channel_type)
            if channel is None:
                return False
            get_login_status = getattr(channel, "get_login_status", None)
            if callable(get_login_status):
                status = str(get_login_status() or "")
                ready_statuses = {
                    str(getattr(channel, "STATUS_LOGGED_IN", "logged_in")),
                    str(getattr(channel, "STATUS_CONNECTED", "connected")),
                }
                return status in ready_statuses
            return True

        from channel.channel_factory import create_channel
        channel = create_channel(channel_type)
        if channel is None:
            return False

        if channel_type == "weixin":
            tokens = getattr(channel, "_context_tokens", None)
            if not tokens or receiver not in tokens:
                return False
            return True

        if channel_type == "web":
            queues = getattr(channel, "session_queues", None)
            if not queues or receiver not in queues:
                return False
            return True

        return True
    except Exception as e:
        logger.warning(f"[Scheduler] Channel readiness check failed for {channel_type}: {e}")
        return True


def _get_running_channel(channel_type: str):
    """Return a managed running channel instance when outbound delivery needs it."""
    try:
        import sys
        for module_name in ("__main__", "app"):
            app_module = sys.modules.get(module_name)
            mgr = getattr(app_module, "_channel_mgr", None) if app_module else None
            if not mgr:
                continue
            channel = mgr.get_channel(channel_type)
            if channel is not None:
                return channel
    except Exception as e:
        logger.warning(f"[Scheduler] Failed to get running channel {channel_type}: {e}")
    return None


def _create_delivery_channel(channel_type: str):
    """Create or reuse the channel instance used to deliver scheduler output."""
    if channel_type == "wechat_group":
        return _get_running_channel(channel_type)

    from channel.channel_factory import create_channel
    return create_channel(channel_type)


def _prepare_delivery_action(task: dict):
    """Resolve channel-specific delivery identity before sending.

    Legacy tasks that only contain ``receiver`` are returned unchanged. New
    WeChat group tasks persist ``stable_receiver`` and resolve it to the
    currently active runtime room right before delivery.
    """
    action = dict(task.get("action", {}) or {})
    channel_type = action.get("channel_type", "unknown")
    if channel_type != "wechat_group" or action.get("receiver_kind") != "wechat_group":
        return action

    stable_receiver = str(action.get("stable_receiver") or "").strip()
    if not stable_receiver:
        return action

    channel = _get_running_channel("wechat_group")
    identity_service = getattr(channel, "identity_service", None) if channel else None
    runtime_receiver = ""
    if identity_service and hasattr(identity_service, "get_active_runtime_room_id"):
        try:
            runtime_receiver = str(identity_service.get_active_runtime_room_id(stable_receiver) or "").strip()
        except Exception as e:
            logger.warning(
                f"[Scheduler] Failed to resolve WeChat group stable receiver "
                f"{stable_receiver}: {e}"
            )

    if not runtime_receiver:
        _mark_waiting_identity_binding(task, action, stable_receiver)
        return None

    action["receiver"] = runtime_receiver
    action["runtime_receiver"] = runtime_receiver
    action["delivery_status"] = "ready"
    task["action"] = action
    return action


def _mark_waiting_identity_binding(task: dict, action: dict, stable_receiver: str) -> None:
    task_id = str(task.get("id") or "")
    action = dict(action or {})
    action["delivery_status"] = "waiting_identity_binding"
    action["delivery_status_reason"] = "active_runtime_room_missing"
    action["stable_receiver"] = stable_receiver
    updates = {
        "delivery_status": "waiting_identity_binding",
        "delivery_status_reason": "active_runtime_room_missing",
        "last_error": "WeChat group stable receiver has no active runtime room binding",
        "last_error_at": datetime.now().isoformat(),
        "action": action,
    }
    task.update(updates)
    if _task_store and task_id:
        try:
            _task_store.update_task(task_id, updates)
        except Exception as e:
            logger.warning(
                f"[Scheduler] Failed to persist waiting identity state for task {task_id}: {e}"
            )


def _apply_wechat_group_delivery_context(context: Context, action: dict) -> None:
    if action.get("channel_type") != "wechat_group":
        return
    stable_receiver = str(action.get("stable_receiver") or "").strip()
    runtime_receiver = str(action.get("runtime_receiver") or action.get("receiver") or "").strip()
    if stable_receiver:
        context["wechat_group_stable_room_id"] = stable_receiver
        context["wechat_group_stable_receiver"] = stable_receiver
    if runtime_receiver:
        context["wechat_group_runtime_room_id"] = runtime_receiver
        context["wechat_group_room_id"] = runtime_receiver
    if action.get("suppress_mention"):
        context["suppress_mention"] = True
    if action.get("no_need_at"):
        context["no_need_at"] = True


def _wechat_group_delivery_session_id(action: dict, fallback: str = "") -> str:
    if action.get("channel_type") != "wechat_group":
        return str(fallback or "")
    return str(
        action.get("notify_session_id")
        or action.get("stable_receiver")
        or fallback
        or ""
    )


def _scheduler_execution_session_id(action: dict, task_id: str, receiver: str) -> str:
    session_receiver = str(action.get("stable_receiver") or receiver or "")
    return f"scheduler_{session_receiver}_{task_id}"


def get_task_store():
    """Get the global task store instance"""
    return _task_store


def get_scheduler_service():
    """Get the global scheduler service instance"""
    return _scheduler_service


def enqueue_wechat_group_message(
    task_id: str,
    name: str,
    content: str,
    stable_receiver: str,
    max_lateness_seconds: int = 72 * 3600,
    metadata: Optional[dict] = None,
) -> str:
    """Persist a deterministic one-time message for the running WeChat group channel."""
    task_id = str(task_id or "").strip()
    stable_receiver = str(stable_receiver or "").strip()
    content = str(content or "").strip()
    if not task_id:
        raise ValueError("task_id is required")
    if not stable_receiver:
        raise ValueError("stable_receiver is required")
    if not content:
        raise ValueError("content is required")

    metadata = dict(metadata or {})
    runtime_receiver = ""
    channel = _get_running_channel("wechat_group")
    identity_service = getattr(channel, "identity_service", None) if channel else None
    if identity_service and hasattr(identity_service, "get_active_runtime_room_id"):
        try:
            runtime_receiver = str(
                identity_service.get_active_runtime_room_id(stable_receiver) or ""
            ).strip()
        except Exception as e:
            logger.warning(
                f"[Scheduler] Failed to snapshot WeChat group runtime receiver "
                f"for {stable_receiver}: {e}"
            )

    run_at = datetime.now() + timedelta(seconds=1)
    action = {
        "type": "send_message",
        "content": content,
        "receiver": runtime_receiver,
        "runtime_receiver": runtime_receiver,
        "stable_receiver": stable_receiver,
        "receiver_kind": "wechat_group",
        "receiver_name": stable_receiver,
        "is_group": True,
        "channel_type": "wechat_group",
        "notify_session_id": f"wechat_group:{stable_receiver}",
        "suppress_mention": True,
        "no_need_at": True,
    }
    for key in ("source", "external_delivery_id", "repository", "ref"):
        if metadata.get(key):
            action[key] = str(metadata[key])

    task = {
        "id": task_id,
        "name": str(name or "External notification"),
        "enabled": True,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "next_run_at": run_at.isoformat(),
        "max_lateness_seconds": max(int(max_lateness_seconds or 0), 600),
        "schedule": {"type": "once", "run_at": run_at.isoformat()},
        "action": action,
        "metadata": metadata,
    }

    store = _get_or_create_task_store()
    with _enqueue_lock:
        if store.get_task(task_id) is not None:
            return "existing"
        store.add_task(task)
    logger.info(
        f"[Scheduler] Queued external message task {task_id} "
        f"for stable WeChat group {stable_receiver}"
    )
    return "enqueued"


def _remember_delivered_output(
    agent_bridge,
    task: dict,
    channel_type: str,
    content: str,
) -> None:
    """Best-effort persistence of the message the scheduler sent to a user.

    Uses notify_session_id (the real chat session_id stored at task creation time)
    so that group chats correctly associate the output with the user's conversation.
    Falls back to receiver for backward compatibility with old tasks.

    Per-action-type behaviour:
        - agent_task / tool_call / skill_call: gated by ``scheduler_inject_to_session``
          (default True). These produce AI-generated content worth remembering.
        - send_message: additionally gated by ``scheduler_inject_send_message``
          (default False). Fixed reminder text rarely benefits follow-up Q&A and
          would just consume context tokens.
    """
    if not content:
        return
    action = task.get("action", {})
    action_type = action.get("type", "")

    # send_message defaults to NOT being injected; explicit opt-in via config.
    if action_type == "send_message":
        if not conf().get("scheduler_inject_send_message", False):
            return

    session_id = action.get("notify_session_id") or action.get("receiver")
    if not session_id:
        return
    try:
        remember = getattr(agent_bridge, "remember_scheduled_output", None)
        if remember:
            task_desc = action.get("task_description") or action.get("content", "")
            remember(session_id, str(content), channel_type=channel_type, task_description=task_desc)
    except Exception as e:
        logger.warning(
            f"[Scheduler] Failed to remember delivered output for {session_id}: {e}"
        )


def _execute_agent_task(task: dict, agent_bridge) -> bool:
    """
    Execute an agent_task action - let Agent handle the task.
    Returns True on successful delivery, False to retry next tick.
    """
    try:
        action = _prepare_delivery_action(task)
        if action is None:
            return False
        task_description = action.get("task_description")
        receiver = action.get("receiver")
        is_group = action.get("is_group", False)
        channel_type = action.get("channel_type", "unknown")
        
        if not task_description:
            logger.error(f"[Scheduler] Task {task['id']}: No task_description specified")
            return True  # malformed task, don't loop forever
        
        if not receiver:
            logger.error(f"[Scheduler] Task {task['id']}: No receiver specified")
            return True
        
        # Check for unsupported channels
        if channel_type == "dingtalk":
            logger.warning(f"[Scheduler] Task {task['id']}: DingTalk channel does not support scheduled messages (Stream mode limitation). Task will execute but message cannot be sent.")
        
        logger.info(f"[Scheduler] Task {task['id']}: Executing agent task '{task_description}'")
        
        # Create a unique session_id for this scheduled task to avoid polluting user's conversation
        # Format: scheduler_<receiver>_<task_id> to ensure isolation
        scheduler_session_id = _scheduler_execution_session_id(action, task["id"], receiver)
        
        # Create context for Agent
        context = Context(ContextType.TEXT, task_description)
        context["receiver"] = receiver
        context["isgroup"] = is_group
        context["session_id"] = scheduler_session_id
        _apply_wechat_group_delivery_context(context, action)
        
        # Channel-specific setup
        if channel_type == "web":
            import uuid
            request_id = f"scheduler_{task['id']}_{uuid.uuid4().hex[:8]}"
            context["request_id"] = request_id
        elif channel_type == "feishu":
            context["receive_id_type"] = "chat_id" if is_group else "open_id"
            context["msg"] = None
        elif channel_type == "dingtalk":
            # DingTalk requires msg object, set to None for scheduled tasks
            context["msg"] = None
            if not is_group:
                sender_staff_id = action.get("dingtalk_sender_staff_id")
                if sender_staff_id:
                    context["dingtalk_sender_staff_id"] = sender_staff_id
        elif channel_type == "wecom_bot":
            context["msg"] = None

        # Use Agent to execute the task
        # Mark this as a scheduled task execution to prevent recursive task creation
        context["is_scheduled_task"] = True
        
        try:
            # Don't clear history - scheduler tasks use isolated session_id so they won't pollute user conversations
            reply = agent_bridge.agent_reply(task_description, context=context, on_event=None, clear_history=False)

            if not (reply and reply.content):
                logger.error(f"[Scheduler] Task {task['id']}: No result from agent execution")
                return True  # agent ran but produced nothing; don't loop

            channel = _create_delivery_channel(channel_type)
            if not channel:
                logger.error(f"[Scheduler] Failed to create channel: {channel_type}")
                return False

            if channel_type == "web" and hasattr(channel, 'request_to_session'):
                request_id = context.get("request_id")
                if request_id:
                    channel.request_to_session[request_id] = receiver

            try:
                channel.send(reply, context)
            except Exception as e:
                logger.error(f"[Scheduler] Failed to send result: {e}")
                return False

            _remember_delivered_output(agent_bridge, task, channel_type, reply.content)
            logger.info(f"[Scheduler] Task {task['id']} executed successfully, result sent to {receiver}")
            return True

        except Exception as e:
            logger.error(f"[Scheduler] Failed to execute task via Agent: {e}")
            import traceback
            logger.error(f"[Scheduler] Traceback: {traceback.format_exc()}")
            return False

    except Exception as e:
        logger.error(f"[Scheduler] Error in _execute_agent_task: {e}")
        import traceback
        logger.error(f"[Scheduler] Traceback: {traceback.format_exc()}")
        return False


def _execute_send_message(task: dict, agent_bridge) -> bool:
    """Execute a send_message action. Returns True/False for delivery."""
    try:
        action = _prepare_delivery_action(task)
        if action is None:
            return False
        content = action.get("content", "")
        receiver = action.get("receiver")
        is_group = action.get("is_group", False)
        channel_type = action.get("channel_type", "unknown")
        
        if not receiver:
            logger.error(f"[Scheduler] Task {task['id']}: No receiver specified")
            return True
        
        # Create context for sending message
        context = Context(ContextType.TEXT, content)
        context["receiver"] = receiver
        context["isgroup"] = is_group
        context["session_id"] = _wechat_group_delivery_session_id(action, receiver)
        _apply_wechat_group_delivery_context(context, action)
        
        # Channel-specific context setup
        if channel_type == "web":
            # Web channel needs request_id
            import uuid
            request_id = f"scheduler_{task['id']}_{uuid.uuid4().hex[:8]}"
            context["request_id"] = request_id
            logger.debug(f"[Scheduler] Generated request_id for web channel: {request_id}")
        elif channel_type == "feishu":
            # Feishu channel: for scheduled tasks, send as new message (no msg_id to reply to)
            # Use chat_id for groups, open_id for private chats
            context["receive_id_type"] = "chat_id" if is_group else "open_id"
            # Keep isgroup as is, but set msg to None (no original message to reply to)
            # Feishu channel will detect this and send as new message instead of reply
            context["msg"] = None
            logger.debug(f"[Scheduler] Feishu: receive_id_type={context['receive_id_type']}, is_group={is_group}, receiver={receiver}")
        elif channel_type == "dingtalk":
            # DingTalk channel setup
            context["msg"] = None
            # 如果是单聊，需要传递 sender_staff_id
            if not is_group:
                sender_staff_id = action.get("dingtalk_sender_staff_id")
                if sender_staff_id:
                    context["dingtalk_sender_staff_id"] = sender_staff_id
                    logger.debug(f"[Scheduler] DingTalk single chat: sender_staff_id={sender_staff_id}")
                else:
                    logger.warning(f"[Scheduler] Task {task['id']}: DingTalk single chat message missing sender_staff_id")
        elif channel_type == "wecom_bot":
            context["msg"] = None
        elif channel_type == "qq":
            context["msg"] = None

        # Create reply
        reply = Reply(ReplyType.TEXT, content)
        
        # Get channel and send
        channel = _create_delivery_channel(channel_type)
        if not channel:
            logger.error(f"[Scheduler] Failed to create channel: {channel_type}")
            return False

        if channel_type == "web" and hasattr(channel, 'request_to_session'):
            channel.request_to_session[request_id] = receiver

        try:
            channel.send(reply, context)
        except Exception as e:
            logger.error(f"[Scheduler] Failed to send message: {e}")
            return False

        if action.get("source") == "github_webhook" and action.get("external_delivery_id"):
            try:
                from channel.web.github_commit_webhook import mark_github_delivery_delivered

                mark_github_delivery_delivered(action.get("external_delivery_id"))
            except Exception as e:
                logger.warning(
                    f"[Scheduler] Failed to mark GitHub delivery as delivered: {e}"
                )

        _remember_delivered_output(agent_bridge, task, channel_type, content)
        logger.info(f"[Scheduler] Task {task['id']} executed: sent message to {receiver}")
        return True

    except Exception as e:
        logger.error(f"[Scheduler] Error in _execute_send_message: {e}")
        import traceback
        logger.error(f"[Scheduler] Traceback: {traceback.format_exc()}")
        return False


def _execute_tool_call(task: dict, agent_bridge) -> bool:
    """Execute a tool_call action. Returns True/False for delivery."""
    try:
        action = _prepare_delivery_action(task)
        if action is None:
            return False
        tool_name = action.get("call_name") or action.get("tool_name")
        tool_params = action.get("call_params") or action.get("tool_params", {})
        result_prefix = action.get("result_prefix", "")
        receiver = action.get("receiver")
        is_group = action.get("is_group", False)
        channel_type = action.get("channel_type", "unknown")

        if not tool_name:
            logger.error(f"[Scheduler] Task {task['id']}: No tool_name specified")
            return True
        if not receiver:
            logger.error(f"[Scheduler] Task {task['id']}: No receiver specified")
            return True

        from agent.tools.tool_manager import ToolManager
        tool = ToolManager().create_tool(tool_name)
        if not tool:
            logger.error(f"[Scheduler] Task {task['id']}: Tool '{tool_name}' not found")
            return True

        logger.info(f"[Scheduler] Task {task['id']}: Executing tool '{tool_name}' with params {tool_params}")
        result = tool.execute(tool_params)
        content = result.result if hasattr(result, 'result') else str(result)
        if result_prefix:
            content = f"{result_prefix}\n\n{content}"

        context = Context(ContextType.TEXT, content)
        context["receiver"] = receiver
        context["isgroup"] = is_group
        context["session_id"] = _wechat_group_delivery_session_id(action, receiver)
        _apply_wechat_group_delivery_context(context, action)

        request_id = None
        if channel_type == "web":
            import uuid
            request_id = f"scheduler_{task['id']}_{uuid.uuid4().hex[:8]}"
            context["request_id"] = request_id
        elif channel_type == "feishu":
            context["receive_id_type"] = "chat_id" if is_group else "open_id"
            context["msg"] = None
        elif channel_type == "wecom_bot":
            context["msg"] = None

        reply = Reply(ReplyType.TEXT, content)

        channel = _create_delivery_channel(channel_type)
        if not channel:
            logger.error(f"[Scheduler] Failed to create channel: {channel_type}")
            return False

        if channel_type == "web" and request_id and hasattr(channel, 'request_to_session'):
            channel.request_to_session[request_id] = receiver

        try:
            channel.send(reply, context)
        except Exception as e:
            logger.error(f"[Scheduler] Failed to send tool result: {e}")
            return False

        _remember_delivered_output(agent_bridge, task, channel_type, content)
        logger.info(f"[Scheduler] Task {task['id']} executed: sent tool result to {receiver}")
        return True

    except Exception as e:
        logger.error(f"[Scheduler] Error in _execute_tool_call: {e}")
        return False


def _execute_skill_call(task: dict, agent_bridge) -> bool:
    """Execute a skill_call action by asking Agent to run the skill.
    Returns True/False for delivery."""
    try:
        action = _prepare_delivery_action(task)
        if action is None:
            return False
        skill_name = action.get("call_name") or action.get("skill_name")
        skill_params = action.get("call_params") or action.get("skill_params", {})
        result_prefix = action.get("result_prefix", "")
        receiver = action.get("receiver")
        is_group = action.get("isgroup", False)
        channel_type = action.get("channel_type", "unknown")

        if not skill_name:
            logger.error(f"[Scheduler] Task {task['id']}: No skill_name specified")
            return True
        if not receiver:
            logger.error(f"[Scheduler] Task {task['id']}: No receiver specified")
            return True

        logger.info(f"[Scheduler] Task {task['id']}: Executing skill '{skill_name}' with params {skill_params}")

        scheduler_session_id = _scheduler_execution_session_id(action, task["id"], receiver)
        param_str = ", ".join([f"{k}={v}" for k, v in skill_params.items()])
        query = f"Use {skill_name} skill"
        if param_str:
            query += f" with {param_str}"

        context = Context(ContextType.TEXT, query)
        context["receiver"] = receiver
        context["isgroup"] = is_group
        context["session_id"] = scheduler_session_id
        _apply_wechat_group_delivery_context(context, action)

        if channel_type == "web":
            import uuid
            request_id = f"scheduler_{task['id']}_{uuid.uuid4().hex[:8]}"
            context["request_id"] = request_id
        elif channel_type == "feishu":
            context["receive_id_type"] = "chat_id" if is_group else "open_id"
            context["msg"] = None
        elif channel_type == "wecom_bot":
            context["msg"] = None

        try:
            reply = agent_bridge.agent_reply(query, context=context, on_event=None, clear_history=False)
        except Exception as e:
            logger.error(f"[Scheduler] Failed to execute skill via Agent: {e}")
            import traceback
            logger.error(f"[Scheduler] Traceback: {traceback.format_exc()}")
            return False

        if not (reply and reply.content):
            logger.error(f"[Scheduler] Task {task['id']}: No result from skill execution")
            return True

        content = reply.content
        if result_prefix:
            content = f"{result_prefix}\n\n{content}"

        channel = _create_delivery_channel(channel_type)
        if not channel:
            logger.error(f"[Scheduler] Failed to create channel: {channel_type}")
            return False

        if channel_type == "web" and hasattr(channel, 'request_to_session'):
            req_id = context.get("request_id")
            if req_id:
                channel.request_to_session[req_id] = receiver

        try:
            channel.send(Reply(ReplyType.TEXT, content), context)
        except Exception as e:
            logger.error(f"[Scheduler] Failed to send skill result: {e}")
            return False

        _remember_delivered_output(agent_bridge, task, channel_type, content)
        logger.info(f"[Scheduler] Task {task['id']} executed: skill result sent to {receiver}")
        return True

    except Exception as e:
        logger.error(f"[Scheduler] Error in _execute_skill_call: {e}")
        import traceback
        logger.error(f"[Scheduler] Traceback: {traceback.format_exc()}")
        return False


def attach_scheduler_to_tool(tool, context: Context = None):
    """
    Attach scheduler components to a SchedulerTool instance
    
    Args:
        tool: SchedulerTool instance
        context: Current context (optional)
    """
    if _task_store:
        tool.task_store = _task_store
    
    if context:
        tool.current_context = context
        
        channel_type = context.get("channel_type") or conf().get("channel_type", "unknown")
        if not tool.config:
            tool.config = {}
        tool.config["channel_type"] = channel_type
