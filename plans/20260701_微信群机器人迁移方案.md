# 微信群聊机器人迁移开发计划

> 日期：2026-07-01
> 范围：参考 `D:\JiangShuai\SourceCode\BaiLongmaPro` 的微信群聊机器人实现，在 CowAgent 中以低风险、可验证、可回退的方式接入微信群聊机器人。

## 1. 目标定位

微信群聊机器人在 CowAgent 中应被定位为**一个消息通道**，而不是一套独立 Agent。

核心原则：

- Wechaty 侧车只负责微信登录、群列表、群消息收发、文件/图片/语音传输和 Wechaty 运行细节。
- Python 侧把微信群消息转换为 CowAgent 现有 `Context` / `ChatMessage`，继续复用 `ChatChannel`、`Bridge`、Agent、插件、模型、语音、图像和记忆能力。
- 不在微信群通道里重写一套模型调用、工具调用或 Agent 执行逻辑，避免后续能力分叉。
- 首轮核心体验不是“能在群里机械回复”，而是结合当前群最近上下文、群永久记忆和群友画像，让回复更像长期参与群聊的人。

## 2. 当前调研结论

CowAgent 已具备可复用基础：

- `channel/channel_factory.py` 负责按 `channel_type` 创建渠道实例。
- `channel/chat_channel.py` 已有群聊通用语义，包括 `isgroup`、`is_at`、`actual_user_id`、`at_list`、群白名单、群共享会话和群回复装饰。
- `channel/chat_message.py` 定义了群聊渠道需要填充的统一消息字段。
- `bridge/` 和 `agent/` 已承接文本、Agent、工具、模型路由等核心能力。
- `voice/`、`bridge` 和现有回复类型已具备语音识别/语音合成接入基础。
- 图像理解和图像生成应优先走现有 `ContextType.IMAGE`、`ContextType.IMAGE_CREATE`、`ReplyType.IMAGE` / `IMAGE_URL` 等路径。
- `agent/memory` 已有 SQLite + FTS5 + embedding 的长期记忆基础，但默认 `scope` 语义是 `shared` / `user` / `session`，不能直接表达微信群和群友隔离。

CowAgent 现有 `channel/weixin/` 是 iLink 私聊通道：

- 当前支持微信 iLink 长轮询、扫码登录、媒体发送/下载和私聊处理。
- `channel/weixin/weixin_message.py` 明确设置 `is_group = False`，因此不能直接满足微信群聊。

BaiLongmaPro 的微信群助手主要集中在 `src/social/`：

- `wechaty-duty-group.js`：Wechaty 连接、扫码登录、群列表、已选群路由、@ 触发、文本/文件/图片发送、离线二维码通知和 worker 状态。
- `wechat-groups.js`：微信群外部 ID、唤醒规则、最近群消息归档和群提示词构造。
- `wechat-group-memory.js`：群消息、群记忆条目、群友画像和记忆上下文召回。
- `wechat-group-stats.js`：本地群活跃记录、成员名称、群统计、记录导出/导入和战报发送标记。
- `wechat-command-guard.js`：微信群入口安全守卫。
- `wechat-file-reply.js`：按明确格式要求生成附件回复。
- `wechat-image-vision.js`、`wechat-video-analysis-skill.js`、战报与备份模块：属于更重的媒体理解、摘要、备份和 UI 支撑能力。

已通过 Context7 对 Wechaty 当前文档做最小核验。Wechaty 仍以 `scan`、`login`、`message` 事件为核心，群发消息使用 `room.say()` 或 `message.say()`，媒体发送使用 `FileBox`。

## 3. 推荐迁移路线

采用“Node.js Wechaty 侧车进程 + Python CowAgent 渠道适配器”。

理由：

- BaiLongmaPro 当前微信群实现实际依赖 Node/npm 生态，包括 `wechaty`、`wechaty-puppet-wechat4u`、`file-box`、`qrcode` 等。
- 该路线能最大化复用 BaiLongmaPro 已验证的 Wechaty 行为。
- CowAgent 保持 Python 主体，只需要把 Wechaty 消息适配为现有渠道消息。
- Python Wechaty 可作为后续预研选项，但首轮不优先采用，避免引入 Puppet Service Token / gRPC 服务等额外不确定性。

职责边界：

- Node 侧车：扫码、登录态、群列表、群消息监听、媒体下载/发送、room/contact 元数据。
- Python 渠道：侧车进程管理、消息去重、`ChatMessage` 转换、群白名单、上下文构造、回复发送、安全拦截。
- CowAgent 核心：模型回复、Agent、工具、图像理解、图像生成、语音识别、语音合成、长期记忆召回。

## 4. 首轮核心能力

### 4.1 微信群通道闭环

状态：已完成 4.1 首轮闭环。当前实现包含扫码登录、状态/二维码接口、群列表刷新、目标群 room ID 与群名兜底选择、@ 触发、真实发送人身份保留、回复发回原群并携带 mention 元数据、消息去重、自发消息过滤、人设预设/自定义保存与 `<wechat-group-persona>` 注入。管理员配置/诊断类请求会跳过普通人设注入，但仍不绕过程序安全边界。后续 4.2 及之后的最近上下文、群记忆、安全守卫完整实现仍按后续阶段推进。

1. 扫码登录与连接状态
   - 启动、停止和重新登录 Wechaty 侧车。
   - 登录态持久化到仓库外的数据目录，避免写入 Git 跟踪内容。
   - 暴露状态：`idle`、`starting`、`qr_ready`、`logged_in`、`connected`、`error`。

2. 群列表发现与目标群选择
   - 获取当前微信号加入的群列表。
   - 支持按稳定 room ID 配置目标群，同时保留群名兜底。
   - 兼容 CowAgent 现有 `group_name_white_list` 行为。

3. 群内触发规则
   - 默认支持 @ 机器人触发回复。
   - 兼容 CowAgent 现有 `group_chat_prefix`、`group_chat_keyword`。
   - 非 @ 主动接话首轮默认关闭，后续在防刷屏和安全策略稳定后再启用。

4. 真实身份与回复目标
   - 保留真实发送人身份：`actual_user_id`、`actual_user_nickname`、`at_list`。
   - 回复必须发回同一个微信群。
   - 尽可能通过 Wechaty `Contact` @ 真实发送人，而不是只拼接昵称文本。
   - 不允许模型输出改变本轮要 @ 的目标成员。

5. 重复消息与自发消息过滤
   - 按消息 ID 去重。
   - 默认跳过机器人自己发送的消息，除非 CowAgent 现有配置显式允许自触发。

6. 人设设定与生效规则
   - 参考 BaiLongmaPro 微信群助手的 `personaPrompt` / `personaPresetId` 设计，在 CowAgent 微信群通道中支持“预设人设 + 自定义人设”的最小闭环。
   - 首轮内置 3 个人设预设：`owner-digital-twin`（主人数字分身）、`tech-duty`（技术值班助手）、`social-fun`（幽默社交助手）。预设只作为默认提示词模板，不引入 BaiLongmaPro 的旧 UI、网页微信 DOM 或独立 Agent 流程。
   - 配置层保存当前生效的 `wechat_group_persona_prompt` 和 `wechat_group_persona_preset_id`；当提示词与任一内置预设完全匹配时使用对应 preset ID，否则标记为 `custom`。
   - 自定义人设提示词用于约束微信群回复的身份、语气、风格、回复长度和边界，最大长度建议限制为 6000 字符，保存时做换行归一化和首尾空白裁剪。
   - 人设只影响微信群回复风格，不得绕过安全守卫、管理员权限校验、群白名单、目标群限制、回复目标锁定和记忆隔离。
   - 普通群友不能通过群消息修改长期人设；修改人设只能来自本地控制台/桌面 UI，或后续明确设计的已验证管理员配置入口。
   - 进入提示词时使用独立块，例如 `<wechat-group-persona>...</wechat-group-persona>`，并放在群最近上下文和群记忆之前，作为风格约束而不是事实来源。
   - 已验证管理员发出的配置/诊断类请求可以临时降低普通人设优先级，避免人设覆盖管理员意图；但管理员请求仍不能绕过程序实际权限和高风险安全边界。

### 4.2 当前群最近上下文

状态：已完成 4.2 最小闭环。当前实现新增微信群专用 SQLite 归档与最近上下文格式化服务，按 `room_id` 隔离记录入站群消息，并在微信群文本请求进入 CowAgent 回复链路前注入 `<recent-wechat-group-transcript>`。注入窗口受 `wechat_group_recent_context_enabled`、`wechat_group_recent_context_limit`、`wechat_group_recent_context_minutes` 控制；最近上下文只作为本轮提示词素材，不写入 CowAgent 全局长期记忆。出站助手回复已进入 `wechat_group_assistant_replies` 表，为后续记忆与审计阶段保留基础数据。

架构论证：4.2 的“最近上下文”不是长期记忆，而是微信群通道的短期事件归档与提示词素材。它需要按时间窗口读取当前 `room_id` 的原始聊天流水，写入频率高、语义价值不稳定、生命周期短；如果直接塞进 CowAgent 现有 `MemoryManager`，会把普通闲聊提升为全局/用户/会话记忆，增加 embedding 与检索噪声，并且现有 `shared` / `user` / `session` scope 不能天然表达 `room_id` 和 `room_id + sender_id` 隔离。当前专用归档表的定位是低风险地复用 BaiLongmaPro 的 recent transcript 思路，先保证群隔离、时间窗查询和可审计流水。CowAgent 的长期记忆能力在 4.3 执行通用作用域记忆升级：通过 `scope_type`、`scope_id`、`channel_type`、`subject_id` 兼容扩展原记忆表，让群永久记忆和群友画像进入统一 `MemoryManager`，同时仍要求所有写入与召回入口显式携带 `room_id` / `sender_id`，避免污染 Web、CLI、私聊和 Agent 全局记忆。

回复前注入当前群最近上下文，让模型知道群里刚刚发生了什么。

设计要求：

- 原始消息按 `room_id` 强隔离。
- 每次只查询当前 `room_id` 最近 N 条消息或最近 M 分钟消息。
- 上下文格式要简洁，包含发送人昵称、消息类型、时间和文本摘要。
- 不把其他群的最近消息注入当前群。
- 最近上下文只作为本轮提示词素材，不等同于永久记忆。

建议默认：

- `wechat_group_recent_context_enabled = true`
- `wechat_group_recent_context_limit = 20`
- `wechat_group_recent_context_minutes = 60`

### 4.3 群永久记忆与群友画像

群记忆是首轮核心能力。经方案确认，4.3 不再把群永久记忆做成微信群专用长期记忆孤岛，而是把 CowAgent 原本记忆升级为“通用作用域记忆”，让群记忆、群友画像进入统一记忆管理体系，同时通过 `room_id` / `sender_id` 作用域约束保证隔离。

阶段一不直接把微信群消息塞进现有 `shared` / `user` / `session` 语义里，也不使用独立微信群长期记忆表绕开 CowAgent 记忆系统。推荐做法是对 `agent/memory/storage.py` 的 `chunks` 表做兼容扩展：保留旧字段与旧调用路径，同时新增 `scope_type`、`scope_id`、`channel_type`、`subject_id` 等 nullable 字段。旧记忆继续按原行为运行；微信群 4.3 通过新的作用域字段进入统一 `MemoryManager`，并由 `WechatGroupMemoryService` 做强校验和提示词装配适配。

记忆分层：

1. 原始群消息归档
   - 保存群 ID、群名、发送人 ID、发送人昵称、消息类型、规范化文本、原始元数据、是否 @ 机器人和时间戳。
   - 只允许按当前 `room_id` 查询。
   - 原始闲聊不直接写入长期记忆。

2. 群永久记忆
   - 保存当前群长期稳定信息，例如群规、群偏好、长期项目、共同背景、群内约定。
   - 统一记忆作用域：`scope_type = wechat_group`，`scope_id = room_id`，`channel_type = wechat_group`。
   - 只在当前群回复中召回。

3. 群友画像
   - 保存某个群内成员的一份当前生效长期画像，而不是多条零散记忆。
   - 统一记忆作用域：`scope_type = wechat_group_member_profile`，`scope_id = room_id`，`subject_id = sender_id`，`channel_type = wechat_group`。
   - 画像建议包含身份/角色、长期偏好、专业背景、互动风格、已知边界、最近更新依据和更新时间。
   - 同一个 sender ID 出现在不同群时，默认视为不同画像空间，除非后续做明确身份合并。
   - 来源消息 ID、来源摘要和历史版本作为 metadata 或审计记录保留；提示词召回只使用当前生效画像。

4. 与 CowAgent 全局记忆的关系
   - 微信群长期记忆写入 CowAgent 统一记忆索引，但必须携带明确作用域。
   - `WechatGroupMemoryService` 只作为微信群通道适配层：负责校验 `room_id` / `sender_id`、组装作用域、调用通用 `MemoryManager`、生成 `<wechat-group-memory>`。
   - embedding provider、chunker、FTS、向量检索和后续统一记忆管理能力复用 CowAgent 原本组件。
   - 只有用户或管理员明确要求“写入全局记忆”的稳定知识，才允许提升到 `scope_type = shared` 的全局 shared 记忆；普通群记忆和群友画像虽然进入通用 `MemoryManager`，但必须保留 `wechat_group` 或 `wechat_group_member_profile` 作用域。
   - 旧 `shared` / `user` / `session` 调用方必须保持兼容，不能因为新增作用域字段影响 Web、CLI、私聊和 Agent 既有记忆行为。

通用作用域映射：

```text
旧 shared memory:
scope_type = shared
scope_id = ""
channel_type = ""
subject_id = ""

旧 user memory:
scope_type = user
scope_id = user_id
channel_type = ""
subject_id = user_id

旧 session memory:
scope_type = session
scope_id = session_id
channel_type = ""
subject_id = user_id 或空

微信群群永久记忆:
scope_type = wechat_group
scope_id = room_id
channel_type = wechat_group
subject_id = ""

微信群群友画像:
scope_type = wechat_group_member_profile
scope_id = room_id
channel_type = wechat_group
subject_id = sender_id
```

召回顺序：

```text
当前群最近消息
→ 当前群群永久记忆
→ 当前群当前发言人的群友画像
→ 当前群本轮明确 @ 到成员的群友画像
→ CowAgent 全局 shared memory
```

安全原则：

- 任何群记忆召回都必须带 `room_id`。
- 群友画像必须带 `room_id + sender_id`。
- 不允许把 A 群的人设、隐私、聊天结论带到 B 群。
- 全局 shared memory 只能作为通用背景，不允许反向泄露其他群信息。

首轮实现边界：

- 先实现“手动写入 + 隔离召回 + 上下文注入 + 最小 UI 运维”，不默认开启自动提取。
- `wechat_group_memory_auto_extract` 首轮继续默认关闭；4.3.7 开启受控自动蒸馏后，也必须只从当前 `room_id` 的最近消息窗口提取，并保留 `source_message_ids`，不得把普通闲聊直接提升为长期记忆。
- 手动写入采用明确语义入口：
  - 群永久记忆：管理员在 UI 中选择目标群后写入，或后续通过群内管理命令写入。
  - 群友画像：管理员在 UI 中选择目标群和成员后创建或更新画像；普通成员自助更新只允许落到“当前群 + 自己 sender_id”画像空间。
- 召回上下文使用独立 `<wechat-group-memory>` 块，和 `<wechat-group-persona>`、`<recent-wechat-group-transcript>` 分开，避免模型把人设、短期聊天和长期事实混为一类。
- 群记忆 UI 保持运维型能力：开关状态、按群/群友画像分类展示、手动新增或更新、搜索、停用、来源查看、诊断预览和 4.3.7 的自动蒸馏候选审核；不做完整社交工作台、批量导入、跨群身份合并或可视化战报。

建议注入顺序：

```text
<wechat-group-persona>
...
</wechat-group-persona>

<recent-wechat-group-transcript>
...
</recent-wechat-group-transcript>

<wechat-group-memory>
[group_memory] ...
[member_profile sender_id="..."] ...
</wechat-group-memory>

用户本轮真实问题
```

`<wechat-group-memory>` 最多注入当前群命中的群记忆、当前发言人的群友画像和本轮明确 @ 到成员的群友画像。群记忆可以是多条事实；群友画像对每个 `room_id + sender_id` 只注入一份当前生效画像。所有召回必须带来源类型，内部检索结果必须先按 `room_id` / `room_id + sender_id` 过滤，再排序。

#### 4.3.1 已确认实施范围

4.3 拆成“通用作用域记忆升级、微信群记忆适配、上下文注入、Web 运维 UI、测试回归”五个首轮闭环，并在首轮闭环后追加“自动记忆蒸馏小阶段”。首轮已交付 Web 控制台“永久记忆”页；新增 4.3.7 负责从聊天记录自动生成群记忆和群友画像，采用“高置信度自动写入、低置信度进入候选审核”的策略。桌面端后续复用同一组 API 跟进，不进入 4.3 当前新增小阶段范围。

1. 通用作用域记忆升级
   - 修改 `agent/memory/storage.py`、`agent/memory/manager.py`、`agent/memory/service.py` 和 `agent/memory/config.py`，为现有 `chunks` 表兼容新增 `scope_type`、`scope_id`、`channel_type`、`subject_id`、`status`、`source_message_ids` 字段。
   - 新增 `agent/memory/scope.py`，定义 `MemoryScope`，统一表达 `shared`、`user`、`session`、`wechat_group`、`wechat_group_member_profile`。
   - 旧 `scope` / `user_id` 字段暂不删除；旧 API 继续按原语义读写，迁移逻辑只补齐新字段，不改变 Web、CLI、私聊和 Agent 既有记忆行为。
   - 新检索入口必须先按 `MemoryScope` 做强过滤，再进入 FTS、向量相似度或时间排序；embedding 不可用时降级到 FTS/LIKE，不阻断群回复。

2. 微信群记忆适配层
   - 新增 `channel/wechat_group/wechat_group_memory.py`，提供 `WechatGroupMemoryService`，通道层只通过该服务写入、查询、停用和预览微信群记忆。
   - 群永久记忆写入 `MemoryScope(scope_type="wechat_group", scope_id=room_id, channel_type="wechat_group")`。
   - 群友画像写入 `MemoryScope(scope_type="wechat_group_member_profile", scope_id=room_id, channel_type="wechat_group", subject_id=sender_id)`。
   - 群友画像采用“单份 active profile + 独立 revision 表审计”模型：提示词只召回当前 active 画像；旧内容、来源消息和更新摘要写入独立 revision 表，供 UI 稳定分页和审计。
   - 停用采用软删除，把 `status` 更新为 `disabled`，不物理删除正文和来源。

3. 上下文装配链路
   - 新增或扩展 `channel/wechat_group/wechat_group_prompt.py`，统一装配 `<wechat-group-persona>`、`<recent-wechat-group-transcript>` 和 `<wechat-group-memory>`。
   - 在 `WechatGroupChannel._compose_context()` 中只补充长期记忆块接入，不改 Agent 主链路、不改 `Bridge.fetch_agent_reply()` 入参语义。
   - `<wechat-group-memory>` 放在 `<recent-wechat-group-transcript>` 后、用户真实问题前；记忆关闭、检索失败或无命中时不注入空块。
   - 召回条数保持保守：群永久记忆最多 5 条；当前发言人画像最多 1 份；本轮明确 @ 到的其他成员每人最多 1 份画像。

4. 后端 Web API
   - `/api/channels` 继续负责通道状态和基础配置，可在 `wechat_group.extra.memory` 返回记忆开关、目标群数量、群记忆总数、群友画像总数和最近更新时间摘要。
   - 新增独立微信群记忆 API，路径集中在 `/api/wechat-group/memories/` 下，覆盖列表、搜索、新增群记忆、创建/更新群友画像、停用、画像版本查看和提示词预览。
   - API 请求必须显式携带 `room_id`；画像相关请求必须显式携带 `sender_id`。昵称只作展示和输入辅助，不能作为隔离键。
   - 所有写入接口先校验目标群是否在已选择或允许的 `wechat_group_room_ids` 内，避免 UI 或脚本向未授权群写入长期记忆。

5. 配置项
   - 保留 `wechat_group_memory_enabled` 控制群永久记忆召回。
   - 保留 `wechat_group_member_memory_enabled` 控制群友画像召回，兼容既有命名但 UI 文案显示为“群友画像”。
   - 保留 `wechat_group_memory_auto_extract = false` 作为总开关，默认关闭；4.3.7 增量实现自动蒸馏与候选审核 UI 后，管理员可在 Web 控制台显式开启。
   - `wechat_group_memory_context_limit` 与 `wechat_group_member_memory_context_limit` 仅影响提示词召回上限，不影响 UI 列表分页。

4.3.1 开发进度（2026-07-02）：
- 状态：已完成首个可验证切片。已新增 `agent/memory/scope.py` 的 `MemoryScope`，并在 `agent/memory/storage.py` 为 `chunks` 表兼容新增 `scope_type`、`scope_id`、`channel_type`、`subject_id`、`status`、`source_message_ids` 字段；旧库启动时会自动 `ALTER TABLE` 补字段并回填旧 `shared` / `user` 作用域。
- 实际改动：`MemoryStorage.save_chunk()` / `save_chunks_batch()` 会同时保存旧字段和新作用域字段；`search_keyword()` / `search_vector()` 支持传入 `memory_scope` 并先按作用域与 `status = active` 强过滤，再进入 FTS、LIKE 或向量排序；`MemoryManager.add_memory()` / `search()` 支持 `memory_scope`，作用域记忆生成隔离路径，避免不同群写入同一 chunk ID。
- 兼容性：旧 `scope` / `user_id` 字段和旧调用路径保留；无 embedding provider 时，`MemoryManager` 会把关键词结果权重提升为 1.0，避免纯 FTS/LIKE 结果被默认 `min_score` 误过滤。
- 验证结果：已运行 `python -m unittest tests.test_memory_scope`，覆盖旧 shared 记忆字段回填、微信群 `room_id` 隔离、群友画像 `room_id + sender_id` 隔离、disabled 记忆不召回，以及 `MemoryManager` 级作用域写入/检索。
- 下一步：进入 4.3.2 微信群记忆适配层，新增 `WechatGroupMemoryService`，并在服务层实现群永久记忆、群友画像 active profile、revision 审计和 preview prompt 的最小闭环。

#### 4.3.2 已确认 API 形态

首轮 API 只支撑 Web 运维闭环，不做批量导入和跨群身份合并。接口命名确认使用独立 `/api/wechat-group/memories/` 前缀，不挂到 `/api/channels/wechat-group/*` 下。

4.3.2 开发进度（2026-07-02）：
- 状态：已完成微信群记忆适配层与上下文注入的后端基础，不含 Web API 路由与 Web UI 页面。
- 实际改动：新增 `channel/wechat_group/wechat_group_memory.py`，提供 `WechatGroupMemoryService`，支持当前群群永久记忆写入/列表、群友画像 active profile 创建或更新、画像 revision 审计、`preview_prompt_memories()` 和同步通道预览入口。服务层会校验 `room_id`，画像接口校验 `sender_id`，并使用 `MemoryScope.wechat_group()` / `MemoryScope.wechat_group_member_profile()` 读写统一 `MemoryManager`。
- 上下文链路：`WechatGroupChannel._compose_context()` 已接入 `<wechat-group-memory>`，顺序为 `<wechat-group-persona>`、`<recent-wechat-group-transcript>`、`<wechat-group-memory>`、用户真实问题；当 `wechat_group_memory_enabled` 与 `wechat_group_member_memory_enabled` 均关闭、服务异常或无内容时不注入空块。
- 画像策略：同一 `room_id + sender_id` 使用固定 active profile 路径覆盖当前画像；每次更新额外写入 `wechat_group_member_profile_revisions` 独立 revision 表，保留结构化字段快照、来源消息 ID 和创建时间。
- 降级策略：群记忆检索优先走 `MemoryManager.search(memory_scope=...)`；embedding 或分词不可用导致无命中时，降级列出当前群最近 active 群记忆，不跨群召回，不阻断群回复。
- Web API 进度：已新增 `WechatGroupMemoriesHandler` 与路由 `/api/wechat-group/memories/(.*)`，完成 `GET summary`、`GET groups`、`GET group`、`GET profiles`、`GET profiles/revisions`、`POST preview`、`POST group`、`POST profiles`、`POST disable` 的后端闭环。
- 验证结果：已运行 `python -m unittest tests.test_wechat_group_memory`、`python -m unittest tests.test_wechat_group_context` 和 `python -m unittest tests.test_wechat_group_web`，覆盖当前群记忆注入、发言人画像注入、被 @ 群友画像注入、排除机器人自身、跨群隔离、关闭配置不注入、无命中空块、未授权 room 拒绝、active profile 覆盖、revision 记录、preview API 路径和基础参数错误。
- 下一步：4.3.3 Web 控制台“永久记忆”页已同步完成；后续只保留真实微信链路手动验证和桌面端后续跟进。

```text
GET  /api/wechat-group/memories/summary
  query: room_id optional
  return: 全局或指定群的群记忆数量、画像数量、disabled 数量、最近更新时间

GET  /api/wechat-group/memories/groups
  return: 已选目标群列表，附带 room_id、群名、群记忆数量、画像数量、最近更新时间

GET  /api/wechat-group/memories/group
  query: room_id, status=active, limit, offset, q optional
  return: 当前群群永久记忆列表；q 只在当前 room_id 内搜索

POST /api/wechat-group/memories/group
  body: room_id, content, source_message_ids optional
  effect: 新增当前群 active 群永久记忆

GET  /api/wechat-group/memories/profiles
  query: room_id, status=active, limit, offset, q optional
  return: 当前群群友画像卡片列表

POST /api/wechat-group/memories/profiles
  body: room_id, sender_id, sender_nickname optional, role, preferences, expertise, interaction_style, boundaries, evidence, source_message_ids optional
  effect: 按六个结构化字段创建或更新当前群该 sender_id 的 active 画像，并写入独立 revision 记录

GET  /api/wechat-group/memories/profiles/revisions
  query: room_id, sender_id, limit, offset
  return: 该成员在当前群的画像历史版本、结构化字段快照和来源摘要

POST /api/wechat-group/memories/disable
  body: memory_type, memory_id, room_id, sender_id optional
  effect: 仅在匹配 scope 后软停用

POST /api/wechat-group/memories/preview
  body: room_id, sender_id, query, mentioned_sender_ids optional
  return: 只读 <wechat-group-memory> 预览，不调用模型，不写入记忆
```

返回结构建议统一包含 `scope_type`、`scope_id`、`channel_type`、`subject_id`、`status`、`updated_at`、`source_message_ids` 和 `source_summary`，方便 UI 明确展示隔离边界和来源。

#### 4.3.3 Web UI 设计细化

4.3 的 UI 目标是“管理员能按群查看、手动维护、诊断预览”，不是社交工作台。首轮只做 Web 控制台“永久记忆”页，并保持信息架构为：`基础设置 / 群聊开关 / 人设设定 / 永久记忆`。桌面端不在本轮交付范围，后续只需复用本轮 API 与信息架构。

1. 入口与导航
   - 永久记忆入口放在“群聊”管理页的子菜单中，命名为“永久记忆”；不放在个人微信群通道卡片内。
   - Web 控制台沿用群聊管理页内部子菜单，不修改桌面端 `desktop/` 页面。
   - 页面顶部显示全局摘要：记忆功能状态、已选群数、群记忆总数、群友画像总数、最近更新时间和“诊断预览”入口。

2. 页面布局
   - 宽屏采用左右布局：左侧为目标群列表，右侧为当前群详情；窄屏改为上方群选择、下方详情。
   - 群列表每项展示群名、`room_id`、群记忆数量、群友画像数量和最近更新时间；`room_id` 使用等宽字体并支持复制。
   - 一次只展示一个群的记忆正文，不允许在同一详情区混看多个群，避免管理员误判来源。
   - 当前群详情使用分段控件或标签页分为“群记忆”“群友画像”“诊断预览”。

3. 群记忆面板
   - 顶部显示当前群名、`room_id`、`wechat_group_memory_enabled` 开关状态、召回上限和 active 记忆数量。
   - “新增群记忆”使用多行文本输入，保存按钮有 loading/disabled 状态；正文 trim 后不能为空，首轮建议限制 2000 字以内。
   - 列表项展示内容摘要、更新时间、来源消息 ID、作用域标识、状态和停用按钮。
   - 搜索框只搜索当前 `room_id`；搜索结果标注匹配方式，例如 `fts`、`vector` 或 `like`。
   - 空状态提示“当前群还没有长期记忆”，并提供新增入口；错误状态提供重试按钮和错误摘要。

4. 群友画像面板
   - 顶部显示 `wechat_group_member_memory_enabled` 开关状态、画像数量和“只看有画像成员”过滤。
   - 成员选择优先来自 `wechat_group_member_identities` 或最近群消息归档；允许手动输入稳定 `sender_id`，但必须明确提示昵称不是隔离键。
   - 画像卡按成员一人一张展示：昵称、`sender_id`、画像摘要、标签、来源数量、版本数量、最近更新时间和状态。
   - 创建/更新表单字段为：身份/角色、长期偏好、专业背景、互动风格、已知边界、更新依据；保存时合并为当前 active 画像。
   - 点击画像卡打开详情抽屉或弹窗，展示当前画像正文、来源依据、历史版本列表、手动编辑和停用按钮。
   - 历史版本只读展示，不做复杂 diff 编辑器；停用画像需要二次确认，停用后不再进入提示词召回。

5. 诊断预览
   - 输入模拟问题、当前发言人 `sender_id`、可选被 @ 成员 `sender_id` 列表，点击后展示本轮将注入的 `<wechat-group-memory>`。
   - 预览必须明确显示命中的群记忆、当前发言人画像、被 @ 成员画像和被过滤原因；不调用 LLM，不写入记忆。
   - 当某个 `sender_id` 没有画像时，预览显示“无 active 画像”，不制造占位画像内容。

6. 视觉与交互约束
   - 沿用现有语义 token、表单控件、卡片半径和信息密度；不新增 UI 框架，不做营销式 hero 或装饰性渐变。
   - Web 控制台沿用现有按钮、表单与状态样式；如无既有图标体系则保持文本按钮，不使用 emoji 作为结构性图标。
   - 所有异步按钮必须有 loading/disabled 状态；开关保存失败时回滚到服务端状态并显示错误。
   - 长 `room_id`、`sender_id`、来源 ID 使用 `font-mono`、`truncate`、`break-words`，避免撑破 Web 控制台布局。
   - 重要状态不能只靠颜色表达，需要结合文本、图标或状态徽标。

7. 自动蒸馏与候选审核 UI（4.3.7 新增小阶段）
   - 在“永久记忆”页当前群详情中新增“自动生成”区域或标签页，不新建社交工作台；入口保持运维属性。
   - 顶部展示当前群自动蒸馏状态：总开关、最近运行时间、最近处理消息范围、自动写入数量、待审核候选数量、失败摘要。
   - 提供“从最近聊天生成记忆”手动触发按钮；按钮必须有 loading/disabled 状态，运行中显示当前选中群、时间窗口和消息数量上限。
   - 提供配置控件：高置信度阈值、低置信度候选阈值、时间窗口分钟数、最大消息数、是否允许自动写入群记忆、是否允许自动写入群友画像。配置保存失败时回滚到服务端值。
   - 候选列表按当前 `room_id` 过滤，分为“群记忆候选”和“群友画像候选”；每条展示 LLM 摘要、置信度、目标类型、目标 `sender_id`、昵称、来源消息 ID、证据摘录、状态和创建时间。
   - 候选操作只允许“批准写入”“忽略/驳回”“查看来源消息”；批准时仍调用 `WechatGroupMemoryService.add_group_memory()` 或 `upsert_member_profile()`，UI 不直接写底层 `chunks`。
   - 自动写入日志必须可见：高置信度自动写入的条目在 UI 中显示来源为 `auto_distill`，并能查看对应候选或运行记录。
   - 低置信度候选不能进入 `<wechat-group-memory>` 召回，只有批准写入或高置信度自动写入成功后的 active 群记忆/画像才能进入提示词。
   - 桌面端本小阶段仍不做页面；后续复用 Web API、候选列表与状态模型。

4.3.3 开发进度（2026-07-02）：
- 状态：已完成 Web 控制台“群聊 -> 永久记忆”首轮闭环，不修改桌面端 `desktop/`。
- 实际改动：`channel/web/static/js/console.js` 在群聊管理页新增“永久记忆”子菜单，按已选 `room_id` 展示目标群列表；当前群详情包含群记忆、群友画像和注入预览三个区域。群记忆支持新增、搜索当前群、查看 active 列表和停用；群友画像支持结构化字段创建/更新、卡片列表、停用和点击后只读查看 revision；诊断预览调用只读 preview API 展示本轮 `<wechat-group-memory>`。
- API 使用：UI 只调用 `/api/wechat-group/memories/` 下的 `summary`、`group`、`profiles`、`profiles/revisions`、`preview`、`disable`，不直接访问 `chunks` 或 revision 表；目标群来源仍以 `/api/channels` 返回的已选 `wechat_group_room_ids` 为准。
- 边界：首轮不做桌面端页面、不做富文本编辑、批量导入、自动提取审核台、跨群身份合并或复杂 revision diff。
- 验证结果：已运行 `python -m unittest tests.test_wechat_group_memory_ui`、`node --check .\channel\web\static\js\console.js`，并在 4.3 回归组合中覆盖 Web UI 静态入口、summary/disable Web API、群记忆/画像服务和上下文注入链路。

#### 4.3.4 本轮明确不做

- 不做跨群身份合并，不把相同 `sender_id` 在不同群的画像自动合并。
- 不做普通文本昵称匹配召回群友画像，首轮只处理当前发言人和本轮明确 @ 到的成员。
- 不做完全无人值守的自动长期记忆系统；4.3.7 只做“高置信度自动写入、低置信度候选审核”的受控自动蒸馏，且总开关默认关闭。
- 不做富文本编辑器、批量导入、备份导入、战报、图库或群统计。
- 不做桌面端“永久记忆”页；桌面端后续复用 `/api/wechat-group/memories/` 跟进。
- 不允许 UI 绕过 `WechatGroupMemoryService` 直接操作 `chunks` 或自建微信群长期记忆事实表。

#### 4.3.5 已确认决策

1. UI 范围：4.3 首轮只交付 Web 控制台“永久记忆”页，不做桌面端页面。
2. 画像表单：按六个结构化字段保存，即身份/角色、长期偏好、专业背景、互动风格、已知边界、更新依据；不提供“一段完整画像正文”的自由编辑作为首轮主路径。
3. API 命名：确认使用 `/api/wechat-group/memories/` 独立接口组。
4. 画像 revision：使用独立 revision 表，支持稳定分页、来源追踪和审计。
5. 自动蒸馏策略：确认采用“高置信度自动写入、低置信度进入候选审核”，候选必须按 `room_id` 隔离，画像候选必须有可验证的 `sender_id`。

#### 4.3.6 实施任务与验收点

1. 以 `AGENTS.md` 的个人微信群 LLM 请求上下文链路为准则，保证 `<wechat-group-memory>` 只包含当前群记忆、当前发言人画像和本轮被 @ 群友画像。
2. 实现 `WechatGroupMemoryService.preview_prompt_memories(room_id, sender_id, query, mentioned_sender_ids=None, bot_sender_id=None)`：输入当前 `room_id`、发言人 `sender_id`、本轮 `at_list` 派生出的成员 ID 和用户问题，输出已过滤、已排序、可直接注入的 `<wechat-group-memory>` 内容；无命中时返回空内容和过滤说明，不生成空标签块。
3. 群记忆召回必须使用 `scope_type = wechat_group`、`scope_id = room_id`、`channel_type = wechat_group`、`status = active`，禁止跨群召回。
4. 当前发言人画像召回必须使用 `scope_type = wechat_group_member_profile`、`scope_id = room_id`、`subject_id = sender_id`、`channel_type = wechat_group`、`status = active`，每人只返回一份当前生效画像。
5. 本轮被 @ 群友画像从 `at_list` 中排除机器人自身和当前发言人后逐个召回；首轮只处理明确 @ 到的成员，不做普通昵称文本匹配。
6. 在 `WechatGroupChannel._compose_context()` 中把 `<wechat-group-memory>` 放在 `<recent-wechat-group-transcript>` 之后、用户真实问题之前；当群记忆和群友画像配置均关闭、检索失败或无命中时不注入空噪声。
7. Web API 和 Web UI 都不得绕过 `WechatGroupMemoryService` 操作底层 `chunks` 或 revision 表；所有写入、停用、预览必须显式携带并校验 `room_id`，画像接口还必须校验 `sender_id`。
8. 测试必须覆盖：当前群记忆注入、发言人画像注入、被 @ 群友画像注入、跨群隔离、排除机器人自身、无命中不注入、关闭配置不注入、独立 revision 记录、Web API 路径和结构化画像字段。

4.3.6 验收进度（2026-07-02）：
- 已完成：通用作用域记忆升级、微信群记忆服务、上下文注入、Web API、Web 控制台永久记忆页和回归测试。
- 已验证：`python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_context tests.test_wechat_group_memory tests.test_memory_scope tests.test_wechat_group_memory_ui`，`python -m py_compile ...`，`node --check .\channel\web\static\js\console.js`。
- 未做：真实微信群扫码、群内 @ 回复和真实 mention 链路仍需手动验证；桌面端永久记忆页不属于 4.3 首轮范围。

#### 4.3.7 聊天记录自动蒸馏群记忆与群友画像（新增计划）

目标：从已归档的微信群聊天记录中，由 LLM 自动总结稳定群记忆和成员画像候选；高置信度结果自动写入当前群 scoped memory，低置信度结果进入 Web 控制台候选审核，不再污染 CowAgent 全局 `shared` / `MEMORY.md`。

产品策略：

- 默认关闭：`wechat_group_memory_auto_extract = false` 仍为总开关，管理员必须在 Web 控制台显式开启。
- 高置信度自动写入：当候选 `confidence >= wechat_group_memory_auto_apply_threshold`，且通过服务层作用域、来源消息和目标成员校验时，自动调用 `WechatGroupMemoryService.add_group_memory()` 或 `upsert_member_profile()` 写入。
- 低置信度进候选：当 `wechat_group_memory_candidate_threshold <= confidence < wechat_group_memory_auto_apply_threshold`，只写入候选表，等待管理员批准或驳回。
- 低于候选阈值丢弃：低于 `wechat_group_memory_candidate_threshold` 的结果只记录在运行日志摘要中，不进入候选列表，不写长期记忆。
- 候选不召回：pending / rejected / failed 候选不能进入 `<wechat-group-memory>`，只有 active 群记忆和 active 群友画像能被召回。
- 人员识别保守：群友画像候选的 `target_sender_id` 必须来自本次输入消息窗口中的发送人 ID 或明确 `at_list` 解析出的成员 ID；不允许 LLM 只凭昵称、外号或普通文本自行发明 `sender_id`。
- 来源可审计：每条候选和自动写入都必须保留 `source_message_ids`、证据摘录、运行批次 ID、置信度和 LLM 原始输出摘要，支持后续追溯与回滚。

后端开发计划：

1. 归档层扩展
   - 修改 `channel/wechat_group/wechat_group_archive.py`，新增按 `room_id + 时间窗口/游标` 拉取消息的方法，例如 `get_messages_for_distill(room_id, since_ts, until_ts, limit)`。
   - 新增蒸馏运行表 `wechat_group_memory_distill_runs`：记录 `run_id`、`room_id`、窗口起止、消息数量、状态、自动写入数、候选数、失败原因、开始/结束时间、LLM 原始输出摘要。
   - 新增候选表 `wechat_group_memory_candidates`：记录 `candidate_id`、`run_id`、`room_id`、`candidate_type`、`target_sender_id`、`target_sender_nickname`、结构化内容 JSON、`confidence`、`evidence_message_ids`、`evidence_text`、`status`、`applied_memory_id`、`created_at`、`reviewed_at`。
   - 候选状态限定为 `pending`、`auto_applied`、`approved`、`rejected`、`failed`；所有列表查询必须先按 `room_id` 过滤。

2. 自动蒸馏服务
   - 新增 `channel/wechat_group/wechat_group_memory_distiller.py`，封装 `WechatGroupMemoryDistiller`。
   - 输入依赖：`WechatGroupArchive`、`WechatGroupMemoryService`、LLM 调用器、配置读取函数；不直接访问 `chunks`。
   - LLM 调用复用 `agent.memory.summarizer.MemorySummarizer.deep_dream()` 的 `LLMRequest` 模式，使用非流式请求、低温度、严格 JSON 输出提示词。
   - Prompt 输入格式必须包含稳定字段：`message_id`、`room_id`、`sender_id`、`sender_nickname`、`text`、`created_at`、明确 @ 到的成员 ID 列表；不要只给自然语言流水。
   - Prompt 输出 schema 固定为 `group_memories[]` 和 `member_profiles[]`，每条必须包含 `confidence`、`evidence_message_ids` 和结构化字段；不接受散文式输出。
   - 解析后先做本地校验：JSON 可解析、候选类型合法、置信度在 0-1、来源消息都属于当前 `room_id`、画像目标 `sender_id` 在当前窗口可证明存在。
   - 通过高阈值的候选自动写入；低阈值候选写候选表；失败或非法候选只进入 run 失败摘要，不写长期记忆。

3. 写入合并策略
   - 群记忆自动写入前，先在当前 `room_id` 的 active 群记忆中做轻量去重：相同 `source_message_ids` 或正文高度相似时跳过并记录为重复。
   - 群友画像自动写入仍使用 active profile upsert，不新增多份画像；LLM 输出的字段只覆盖其明确给出的字段，空字段不清空旧画像。
   - `updated_by` / `created_by` 来源标记为 `auto_distill` 或 `candidate_review`，便于 UI 区分手工写入和自动生成。
   - 自动写入失败时，候选状态改为 `failed` 并记录错误，不重试写入全局记忆。

4. 触发机制
   - 首个切片先实现手动触发 API：管理员在 Web 控制台选择当前群并点击“从最近聊天生成记忆”。
   - 第二个切片再接入后台定时：当总开关开启后，按配置的时间窗口或累计消息数触发；同一 `room_id` 同时只允许一个运行批次。
   - 默认窗口建议：最近 60 分钟、最多 200 条文本消息；图片、语音、文件消息首轮只作为“非文本消息占位”进入统计，不交给 LLM 总结。
   - 每个 `room_id` 维护上次成功处理游标，避免同一批消息重复蒸馏；手动强制运行可以选择忽略游标但仍要去重。

5. Web API 计划
   - 扩展 `/api/wechat-group/memories/`：
     - `POST distill/run`：手动触发当前群蒸馏，body 包含 `room_id`、`window_minutes`、`limit`、`force`。
     - `GET distill/runs`：按当前 `room_id` 查询运行记录。
     - `GET distill/candidates`：按当前 `room_id`、状态、类型查询候选。
     - `POST distill/candidates/approve`：批准候选并写入群记忆或群友画像。
     - `POST distill/candidates/reject`：驳回候选，必须记录 `review_note`。
     - `GET distill/messages`：只读查看候选来源消息，返回时仍按 `room_id` 强过滤。
   - 所有接口都必须 `_require_auth()`，并复用已选 `wechat_group_room_ids` 校验，未授权群直接拒绝。

UI 开发计划：

1. 信息架构
   - 在 Web 控制台“群聊 -> 永久记忆”当前群详情内新增“自动生成”标签页，和“群记忆 / 群友画像 / 诊断预览”并列。
   - 不修改桌面端 `desktop/`；桌面端后续复用同 API。

2. 状态与配置区
   - 展示总开关、最近运行时间、最近处理消息范围、自动写入数、待审核候选数和最近错误。
   - 提供高置信度阈值、候选阈值、窗口分钟数、最大消息数、允许自动写群记忆、允许自动写群友画像等控件。
   - 阈值 UI 使用数字输入或滑块，约束 `0 <= candidate_threshold < auto_apply_threshold <= 1`；保存失败回滚到服务端状态。

3. 手动运行区
   - “从最近聊天生成记忆”按钮只对当前选中 `room_id` 生效。
   - 运行前展示将处理的窗口和消息上限；运行中禁用按钮并显示 loading。
   - 运行完成后刷新运行记录、候选列表、群记忆列表和群友画像列表。

4. 候选审核区
   - 分段筛选：全部、待审核、已自动写入、已批准、已驳回、失败。
   - 候选卡展示类型、置信度、目标成员、内容摘要、证据摘录、来源消息 ID、生成时间和状态。
   - 待审核候选提供“批准写入”“驳回”按钮；已写入候选提供跳转到对应群记忆或画像卡的入口。
   - 来源消息查看使用只读弹窗或抽屉，按时间顺序展示相关消息，不允许跨群混看。

5. 反馈与安全文案
   - 自动生成区域明确提示：只有高置信度候选会自动写入；低置信度候选需要审核；候选不会进入回复上下文。
   - 失败状态必须显示可诊断摘要，例如 LLM JSON 解析失败、来源消息不属于当前群、目标成员 ID 不可验证、写入服务拒绝。

测试与验收：

- 新增 `tests/test_wechat_group_memory_distiller.py`：覆盖 JSON 解析、置信度分流、非法 `sender_id` 拒绝、跨群来源拒绝、高置信度自动写入、低置信度候选、低于阈值丢弃、重复候选去重。
- 扩展 `tests/test_wechat_group_web.py`：覆盖 distill API 鉴权、room 授权校验、运行接口、候选列表、批准和驳回。
- 新增或扩展 `tests/test_wechat_group_memory_ui.py`：静态检查 Web 控制台存在“自动生成”入口、候选 API 调用、loading/disabled 状态、候选状态文案和来源消息入口。
- 最小验证命令：
  ```powershell
  python -m unittest tests.test_wechat_group_memory_distiller tests.test_wechat_group_web tests.test_wechat_group_memory_ui
  node --check .\channel\web\static\js\console.js
  ```
- 涉及配置模板时同步运行：
  ```powershell
  python -m unittest tests.test_wechat_group_memory tests.test_wechat_group_context
  ```

执行进度（2026-07-02）：

- 状态：已完成 4.3.7 首个手动触发切片；后台定时触发、处理游标复用和来源消息弹窗仍按第二切片保留，未在本次顺手实现。
- 实际改动：
  - 扩展 `channel/wechat_group/wechat_group_archive.py`，新增当前 `room_id + 时间窗口` 蒸馏消息读取、蒸馏运行记录表和候选表，候选/运行查询均按 `room_id` 过滤。
  - 新增 `channel/wechat_group/wechat_group_memory_distiller.py`，封装 `WechatGroupMemoryDistiller`，支持严格 JSON 输出解析、置信度分流、来源消息校验、画像目标 sender_id 可证明校验、高置信度自动写入、低置信度候选、低阈值丢弃、候选批准和驳回。
  - 扩展 `channel/wechat_group/wechat_group_memory.py`，群记忆和画像写入 metadata 标记 `created_by`；自动画像更新只合并 LLM 明确给出的非空字段，不清空旧画像。
  - 扩展 `channel/web/web_channel.py` 与配置模板，新增自动蒸馏配置返回/保存和 `/api/wechat-group/memories/distill/*` 手动运行、运行列表、候选列表、批准、驳回、来源消息查询接口。
  - 更新 Web 控制台 `channel/web/static/js/console.js` 与 `channel/web/chat.html`，在“群聊 -> 永久记忆”当前群详情中新增“自动生成”标签页，包含配置保存、手动运行、运行记录、候选审核和脚本缓存版本更新。
  - 新增 `tests/test_wechat_group_memory_distiller.py`，扩展 `tests/test_wechat_group_web.py` 覆盖 distill 服务与 Web API。
- 已验证：
  ```powershell
  python -m unittest tests.test_wechat_group_memory_distiller tests.test_wechat_group_web
  node --check .\channel\web\static\js\console.js
  python -m unittest tests.test_wechat_group_memory_ui tests.test_wechat_group_web tests.test_wechat_group_memory_distiller
  python -m py_compile channel\wechat_group\wechat_group_archive.py channel\wechat_group\wechat_group_memory.py channel\wechat_group\wechat_group_memory_distiller.py channel\web\web_channel.py tests\test_wechat_group_memory_distiller.py tests\test_wechat_group_web.py tests\test_wechat_group_memory_ui.py
  python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_memory tests.test_wechat_group_web tests.test_wechat_group_memory_ui tests.test_wechat_group_memory_distiller
  ```
- 剩余事项：
  - 后台定时触发、每群处理游标、同一 `room_id` 并发运行锁和来源消息弹窗/抽屉仍留到下一切片。
  - 真实 LLM 蒸馏链路需要在已配置模型、已登录个人微信群并有归档消息的环境中手动验证。

### 4.4 多模态能力

首轮需要支持文本、图片理解、图片生成、语音识别和语音合成，但实现上应复用 CowAgent 现有能力。

1. 文本回复
   - 群消息映射为 `ContextType.TEXT`。
   - 回复使用 `ReplyType.TEXT`，超长文本按微信发送限制拆分。

2. 图像理解
   - Wechaty 下载图片到 CowAgent 工作区临时目录。
   - 消息映射为 `ContextType.IMAGE`，或文本消息附带图片路径引用。
   - 优先复用 CowAgent 现有图片理解链路，不在微信群通道里单独调用视觉模型。

3. 图像生成
   - 命中现有 `image_create_prefix` 或 CowAgent 现有图像生成路由时，使用 `ContextType.IMAGE_CREATE`。
   - 生成结果通过 Wechaty `FileBox` 或图片 URL 发送到当前群。

4. 语音识别
   - Wechaty 下载语音文件到临时目录。
   - 映射为 `ContextType.VOICE`，复用 CowAgent 现有 voice-to-text 流程。

5. 语音合成
   - 当上下文要求语音回复或配置开启语音回复时，复用 CowAgent text-to-speech。
   - 如果微信原生语音发送不稳定，首轮以音频文件附件形式发送。

6. 文件/视频基础处理
   - 文件和视频先作为 `ContextType.FILE` 处理。
   - 视频理解不进入首轮必交付，只保留文件传输和提示能力。

### 4.5 安全守卫

微信群入口必须有前置安全守卫。

首轮迁移 `wechat-command-guard.js` 的核心高风险分类：

- 读取/列出本机文件。
- 读取密钥、token、cookie、环境变量、登录态。
- 执行 Shell、脚本、代码或安装依赖。
- 控制浏览器、桌面、摄像头、麦克风、屏幕。
- 支付、转账、下单、金融交易。
- 群管理操作，例如踢人、拉人、改群名、群发刷屏。
- 破坏性 Git / 文件操作。
- 绕过安全规则或冒充管理员。

规则：

- 只对微信群来源生效。
- 在模型和工具执行前拦截。
- 普通群成员不允许绕过。
- 管理员身份只基于精确 sender ID，不接受昵称、自称或模型推断。

## 5. 首轮暂缓迁移的功能

以下能力暂不进入首轮：

- 完整 Brain UI 社交指挥中心。
- 群备份/导入中心。
- 群统计战报和海报渲染。
- 图片视觉库、图片标签和图库召回。
- 视频解析 Skill。
- 表情包搜索和公开图片搜索。
- ClawBot 私聊控制通道。
- 企业微信应用离线二维码通知。
- 非 @ 主动接话默认开启。

这些能力有价值，但会显著扩大依赖面和验证成本，建议在核心微信群通道、记忆隔离和多模态基础能力稳定后逐项迁移。

## 6. 文件级开发计划

### 任务一：定义侧车通信协议

新增：

- `channel/wechat_group/README.md`
- `channel/wechat_group/protocol.py`

侧车发给 Python 的事件：

- `status`
- `qr`
- `rooms`
- `message`
- `media_ready`
- `send_result`
- `error`

Python 发给侧车的命令：

- `start`
- `stop`
- `relogin`
- `list_rooms`
- `send_text`
- `send_file`
- `send_image`
- `send_audio`

协议建议使用 stdio JSON Lines；只有确有必要时再考虑 HTTP loopback。stdio 暴露面更小，也更符合本项目安全边界。

### 任务二：新增 Node Wechaty 侧车

新增：

- `channel/wechat_group/sidecar/package.json`
- `channel/wechat_group/sidecar/wechaty-sidecar.mjs`

职责：

- 使用配置的 puppet 初始化 Wechaty。
- 输出二维码、状态、群列表和群消息事件。
- 将 Wechaty 群消息规范化为 CowAgent 可消费的 JSON。
- 下载图片、语音、文件到指定临时目录，并回传本地路径。
- 接收 Python 发送命令。
- 支持文本、图片、文件、音频文件发送。

### 任务三：新增 Python 渠道适配器

新增：

- `channel/wechat_group/wechat_group_channel.py`
- `channel/wechat_group/wechat_group_message.py`
- `channel/wechat_group/wechat_group_client.py`

修改：

- `channel/channel_factory.py`
- `common/const.py`
- `config.py`
- `config-template.json`

职责：

- 启动并监督侧车进程。
- 将侧车消息 JSON 转换为 `ChatMessage`。
- 调用 `_compose_context(..., isgroup=True, msg=...)` 进入 CowAgent 群聊链路。
- 复用 CowAgent 现有群白名单、前缀、关键词、会话、插件和回复流水线。
- 将回复通过侧车命令发回微信群。
- 在 `config.py` 和 `config-template.json` 中加入微信群人设配置项：`wechat_group_persona_prompt`、`wechat_group_persona_preset_id`。
- 在 Python 配置读取层提供默认人设与预设解析，保存配置时对 prompt 做长度限制、换行归一化和空白裁剪。

### 任务四：新增群归档与最近上下文服务

新增：

- `channel/wechat_group/wechat_group_archive.py`
- `channel/wechat_group/wechat_group_context.py`

职责：

- 懒加载创建 SQLite schema。
- 记录群内入站消息和助手回复。
- 支持按 `room_id` 查询最近消息。
- 生成可注入提示词的最近上下文摘要。
- 媒体路径相对配置的数据目录或工作区保存。

建议表：

- `wechat_group_messages`
- `wechat_group_assistant_replies`

### 任务五：升级通用作用域记忆并新增微信群记忆适配层

修改：

- `agent/memory/storage.py`
- `agent/memory/manager.py`
- `agent/memory/service.py`
- `agent/memory/config.py`

新增：

- `agent/memory/scope.py`
- `channel/wechat_group/wechat_group_memory.py`

职责：

- 将 CowAgent 原本记忆升级为通用作用域记忆，支持 `shared` / `user` / `session` / `wechat_group` / `wechat_group_member_profile`。
- 保持旧 `scope` / `user_id` 调用兼容，旧调用方不需要一次性改造。
- `WechatGroupMemoryService` 管理群永久记忆和群友画像的通道适配。
- 强制所有查询携带 `room_id`。
- 群友画像强制使用 `room_id + sender_id`，且每个成员在每个群只有一份当前 active 画像。
- 支持手动写入、检索召回、删除/停用，并为后续受控自动提取保留来源字段；4.3 首轮不启用自动提取审核流。
- 4.3.7 追加受控自动蒸馏：高置信度候选自动写入，低置信度候选进入 Web 审核，不允许 LLM 直接写全局 shared memory。
- 复用 CowAgent embedding provider、文本切分、摘要提取、FTS 和向量检索能力，但不能把群记忆写入全局 shared memory。
- 原始群消息仍保留在 `wechat_group_messages`，不进入长期记忆，除非通过明确手动写入或后续受控自动提取。

建议 schema 兼容扩展：

- `chunks` 新增 nullable 字段：
  - `scope_type TEXT`
  - `scope_id TEXT`
  - `channel_type TEXT`
  - `subject_id TEXT`
  - `status TEXT NOT NULL DEFAULT 'active'`
  - `source_message_ids TEXT`
- 新增独立画像 revision 表，例如 `wechat_group_member_profile_revisions`：
  - `id INTEGER PRIMARY KEY`
  - `room_id TEXT NOT NULL`
  - `sender_id TEXT NOT NULL`
  - `profile_chunk_id TEXT NOT NULL`
  - `role TEXT`
  - `preferences TEXT`
  - `expertise TEXT`
  - `interaction_style TEXT`
  - `boundaries TEXT`
  - `evidence TEXT`
  - `source_message_ids TEXT`
  - `created_by TEXT`
  - `created_at TEXT NOT NULL`
  - `metadata TEXT`
- 迁移脚本或初始化迁移逻辑必须把旧数据映射到新字段：
  - `scope = shared` -> `scope_type = shared`
  - `scope = user` -> `scope_type = user`，`scope_id = user_id`，`subject_id = user_id`
  - `scope = session` -> `scope_type = session`
- 旧字段 `scope`、`user_id` 暂不删除，所有旧 API 继续可读可写。

建议索引：

- `chunks(scope_type, scope_id, channel_type, status, updated_at)`。
- `chunks(scope_type, scope_id, subject_id, channel_type, status, updated_at)`。
- `wechat_group_member_profile_revisions(room_id, sender_id, created_at)`。
- `wechat_group_member_profile_revisions(profile_chunk_id, created_at)`。
- 保留原有 `idx_chunks_user`、`idx_chunks_scope`、FTS 和 trigram FTS 索引。

可选辅助表：

- `wechat_group_member_identities`：只记录 `room_id`、`sender_id`、`current_nickname`、`alias_names`、`last_seen_at`、`created_at`、`updated_at`，用于 UI 显示昵称变化和成员选择，不承载长期记忆正文。
- `wechat_group_member_identities(room_id, sender_id)` 唯一索引。

写入策略：

- 原始群消息先进入 `wechat_group_messages`，不自动等同为长期记忆。
- 管理员或明确指令写入的稳定事实可以直接进入群记忆；群友相关稳定信息应合并进该成员当前画像。
- `wechat_group_memory_auto_extract` 默认关闭；开启后也只能从当前 `room_id` 的消息窗口中提取，并保留来源消息 ID。自动提取结果必须先成为候选，再由置信度分流为自动写入或人工审核。
- 群友画像必须落在“当前群 + 当前成员”空间内，不按昵称合并，不跨群合并。
- UI 写入必须经过字段校验：`room_id` 必填；群友画像还要求 `sender_id` 必填；画像按六个结构化字段写入，至少一个字段 trim 后非空，首轮建议合并后的画像正文限制在 2000 字以内。
- 所有删除操作首轮采用软删除/停用：把 `status` 更新为 `disabled`，不物理删除原始记录，方便审计和回滚。
- 群友画像更新采用 upsert：六个结构化字段先合并到当前 active 画像，再把本次字段快照、来源消息和更新摘要写入独立 revision 表；提示词不召回多个历史版本。

召回策略：

- 群记忆检索必须传入 `room_id`。
- 群友画像读取必须传入 `room_id + sender_id`，返回当前 active 画像。
- embedding 相似度、关键词匹配和时间衰减可以组合使用，但 SQL 查询必须先按 `scope_type`、`scope_id`、`channel_type`、`subject_id` 和 `status` 过滤，再执行相关性排序。
- 返回给提示词装配层的每条上下文必须标注来源类型：`group_memory` 或 `member_profile`。
- embedding provider 不可用时必须降级到 FTS/LIKE 关键词检索；不能因为 embedding 初始化失败阻断微信群正常回复。
- 召回默认条数保持保守：群记忆最多 5 条；当前发言人群友画像最多 1 份；本轮明确 @ 到成员每人最多 1 份画像。

建议服务接口：

- `add_group_memory(room_id, room_name, content, source_message_ids=None, created_by="ui")`
- `upsert_member_profile(room_id, sender_id, sender_nickname, profile_fields, source_message_ids=None, updated_by="ui")`
- `search_group_memories(room_id, query, limit=5)`
- `get_member_profile(room_id, sender_id)`
- `list_group_memories(room_id, status="active", limit=50, offset=0)`
- `list_member_profiles(room_id, status="active", limit=50, offset=0)`
- `list_member_profile_revisions(room_id, sender_id, limit=20)`
- `disable_memory(memory_type, memory_id, room_id, sender_id=None)`
- `preview_prompt_memories(room_id, sender_id, query, mentioned_sender_ids=None, bot_sender_id=None)`

建议通用记忆接口：

- `MemoryScope(scope_type, scope_id="", channel_type="", subject_id="")`
- `MemoryManager.add_text(text, memory_scope, metadata=None)`
- `MemoryManager.search(query, memory_scope, limit=10)`
- `MemoryManager.list_by_scope(memory_scope, status="active", limit=50, offset=0)`
- `MemoryManager.disable(chunk_id, memory_scope)`

迁移与兼容验证要求：

- 旧 `shared` / `user` / `session` 记忆在 schema 扩展前后的搜索结果、权限过滤和返回格式保持一致。
- 旧数据迁移后必须能通过新 `MemoryScope` 查询到等价结果，同时旧 API 仍能查询到原结果。
- 新增作用域字段为空、缺省或旧库未迁移完成时，必须有兼容读取路径，不能导致现有记忆启动失败。

### 任务六：新增微信群提示词上下文装配

新增：

- `channel/wechat_group/wechat_group_prompt.py`

职责：

- 把微信群人设、最近群消息、群永久记忆、当前发言人画像、本轮明确 @ 到成员画像拼成紧凑上下文。
- 将当前生效人设作为独立 `<wechat-group-persona>` 块注入，只影响回复风格和边界，不作为群事实或记忆证据。
- 当本轮请求来自已验证管理员且属于配置/诊断语义时，可以跳过或降低普通人设块优先级，避免人设覆盖管理员意图。
- 控制 token 长度和条数。
- 标明每段上下文来源，避免模型把其他群信息当作当前群事实。
- 在进入 CowAgent 现有回复链路前追加到当前用户消息或 context metadata。
- 在 `WechatGroupChannel._compose_context()` 中按顺序追加人设、最近上下文和长期记忆块；当前实现已有前两者，4.3 只补充长期记忆块和统一装配帮助函数，不改 Agent 主链路。
- 长期记忆来源必须是 `WechatGroupMemoryService` 调用通用 `MemoryManager` 后返回的已过滤结果；提示词装配层不得自己拼 SQL、不得直接扫 `chunks`，也不得绕过 `MemoryScope`。
- 群永久记忆召回必须使用 `MemoryScope(scope_type="wechat_group", scope_id=room_id, channel_type="wechat_group")`。
- 当前发言人的群友画像读取必须使用 `MemoryScope(scope_type="wechat_group_member_profile", scope_id=room_id, channel_type="wechat_group", subject_id=sender_id)`。
- 被 @ 成员的群友画像读取必须先从 `at_list` 排除机器人自身和当前发言人，再逐个使用对应成员的 `subject_id`；不能按昵称模糊合并。
- 每个成员最多注入一份当前 active 画像；历史 revision 和来源依据只用于 UI 审计，不进入默认提示词。
- 当 `wechat_group_memory_enabled` 与 `wechat_group_member_memory_enabled` 都关闭时，不生成 `<wechat-group-memory>`。
- 当长期记忆检索失败时记录 warning 并继续原回复链路，不能因为记忆服务异常导致群消息不可回复。
- 建议长期记忆块格式：

```text
<wechat-group-memory>
[group_memory scope_type="wechat_group" scope_id="room@@abc"] 群规：工作日不刷屏。
[member_profile scope_type="wechat_group_member_profile" scope_id="room@@abc" sender_id="wxid_alice" nickname="Alice"]
身份/角色：项目负责人。
长期偏好：偏好简短结论。
互动风格：直接、关注执行。
已知边界：不要公开其私人联系方式。
最近更新依据：2026-07-02 群聊中确认。
</wechat-group-memory>
```

### 任务七：新增多模态适配

修改：

- `channel/wechat_group/wechat_group_message.py`
- `channel/wechat_group/wechat_group_channel.py`
- `channel/wechat_group/wechat_group_client.py`

职责：

- 图片消息映射为 `ContextType.IMAGE` 或文本附带图片路径。
- 图像生成请求映射为 `ContextType.IMAGE_CREATE`。
- 语音消息映射为 `ContextType.VOICE`。
- 文件/视频消息映射为 `ContextType.FILE`。
- 回复中的图片、文件、音频通过侧车发送。

### 任务八：新增安全守卫

新增：

- `channel/wechat_group/wechat_group_guard.py`

修改：

- `channel/wechat_group/wechat_group_channel.py`

职责：

- 用 Python 实现 BaiLongmaPro 高风险规则的核心版本。
- 命中风险时返回普通文本拒绝，不进入模型和工具执行。
- 支持管理员 sender ID 精确匹配。
- 支持屏蔽成员 sender ID。

### 任务九：新增最小 UI 与配置

修改或新增：

- 后端渠道管理接口对应字段。
- `channel/web/web_channel.py`
- `channel/web/static/js/console.js`
- `channel/web/static/css/console.css`

首轮 UI 只包含：

- 启用/停用微信群机器人。
- 扫码状态和二维码。
- 刷新群列表。
- 选择目标群。
- 保存配置。
- 最近事件和错误提示。
- 安全守卫、管理员 ID、屏蔽 ID 的最小配置入口。
- 微信群人设设定：显示 3 个内置预设卡片、自定义人设文本框、当前生效人设、已生效/有未保存修改状态和“保存人设并生效”按钮。
- 人设设置文案明确说明：点击预设只填入文本，不会立即生效；保存后才写入配置；人设不能绕过安全守卫。
- 群记忆运维入口：放在已有“群聊”管理页中新增“永久记忆”子菜单，不放回通道卡片，避免通道接入页承载过多运维细项。
- 永久记忆页整体采用“按群分组”的信息架构：
  - 左侧或顶部第一层显示已选目标群列表，包含群名、`room_id`、群记忆数量、群友画像数量和最近更新时间。
  - 选中某个群后，右侧或下方显示当前群详情，不允许同时混看多个群的记忆正文。
  - 当前群详情内分为“群记忆”和“群友画像”两个清晰区域，可用标签页、分栏或分段控件实现。
  - 群友画像区域按成员一人一张画像卡展示：成员昵称 / `sender_id`、画像摘要、标签、完整度/置信度、最近更新时间。
- 群永久记忆面板：
  - 显示 `wechat_group_memory_enabled` 开关、召回条数说明、当前选中群和当前群记忆数量。
  - 提供“新增群记忆”表单：目标群只允许从已选群列表中选择，正文为多行文本，保存时按钮 loading/disabled。
  - 展示当前群 active 记忆列表：内容摘要、更新时间、作用域标识、来源消息 ID、停用按钮。
  - 提供关键词搜索框，查询只调用当前 `room_id`，结果区域显示命中分数或匹配方式。
- 群友画像面板：
  - 显示 `wechat_group_member_memory_enabled` 开关。
  - 先选择目标群，再选择或输入稳定 `sender_id`；昵称只作辅助显示，不作为隔离键。
  - 提供“创建/更新群友画像”表单，字段固定为身份/角色、长期偏好、专业背景、互动风格、已知边界、更新依据。
  - 画像列表不显示“记忆条数”，而显示画像是否存在、最近更新时间、来源数量和版本数量。
  - 点击画像卡进入详情：展示当前画像正文、来源依据列表、历史版本列表、手动编辑按钮、停用画像按钮。
  - 自动提取后续开启时，UI 只展示“画像更新预览”：列出将新增/修改的字段，管理员确认后再合并到当前画像。
  - 明确提示“画像是当前群内对该成员的长期理解，不代表跨群身份”。
  - 支持只看有画像成员、按昵称 / `sender_id` / 标签搜索成员。
- 诊断预览：
  - 提供只读“本轮将注入的记忆预览”：输入模拟问题、当前发言人 sender ID、可选被 @ sender IDs，展示 `<wechat-group-memory>` 预览块。
  - 预览接口只读，不触发模型调用，不写入记忆。
- 统一记忆管理入口如果后续新增，也必须支持按 `scope_type` 分类筛选；其中微信群记忆应显示为“微信群 / 群记忆”和“微信群 / 群友画像”，而不是混入普通 shared/user 记忆列表。
- 4.3 首轮只做 Web 控制台“永久记忆”页，不修改桌面端 `desktop/`。桌面端后续复用 `/api/wechat-group/memories/` 和同一信息架构跟进。
- UI 使用 Web 控制台现有样式、表单控件和状态反馈；不新增 UI 框架，不使用 emoji 图标。所有按钮要有 loading/disabled 状态，长 `room_id` / `sender_id` 使用 `font-mono`、`truncate` 或 `break-words` 防止撑破布局。
- 后端 API 首轮沿用 `/api/channels` 返回 `wechat_group.extra.memory` 作为开关与摘要状态；记忆列表、写入、停用和预览使用独立接口 `/api/wechat-group/memories/`，避免把复杂 CRUD 塞进通道配置保存接口。
- UI 分类展示的数据必须来自统一记忆 API 的 `scope_type` / `scope_id` / `subject_id` 聚合结果，不得另建微信群长期记忆统计表作为事实来源。可选的成员身份表只用于昵称和成员选择辅助显示；画像来源和历史版本只用于审计，不作为当前画像正文的替代事实来源。

不做桌面端“永久记忆”页、完整富文本记忆编辑器、跨群身份合并 UI、完全无人值守自动记忆系统、战报、图库、备份导入 UI。群友画像首轮只做结构化字段编辑、来源/版本只读查看和停用；4.3.7 的自动生成 UI 只做候选审核和来源查看，不做复杂版本 diff 编辑器。

### 任务十：新增测试

新增测试文件建议：

- `tests/test_wechat_group_message.py`
- `tests/test_wechat_group_channel.py`
- `tests/test_wechat_group_archive.py`
- `tests/test_wechat_group_context.py`
- `tests/test_wechat_group_persona.py`
- `tests/test_wechat_group_web.py`
- `tests/test_memory_scope.py`
- `tests/test_wechat_group_memory_scope.py`
- `tests/test_wechat_group_memory.py`
- `tests/test_wechat_group_guard.py`
- `tests/test_wechat_group_multimodal.py`

最低覆盖：

- 群消息能映射到正确 `ChatMessage` 字段。
- @ 机器人消息能触发群上下文。
- 非白名单群会被忽略。
- 最近上下文只返回当前 `room_id`。
- 默认人设能注入 `<wechat-group-persona>`，自定义人设保存后能替换默认人设。
- `wechat_group_persona_preset_id` 能区分内置预设和 `custom`，未保存修改不会被误标记为已生效。
- 已验证管理员的配置/诊断请求不会被普通人设覆盖，但仍会经过安全守卫。
- 群永久记忆只按当前 `room_id` 召回。
- 群友画像只按 `room_id + sender_id` 读取。
- 同一个 `room_id + sender_id` 更新画像时只保留一份当前 active 画像，旧内容和结构化字段快照进入独立 revision 表。
- 本轮被 @ 群友画像会从 `at_list` 中排除机器人自身和当前发言人后召回。
- 记忆关闭或无命中时不注入 `<wechat-group-memory>` 空块。
- A 群记忆不会泄漏到 B 群。
- 通用记忆 `shared` / `user` / `session` 旧调用路径保持兼容。
- 统一记忆检索必须先按 `scope_type` / `scope_id` / `channel_type` / `subject_id` 过滤，再做排序。
- 图片、语音、文件消息能映射到正确 `ContextType`。
- 高风险命令在模型执行前被拒绝。
- 出站回复使用 room ID 和稳定发送人 @ 元数据。
- Web API 能返回微信群记忆开关与摘要状态。
- Web API 写入群记忆时必须校验 `room_id`，创建/更新群友画像时必须校验 `room_id + sender_id`。
- Web API 查询和停用不得跨 `room_id` 操作。
- Web 控制台“永久记忆”页能保存开关、写入记忆、搜索当前群记忆、停用记忆，并在加载/失败/空状态下给出明确反馈。
- Web 控制台必须能直观看到按群分类的记忆数量与内容；选中某个群后，群友画像必须按成员一人一张画像卡展示。

## 7. 建议配置项

新增保守默认值：

```json
{
  "wechat_group_enabled": false,
  "wechat_group_puppet": "wechaty-puppet-wechat4u",
  "wechat_group_sidecar_node": "node",
  "wechat_group_sidecar_memory_path": "",
  "wechat_group_names": [],
  "wechat_group_room_ids": [],
  "wechat_group_ambient_names": [],
  "wechat_group_admin_sender_ids": [],
  "wechat_group_blocked_sender_ids": [],
  "wechat_group_record_messages": true,
  "wechat_group_media_dir": "",
  "wechat_group_guard_enabled": true,
  "wechat_group_sidecar_start_timeout": 60,
  "wechat_group_persona_preset_id": "owner-digital-twin",
  "wechat_group_persona_prompt": "",
  "wechat_group_recent_context_enabled": true,
  "wechat_group_recent_context_limit": 20,
  "wechat_group_recent_context_minutes": 60,
  "wechat_group_memory_enabled": true,
  "wechat_group_member_memory_enabled": true,
  "wechat_group_memory_auto_extract": false,
  "wechat_group_memory_auto_apply_threshold": 0.82,
  "wechat_group_memory_candidate_threshold": 0.55,
  "wechat_group_memory_distill_minutes": 60,
  "wechat_group_memory_distill_message_limit": 200,
  "wechat_group_memory_distill_auto_apply_group": true,
  "wechat_group_memory_distill_auto_apply_profile": true,
  "wechat_group_memory_context_limit": 5,
  "wechat_group_member_memory_context_limit": 5,
  "wechat_group_voice_reply_enabled": false
}
```

说明：`wechat_group_member_memory_enabled` 和 `wechat_group_member_memory_context_limit` 为兼容既有命名保留，4.3 语义调整为“群友画像开关”和“群友画像上下文上限”。如果后续做配置重命名，需要提供旧键兼容读取。`wechat_group_memory_auto_apply_threshold` 必须大于 `wechat_group_memory_candidate_threshold`；低于候选阈值的 LLM 结果不写入候选表，高于自动写入阈值的结果仍需通过 `room_id`、`sender_id` 和来源消息校验后才能写入 scoped memory。

继续兼容 CowAgent 现有配置：

- `group_name_white_list`
- `group_chat_prefix`
- `group_chat_keyword`
- `group_shared_session`
- `group_chat_in_one_session`
- `nick_name_black_list`
- `image_create_prefix`
- `always_reply_voice`
- `voice_reply_voice`

## 8. 验证计划

首轮实现后运行：

```powershell
python -m unittest tests.test_wechat_group_message
python -m unittest tests.test_wechat_group_channel
python -m unittest tests.test_wechat_group_archive
python -m unittest tests.test_wechat_group_context
python -m unittest tests.test_wechat_group_persona
python -m unittest tests.test_wechat_group_web
python -m unittest tests.test_memory_scope
python -m unittest tests.test_wechat_group_memory_scope
python -m unittest tests.test_wechat_group_memory
python -m unittest tests.test_wechat_group_guard
python -m unittest tests.test_wechat_group_multimodal
```

通用作用域记忆改造后优先运行：

```powershell
python -m unittest tests.test_memory_scope tests.test_wechat_group_memory_scope tests.test_wechat_group_context
```

4.3 首轮不涉及桌面端，不要求运行桌面端构建。后续补桌面端“永久记忆”页时再运行：

```powershell
Set-Location -LiteralPath .\desktop
npm run build
```

交付前运行：

```powershell
python -m unittest discover -s tests
```

需要真实微信登录的手动验证：

- 使用包含 `wechat_group` 的 `channel_type` 启动 CowAgent。
- 扫码登录。
- 确认群列表可获取。
- 只选择一个测试群。
- 非 @ 消息默认不回复。
- @ 机器人，确认回复会结合最近上下文。
- 在 UI 中切换“技术值班助手”预设但不保存，确认状态显示有未保存修改且实际回复仍沿用旧人设。
- 点击“保存人设并生效”后再次 @ 机器人，确认回复风格体现新的人设设定。
- 输入自定义人设并保存，确认配置标记为 `custom`，且人设只影响回复风格，不影响安全拦截和记忆隔离。
- 写入一条当前群群记忆，确认只在当前群召回。
- 创建或更新当前群某成员画像，确认只在该群该成员相关问题中召回。
- 再次更新同一成员画像，确认提示词只注入当前画像，旧画像只作为来源/版本审计展示。
- 切换到另一个测试群，确认不会召回前一个群的记忆。
- 发送图片，确认能进入图片理解或图片路径上下文。
- 触发图片生成，确认生成图能发回当前群。
- 发送语音，确认能进入语音识别链路。
- 开启语音回复时，确认 TTS 结果能以音频文件或可支持形式发回。
- 停止并重启，确认没有把登录态写入仓库跟踪文件。

## 9. 推荐首轮交付边界

首轮交付包含：

- Node Wechaty 侧车。
- Python `wechat_group` 渠道。
- 扫码登录、群列表、目标群选择。
- @ 触发文本回复。
- 微信群助手人设设定：内置预设、自定义 prompt、当前生效状态和保存后注入。
- 当前群最近上下文注入。
- 群永久记忆和群友画像的基础写入/更新、隔离、召回。
- 文本、图片理解、图片生成、语音识别、语音合成的基础通路。
- 微信群入口安全守卫。
- 最小 UI 运维面板。

首轮不追求：

- 完整社交工作台。
- 精美战报。
- 复杂群记忆管理 UI。
- 复杂人设市场、分群独立人设、群友可在线改人设。
- 图片库检索。
- 视频理解。
- 备份迁移中心。

交付判断标准：

- 能稳定作为 CowAgent 的一个微信群消息通道运行。
- 回复能结合当前群最近上下文。
- 人设设定能通过 UI 保存并注入当前微信群回复，且不能绕过安全守卫。
- 群记忆和群友画像不会跨群泄漏。
- 多模态请求能复用 CowAgent 现有能力。
- 安全守卫能在模型和工具执行前阻断高风险请求。
