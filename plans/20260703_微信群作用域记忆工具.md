# 微信群作用域记忆工具实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 为个人微信群 Agent 回复链路增加当前群绑定的记忆/画像检索工具，让 Agent 能按需二次查询群记忆，同时保持 room 隔离。

**架构:** 新增一组只由微信群请求临时挂载的工具，工具构造时绑定 `room_id`、`sender_id`、`bot_sender_id` 和 `WechatGroupMemoryService`，参数中不暴露 `room_id`。`AgentBridge.agent_reply()` 在 `channel_type == "wechat_group"` 且上下文包含微信群消息时临时追加工具和系统提示后缀，运行结束恢复原工具列表和后缀。

**技术栈:** Python、`BaseTool`、`MemoryManager`/`MemoryScope`、`WechatGroupMemoryService`、`unittest`。

---

## 文件结构

- 新增 `channel/wechat_group/wechat_group_memory_tools.py`：当前群绑定工具实现与工具构造函数。
- 修改 `bridge/agent_bridge.py`：在微信群 turn 临时挂载 scoped memory tools，并恢复原状态。
- 修改 `agent/prompt/builder.py`：为微信群工具补充工具列表摘要。
- 修改 `tests/test_wechat_group_memory.py`：覆盖工具直接检索群记忆/画像、room 隔离和参数不暴露 room。
- 新增或修改 `tests/test_wechat_group_context.py`：覆盖微信群上下文可触发工具临时挂载。
- 修改 `CHANGES.md`：记录代码变更与验证结果。

## 任务清单

### Task 1: 失败测试 - scoped 工具行为

- [ ] 在 `tests/test_wechat_group_memory.py` 中新增测试：
  - `wechat_group_memory_search` 只返回当前 room 的群记忆。
  - `wechat_group_profile_get` 返回当前发言人画像或指定 sender_id 的当前群画像。
  - 工具 schema 不包含 `room_id` 参数。
- [ ] 运行 `python -m unittest tests.test_wechat_group_memory`，确认新增测试因工具不存在失败。

### Task 2: 最小实现 - scoped 工具

- [ ] 新增 `channel/wechat_group/wechat_group_memory_tools.py`。
- [ ] 实现 `WechatGroupMemorySearchTool`：
  - 参数：`query`、`max_results`、`min_score`。
  - 内部使用 `MemoryScope.wechat_group(bound_room_id)` 搜索。
- [ ] 实现 `WechatGroupProfileGetTool`：
  - 参数：可选 `sender_id`。
  - 不传时读取当前发言人画像。
  - 传入时只在当前 room 内读取该 sender 的画像。
- [ ] 实现 `create_wechat_group_memory_tools(...)` 作为 AgentBridge 调用入口。
- [ ] 运行 `python -m unittest tests.test_wechat_group_memory`，确认通过。

### Task 3: 失败测试 - AgentBridge 临时挂载

- [ ] 新增/补充测试，构造 `Context`，设置：
  - `channel_type = "wechat_group"`
  - `wechat_group_room_id`
  - `wechat_group_sender_id`
  - `wechat_group_bot_sender_id`
- [ ] 断言当前 turn 的 Agent 工具列表包含 `wechat_group_memory_search` 和 `wechat_group_profile_get`。
- [ ] 断言 run 结束后 Agent 工具列表恢复原状。
- [ ] 运行对应测试，确认因 AgentBridge 未挂载失败。

### Task 4: 最小实现 - AgentBridge 挂载和 Prompt 规则

- [ ] 在 `WechatGroupChannel._compose_context()` 中写入 `wechat_group_room_id`、`wechat_group_sender_id`、`wechat_group_bot_sender_id`。
- [ ] 在 `AgentBridge.agent_reply()` 中检测微信群上下文并临时追加 scoped tools。
- [ ] 临时追加 `extra_system_suffix`，提示：
  - 涉及当前群规、群偏好、群历史约定时优先调用 `wechat_group_memory_search`。
  - 涉及当前群成员偏好、角色、边界、画像时优先调用 `wechat_group_profile_get`。
  - 不要把微信群工具当成跨群或全局记忆查询。
- [ ] 在 `finally` 中恢复原工具列表和原 `extra_system_suffix`。
- [ ] 在 `agent/prompt/builder.py` 为两个工具增加简短摘要。

### Task 5: 验证与记录

- [ ] 运行 `python -m unittest tests.test_wechat_group_memory tests.test_wechat_group_context`。
- [ ] 如 AgentBridge 增加独立测试文件，运行该测试文件。
- [ ] 更新 `CHANGES.md`，记录日期、背景、改动文件和验证结果。
- [ ] 检查 `git diff --stat` 和 `git diff --check`。

## 当前状态

- [x] 已确认设计方向。
- [x] 已创建实施计划。
- [x] 已写失败测试并确认 RED：
  - `python -m unittest tests.test_wechat_group_memory_tools`
  - `python -m unittest tests.test_wechat_group_agent_bridge_tools`
  - `python -m unittest tests.test_wechat_group_context`
- [x] 已实现：
  - 新增 `channel/wechat_group/wechat_group_memory_tools.py`。
  - `WechatGroupChannel._compose_context()` 注入 `wechat_group_room_id`、`wechat_group_sender_id`、`wechat_group_bot_sender_id`。
  - `AgentBridge.agent_reply()` 在微信群 turn 临时挂载 scoped memory tools 和提示后缀，并在结束后恢复。
  - `agent/prompt/builder.py` 补充两个微信群工具摘要。
- [x] 已验证：
  - `python -m unittest tests.test_wechat_group_memory_tools tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_context tests.test_wechat_group_memory`
  - `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_memory_tools tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_context tests.test_wechat_group_memory`
  - `python -m py_compile channel\wechat_group\wechat_group_memory_tools.py channel\wechat_group\wechat_group_channel.py bridge\agent_bridge.py agent\prompt\builder.py tests\test_wechat_group_memory_tools.py tests\test_wechat_group_agent_bridge_tools.py tests\test_wechat_group_context.py`
  - `git diff --check`
- [x] 已完成 `CHANGES.md` 记录。
