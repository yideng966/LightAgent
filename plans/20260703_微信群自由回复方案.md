# 微信群自由回复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 CowAgent 个人微信群通道中实现可按指定群开启、按本地规则评分与阈值筛选、再经 LLM 二次判定后自然接话的“自由回复”能力。

**Architecture:** 自由回复只扩展 `channel/wechat_group/` 的渠道适配层，不新增独立 Agent loop。普通文本消息（未 @ 机器人）先经过群范围、本地评分、强抑制和运行时限流；命中后进入自由回复独立 worker 池；worker 执行 TTL 检查和轻量 LLM JSON 二次判定；判定通过后再复用现有 `WechatGroupChannel -> ChatChannel -> Channel.build_reply_content() -> Bridge` 最终回复链路。@ 机器人、群前缀、群关键词触发仍走原必回链路，不进入自由回复 worker 池，不受自由回复阈值、冷却和 LLM 二次判定影响。

**Tech Stack:** Python `unittest`、CowAgent `ChatChannel` / `Context` / `Reply`、`Bridge().fetch_reply_content()` 轻量聊天判定、Wechaty sidecar JSON Lines、Web 控制台原生 HTML/CSS/JS、现有 Tailwind/FontAwesome 风格。

---

## 1. 需求边界

### 1.1 必须实现

- 功能名称统一为“自由回复”。
- 自由回复总开关，默认关闭。
- 自由回复群范围与 @ 必回群范围分离。
- 支持按 `room_id` 精确开启自由回复；群名只作为兜底。
- 首轮只处理普通文本消息。
- 本地规则生成接话得分，达到当前活跃档位阈值后才进入 worker 池。
- 本地评分低于阈值、命中强抑制、命中冷却或上限时，直接静默，不调用 LLM。
- 自由回复必须进入独立 worker 池执行，避免自由回复任务挤占 @ 必回链路。
- worker 池必须支持最大并发、队列长度、排队 TTL 和运行状态快照。
- worker 中必须执行 LLM 二次判定是否接话。
- LLM 二次判定只允许轻量 JSON 判定：不调用 Agent 工具、不写记忆、不发送消息、不新增模型 Provider。
- LLM 二次判定通过后，最终回复仍复用 CowAgent 原回复链路。
- 自由回复默认不真实 mention 发言人，也不拼接普通文本 `@昵称`。
- 自由回复继续注入微信群人设、最近群聊上下文、群记忆、群友画像。
- Web 控制台支持配置开关、自由回复群、活跃档位、阈值、冷却、小时上限、连续上限、worker 参数和 LLM 判定参数。
- Web 控制台展示最近一次本地判定、LLM 判定和 worker 状态，便于排障。
- @ 机器人、群前缀、群关键词触发仍按原逻辑必回，不受自由回复影响。

### 1.2 首轮不实现

- 图片、语音、视频消息的自由回复。
- 完整判定日志检索页；首轮只展示最近一次判定快照。
- 桌面端 `desktop/` UI；首轮只实现 Web 控制台 UI。
- 社交工作台、战报、图库、备份迁移中心。

### 1.3 默认策略

- 文本自由回复默认关闭。
- 开启后自由回复默认不 @ 原发送者。
- 自由回复群不能绕过接入群校验：消息必须先属于当前微信群通道接入范围，再判断是否属于自由回复范围。
- 如果自由回复任务排队超过 TTL，worker 丢弃该任务，避免旧话题延迟接话。
- LLM 二次判定失败、超时、返回非 JSON、置信度不足或建议不接话时，默认静默。
- LLM 二次判定默认开启；关闭开关只作为排障兜底，不作为推荐运行模式。
- @ 必回消息不进入自由回复 worker 池，也不做自由回复 LLM 二次判定。

---

## 2. 文件结构与职责

### 2.1 新增文件

- `channel/wechat_group/wechat_group_free_reply.py`
  - 自由回复配置归一化。
  - 自由回复群范围判断。
  - 文本评分规则。
  - 强抑制规则。
  - 每群运行时限流状态。
  - 最近一次本地判定快照。

- `channel/wechat_group/wechat_group_free_reply_judge.py`
  - 构造 LLM 二次判定 prompt。
  - 调用 `Bridge().fetch_reply_content(query, context)` 获取轻量判定。
  - 解析严格 JSON 输出。
  - 处理超时、异常、非 JSON、置信度不足。
  - 返回统一 `FreeReplyJudgeDecision` 字典。

- `channel/wechat_group/wechat_group_free_reply_worker.py`
  - 管理自由回复独立 worker 池。
  - 管理自由回复队列、最大并发、队列长度、TTL。
  - 执行 LLM 二次判定。
  - 判定通过后回调通道提交最终回复上下文。
  - 提供运行状态快照。

- `tests/test_wechat_group_free_reply.py`
  - 覆盖配置、评分、抑制、阈值、冷却、群范围、最近判定。

- `tests/test_wechat_group_free_reply_judge.py`
  - 覆盖 LLM 判定 JSON 解析、失败静默、置信度阈值、prompt 约束。

- `tests/test_wechat_group_free_reply_worker.py`
  - 覆盖入队、TTL 过期、队列满、worker 并发、判定通过回调、判定失败静默。

### 2.2 修改文件

- `config.py`
  - 增加自由回复默认配置。

- `config-template.json`
  - 同步示例配置。

- `channel/wechat_group/wechat_group_channel.py`
  - 初始化自由回复状态、LLM 判定器和 worker 池。
  - 在普通文本消息（未 @ 机器人）进入 `_compose_context()` 前做本地自由回复判定。
  - 本地判定命中后只入队，不直接 `produce()`。
  - worker 的 LLM 判定通过后再组装 `Context` 并 `produce()`。
  - 自由回复上下文标记 `wechat_group_free_reply_triggered`、`wechat_group_free_reply_decision`、`wechat_group_free_reply_llm_decision`、`no_need_at`、`suppress_mention`。
  - 发送自由回复时不传 `mention_ids`。
  - 对外暴露 `free_reply_status()`，供 Web API 读取。
  - 通道停止时关闭自由回复 worker 池。

- `channel/web/web_channel.py`
  - `wechat_group.extra` 返回自由回复配置、规则、最近判定和 worker 状态。
  - `/api/channels save/wechat_group` 允许保存自由回复配置。
  - 做类型归一化和边界校验。

- `channel/web/static/js/console.js`
  - 群聊管理页新增“自由回复”子区。
  - 支持自由回复群选择、档位、阈值、worker 参数、LLM 判定参数、最近判定展示。
  - 保存时把自由回复配置写入 `save/wechat_group`。

- `channel/web/chat.html`
  - 如果当前脚本使用 `console.js?v=<version>`，将版本号递增一次以降低浏览器缓存影响。
  - 如果群聊页容器缺少承载自由回复配置的锚点，新增 `id="wechat-group-free-reply-settings"` 挂载点。

- `tests/test_wechat_group_channel.py`
  - 覆盖自由回复命中/不命中、@ 必回不入队、worker 通过后 produce、自由回复不 mention。

- `tests/test_wechat_group_web.py`
  - 覆盖 `extra.free_reply` 返回与保存配置。

- `CHANGES.md`
  - 仅在实际代码开发完成时追加变更记录；本计划文档本身不要求更新。

---

## 3. 配置设计

新增保守默认值：

```json
{
  "wechat_group_free_reply_enabled": false,
  "wechat_group_free_reply_room_ids": [],
  "wechat_group_free_reply_names": [],
  "wechat_group_free_reply_activity_level": "normal",
  "wechat_group_free_reply_queue_ttl_seconds": 120,
  "wechat_group_free_reply_worker_max_workers": 2,
  "wechat_group_free_reply_worker_queue_size": 100,
  "wechat_group_free_reply_llm_judge_enabled": true,
  "wechat_group_free_reply_llm_judge_timeout_seconds": 8,
  "wechat_group_free_reply_llm_judge_min_confidence": 0.6,
  "wechat_group_free_reply_profiles": {
    "quiet": { "min_score": 65, "min_interval_seconds": 30, "hourly_limit": 0, "consecutive_limit": 0 },
    "normal": { "min_score": 50, "min_interval_seconds": 10, "hourly_limit": 0, "consecutive_limit": 0 },
    "active": { "min_score": 35, "min_interval_seconds": 3, "hourly_limit": 0, "consecutive_limit": 0 },
    "crazy": { "min_score": 20, "min_interval_seconds": 0, "hourly_limit": 0, "consecutive_limit": 0 }
  }
}
```

兼容说明：

- `wechat_group_free_reply_room_ids` 优先级高于群名。
- `wechat_group_free_reply_names` 只作为没有稳定 `room_id` 时的兜底。
- `wechat_group_room_ids` / `wechat_group_names` 继续只表示接入与 @ 必回范围。
- 自由回复群不能绕过 `_is_selected_room()`；消息必须先属于接入群，再判断是否属于自由回复群。
- LLM 二次判定复用当前聊天模型配置，不新增单独 Provider 配置。

数值边界：

```text
activity_level: quiet | normal | active | crazy
min_score: 0-100
min_interval_seconds: 0-3600
hourly_limit: 0-999，0 表示不限
consecutive_limit: 0-99，0 表示不限
free_reply_queue_ttl_seconds: 10-600
free_reply_worker_max_workers: 1-8
free_reply_worker_queue_size: 1-1000
free_reply_llm_judge_timeout_seconds: 1-30
free_reply_llm_judge_min_confidence: 0.0-1.0
```

---

## 4. 判定链路

### 4.1 本地规则初筛

本地初筛只处理普通文本消息（未 @ 机器人）：

1. 消息必须来自当前已接入微信群。
2. 消息所在群必须开启自由回复。
3. 排除机器人自己的消息、屏蔽成员、低信息短句、敏感/危险/本机文件、明显刷屏、两人私聊式对话。
4. 按规则加分和扣分。
5. 检查当前活跃档位阈值。
6. 检查冷却、小时上限、连续上限。
7. 命中后生成 `free_reply_task` 入队。

加分规则：

- 提到机器人昵称但未 @：+45
- 明显向群里求助/提问：+30
- 短时间无人回答的问题：+25
- 命中 CowAgent 能力：+25
- 需要群记忆/聊天记录：+20
- 问 AI 怎么看：+35
- 玩笑接梗：按档位 +5/+10/+18/+28
- 冷场可接话点：+10

抑制规则：

- 机器人自己的消息。
- 群未开启自由回复。
- 屏蔽成员。
- 低信息短句。
- 两人私聊式对话。
- 刷屏。
- 敏感、危险、隐私、本机文件请求。
- 冷却、小时上限、连续上限。

### 4.2 worker 池处理

自由回复 worker 池只处理自由回复候选任务：

```text
handle_text()
  ├─ @ / 前缀 / 关键词：原必回链路
  └─ 普通文本（未 @ 机器人）：
      ├─ 本地评分未命中：静默
      └─ 本地评分命中：enqueue(task)
             └─ worker:
                 ├─ TTL 过期：丢弃
                 ├─ LLM 二次判定失败：静默
                 └─ LLM 二次判定通过：compose_context() -> produce()
```

worker 状态快照：

```json
{
  "running": true,
  "max_workers": 2,
  "queue_size": 0,
  "queue_limit": 100,
  "active_workers": 0,
  "submitted_total": 0,
  "dropped_total": 0,
  "expired_total": 0,
  "approved_total": 0,
  "rejected_total": 0,
  "last_error": ""
}
```

### 4.3 LLM 二次判定

LLM 判定必须使用轻量 JSON 输出：

```json
{
  "should_reply": true,
  "confidence": 0.82,
  "reason": "群内有人提出需要总结的开放问题，机器人可自然补充。",
  "tone": "natural"
}
```

判定 prompt 要求：

- 只判断是否适合接话，不生成最终回复正文。
- 只返回 JSON，不返回 Markdown。
- 不要求工具调用。
- 不写记忆。
- 不使用跨群信息。
- 对敏感、隐私、危险、低信息、两人私聊、刷屏场景返回 `should_reply=false`。

判定失败策略：

- 超时：静默，`suppressions += ["llm_judge_timeout"]`。
- 非 JSON：静默，`suppressions += ["llm_judge_invalid_json"]`。
- `should_reply=false`：静默，记录原因。
- `confidence < min_confidence`：静默，`suppressions += ["llm_judge_low_confidence"]`。

---

## 5. UI 设计

### 5.1 信息架构

默认只修改 Web 控制台群聊管理页，不修改桌面端。

群聊管理页建议维持现有子区结构，在“群聊开关 / 目标群”之后新增“自由回复”配置块：

```text
群聊
├─ 基础设置
├─ 群聊开关
├─ 自由回复
├─ 人设设定
└─ 永久记忆
```

如果当前页面尚未有稳定子导航，则在右侧内容区按顺序插入“自由回复”折叠区，不新增新的全局导航。

### 5.2 布局原则

- 使用现有控制台页面宽度、间距、边框、深浅色模式样式。
- 每个配置区使用现有轻量分组样式，不做营销式 hero。
- 不使用卡片套卡片。
- 长 `room_id` 使用 `font-mono break-all text-xs`。
- 群名、规则说明、判定原因允许换行，不横向撑破。
- 所有输入必须有可见 label 和短 hint。
- 保存按钮异步时 disabled 并显示 loading。
- 输入非法值时在字段下方显示错误，不只在顶部提示。
- 状态 tag 必须有文本，不只靠颜色表达含义。

### 5.3 控件明细

#### 总开关

- 控件：checkbox / toggle。
- 文案：`启用自由回复`。
- 帮助文本：`开启后仅对下方选择的群生效；@ 机器人仍然必回。`
- 默认：关闭。

#### 自由回复群

- 控件：复用当前目标群列表的多选 checkbox。
- 每行显示群名、`room_id`、是否已在接入群范围内。
- 如果没有群列表，显示“登录后刷新群列表，或先填写群名兜底”。
- 群名兜底输入使用 textarea，每行一个群名。

#### 活跃档位

- 控件：segmented buttons 或 radio group。
- 选项：安静 `quiet`、正常 `normal`、活跃 `active`、发疯 `crazy`。
- 选中后显示对应档位的阈值表单。

#### 当前档位参数

- `接话阈值`：number，0-100。
- `最小间隔（秒）`：number，0-3600。
- `每小时上限`：number，0-999，0 表示不限。
- `连续发言上限`：number，0-99，0 表示不限。
- `排队 TTL（秒）`：number，10-600，全局字段。

#### worker 池参数

- `worker 并发数`：number，1-8。
- `队列长度上限`：number，1-1000。
- 只读状态：运行中、排队数、活跃 worker、丢弃数、过期数、通过数、拒绝数、最近错误。

#### LLM 二次判定

- `启用 LLM 二次判定`：toggle，默认开启。
- `判定超时（秒）`：number，1-30。
- `最低置信度`：number，0-1，步长 0.05。
- 只读说明：`LLM 判定只判断是否接话，不生成最终回复，不调用工具。`

#### 最近判定

只读诊断区字段：

- 群名。
- 发送者昵称。
- 本地得分 / 阈值。
- 本地是否命中。
- LLM 是否建议接话。
- LLM 置信度。
- worker 结果：queued / expired / approved / rejected / error。
- 活跃档位。
- 加分原因 tags。
- 抑制原因 tags。
- 时间。
- 文本预览。

空状态：

```text
还没有自由回复判定。开启后，普通群消息会先经过本地评分和 LLM 二次判定。
```

### 5.4 UI 验证点

- 375px 宽度不横向滚动。
- 深色模式下文字、边框、错误状态可读。
- 所有输入有可见 label。
- 保存按钮有 loading/disabled 状态。
- 规则 tags 不仅靠颜色表达含义，必须有文本。
- 最近判定为空、本地未命中、LLM 拒绝、LLM 通过、TTL 过期五种状态都有明确展示。

---

## 6. 任务分解

### Task 1: 自由回复配置与本地评分模块

**Files:**
- Create: `channel/wechat_group/wechat_group_free_reply.py`
- Create: `tests/test_wechat_group_free_reply.py`
- Modify: `config.py`
- Modify: `config-template.json`

- [ ] **Step 1: 编写默认配置测试**

测试点：

```python
def test_default_config_is_disabled_and_normal(self):
    cfg = get_wechat_group_free_reply_config()

    self.assertFalse(cfg["enabled"])
    self.assertEqual("normal", cfg["activity_level"])
    self.assertEqual(120, cfg["queue_ttl_seconds"])
    self.assertEqual(2, cfg["worker_max_workers"])
    self.assertEqual(100, cfg["worker_queue_size"])
    self.assertTrue(cfg["llm_judge_enabled"])
    self.assertEqual(8, cfg["llm_judge_timeout_seconds"])
    self.assertEqual(0.6, cfg["llm_judge_min_confidence"])
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
python -m unittest tests.test_wechat_group_free_reply.WechatGroupFreeReplyConfigTest.test_default_config_is_disabled_and_normal
```

Expected:

```text
ModuleNotFoundError: No module named 'channel.wechat_group.wechat_group_free_reply'
```

- [ ] **Step 3: 增加配置默认值**

在 `config.py` 和 `config-template.json` 加入第 3 节列出的全部 `wechat_group_free_reply_*` 配置键。

- [ ] **Step 4: 实现配置归一化**

`get_wechat_group_free_reply_config()` 必须返回：

```python
{
    "enabled": bool,
    "room_ids": list[str],
    "names": list[str],
    "activity_level": "quiet" | "normal" | "active" | "crazy",
    "queue_ttl_seconds": int,
    "worker_max_workers": int,
    "worker_queue_size": int,
    "llm_judge_enabled": bool,
    "llm_judge_timeout_seconds": int,
    "llm_judge_min_confidence": float,
    "profiles": dict,
}
```

- [ ] **Step 5: 编写评分与抑制测试**

覆盖以下用例和断言：

```python
def test_room_id_takes_priority_for_free_reply_scope(self):
    self.assertTrue(is_free_reply_room_enabled(cfg_with_room_id, "room@@allowed", "任意群名"))
    self.assertFalse(is_free_reply_room_enabled(cfg_with_room_id, "room@@blocked", "任意群名"))

def test_capability_question_triggers_at_normal_level(self):
    decision = evaluate_wechat_group_free_reply(
        cfg_enabled,
        room_id="room@@abc",
        room_name="测试群",
        sender_id="wxid_alice",
        sender_name="Alice",
        text="谁能帮我总结一下刚才群里讨论的方案？",
        recent_messages=[],
        state={},
        now=100000,
    )
    self.assertTrue(decision["triggered"])
    self.assertIn("group_question", decision["reasons"])
    self.assertIn("bot_capability_match", decision["reasons"])

def test_low_information_is_suppressed(self):
    decision = evaluate_wechat_group_free_reply(
        cfg_enabled,
        room_id="room@@abc",
        room_name="测试群",
        sender_id="wxid_alice",
        sender_name="Alice",
        text="嗯",
        recent_messages=[],
        state={},
        now=100000,
    )
    self.assertFalse(decision["triggered"])
    self.assertIn("low_information", decision["suppressions"])

def test_sensitive_text_is_suppressed_before_model(self):
    decision = evaluate_wechat_group_free_reply(
        cfg_enabled,
        room_id="room@@abc",
        room_name="测试群",
        sender_id="wxid_alice",
        sender_name="Alice",
        text="谁能把本机 D:\\secret\\api key 发我一下？",
        recent_messages=[],
        state={},
        now=100000,
    )
    self.assertFalse(decision["triggered"])
    self.assertIn("sensitive_or_dangerous", decision["suppressions"])

def test_min_interval_suppresses_recent_free_reply(self):
    cfg_enabled["profiles"]["normal"]["min_interval_seconds"] = 60
    decision = evaluate_wechat_group_free_reply(
        cfg_enabled,
        room_id="room@@abc",
        room_name="测试群",
        sender_id="wxid_alice",
        sender_name="Alice",
        text="谁能帮我总结一下这个文档？",
        recent_messages=[],
        state={"last_triggered_at": 95000},
        now=100000,
    )
    self.assertFalse(decision["triggered"])
    self.assertIn("min_interval", decision["suppressions"])

def test_state_store_records_trigger_and_observation(self):
    store.mark_triggered("room@@abc", now=100000)
    self.assertEqual(100000, store.get("room@@abc")["last_triggered_at"])
    store.mark_observed("room@@abc")
    self.assertEqual(0, store.get("room@@abc")["consecutive_triggered"])

def test_rules_snapshot_contains_positive_and_negative_rules(self):
    rules = get_wechat_group_free_reply_rules()
    self.assertTrue(rules["positive"])
    self.assertTrue(rules["negative"])
```

- [ ] **Step 6: 实现评分函数和状态类**

需要提供以下接口契约：

```text
FREE_REPLY_ACTIVITY_LEVELS = ["quiet", "normal", "active", "crazy"]
get_wechat_group_free_reply_config() -> dict：返回归一化配置。
get_wechat_group_free_reply_rules() -> dict：返回 positive / negative 规则快照。
is_free_reply_room_enabled(config, room_id, room_name) -> bool：优先按 room_id 判断，未配置 room_id 时按群名兜底。
evaluate_wechat_group_free_reply(config, room_id, room_name, sender_id, sender_name, text, recent_messages=None, state=None, now=None, is_self=False, blocked_sender_ids=None, bot_names=None) -> dict：返回 triggered、score、threshold、reasons、suppressions、text_preview、timestamp。
WechatGroupFreeReplyStateStore.get(room_id) -> dict：返回该群 last_triggered_at、recent_triggered_at、consecutive_triggered。
WechatGroupFreeReplyStateStore.mark_triggered(room_id, now) -> None：记录一次通过本地判定并入队的自由回复。
WechatGroupFreeReplyStateStore.mark_observed(room_id) -> None：记录普通观察消息并重置连续回复计数。
WechatGroupFreeReplyStateStore.remember_decision(decision) -> None：保存最近一次本地判定快照。
WechatGroupFreeReplyStateStore.last_decision() -> dict：返回最近一次本地判定快照副本。
```

- [ ] **Step 7: 运行模块测试**

Run:

```powershell
python -m unittest tests.test_wechat_group_free_reply
```

Expected:

```text
OK
```

### Task 2: LLM 二次判定模块

**Files:**
- Create: `channel/wechat_group/wechat_group_free_reply_judge.py`
- Create: `tests/test_wechat_group_free_reply_judge.py`

- [ ] **Step 1: 编写 JSON 解析测试**

覆盖以下断言：

```python
def test_parse_approved_json_decision(self):
    result = parse_free_reply_judge_reply('{"should_reply": true, "confidence": 0.82, "reason": "可接话", "tone": "natural"}', 0.6)
    self.assertTrue(result["approved"])
    self.assertEqual(0.82, result["confidence"])

def test_parse_rejected_json_decision(self):
    result = parse_free_reply_judge_reply('{"should_reply": false, "confidence": 0.9, "reason": "两人私聊", "tone": "silent"}', 0.6)
    self.assertFalse(result["approved"])
    self.assertEqual("两人私聊", result["reason"])

def test_invalid_json_is_rejected(self):
    result = parse_free_reply_judge_reply("我觉得可以接", 0.6)
    self.assertFalse(result["approved"])
    self.assertEqual("invalid_json", result["error"])

def test_low_confidence_is_rejected(self):
    result = parse_free_reply_judge_reply('{"should_reply": true, "confidence": 0.4, "reason": "不确定", "tone": "natural"}', 0.6)
    self.assertFalse(result["approved"])
    self.assertEqual("low_confidence", result["error"])
```

期望统一输出：

```python
{
    "approved": bool,
    "should_reply": bool,
    "confidence": float,
    "reason": str,
    "tone": str,
    "error": str,
}
```

- [ ] **Step 2: 编写 prompt 约束测试**

断言 prompt 包含以下约束：

```text
只判断是否适合接话
只返回 JSON
不要生成最终回复
不要调用工具
不要写入记忆
```

- [ ] **Step 3: 实现判定器**

提供以下接口契约：

```text
WechatGroupFreeReplyJudge.__init__(bridge=None)：默认使用 Bridge()。
WechatGroupFreeReplyJudge.judge(task, config) -> dict：构造 prompt、调用轻量聊天模型、解析 JSON、返回 approved 决策。
build_free_reply_judge_prompt(task) -> str：包含群名、发送者、文本预览、本地得分、原因和抑制项。
parse_free_reply_judge_reply(text, min_confidence) -> dict：从模型输出中解析 JSON 并执行置信度校验。
```

实现要求：

- `judge()` 使用 `Bridge().fetch_reply_content(prompt, context)`。
- `context` 使用当前 `room_id` 作为 `session_id`，并设置自由回复判定专用标记，避免误走 Agent 工具链。
- 对超时、异常、非 JSON 和低置信度统一返回 `approved=False`。
- 判定模块不调用 `produce()`，不发送消息。

- [ ] **Step 4: 运行判定测试**

Run:

```powershell
python -m unittest tests.test_wechat_group_free_reply_judge
```

Expected:

```text
OK
```

### Task 3: 自由回复 worker 池

**Files:**
- Create: `channel/wechat_group/wechat_group_free_reply_worker.py`
- Create: `tests/test_wechat_group_free_reply_worker.py`

- [ ] **Step 1: 编写 worker 入队与回调测试**

测试点和断言：

```python
def test_worker_approves_task_and_calls_submit_callback(self):
    pool.submit(task)
    wait_until_processed()
    submit_callback.assert_called_once()
    self.assertEqual(1, pool.status()["approved_total"])

def test_worker_rejects_task_without_callback(self):
    judge.judge.return_value = {"approved": False, "error": "low_confidence"}
    pool.submit(task)
    wait_until_processed()
    submit_callback.assert_not_called()
    self.assertEqual(1, pool.status()["rejected_total"])

def test_expired_task_is_dropped_before_llm_judge(self):
    task["queued_at"] = time.time() - 999
    pool.submit(task)
    wait_until_processed()
    judge.judge.assert_not_called()
    self.assertEqual(1, pool.status()["expired_total"])

def test_queue_full_drops_task(self):
    small_pool = WechatGroupFreeReplyWorkerPool(judge, submit_callback, max_workers=1, queue_size=1, ttl_seconds=120)
    self.assertTrue(small_pool.submit(task_a))
    self.assertFalse(small_pool.submit(task_b))

def test_status_snapshot_contains_counters(self):
    status = pool.status()
    self.assertIn("queue_size", status)
    self.assertIn("submitted_total", status)
    self.assertIn("dropped_total", status)
```

- [ ] **Step 2: 实现任务结构**

任务字段：

```python
{
    "room_id": str,
    "room_name": str,
    "sender_id": str,
    "sender_name": str,
    "text": str,
    "msg": WechatGroupMessage,
    "local_decision": dict,
    "queued_at": float,
}
```

- [ ] **Step 3: 实现 worker 池**

提供以下接口契约：

```text
WechatGroupFreeReplyWorkerPool.__init__(judge, submit_callback, max_workers=2, queue_size=100, ttl_seconds=120)：保存依赖并初始化队列、线程列表和计数器。
WechatGroupFreeReplyWorkerPool.start() -> None：启动固定数量后台线程。
WechatGroupFreeReplyWorkerPool.stop() -> None：设置停止标记并等待线程退出。
WechatGroupFreeReplyWorkerPool.submit(task) -> bool：队列可写入返回 True，队列满返回 False 并增加 dropped_total。
WechatGroupFreeReplyWorkerPool.status() -> dict：返回 running、max_workers、queue_size、queue_limit、active_workers 和累计计数。
```

实现要求：

- 内部使用 `queue.Queue(maxsize=queue_size)`。
- worker 线程只处理自由回复任务。
- TTL 过期不调用 LLM。
- 队列满直接丢弃并记录计数。
- LLM 判定通过才调用 `submit_callback(task, llm_decision)`。
- `stop()` 要能在通道退出时停止线程。

- [ ] **Step 4: 运行 worker 测试**

Run:

```powershell
python -m unittest tests.test_wechat_group_free_reply_worker
```

Expected:

```text
OK
```

### Task 4: 接入 WechatGroupChannel 回复链路

**Files:**
- Modify: `channel/wechat_group/wechat_group_channel.py`
- Modify: `tests/test_wechat_group_channel.py`

- [ ] **Step 1: 编写通道行为测试**

覆盖以下断言：

```python
def test_non_at_message_without_free_reply_enabled_is_ignored(self):
    channel.handle_text(non_at_text_msg)
    channel.produce.assert_not_called()

def test_free_reply_scored_message_is_enqueued_not_produced_directly(self):
    channel.handle_text(non_at_capability_question)
    channel.free_reply_worker.submit.assert_called_once()
    channel.produce.assert_not_called()

def test_at_message_does_not_enter_free_reply_worker(self):
    channel.handle_text(at_msg)
    channel.free_reply_worker.submit.assert_not_called()
    channel.produce.assert_called_once()

def test_worker_approved_task_enters_reply_context(self):
    channel._submit_free_reply_after_judge(task, {"approved": True, "confidence": 0.9})
    context = channel.produce.call_args.args[0]
    self.assertTrue(context["wechat_group_free_reply_triggered"])
    self.assertTrue(context["suppress_mention"])

def test_free_reply_does_not_mention_sender(self):
    mentions = channel._build_reply_mentions({"suppress_mention": True, "msg": group_msg})
    self.assertEqual([], mentions)

def test_free_reply_status_returns_config_decision_and_worker_status(self):
    status = channel.free_reply_status()
    self.assertIn("config", status)
    self.assertIn("last_decision", status)
    self.assertIn("worker", status)
```

- [ ] **Step 2: 初始化自由回复组件**

在 `WechatGroupChannel.__init__()` 中初始化：

```python
self.free_reply_state = WechatGroupFreeReplyStateStore()
self.free_reply_judge = WechatGroupFreeReplyJudge()
self.free_reply_worker = WechatGroupFreeReplyWorkerPool(
    judge=self.free_reply_judge,
    submit_callback=self._submit_free_reply_after_judge,
    max_workers=cfg["worker_max_workers"],
    queue_size=cfg["worker_queue_size"],
    ttl_seconds=cfg["queue_ttl_seconds"],
)
self.free_reply_worker.start()
```

- [ ] **Step 3: 普通文本消息（未 @ 机器人）本地判定后入队**

`handle_text()` 逻辑：

```python
if msg.ctype == ContextType.TEXT and not msg.is_at:
    should_enqueue, decision = self._should_enqueue_free_reply_message(msg)
    if not should_enqueue:
        return
    self.free_reply_worker.submit(self._build_free_reply_task(msg, decision))
    return
```

- [ ] **Step 4: worker 通过后提交最终回复上下文**

新增：

```python
def _submit_free_reply_after_judge(self, task, llm_decision):
    msg = task["msg"]
    context = self._compose_context(msg.ctype, msg.content, isgroup=True, msg=msg)
    if not context:
        return
    context["wechat_group_free_reply_triggered"] = True
    context["wechat_group_free_reply_decision"] = task["local_decision"]
    context["wechat_group_free_reply_llm_decision"] = llm_decision
    context["suppress_mention"] = True
    context["no_need_at"] = True
    self.produce(context)
```

- [ ] **Step 5: 自由回复不 mention**

调整 `_build_reply_mentions()`：

```python
if context.get("suppress_mention"):
    return []
```

- [ ] **Step 6: 暴露状态**

`free_reply_status()` 返回：

```python
{
    "config": cfg,
    "rules": get_wechat_group_free_reply_rules(),
    "last_decision": self.free_reply_state.last_decision(),
    "worker": self.free_reply_worker.status(),
}
```

- [ ] **Step 7: 通道停止时关闭 worker**

在通道已有停止/退出路径中调用：

```python
self.free_reply_worker.stop()
```

如果当前通道没有集中停止钩子，则在本任务中新增最小私有方法并由已有关闭入口调用，不改其他渠道。

- [ ] **Step 8: 运行通道测试**

Run:

```powershell
python -m unittest tests.test_wechat_group_channel
```

Expected:

```text
OK
```

### Task 5: Web API 配置读写

**Files:**
- Modify: `channel/web/web_channel.py`
- Modify: `tests/test_wechat_group_web.py`

- [ ] **Step 1: 编写 extra 返回测试**

覆盖以下断言：

```python
def test_wechat_group_extra_returns_free_reply_config_rules_decision_and_worker(self):
    extra = ChannelsHandler._wechat_group_extra()
    self.assertIn("free_reply", extra)
    self.assertIn("rules", extra["free_reply"])
    self.assertIn("last_decision", extra["free_reply"])
    self.assertIn("worker", extra["free_reply"])
```

断言：

```python
self.assertIn("free_reply", extra)
self.assertIn("rules", extra["free_reply"])
self.assertIn("last_decision", extra["free_reply"])
self.assertIn("worker", extra["free_reply"])
```

- [ ] **Step 2: 编写保存配置测试**

覆盖 `wechat_group_free_reply_*` 全部保存键，重点断言：

```python
self.assertEqual(600, applied["wechat_group_free_reply_queue_ttl_seconds"])
self.assertEqual(8, applied["wechat_group_free_reply_worker_max_workers"])
self.assertEqual(1000, applied["wechat_group_free_reply_worker_queue_size"])
self.assertEqual(30, applied["wechat_group_free_reply_llm_judge_timeout_seconds"])
self.assertEqual(1.0, applied["wechat_group_free_reply_llm_judge_min_confidence"])
```

- [ ] **Step 3: 修改 Web extra**

`_wechat_group_extra()` 返回：

```python
"free_reply": {
    "enabled": cfg["enabled"],
    "room_ids": cfg["room_ids"],
    "names": cfg["names"],
    "activity_level": cfg["activity_level"],
    "queue_ttl_seconds": cfg["queue_ttl_seconds"],
    "worker_max_workers": cfg["worker_max_workers"],
    "worker_queue_size": cfg["worker_queue_size"],
    "llm_judge_enabled": cfg["llm_judge_enabled"],
    "llm_judge_timeout_seconds": cfg["llm_judge_timeout_seconds"],
    "llm_judge_min_confidence": cfg["llm_judge_min_confidence"],
    "profiles": cfg["profiles"],
    "rules": get_wechat_group_free_reply_rules(),
    "last_decision": running_status.get("last_decision", {}),
    "worker": running_status.get("worker", {}),
}
```

- [ ] **Step 4: 增加保存键与归一化**

允许保存：

```python
"wechat_group_free_reply_enabled",
"wechat_group_free_reply_room_ids",
"wechat_group_free_reply_names",
"wechat_group_free_reply_activity_level",
"wechat_group_free_reply_queue_ttl_seconds",
"wechat_group_free_reply_worker_max_workers",
"wechat_group_free_reply_worker_queue_size",
"wechat_group_free_reply_llm_judge_enabled",
"wechat_group_free_reply_llm_judge_timeout_seconds",
"wechat_group_free_reply_llm_judge_min_confidence",
"wechat_group_free_reply_profiles",
```

- [ ] **Step 5: 运行 Web 测试**

Run:

```powershell
python -m unittest tests.test_wechat_group_web
```

Expected:

```text
OK
```

### Task 6: Web 控制台 UI

**Files:**
- Modify: `channel/web/static/js/console.js`
- Modify: `channel/web/chat.html`
- Test: `tests/test_wechat_group_web.py` 或现有 Web 静态文本断言

- [ ] **Step 1: 增加 i18n 文案**

中文键：

```javascript
wechat_group_free_reply_title: '自由回复',
wechat_group_free_reply_hint: '仅对选中的群生效；@ 机器人仍然必回。',
wechat_group_free_reply_enabled: '启用自由回复',
wechat_group_free_reply_groups: '自由回复群',
wechat_group_free_reply_names_label: '自由回复群名兜底',
wechat_group_free_reply_level: '活跃档位',
wechat_group_free_reply_threshold: '接话阈值',
wechat_group_free_reply_interval: '最小间隔（秒）',
wechat_group_free_reply_hourly: '每小时上限',
wechat_group_free_reply_consecutive: '连续发言上限',
wechat_group_free_reply_ttl: '排队 TTL（秒）',
wechat_group_free_reply_worker_title: 'worker 池',
wechat_group_free_reply_worker_max_workers: 'worker 并发数',
wechat_group_free_reply_worker_queue_size: '队列长度上限',
wechat_group_free_reply_llm_title: 'LLM 二次判定',
wechat_group_free_reply_llm_enabled: '启用 LLM 二次判定',
wechat_group_free_reply_llm_timeout: '判定超时（秒）',
wechat_group_free_reply_llm_confidence: '最低置信度',
wechat_group_free_reply_rules: '评分规则',
wechat_group_free_reply_last_decision: '最近判定',
wechat_group_free_reply_no_decision: '还没有自由回复判定。开启后，普通群消息会先经过本地评分和 LLM 二次判定。',
```

英文键同步补齐，保持现有 i18n 对象结构。

- [ ] **Step 2: 增加 UI 渲染函数**

新增 `renderWechatGroupFreeReplySettings(extra = {})`，渲染：

- 总开关。
- 群多选。
- 群名兜底 textarea。
- 活跃档位。
- 当前档位参数。
- worker 池参数。
- LLM 二次判定参数。
- 评分规则。
- 最近判定。
- worker 状态。

- [ ] **Step 3: 接入群聊页渲染**

在现有群聊管理页渲染函数中，把：

```javascript
${renderWechatGroupFreeReplySettings(extra)}
```

插入目标群设置后、人设设置前。

- [ ] **Step 4: 保存 payload 增加自由回复配置**

保存时写入所有 `wechat_group_free_reply_*` 键。数值在前端做一次 clamp，后端仍做最终归一化。

- [ ] **Step 5: 更新脚本缓存版本**

如 `channel/web/chat.html` 中引用 `console.js?v=<version>`，把版本号递增一次。

- [ ] **Step 6: 运行 JS 语法检查**

Run:

```powershell
node --check .\channel\web\static\js\console.js
```

Expected:

```text
无语法错误输出，退出码 0
```

### Task 7: 变更记录与完整验证

**Files:**
- Modify: `CHANGES.md`

- [ ] **Step 1: 更新 `CHANGES.md`**

实际代码开发完成后追加中文记录，包含日期、背景、关键改动文件和验证命令。例如：

```markdown
## 2026-07-03

- 微信群通道新增自由回复：支持按群开启、本地规则评分、独立 worker 池、LLM 二次判定、冷却/小时/连续上限抑制、自由回复默认不 mention 原发送者，并在 Web 控制台提供配置、worker 状态和最近判定展示。关键文件：`channel/wechat_group/wechat_group_free_reply.py`、`channel/wechat_group/wechat_group_free_reply_judge.py`、`channel/wechat_group/wechat_group_free_reply_worker.py`、`channel/wechat_group/wechat_group_channel.py`、`channel/web/web_channel.py`、`channel/web/static/js/console.js`。验证：`python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_judge tests.test_wechat_group_free_reply_worker tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`、`node --check .\channel\web\static\js\console.js`。
```

- [ ] **Step 2: 运行最小相关测试**

Run:

```powershell
python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_judge tests.test_wechat_group_free_reply_worker tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web
```

Expected:

```text
OK
```

- [ ] **Step 3: 运行 JS 语法检查**

Run:

```powershell
node --check .\channel\web\static\js\console.js
```

Expected:

```text
退出码 0
```

- [ ] **Step 4: 运行 Python 编译检查**

Run:

```powershell
python -m py_compile channel\wechat_group\wechat_group_free_reply.py channel\wechat_group\wechat_group_free_reply_judge.py channel\wechat_group\wechat_group_free_reply_worker.py channel\wechat_group\wechat_group_channel.py channel\web\web_channel.py tests\test_wechat_group_free_reply.py tests\test_wechat_group_free_reply_judge.py tests\test_wechat_group_free_reply_worker.py tests\test_wechat_group_channel.py tests\test_wechat_group_web.py
```

Expected:

```text
无输出，退出码 0
```

- [ ] **Step 5: 手动验证真实微信群链路**

步骤：

```text
1. 启动 CowAgent，channel_type 包含 wechat_group。
2. 打开 Web 控制台 -> 通道管理 -> 个人微信群，扫码登录。
3. 进入群聊管理页，选择一个测试群作为接入群。
4. 不开启自由回复，在群里发送普通问题，确认机器人不回复。
5. @ 机器人发送问题，确认机器人回复并真实 mention 发送者。
6. 开启自由回复，只选择同一个测试群。
7. 发送“谁能帮我总结一下刚才讨论的方案？”，确认本地判定命中、worker 有处理记录、LLM 判定通过后机器人自然接话且不 mention。
8. 连续发送低信息短句“嗯”“哈哈”，确认不回复。
9. 发送包含本机路径或 api key 的普通请求（未 @ 机器人），确认不回复。
10. 检查 Web 控制台最近判定，确认显示本地得分、阈值、LLM 判定、worker 状态、原因和抑制项。
```

- [ ] **Step 6: 提交最终变更**

Run:

```powershell
git status --short
git add AGENTS.md CHANGES.md config.py config-template.json channel/wechat_group/wechat_group_free_reply.py channel/wechat_group/wechat_group_free_reply_judge.py channel/wechat_group/wechat_group_free_reply_worker.py channel/wechat_group/wechat_group_channel.py channel/web/web_channel.py channel/web/chat.html channel/web/static/js/console.js tests/test_wechat_group_free_reply.py tests/test_wechat_group_free_reply_judge.py tests/test_wechat_group_free_reply_worker.py tests/test_wechat_group_channel.py tests/test_wechat_group_web.py
git commit -m "实现微信群自由回复"
```

如果 `AGENTS.md` 未变化但项目规则要求提交时检查它，确认 `git status --short AGENTS.md` 为空即可，不为满足提交范围而制造无意义改动。若用户未要求提交，只保留工作区变更并在交付说明中说明未提交。

---

## 7. 风险与回退

- 风险：自由回复误触发导致刷屏。
  - 控制：默认关闭；只对指定群开启；本地评分；LLM 二次判定；强抑制；冷却和上限。

- 风险：自由回复挤占 @ 必回链路。
  - 控制：自由回复进入独立 worker 池；@ 必回不入队、不做自由回复判定。

- 风险：自由回复打扰发言人。
  - 控制：自由回复默认 `suppress_mention = True`，不真实 mention。

- 风险：LLM 二次判定引入延迟或不稳定。
  - 控制：本地低分不调用 LLM；worker TTL；判定超时静默；非 JSON 静默；Web 暴露最近错误。

- 风险：绕过现有 Agent 主链路。
  - 控制：判定模块只决定是否进入链路，不直接生成最终回复，不执行工具；最终回复仍走 `Channel.build_reply_content()`。

- 风险：跨群泄露上下文。
  - 控制：自由回复仍复用当前 `room_id` 的 recent context 和 scoped memory，不新增跨群查询。

- 风险：UI 配置复杂度过高。
  - 控制：首屏只暴露总开关、群选择、档位、worker 与 LLM 判定关键参数；规则说明与最近判定为只读诊断。

回退方式：

```json
{
  "wechat_group_free_reply_enabled": false,
  "wechat_group_free_reply_room_ids": [],
  "wechat_group_free_reply_names": []
}
```

关闭后普通消息（未 @ 机器人）恢复静默，@ 必回链路不受影响。

---

## 8. 自检结果

- 需求覆盖：已覆盖指定群开启、接话阈值、规则评分、worker 池、LLM 二次判定、默认不 @、Web UI、API、测试和手动验收。
- 范围控制：首轮只支持文本自由回复，不实现图片/语音/视频自由回复，不实现完整判定日志检索页，不修改桌面端，不实现社交工作台、战报、图库、备份迁移中心。
- 命名一致：功能名统一为“自由回复”；配置、文件和上下文字段统一使用 `free_reply`。
- 主链路约束：自由回复只在微信群渠道层做判定与调度，最终回复仍复用 CowAgent 既有 `Bridge` / Agent 链路。
- 占位扫描：本文没有需要后续补内容的占位项；所有任务都有明确文件、步骤和验证命令。

## 9. 开发回写（2026-07-03）

### 9.1 已完成

- 完成 Task 1：新增 `channel/wechat_group/wechat_group_free_reply.py`，实现默认配置归一化、自由回复群范围判断、本地评分、强抑制、冷却/小时/连续上限和最近判定状态；同步更新 `config.py` 与 `config-template.json`。
- 完成 Task 2：新增 `channel/wechat_group/wechat_group_free_reply_judge.py`，实现 LLM 二次判定 prompt、严格 JSON 解析、低置信度/异常静默和 `Bridge().fetch_reply_content()` 调用封装。
- 完成 Task 3：新增 `channel/wechat_group/wechat_group_free_reply_worker.py`，实现独立 worker 池、队列长度、TTL、运行状态快照和判定通过后回调。
- 完成 Task 4：更新 `channel/wechat_group/wechat_group_channel.py`，未 @ 普通文本先本地判定并入队，@ 必回路径不进入自由回复；worker 通过后复用原 `_compose_context()` / `produce()` 链路，并通过 `suppress_mention` 默认不真实 mention。
- 完成 Task 5：更新 `channel/web/web_channel.py`，`wechat_group.extra.free_reply` 返回配置、规则、最近判定和 worker 状态；保存接口允许全部 `wechat_group_free_reply_*` 键并做边界归一化。
- 完成 Task 6：更新 `channel/web/static/js/console.js` 与 `channel/web/chat.html`，群聊页新增“自由回复”配置面板，支持开关、自由回复群、群名兜底、活跃档位、阈值、冷却、上限、worker、LLM 判定参数、评分规则、最近判定与 worker 状态展示；脚本缓存版本已更新。
- 完成 Task 7 部分：已更新 `CHANGES.md` 并完成自动化验证。

### 9.2 验证结果

- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_judge tests.test_wechat_group_free_reply_worker`：通过。
- `python -m unittest tests.test_wechat_group_channel`：通过。
- `python -m unittest tests.test_wechat_group_web`：通过。
- `node --check .\channel\web\static\js\console.js`：通过。
- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_judge tests.test_wechat_group_free_reply_worker tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过。
- `python -m py_compile channel\wechat_group\wechat_group_free_reply.py channel\wechat_group\wechat_group_free_reply_judge.py channel\wechat_group\wechat_group_free_reply_worker.py channel\wechat_group\wechat_group_channel.py channel\web\web_channel.py tests\test_wechat_group_free_reply.py tests\test_wechat_group_free_reply_judge.py tests\test_wechat_group_free_reply_worker.py tests\test_wechat_group_channel.py tests\test_wechat_group_web.py`：通过。

### 9.3 剩余事项

- 尚未执行真实微信群链路手动验证：需要启动 CowAgent、扫码登录个人微信群、选择测试群，分别验证未开启自由回复时普通消息静默、@ 必回仍真实 mention、开启自由回复后普通文本可经本地判定和 LLM 判定自然接话且不 mention。
- 未提交 Git commit；当前仅保留工作区变更。
