# 定时任务确认闭环修复计划

## 目标

修复 Agent 在聊天中口头确认“已设置定时任务”但实际没有调用 `scheduler.create`、没有落库的问题；微信群与普通聊天共享同一保护闭环。

## 范围

- 在 Agent 执行层识别本轮是否成功执行 `scheduler.create`。
- 当当前消息明确要求定时/提醒/周期任务，但本轮没有成功创建 scheduler 任务时，禁止输出“已设置”类假确认。
- 在个人微信群通道中给明确调度请求打标，降低人设和最近群聊上下文对任务意图的稀释。
- 不在本阶段扩展 `scheduler` 的 `end_at` / `until` 能力；“持续到某日期/赛事结束”仍由任务内容说明或后续停用处理。

## 文件计划

- `agent/protocol/agent_stream.py`
  - 新增本轮 scheduler create 成功状态记录。
  - 新增调度请求启发式识别与最终回复拦截。
- `channel/wechat_group/wechat_group_channel.py`
  - 对微信群原始消息中的调度请求设置 `intent_requires_scheduler`。
- `tests/test_agent_stream_scheduler_guard.py`
  - 覆盖未调用 scheduler 时的假确认拦截。
  - 覆盖已成功调用 scheduler.create 时不拦截。
- `tests/test_wechat_group_channel.py`
  - 覆盖微信群定时请求会带上 intent 标记。
- `CHANGES.md`
  - 记录本次代码修复与验证结果。

## 实施步骤

1. 新增失败测试：Agent 最终回复“已设置”但没有 scheduler create 时应被替换为失败提示。
2. 新增失败测试：scheduler create 成功后，正常确认不应被替换。
3. 新增失败测试：微信群消息“每天12点提醒/播报”进入上下文后应有 `intent_requires_scheduler=True`。
4. 实现 Agent 执行层状态记录与拦截。
5. 实现微信群 intent 标记。
6. 更新 `CHANGES.md` 和本计划完成状态。
7. 运行最小相关测试：
   - `python -m unittest tests.test_agent_stream_scheduler_guard tests.test_wechat_group_channel`
   - `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

## 完成记录

- 状态：已完成代码实现与自动化验证
- 实际改动：
  - `agent/protocol/agent_stream.py` 新增调度请求识别、scheduler create 成功记录、假确认拦截和会话历史同步替换。
  - `agent/protocol/agent.py`、`bridge/agent_bridge.py`、`agent/chat/service.py` 透传当前 context 给执行器。
  - `channel/wechat_group/wechat_group_channel.py` 对微信群调度请求设置 `intent_requires_scheduler`。
  - `agent/prompt/builder.py` 在 scheduler 可用时提示模型必须调用 scheduler，不能仅口头确认。
  - 新增 `tests/test_agent_stream_scheduler_guard.py`、`tests/test_prompt_scheduler_guidance.py`，扩展 `tests/test_wechat_group_channel.py`。
- 验证结果：
  - `python -m unittest tests.test_agent_stream_scheduler_guard`
  - `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_wechat_group_scheduler_request_sets_scheduler_intent`
  - `python -m unittest tests.test_prompt_scheduler_guidance`
  - `python -m unittest tests.test_agent_stream_scheduler_guard tests.test_prompt_scheduler_guidance tests.test_wechat_group_channel`
  - `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
  - `python -m py_compile agent\protocol\agent_stream.py agent\protocol\agent.py agent\chat\service.py bridge\agent_bridge.py channel\wechat_group\wechat_group_channel.py agent\prompt\builder.py tests\test_agent_stream_scheduler_guard.py tests\test_prompt_scheduler_guidance.py tests\test_wechat_group_channel.py`
- 剩余事项：
  - 本阶段未实现 `scheduler` 的 `end_at` / `until`，周期任务自动停止仍需单独设计。
  - 真实微信群链路仍需人工验证：群内 @ 机器人创建每日任务，并在 Web 定时任务列表或 `tasks.json` 中确认落库。
