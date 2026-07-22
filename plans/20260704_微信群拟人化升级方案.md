# 微信群机器人拟人化增强实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步实施。步骤使用 `- [ ]` 复选框追踪进度。

**Goal:** 在不偏离 CowAgent 现有“微信群只是主链路增强通道”架构前提下，引入最值得借鉴的拟人化能力，让微信群机器人在群聊中更像真人、更能跟住话题、更会自然接话，并具备可管理、可验证、可回退的运维 UI。

**Architecture:** 继续复用 `ChatChannel -> Bridge -> Agent` 主链路，不在 `channel/wechat_group/` 内重建独立 Agent。新增的“话题工作记忆、风格卡片、群情绪、表情包资产、主动性调度”都作为微信群运行时增强层存在：一部分进入 prompt 注入，一部分进入自由回复决策，一部分通过受限工具或受限服务供主链路使用。

**Tech Stack:** Python、SQLite、Wechaty sidecar、Web 控制台（`channel/web/chat.html` + `channel/web/static/js/console.js`）、`unittest`

---

## 1. 范围与边界

### 1.1 本次必须完成的能力

1. 话题工作记忆
2. 风格卡片学习与注入
3. 群情绪状态与更自然的主动性调度
4. 表情包资产层与可控发送能力
5. 多模态上下文增强补齐
6. Web 控制台对应管理 UI

### 1.2 明确不做的能力

1. 不在 `channel/wechat_group/` 内重写独立模型调用、独立 Agent loop、独立 memory manager。
2. 不引入 QQ/OneBot 专属交互能力，如消息贴表情、撤回、戳一戳、群公告、精华消息。
3. 不默认修改 `desktop/`，除非后续单独立项。
4. 不将群情绪、群风格、群表情包变成跨群共享状态，除“全局群友画像”外其余一律按 `room_id` 隔离。

### 1.3 交付原则

1. 优先复用现有 `wechat_group_archive.py` 作为消息事实源。
2. 所有新能力必须能在 Web 控制台看到状态、样本或结果。
3. 每个阶段都必须能单独验证，避免“大爆炸上线”。
4. 配置默认值应偏保守，先降低误触发和打扰风险。

## 2. 当前基线

当前仓库已经具备以下基础能力，可作为本计划直接复用的底座：

1. 群最近上下文注入：`channel/wechat_group/wechat_group_context.py`
2. 群记忆与全局画像注入：`channel/wechat_group/wechat_group_context_service.py`
3. 全局画像与群记忆管理 API / UI：`channel/web/web_channel.py`、`channel/web/static/js/console.js`
4. 自由回复本地打分 + LLM 二次判定：`channel/wechat_group/wechat_group_free_reply.py`、`wechat_group_free_reply_judge.py`
5. 群图片理解：`channel/wechat_group/wechat_group_channel.py`
6. 群学习运行记录：`channel/wechat_group/wechat_group_knowledge_store.py`

本计划不是重做这些能力，而是在其上增量引入四层新状态：

1. `topic`: 当前群在聊什么，上一轮结论是什么，还有什么没说完
2. `style`: 这个群适合怎么说，哪些表达可以学，哪些不该学
3. `emotion`: 机器人当前愿不愿意说、说话热不热、是否该收敛
4. `sticker`: 群里常用表情包有哪些，什么时候适合发

## 3. 目标架构

### 3.1 运行时链路

运行时仍然走：

`WechatGroupChannel.handle_text()`  
-> `ChatChannel._compose_context()`  
-> 微信群增强块拼装  
-> `Bridge.fetch_agent_reply()`  
-> Agent 主链路出回复

增强后的 prompt 结构目标如下：

```text
<wechat-group-persona>
...
</wechat-group-persona>

<recent-wechat-group-transcript>
...
</recent-wechat-group-transcript>

<wechat-group-topic>
[active_topic]
title: ...
gist: ...
facts: ...
participants: ...
open_loops: ...
recent_turns: ...
</wechat-group-topic>

<wechat-group-knowledge>
[group_memory]
...

[speaker_profile sender_id="..."]
...

[mentioned_profile sender_id="..."]
...
</wechat-group-knowledge>

<wechat-group-style>
- 适合的语气方向
- 可参考的短句味道
- 不适合的表达方式
</wechat-group-style>

<wechat-group-emotion>
valence: ...
energy: ...
sociability: ...
interpreted_state: ...
</wechat-group-emotion>

<wechat-group-multimodal>
图片 / 视频 / 引用 / 合并消息增强
</wechat-group-multimodal>

用户本轮问题
```

### 3.2 决策链路

自由回复决策改造成三层：

1. 本地规则评分层
2. 运行时状态修正层
3. LLM 最终判定层

其中第二层新增使用：

1. 话题是否处于未闭环状态
2. 当前情绪是否低社交意愿或低精力
3. 当前群是否已进入“防话痨衰减”
4. 是否有适合只发表情包而非文本的场景

### 3.3 学习链路

学习链路拆成三个独立 worker 入口，但都消费同一份归档消息：

1. `topic learner`: 生成 / 刷新话题摘要
2. `style learner`: 生成风格卡片候选
3. `sticker learner`: 识别和收集表情包描述

群记忆与全局画像沿用现有 learner 入口扩展，不重开新入口。

## 4. 文件结构与职责

### 4.1 新增文件

- `channel/wechat_group/wechat_group_topic_store.py`
  - 话题线程、话题消息映射、话题摘要快照持久化
- `channel/wechat_group/wechat_group_topic_service.py`
  - 当前话题选择、话题摘要刷新、归档话题搜索
- `channel/wechat_group/wechat_group_style_store.py`
  - 风格卡片候选、已启用卡片、审核状态持久化
- `channel/wechat_group/wechat_group_style_service.py`
  - 风格卡片检索、启用、拒绝、注入格式化
- `channel/wechat_group/wechat_group_emotion_store.py`
  - 每群情绪状态、衰减时间、主动回复统计
- `channel/wechat_group/wechat_group_emotion_service.py`
  - 情绪更新、衰减、解释文本、主动性修正
- `channel/wechat_group/wechat_group_sticker_store.py`
  - 表情包元数据、文件哈希、描述、使用统计
- `channel/wechat_group/wechat_group_sticker_service.py`
  - 自动收集、搜索、发送前选择、上下文注入
- `channel/wechat_group/wechat_group_topic_tools.py`
  - 当前群话题搜索 / 查看工具
- `channel/wechat_group/wechat_group_sticker_tools.py`
  - 当前群表情包搜索 / 发送工具
- `tests/test_wechat_group_topic_service.py`
- `tests/test_wechat_group_style_service.py`
- `tests/test_wechat_group_emotion_service.py`
- `tests/test_wechat_group_sticker_service.py`

### 4.2 修改文件

- `channel/wechat_group/wechat_group_channel.py`
  - 增加 topic/style/emotion/sticker 运行时接入
- `channel/wechat_group/wechat_group_archive.py`
  - 增加 topic / sticker 所需查询接口，避免新模块直接扫描原始库
- `channel/wechat_group/wechat_group_context_service.py`
  - 统一拼装 topic/style/emotion 多块上下文
- `channel/wechat_group/wechat_group_learner.py`
  - 扩展 style / topic / sticker 学习逻辑
- `channel/wechat_group/wechat_group_memory_tools.py`
  - 保留原 scoped tools，并补充 topic/sticker 相关工具装配
- `bridge/agent_bridge.py`
  - 为微信群 turn 临时挂载新增 scoped tools
- `channel/web/web_channel.py`
  - 增加话题 / 风格 / 情绪 / 表情包管理 API
- `channel/web/static/js/console.js`
  - 增加群聊拟人化管理面板
- `channel/web/chat.html`
  - 若需要新增入口按钮或版本戳，最小调整
- `config.py`
  - 新增默认配置
- `config-template.json`
  - 同步新增配置
- `tests/test_wechat_group_channel.py`
- `tests/test_wechat_group_context.py`
- `tests/test_wechat_group_web.py`
- `tests/test_wechat_group_memory_ui.py`
- `tests/test_wechat_group_agent_bridge_tools.py`

## 5. 配置设计

新增配置建议统一挂在 `wechat_group_*` 命名空间下。

### 5.1 话题工作记忆

- `wechat_group_topic_enabled: true`
- `wechat_group_topic_recent_message_limit: 30`
- `wechat_group_topic_active_count_limit: 3`
- `wechat_group_topic_summary_refresh_message_gap: 8`
- `wechat_group_topic_context_limit: 2`
- `wechat_group_topic_archive_recall_limit: 2`

### 5.2 风格卡片

- `wechat_group_style_enabled: true`
- `wechat_group_style_learning_enabled: true`
- `wechat_group_style_context_limit: 3`
- `wechat_group_style_candidate_min_evidence: 2`
- `wechat_group_style_learning_batch_limit: 100`
- `wechat_group_style_auto_apply_enabled: false`

### 5.3 情绪与主动性

- `wechat_group_emotion_enabled: true`
- `wechat_group_emotion_decay_minutes: 10`
- `wechat_group_emotion_default_valence: 0`
- `wechat_group_emotion_default_energy: 0.5`
- `wechat_group_emotion_default_sociability: 0.45`
- `wechat_group_free_reply_time_rules_enabled: false`
- `wechat_group_free_reply_time_rules: []`
- `wechat_group_free_reply_typing_delay_enabled: true`
- `wechat_group_free_reply_typing_chars_per_second: 7`

### 5.4 表情包资产

- `wechat_group_sticker_enabled: true`
- `wechat_group_sticker_auto_collect_enabled: true`
- `wechat_group_sticker_context_limit: 5`
- `wechat_group_sticker_max_size_mb: 2`
- `wechat_group_sticker_daily_send_limit: 20`
- `wechat_group_sticker_storage_dir: ""`

### 5.5 多模态增强

- `wechat_group_video_understanding_enabled: false`
- `wechat_group_forward_preview_enabled: true`
- `wechat_group_quote_context_enabled: true`

## 6. 分阶段实施计划

## Phase 0：基线整理与配置骨架

**目标：** 为后续能力扩展建立最小配置和服务装配点，不改变现有行为。

**涉及文件：**

- 修改：`config.py`
- 修改：`config-template.json`
- 修改：`channel/web/web_channel.py`
- 测试：`tests/test_wechat_group_web.py`

- [x] 新增 topic/style/emotion/sticker 配置默认值，默认都为保守开关或低活跃参数。
- [x] 扩展 `/api/channels` 的 `wechat_group.extra` 返回结构，预留四个新面板配置。
- [x] 为所有新增配置补充保存逻辑和类型归一化。
- [x] 为配置读取编写最小回归测试，确保旧配置缺项时仍能启动。
- [x] 运行：
  - `python -m unittest tests.test_wechat_group_web`

**阶段进度记录：**

- 2026-07-04：完成配置骨架与 `wechat_group.extra` 默认返回结构，修改 `config.py`、`config-template.json`、`channel/web/web_channel.py`，新增 `tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_lists_wechat_group_humanization_defaults` 并通过。
- 2026-07-04：完成 `wechat_group` 拟人化配置保存逻辑与类型归一化，覆盖 `topic/style/emotion/sticker` 新增配置写入，新增 `tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_humanization_config` 并通过。
- 2026-07-04：验证命令：
  - `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_lists_wechat_group_humanization_defaults`
  - `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_humanization_config`
  - `python -m unittest tests.test_wechat_group_web`

**阶段完成标准：**

1. 后端可返回新配置结构。
2. 不启用新能力时，当前微信群行为完全不变。

## Phase 1：话题工作记忆 MVP

**目标：** 让机器人不只看最近消息，而是能“知道这波讨论在聊什么、已经说到哪、还有什么没说完”。

**设计取舍：**

1. 第一阶段不直接复刻 MumuBot 的复杂批量归属逻辑。
2. 先做“当前群活动话题 + 归档话题摘要 + 运行时注入”。
3. 只在稳定后再扩展为多线程并行话题与更复杂归属。

**涉及文件：**

- 新增：`channel/wechat_group/wechat_group_topic_store.py`
- 新增：`channel/wechat_group/wechat_group_topic_service.py`
- 修改：`channel/wechat_group/wechat_group_archive.py`
- 修改：`channel/wechat_group/wechat_group_context_service.py`
- 修改：`channel/wechat_group/wechat_group_channel.py`
- 新增：`tests/test_wechat_group_topic_service.py`
- 修改：`tests/test_wechat_group_context.py`

- [x] 定义 SQLite 表：
  - `wechat_group_topic_threads`
  - `wechat_group_topic_message_refs`
  - `wechat_group_topic_summary_history`
- [x] 在 `archive` 中补充按 `room_id` 读取最近消息、按消息 ID / row_id 建立 topic 归属查询接口。
- [x] 在 `topic_service` 中实现：
  - 已完成：选择当前活动话题
  - 已完成：基于最近窗口生成 / 刷新话题摘要（当前为规则型 MVP）
  - 已完成：返回 prompt block
  - 已完成：按 query 搜索归档话题
- [x] 在 `topic_service` / `wechat_group_channel` 中新增 `<wechat-group-topic>` 块装配。
- [x] 在 `wechat_group_channel._compose_context()` 中接入话题块，并写测试验证注入顺序位于 recent transcript 后、knowledge 前。
- [x] 运行：
  - `python -m unittest tests.test_wechat_group_topic_service tests.test_wechat_group_context`

**阶段进度记录：**

- 2026-07-04：完成 `wechat_group_topic_store.py` 首版，实现话题线程、消息归属映射、摘要历史三张表的建表与基础读写接口。
- 2026-07-04：新增 `tests/test_wechat_group_topic_service.py`，覆盖按群持久化活动话题、消息映射按 `room_id` 隔离、摘要历史按时间倒序读取。
- 2026-07-04：完成 `wechat_group_topic_service.py` 首版，实现活动话题读取、`<wechat-group-topic>` prompt block 组装与按 query 搜索话题。
- 2026-07-04：将 `topic` 注入接入 `wechat_group_channel._compose_context()`，新增从 archive 规则型刷新活动话题的链路，并补 `tests.test_wechat_group_context.WechatGroupRecentContextTest.test_channel_injects_topic_after_recent_context_before_memory` 验证 topic 块位于 recent transcript 之后、knowledge 之前。
- 2026-07-04：验证命令：
  - `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicStoreTest.test_upsert_topic_thread_persists_active_threads_by_room`
  - `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicStoreTest.test_map_message_to_thread_scopes_lookup_to_room`
  - `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicStoreTest.test_append_summary_history_lists_latest_snapshots`
  - `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicServiceTest.test_build_prompt_block_renders_latest_active_topics`
  - `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicServiceTest.test_search_topics_matches_title_and_gist`
  - `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicServiceTest.test_build_prompt_block_from_archive_refreshes_active_topic`
  - `python -m unittest tests.test_wechat_group_context.WechatGroupRecentContextTest.test_channel_injects_topic_after_recent_context_before_memory`
  - `python -m unittest tests.test_wechat_group_context tests.test_wechat_group_topic_service`
  - `python -m unittest tests.test_wechat_group_topic_service`

**阶段完成标准：**

1. 在同一群连续讨论中，prompt 中可看到当前话题摘要。
2. 讨论换题后，摘要能在合理范围内刷新。

## Phase 2：风格卡片学习与回复前分类

**目标：** 让机器人说话更像“这个群的人会说的话”，而不是只有固定 persona。

**设计取舍：**

1. 不让 LLM 直接把风格写成最终 prompt 模板。
2. 风格卡片走“候选 -> 审核 -> 启用”闭环。
3. 运行时只注入短提示，不注入整段原文模板。

**涉及文件：**

- 新增：`channel/wechat_group/wechat_group_style_store.py`
- 新增：`channel/wechat_group/wechat_group_style_service.py`
- 修改：`channel/wechat_group/wechat_group_learner.py`
- 修改：`channel/wechat_group/wechat_group_context_service.py`
- 修改：`channel/wechat_group/wechat_group_channel.py`
- 修改：`channel/web/web_channel.py`
- 修改：`channel/web/static/js/console.js`
- 新增：`tests/test_wechat_group_style_service.py`
- 修改：`tests/test_wechat_group_web.py`

- [x] 定义风格卡片表：
  - `style_id`
  - `room_id`
  - `intent`
  - `tone`
  - `trigger_rule`
  - `avoid_rule`
  - `example`
  - `evidence_count`
  - `status`
- [x] 扩展 learner，在学习批次中抽取“表达风格候选”。
- [x] 增加分类函数：把最近上下文分类为若干固定意图和语气。
- [x] 运行时按当前群优先加载已启用风格卡片，生成 `<wechat-group-style>`。
- [x] Web 端新增“风格卡片”子页：
  - 候选列表
  - 审核通过 / 拒绝
  - 已启用卡片查看
- [x] 运行：
  - `python -m unittest tests.test_wechat_group_style_service tests.test_wechat_group_web`
  - `node --check .\\channel\\web\\static\\js\\console.js`

**阶段完成标准：**

1. 机器人回复前能拿到当前群的风格提示。
2. 管理员可在 Web 控制台审核风格卡片。

**阶段进度记录：**

- 2026-07-04：新增 `wechat_group_style_store.py` 与 `wechat_group_style_service.py`，实现风格卡片候选持久化、基于归档消息的规则型候选学习、审核通过/拒绝和 `<wechat-group-style>` 运行时注入。
- 2026-07-04：更新 `wechat_group_channel.py` 接入风格块，更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js` 增加风格卡片候选、已启用卡片和审核操作 UI/API。
- 2026-07-04：新增 `tests/test_wechat_group_style_service.py`，扩展 `tests/test_wechat_group_context.py` 与 `tests/test_wechat_group_web.py`，覆盖候选生成、审核启用、prompt 注入与 Web 面板结构；验证命令：
  - `python -m unittest tests.test_wechat_group_style_service tests.test_wechat_group_context tests.test_wechat_group_web`
  - `node --check .\\channel\\web\\static\\js\\console.js`

## Phase 3：群情绪状态与主动性调度增强

**目标：** 让机器人不是“永远同样热情”，而是会随节奏收放，像真人一样有状态。

**设计取舍：**

1. 情绪状态按 `room_id` 隔离，不做跨群共享。
2. 初版以确定性规则更新情绪，不先开放 LLM 任意写状态。
3. 自由回复仍走现有框架，只是在本地评分与节流上叠加情绪和时段规则。

**涉及文件：**

- 新增：`channel/wechat_group/wechat_group_emotion_store.py`
- 新增：`channel/wechat_group/wechat_group_emotion_service.py`
- 修改：`channel/wechat_group/wechat_group_free_reply.py`
- 修改：`channel/wechat_group/wechat_group_channel.py`
- 修改：`channel/wechat_group/wechat_group_context_service.py`
- 修改：`channel/web/web_channel.py`
- 修改：`channel/web/static/js/console.js`
- 新增：`tests/test_wechat_group_emotion_service.py`
- 修改：`tests/test_wechat_group_channel.py`

- [x] 定义情绪状态表，字段至少包括：
  - `room_id`
  - `valence`
  - `energy`
  - `sociability`
  - `last_decay_at`
  - `last_reply_at`
  - `reply_count_1h`
- [x] 实现情绪更新规则：
  - 被频繁 @ 或讨论热闹时提高 sociability
  - 长时间高频回复后降低 energy
  - 低价值刷屏时降低 sociability
  - 定时衰减回平稳区间
- [x] 扩展自由回复打分：
  - 读取当前群情绪
  - 叠加时段规则
  - 叠加防话痨衰减
  - 支持“只看不回”的低社交意愿状态
- [x] 在 `send()` 路径增加可选打字延迟模拟。
- [x] UI 增加“情绪与主动性”页：
  - 当前情绪面板
  - 活跃度规则
  - 时段规则
  - 防话痨阈值
  - 最近决策日志
- [x] 运行：
- `python -m unittest tests.test_wechat_group_emotion_service tests.test_wechat_group_channel`

**阶段进度记录：**

- 2026-07-04：新增 `wechat_group_emotion_store.py`，落库 `wechat_group_emotion_states` 情绪状态表，按 `room_id` 持久化 `valence / energy / sociability / last_decay_at / last_reply_at / reply_count_1h / updated_at`。
- 2026-07-04：新增 `wechat_group_emotion_service.py`，实现默认情绪初始化、消息观察、回复后 energy 衰减、定时回归平稳区间、时段规则拦截与 `interpreted_state` 解释。
- 2026-07-04：更新 `wechat_group_channel.py`，在 `handle_text()` 进入主链路前调用 `observe_message()`，在自由回复本地评分后叠加 emotion/time-rule 修正，在文本回复发送前增加可选 typing delay，并在发送成功后 `mark_replied()`。
- 2026-07-04：更新 `wechat_group_channel.py` 与 `tests/test_wechat_group_context.py`，把 `<wechat-group-emotion>` 注入到群聊 prompt，位置位于 `knowledge` 之后、用户问题之前。
- 2026-07-04：新增 `tests/test_wechat_group_emotion_service.py`，扩展 `tests/test_wechat_group_channel.py`、`tests/test_wechat_group_context.py`，覆盖默认值、消息观察、时段拦截、自由回复压制、注入顺序和 typing delay。
- 2026-07-04：更新 `channel/web/web_channel.py`，新增 `/api/wechat-group/emotion/state`、`/api/wechat-group/emotion/config`、`/api/wechat-group/emotion/reset` 三个最小运维接口，支持读取当前群情绪、重置情绪状态和保存时段/typing 配置。
- 2026-07-04：更新 `channel/web/static/js/console.js`，在 groups 视图新增“情绪与主动性”子页，支持选群查看当前状态、查看最近自由回复决策、保存时段规则与 typing 配置、重置当前群情绪。
- 2026-07-04：验证命令：
  - `python -m unittest tests.test_wechat_group_emotion_service tests.test_wechat_group_context tests.test_wechat_group_channel`
  - `python -m unittest tests.test_wechat_group_web tests.test_wechat_group_topic_service tests.test_wechat_group_emotion_service tests.test_wechat_group_context tests.test_wechat_group_channel`
  - `node --check .\\channel\\web\\static\\js\\console.js`

**阶段完成标准：**

1. 相同群在不同时段和不同回复频率下，主动性可见变化。
2. 控制台能看到情绪值和自由回复最近决策。

## Phase 4：表情包资产层与发送链路

**目标：** 让机器人在适合的场景下能用表情包接话，而不只是发文本。

**设计取舍：**

1. 不依赖本地私有图片目录，表情包只来自群内真实媒体或明确人工导入。
2. 先支持“自动收集 + 搜索 + 受限发送”，不做复杂表情包推荐模型。
3. 发送链路仍复用 sidecar 的 `send_image`。

**涉及文件：**

- 新增：`channel/wechat_group/wechat_group_sticker_store.py`
- 新增：`channel/wechat_group/wechat_group_sticker_service.py`
- 新增：`channel/wechat_group/wechat_group_sticker_tools.py`
- 修改：`channel/wechat_group/wechat_group_channel.py`
- 修改：`channel/wechat_group/wechat_group_archive.py`
- 修改：`bridge/agent_bridge.py`
- 修改：`channel/web/web_channel.py`
- 修改：`channel/web/static/js/console.js`
- 新增：`tests/test_wechat_group_sticker_service.py`
- 修改：`tests/test_wechat_group_agent_bridge_tools.py`

- [x] 在收到图片消息时区分普通图片和表情包候选，写入表情包库。
- [x] 记录：
  - 文件哈希
  - room_id
  - media_path
  - 视觉描述
  - source_message_id
  - use_count
  - status
- [x] 为微信群 turn 临时挂载：
  - `wechat_group_sticker_search`
  - `wechat_group_sticker_send`
- [x] 在发送前做限制：
  - 日发送上限
  - 仅当前群可见或全局启用策略
  - 无可用文件时优雅降级为文本
- [x] Web 端新增“表情包”页：
  - 列表
  - 描述搜索
  - 预览
  - 启用 / 停用
  - 使用计数
- [x] 运行：
  - `python -m unittest tests.test_wechat_group_sticker_service tests.test_wechat_group_agent_bridge_tools`

**阶段完成标准：**

1. 群内表情包可自动沉淀成资产。
2. Agent 在当前群 turn 内可搜索并发送表情包。

**阶段进度记录：**

- 2026-07-04：新增 `wechat_group_sticker_store.py`、`wechat_group_sticker_service.py` 与 `wechat_group_sticker_tools.py`，实现表情包资产持久化、文件哈希去重、按群搜索、停用、每日发送限制和发送前结果装配。
- 2026-07-04：更新 `wechat_group_channel.py` 在归档图片消息后收集表情包候选，更新 `bridge/agent_bridge.py` 为微信群 turn 临时挂载 `wechat_group_sticker_search` 与 `wechat_group_sticker_send` 受限工具。
- 2026-07-04：更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`，新增表情包列表、搜索、预览和停用管理 API/UI；新增 `tests/test_wechat_group_sticker_service.py` 并扩展 `tests/test_wechat_group_agent_bridge_tools.py`、`tests/test_wechat_group_web.py`；验证命令：
  - `python -m unittest tests.test_wechat_group_sticker_service tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_web`
  - `node --check .\\channel\\web\\static\\js\\console.js`

## Phase 5：多模态上下文增强补齐

**目标：** 让机器人对引用、最近图片、视频、合并内容的理解更稳定，减少“明明看过却像没看懂”的违和感。

**涉及文件：**

- 修改：`channel/wechat_group/wechat_group_channel.py`
- 修改：`channel/wechat_group/wechat_group_archive.py`
- 修改：`channel/wechat_group/sidecar/wechaty-sidecar.mjs`
- 修改：`channel/wechat_group/protocol.py`
- 修改：`tests/test_wechat_group_channel.py`

- [x] 在不破坏现有协议的前提下，补齐 sidecar 上报的媒体 / 引用字段。
- [x] 增加视频理解入口，默认关闭。
- [x] 增加合并消息预览块，避免大段原文直接注入。
- [x] 优化引用链文本表达，优先命中被引用消息而不是盲猜最近消息。
- [x] 运行：
  - `python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_message tests.test_wechat_group_web`

**阶段进度记录：**

- 2026-07-04：修复 `wechat_group_channel.py` 中图片理解分支缩进错误，补齐多模态上下文格式化 helper，验证 Phase 5 首批目标测试通过：
  - `python -m unittest tests.test_wechat_group_message.WechatGroupMessageTest.test_parse_forward_preview_metadata tests.test_wechat_group_channel.WechatGroupChannelTest.test_compose_context_injects_multimodal_quote_and_forward_block tests.test_wechat_group_channel.WechatGroupChannelTest.test_handle_text_video_message_builds_text_context_when_video_understanding_enabled tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_lists_wechat_group_as_qr_channel tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_image_config`
- 2026-07-04：补齐 `wechat_group_archive.py` 的 `get_recent_messages()` 元数据返回，最近消息查询现在与 `get_message_by_id()` 一样解析 `metadata` 和 `at_list`，用于后续引用、转发、视频上下文增强；新增并通过：
  - `python -m unittest tests.test_wechat_group_context.WechatGroupRecentContextTest.test_archive_recent_messages_include_parsed_metadata`
- 2026-07-04：补齐 Web 控制台“图片与生图”面板中的视频上下文、转发预览、引用上下文三个开关，并接入 `saveWechatGroupSettings()` 保存 payload；验证命令：
  - `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_contains_wechat_group_image_settings`
  - `node --check .\\channel\\web\\static\\js\\console.js`
- 2026-07-04：修复文本识图引用路径中 `get_message_by_id()` 被图片定位和多模态 quote 块重复查询的问题；对已由图片理解命中的引用消息跳过重复 quote section，普通文本引用增强保持不变；验证命令：
  - `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_text_image_request_prefers_quoted_image`
- 2026-07-04：Phase 5/6 高相关集合回归通过，覆盖消息解析、通道、多模态上下文、Web API、Agent scoped tools 与表情包服务：
  - `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_sticker_service`

**阶段完成标准：**

1. 文本“识别这张图/这个视频/刚转发的内容”时，优先命中正确对象。
2. 不因为多模态增强放宽任何跨群边界。

## Phase 6：Web 管理 UI 整体升级

**目标：** 把“更像真人”的新能力做成可理解、可配置、可审核、可排障的 Web 管理页。

**UI 原则：**

1. 只改 Web 控制台，不改桌面端。
2. 复用当前 groups 管理页结构，不新起一套风格。
3. 把“群聊拟人化能力”组织成独立子页，而不是继续堆在单一卡片里。

**建议的 groups 子页结构：**

1. `基础`
   - 已有：群选择、recent context、persona
2. `群记忆`
   - 已有：群记忆、注入预览、学习运行
3. `全局画像`
   - 已有：画像列表与修正
4. `话题`
   - 当前活动话题
   - 归档话题
   - 手动刷新摘要
5. `风格`
   - 候选卡片
   - 已启用卡片
   - 审核操作
6. `情绪与主动性`
   - 情绪状态
   - 时段规则
   - 防话痨与 typing 配置
   - 最近自由回复决策
7. `表情包`
   - 资产列表
   - 搜索
   - 预览
   - 使用统计

**涉及文件：**

- 修改：`channel/web/web_channel.py`
- 修改：`channel/web/static/js/console.js`
- 视情况修改：`channel/web/chat.html`
- 修改：`tests/test_wechat_group_memory_ui.py`
- 修改：`tests/test_wechat_group_web.py`

- [x] 新增对应 API：
  - `/api/wechat-group/topics/*`
  - `/api/wechat-group/styles/*`
  - `/api/wechat-group/emotion/*`
  - `/api/wechat-group/stickers/*`
- [x] 在 groups 视图中增加新导航按钮和面板。
- [x] 为每个面板提供空状态、加载中、错误状态。
- [x] 所有写操作都必须有用户可见反馈。
- [x] 运行：
  - `node --check .\\channel\\web\\static\\js\\console.js`
  - `python -m unittest tests.test_wechat_group_memory_ui tests.test_wechat_group_web`

**阶段完成标准：**

1. 新能力都能在 Web 控制台观察与管理。
2. 出问题时能从 UI 看出是配置问题、学习问题还是运行时状态问题。

**阶段进度记录：**

- 2026-07-04：完成 Web 控制台 groups 视图整体升级，新增话题追踪、风格卡片、情绪与主动性、表情包子页，并保留基础设置、群聊开关、人设、群记忆、全局画像和图片与生图配置入口。
- 2026-07-04：完成 `/api/wechat-group/topics/*`、`/api/wechat-group/styles/*`、`/api/wechat-group/emotion/*`、`/api/wechat-group/stickers/*` 最小运维 API，支持读取、搜索、审核、重置、保存和停用等操作。
- 2026-07-04：补齐 Phase 5 的图片与多模态配置入口，在“图片与生图”面板新增视频上下文、转发预览、引用上下文三个开关；验证命令：
  - `python -m unittest tests.test_wechat_group_web`
  - `node --check .\\channel\\web\\static\\js\\console.js`

## Phase 7：收尾、回归与文档

**目标：** 让整个增强方案具备稳定交付条件。

**涉及文件：**

- 修改：`tests/test_wechat_group_*`
- 修改：`CHANGES.md`
- 视情况修改：`docs/` 下微信群相关文档
- 修改：对应 `/plans/` 文档状态

- [x] 补齐所有新增模块的单测。
- [x] 运行高相关测试集合：
  - `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_agent_bridge_tools`
- [x] 若涉及 sidecar 协议变更，补充 sidecar 手动验证说明。
- [x] 更新 `CHANGES.md`，记录本轮代码交付。
- [x] 回写本计划文档，标记已完成项与未完成项。

**阶段进度记录：**

- 2026-07-04：补齐 topic/style/emotion/sticker/multimodal/Web/Agent tools 高相关测试，最终高相关回归通过：
  - `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_topic_service tests.test_wechat_group_style_service tests.test_wechat_group_emotion_service tests.test_wechat_group_sticker_service tests.test_wechat_group_memory_ui`
- 2026-07-04：sidecar 协议字段已做静态语法验证；因真实微信登录需要扫码与外部账号，仍需人工启动后验证：通道管理选择“个人微信群”扫码登录，在目标群分别发送引用消息、合并聊天记录和视频消息，确认 Python 侧收到 `quote`、`forward`、`raw_app_type`、`message_type=video` 等字段且回复回原群。
- 2026-07-04：更新 `CHANGES.md` 与本计划文档，记录 Phase 2/4/5/6/7 实际改动、验证命令和手动验证边界。

## 7. API 草案

### 7.1 Topics

- `GET /api/wechat-group/topics/active?room_id=...`
- `GET /api/wechat-group/topics/archive?room_id=...&q=...`
- `POST /api/wechat-group/topics/refresh`

### 7.2 Styles

- `GET /api/wechat-group/styles/candidates?room_id=...`
- `POST /api/wechat-group/styles/review`
- `GET /api/wechat-group/styles/active?room_id=...`

### 7.3 Emotion

- `GET /api/wechat-group/emotion/state?room_id=...`
- `POST /api/wechat-group/emotion/reset`
- `POST /api/wechat-group/emotion/config`

### 7.4 Stickers

- `GET /api/wechat-group/stickers/list?room_id=...&q=...`
- `POST /api/wechat-group/stickers/disable`
- `POST /api/wechat-group/stickers/send-test`

## 8. 验证矩阵

### 8.1 自动测试

1. 话题摘要生成、刷新、搜索
2. 风格卡片候选学习、审核、注入
3. 情绪衰减、主动性修正、typing delay
4. 表情包去重、搜索、发送限制
5. 多模态引用优先级
6. Web API 与 console.js 结构

### 8.2 手动验证

1. 启动后打开通道管理，确认个人微信群通道正常连接。
2. 在目标群连续讨论一个技术话题，观察机器人是否能跟住上下文。
3. 在不同时间段和不同活跃度下，观察自由回复频率变化。
4. 连续发送多张表情包，确认可被收集、搜索、发送。
5. 从 Web 控制台查看话题、风格、情绪、表情包面板是否状态一致。

## 9. 风险与回滚

### 9.1 主要风险

1. 话题摘要刷新过于频繁，导致额外模型开销。
2. 风格卡片审核不足，学到不合适表达。
3. 情绪规则过激，导致机器人忽冷忽热。
4. 表情包识别误把普通图片当表情包。
5. UI 面板过多，运维复杂度上升。

### 9.2 缓解策略

1. 所有新能力默认保守开关。
2. 话题、风格、表情包都要保留禁用与清理入口。
3. 自由回复增强必须有详细决策日志。
4. 表情包收集先限制来源于明确图片消息，且保留人工停用。

### 9.3 回滚策略

1. 任一模块可通过配置关闭，不影响主消息收发。
2. 若 topic/style/emotion/sticker 任一模块异常，`_compose_context()` 应直接跳过对应块。
3. 新 API 面板异常时，不影响原基础群设置页使用。

## 10. 建议执行顺序

按价值 / 风险比，建议严格按下面顺序实施：

1. Phase 0 配置骨架
2. Phase 1 话题工作记忆 MVP
3. Phase 3 情绪与主动性调度
4. Phase 2 风格卡片
5. Phase 6 Web 管理 UI 扩展
6. Phase 4 表情包资产层
7. Phase 5 多模态增强补齐
8. Phase 7 收尾回归

这样做的原因：

1. 先解决“能否跟住上下文”和“何时该说”。
2. 再解决“说成什么味道”。
3. 最后补强“用什么媒介表达”。

## 11. 里程碑验收

### M1：能跟住话题

验收信号：

1. prompt 中有稳定的 `<wechat-group-topic>`
2. 机器人不会反复追问刚说过的上下文

### M2：更像这个群的人

验收信号：

1. prompt 中有 `<wechat-group-style>`
2. 已启用风格卡片能明显影响语气，但不出现照抄原话

### M3：更像真人群友

验收信号：

1. 不同时段 / 活跃度下主动性有明显变化
2. 能适度发表情包而不是只发文字

### M4：可管理可排障

验收信号：

1. Web 控制台可查看话题、风格、情绪、表情包状态
2. 运维人员可通过 UI 判断为什么机器人这次没回或回得奇怪
