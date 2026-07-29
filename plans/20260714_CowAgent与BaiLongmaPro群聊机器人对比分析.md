# CowAgent 与 BaiLongmaPro 群聊机器人对比分析

> 状态：历史分析快照。项目现已更名为 LightAgent，且 2026-07-20 至 2026-07-29 已完成画像重建、成员级 session、observe-only 和部分统一 timeline；当前实施依据改为 `plans/20260729_微信群上下文与会话引擎重构计划.md`。本文保留当时证据，不再代表当前代码基线。
>
> 分析时间：2026-07-14 至 2026-07-15  
> 分析对象：两个项目当前工作区代码、当前非敏感运行配置、CowAgent 2026-07-14 运行日志，以及两边本地 SQLite 数据快照  
> 隐私边界：本文不记录真实群名、成员名、聊天正文、密钥、服务地址或本机数据目录

## 1. 执行摘要

用户感受到 BaiLongmaPro 的群聊机器人“更聪明、更像真人、上下文感知和意图理解更强”，这个体感有明确的工程原因，但**主要原因不是模型更强**。

分析快照中，两边主回复链路使用相同的模型名称，并解析到同一类服务入口；真正拉开差距的是模型调用前后的系统设计：

1. **BaiLongmaPro 每轮给模型的群聊现场更厚、更稳定。**它固定读取 24 小时内最多 100 条群消息，并同时组装摘要、90 天归档证据、群记忆、成员记忆、语义聊天记录、外部知识和图片记忆。CowAgent 则通过关键词和触发类型决定是否注入历史，普通的“那怎么办”“你怎么看”“然后呢”之类隐式承接很可能只带当前一句进入主 Agent。
2. **CowAgent 当前的长期记忆链路在稳定身份迁移后实际上没有闭环。**本地数据中，400 个 stable member 与 325 份旧画像主键的交集为 0；7 个 stable room 与群记忆、学习游标的交集也为 0。代码已经优先按 stable ID 查询，但既有数据和部分抽取仍使用 runtime ID，因此“库里有画像，真实回复却一份也召回不到”。
3. **CowAgent 的自由回复是“激进初筛 + 信息不足的 LLM 复判”。**当前 `active` 档阈值为 30，候选很多；但 LLM judge 只看到当前文本和本地分数，不看最近群聊，却又被要求判断是否为两人私聊。它还使用严格 `json.loads()`、没有真正执行配置的超时，而且实际温度可能回退到 0.9，导致大量不稳定拒绝。
4. **BaiLongmaPro 在主 Agent 前就处理高频群聊意图。**群总结、图片标注、视频理解、生图、图库检索、网络图片和表情包等都有显式前置路由；CowAgent 大多把意图识别、工具选择和最终表达一次性交给通用 Agent。前者未必更“通用”，但在高频场景中更确定、更快，也更像“听懂了”。
5. **CowAgent 的会话历史与真实群现场不一致。**当前 7 个微信群都使用共享群 session，但 session 只积累触发过机器人的 Agent 轮次；近期群友消息和机器人真实发言没有形成统一 room timeline。结果可能同时出现“最新现场没看到”和“很久以前的 Agent 问答被恢复”。
6. **生成稳定性进一步放大了差距。**CowAgent 的 `LLMRequest.temperature=0` 没有被 adapter 透传，自定义 Provider 回退到默认 0.9；BaiLongmaPro 当前温度为 0.5。2026-07-14 CowAgent 日志还出现 24 行 LLM API 错误、12 行 Agent reply error 和多次 circuit open。用户会把 JSON 失败、工具选错、超时或错误回复统一感知为“不聪明”。

因此，最准确的总判断是：

> BaiLongmaPro 不是单纯“模型脑子更好”，而是它在群聊场景中给模型提供了更多连续现场、更多可命中的记忆和更明确的意图捷径。CowAgent 的模块、安全边界和稳定作用域设计更规范，但当前关键数据迁移、上下文策略和运行参数没有闭环，导致设计能力没有转化为真实回复能力。

## 2. 一页结论对比

| 维度 | CowAgent 当前状态 | BaiLongmaPro 当前状态 | 对用户体感的影响 |
|---|---|---|---|
| 主模型 | 与对方相同；不能解释差距 | 与 CowAgent 相同 | 不是主因 |
| 近期群聊 | 按触发源/关键词门控；实际窗口 60 分钟 | 每轮固定读取 24 小时最多 100 条 | Bai 更容易承接省略句和隐式指代 |
| 机器人上一句 | 与群友入站归档分离，未形成统一 timeline | 助手回复会记录并参与群聊上下文 | Bai 更容易接住“那你继续”“所以呢” |
| 长期记忆 | 代码能力完整，但 stable/runtime 主键错位，真实注入为 0 | 4,401 条群/成员记忆项并做混合召回 | Bai 更像“认识群友、记得群里的事” |
| 本地摘要/归档 | 仅上下文依赖场景注入；本地摘要仍是抽取拼接 | 每轮组装快速摘要和长期归档证据 | Bai 背景更连续，但 token 和噪声更高 |
| 自由接话 | `active`、阈值 30；judge 无近场消息、严格 JSON | 当前 `quiet`、阈值 65；规则判定读取近 2 小时 18 条 | Cow 候选更多，但该说时反而可能被错误拒绝 |
| 意图路由 | 通用 Agent 承担大部分识别和工具选择 | 多个高频意图在主 Agent 前直接路由 | Bai 在总结、多媒体和找图等场景更确定 |
| 人设与风格 | 人设稳定注入；89 条 style 全是 candidate，实际注入 0 | 人设与群记忆共同参与回复 | Cow“有人设”，但群体语言习惯没有真正生效 |
| Agent session | 缺省按群共享，可能恢复旧触发轮次 | 主要依赖实时群上下文和统一状态 | Cow 可能把旧 Agent 对话误当当前现场 |
| 温度 | 请求的 0 未透传，实际可能回退 0.9 | 当前 0.5 | Cow 的 JSON、工具选择和指令遵循更抖 |
| 运行可靠性 | 当日有 API 错误、Agent error、熔断 | 本次未做同口径故障率对照 | Cow 的失败会直接被感知为能力差 |
| 安全与隔离 | stable scope、权限门禁、原文持久化清洗更系统 | 上下文更厚，部分状态更集中 | Cow 架构基础更稳，Bai 当前体感更强 |

## 3. 分析方法与结论边界

本次分析使用四类证据，并刻意区分“代码有能力”和“运行时真正生效”：

1. **静态代码链路**：从微信群消息接收、触发判断、上下文装配、记忆召回、Agent/工具调用，到回复发送与状态更新。
2. **当前配置**：只读取模型名、温度、时间窗、自由回复档位、阈值和开关等非敏感字段。
3. **CowAgent 运行日志**：统计 2026-07-14 的 Agent turn、上下文块、自由回复判定和错误事件；不读取或引用聊天正文。
4. **本地 SQLite 快照**：只做表级数量、时间范围、状态分布和去标识化主键交集统计。

这些结果足以解释架构和运行差异，但不是严格的模型 A/B 测试：

- 两边数据时间范围、群活跃度和真实问题分布不同。
- BaiLongmaPro 的数据快照截至 2026-07-01，CowAgent 截至 2026-07-14。
- 日志错误数按日志行统计，重试可能对应同一个用户请求，不能直接当作独立失败请求数。
- 本次没有读取私人聊天正文做答案质量打分，也没有让同一批问题同时请求两个在线机器人。

因此，本文对“机制为何产生这种体感”的结论强，对“每个因素贡献了百分之多少”的结论不做虚假精确化。

## 4. 两条完整回复链路

### 4.1 CowAgent

```text
Wechaty sidecar 收到群消息
  -> WechatGroupChannel 解析、去重、稳定身份映射、触发判断
  -> 入站消息写入 archive
  -> WechatGroupHumanizedContextBuilder
       -> 固定策略块：权限、mention、reply policy、persona
       -> 条件历史块：archive、local summary、recent、focus
       -> 可选长期块：group memory、member profile、style、emotion
       -> 多模态/引用块
  -> ChatChannel -> Bridge.fetch_agent_reply()
  -> Agent 恢复 session、加载通用系统 prompt 和工具
  -> LLM 决定回复及工具调用
  -> 微信清洗、发送、记录助手回复和情绪状态
```

关键问题出现在三个交界面：

- `should_include_contextual_history()` 只识别特定触发源和有限关键词，见 `channel/wechat_group/wechat_group_humanized_context.py:235`。
- `group_shared_session` 未配置时按 `True` 处理，见 `channel/chat_channel.py:85`。
- 群友入站消息、助手真实回复、Agent session 是三种不同历史，没有统一为同一条关系型群聊时间线。

### 4.2 BaiLongmaPro

```text
Wechaty 收到群消息
  -> 归档文本/媒体并更新群状态
  -> ambient / mention / admin 等入口判定
  -> 高频意图前置路由
       -> 群总结、图片标注、视频理解、生图
       -> 已存图片、网络图片、表情包等
  -> 未被直接处理时构建群聊增强文本
       -> 24h / 100 条 recent transcript
       -> quick summary、90 天 archive evidence
       -> 群记忆、成员记忆、语义聊天记录
       -> 外部知识、图片记忆、persona、权限信息
  -> 群 worker 调用主 Agent
  -> 发送并把助手回复写回群聊记录
```

相关入口集中在 `src/social/wechat-groups.js:187-193`、`src/social/wechat-groups.js:369-374` 和 `src/social/wechaty-duty-group.js:2697-2739`。

这条链路的核心特点不是更精巧，而是**在每轮调用前尽量把群聊现场准备齐，并把容易误判的高频意图先确定下来**。

## 5. 根因排序

### 5.1 P0：CowAgent 的长期记忆和画像在 stable identity 迁移后真实命中为零

这是当前影响最大、也最容易被表面代码能力掩盖的问题。

CowAgent 已经实现了群记忆、发言人画像、被 mention 成员画像、stable room/member 隔离和相应 prompt 块。只看代码会认为这部分比 BaiLongmaPro 更规范。但本地快照显示：

- 归档中有 400 个 distinct stable member。
- 画像表有 325 份画像，但其 subject 主键与 stable member 的交集为 0。
- 同一批画像与 legacy runtime member 的交集为 235。
- 归档中有 7 个 stable room，但它们与群记忆 scope、画像学习游标 scope 的交集均为 0。
- 2026-07-14 的 160 次微信群 Agent turn 中，`<wechat-group-memory>` 注入次数为 0。

代码层也存在同一错位：

- `wechat_group_profile_llm_extractor.py:86` 仍把归档行的 runtime `sender_id` 提供给 LLM，并要求 LLM 按该 ID 返回画像。
- `wechat_group_profile_evolution_executor.py:167` 的成员统计已优先使用 `stable_member_id`。
- 查询和权限链路又优先使用 stable ID。

也就是说，**统计、抽取、存储和查询没有使用同一种主键**。这不是“记忆召回算法不够强”，而是 join key 不一致。只要这条链路不修，继续优化向量检索、prompt 或画像内容都不会改善真实回复。

BaiLongmaPro 的本地库已有 4,401 条 active 群记忆项，虽然其中噪声和重复不少，但至少每轮混合召回能够拿到真实材料。用户体感自然会是它更记得人和事。

### 5.2 P0：CowAgent 的历史门控漏掉了最像真人聊天的隐式承接

CowAgent 当前只在以下条件中打开归档证据、本地摘要和普通 recent transcript：

- 自由回复、引用机器人、图片消息。
- 文本包含“刚才、上面、前面、之前、谁说、总结、继续、引用、图片、照片、链接、什么意思”等标记。

这个策略适合控制 token 和隐私，但它把自然群聊中最常见的一类句子遗漏了，例如：

- “那怎么办？”
- “你怎么看？”
- “所以呢？”
- “真的假的？”
- “这个能用吗？”

这些句子没有固定关键词，却必须结合刚发生的群聊才能理解。当前 standalone @ 可能只把这一句话交给 Agent；如果 Agent session 恰好还有旧对话，它甚至会用旧话题补全当前省略句。

BaiLongmaPro 每轮读取 24 小时内最多 100 条消息，因此这种句子更容易被正确补全。它的方案成本更高，却直接提升了“像在群里一直听着”的感觉。

正确改法不是让 CowAgent 也无条件塞 100 条，而是把布尔门控升级为分层策略：

```text
current_only -> recent -> contextual -> recall
```

其中省略句、短追问、回复机器人上一句应至少进入有界 `recent`；总结、查证和显式回溯才进入 `recall`。

### 5.3 P0：自由回复 judge 无法完成 prompt 要求它完成的判断

CowAgent 的 judge prompt 明确要求识别：

- 是否为 A 对 B 说话。
- 是否为两个人私聊。
- 是否会打断群聊。
- 是否是群友已经在处理的问题。

但 `build_free_reply_judge_prompt()` 实际只传入群名、发送者、当前文本、本地分数、加分和抑制原因，见 `channel/wechat_group/wechat_group_free_reply_judge.py:53`。它没有最近 3 至 5 条消息、引用对象、mention 关系，也没有机器人上一句。

这相当于要求模型在看不到对话的情况下判断对话关系。随机性不是偶然，而是输入不足。

2026-07-14 全日日志中可识别到：

| 事件 | 次数 | 说明 |
|---|---:|---|
| 本地判定后进入候选队列 | 564 | 当前 `active` 档阈值 30，候选范围较宽 |
| LLM judge 拒绝 | 454 | 包括正常拒绝、解析失败和调用异常 |
| 其中 `invalid_json` | 195 | 占 LLM 拒绝约 43.0% |
| LLM judge 批准 | 71 | 进入最终回复链路 |
| 本地复读规则批准 | 19 | 不依赖 LLM judge |

候选数与已记录判定结果不是严格闭合漏斗，因为进程重启、队列合并、过期和日志截点会留下未闭合任务；但 195 次严格 JSON 失败已经足以说明 judge 的协议不稳定。

另外，`free_reply_judge_timeout_seconds` 只被写入 `Context`，见 `wechat_group_free_reply_judge.py:108`，worker 调用没有用 future、socket timeout 或 watchdog 执行真正的超时控制，见 `wechat_group_free_reply_worker.py:198` 附近。

对比之下，BaiLongmaPro 的 ambient 规则判定会读取近 2 小时最多 18 条消息，并据此检测两人连续对话、刷屏、无人回答和冷场，见 `src/social/wechat-ambient-reply.js:284-323`。其当前档位还是 `quiet`、阈值 65。它候选更少，但每次候选判断看到的信息更完整。

### 5.4 P0：缺少包含 assistant 的统一 room timeline

CowAgent 当前至少有三份“历史”：

1. `wechat_group_messages`：群友入站归档。
2. `wechat_group_assistant_replies`：机器人真实发送的回复。
3. Agent session：仅包含触发主 Agent 的 user/assistant/tool 轮次。

recent、焦点和自由回复 judge 主要读取第一份；Agent 恢复第三份；机器人真实回复则单独记录在第二份。这会产生两个直接问题：

- 群友紧跟机器人说“那重启就行？”时，recent 不一定能看到机器人刚才说了什么。
- 当前群已经换了话题时，共享 Agent session 仍可能恢复较早的一轮问答。

当前配置未显式设置 `group_shared_session`，调用点按 `True` 处理；本机 7 个微信群 session 均为群级共享。共享并非绝对错误，但它必须建立在统一的现场 timeline 和明确的 history mode 之上，否则只是共享“曾经触发过机器人的片段”，并不等于共享真实群聊。

### 5.5 P1：BaiLongmaPro 的专用意图路由减少了主 Agent 的猜测空间

BaiLongmaPro 在进入主 Agent 前，按顺序尝试处理：

- 群聊总结/海报总结。
- 图片标注。
- 视频理解。
- 生图。
- 已入库图片检索和发送。
- 网络图片搜索。
- 表情包搜索。
- 现有图片理解。

这些路由位于 `src/social/wechaty-duty-group.js:2697-2739` 及其后续分支。命中后会直接调用对应服务并发送结果，不再让通用 Agent 同时完成“识别意图 -> 选工具 -> 参数提取 -> 组织回复”。

CowAgent 继续复用统一 `Bridge -> Agent -> tools` 主链路，这个模块边界更干净，但高频群聊意图缺少一个受控的确定性入口。尤其在模型高温度、工具较多或服务不稳定时，用户容易感受到：

- 明明是在总结，却开始泛聊。
- 明明问当前图片，却找了旧图片。
- 明明要生图，却先解释了一段。
- 同一句意图不同时间走了不同工具。

建议借鉴的是“小而明确的前置分类和受控路由”，不是把 BaiLongmaPro 的 4,000 多行群聊主文件整体复制过来。

### 5.6 P1：CowAgent 的温度透传缺口影响 JSON、工具与指令稳定性

Agent 核心构造了 `LLMRequest(temperature=0)`，见 `agent/protocol/agent_stream.py:1098`；但 `AgentLLMModel._build_call_kwargs()` 只转发 messages、tools、stream、model、max_tokens、system 等字段，没有转发 `request.temperature`，见 `bridge/agent_bridge.py:401` 附近。

当前 CowAgent 配置又没有显式 `temperature`，Provider 配置回退到默认 0.9，见 `bridge/agent_bridge.py:54` 和 `bridge/agent_bridge.py:375`。因此代码看起来要求确定性为 0，实际自定义 Provider 可能仍按 0.9 生成。

BaiLongmaPro 当前主链路温度为 0.5，默认值和转发位置见 `src/config.js:420`、`src/core/turn.js:440`。

这个差异不会让模型突然“更有知识”，但会显著影响：

- 严格 JSON 输出成功率。
- 同一意图选择同一工具的稳定性。
- 对系统 prompt 和群聊短句约束的遵循。
- 回复长度、语气和跑题概率。

自由回复 judge 应单独使用 0 至 0.2 的低温度，不应和拟人化最终回复共用同一随机性设置。

### 5.7 P1：CowAgent 学到了风格，但没有让风格生效

CowAgent 当前数据库有 89 条 style card，但全部处于 `candidate` 状态；默认 `wechat_group_style_auto_apply_enabled=false`，当前配置未覆盖该值。`WechatGroupStyleService.list_active_styles()` 只返回 active 项，见 `channel/wechat_group/wechat_group_style_service.py:24-27`。

运行证据也吻合：160 次 Agent turn 中，persona、mention policy 和 reply policy 各注入 160 次，style 注入 0 次。

所以 CowAgent 不是没有拟人化设计，而是：

- 固定 persona 生效了。
- 群体长期形成的用词、节奏和梗偏好没有通过审核/自动启用闭环进入回复。

这会造成“每句都像同一个预设机器人”，而不是“逐渐像这个群里的人”。

### 5.8 P1：运行可靠性会被用户直接归因成智力问题

CowAgent 2026-07-14 日志中出现：

- 24 行 LLM API error。
- 12 行 Agent reply error。
- 多次 primary circuit open。
- 连接重置和上游 503 等错误。

这些数字按日志行统计，包含重试，不能等同于 24 个独立用户请求。但对群聊体验而言，只要一次请求出现长等待、空回复、fallback 或错误文案，用户不会区分是“模型不懂”还是“上游失败”，只会觉得机器人不稳定、不聪明。

### 5.9 P2：工具数量和 prompt 负担是次要因素，不是主因

CowAgent 默认先加载全部工具，再按权限过滤；本次微信群 Agent 实际约暴露 19 个工具，相关入口见 `bridge/agent_bridge.py:706`。

BaiLongmaPro 虽然有动态工具路由，但其微信群大 prompt 固定包含文件、图片、记忆、链接和管理员等能力词。用当前路由规则离线模拟时，约有 28 个工具会被激活。因此不能用“Bai 工具更少，所以更聪明”解释差距。

更准确的判断是：

- 两边主 Agent 都有较大的工具和 prompt 负担。
- Bai 的高频意图在主 Agent 前已被分流，减少了最常用场景的工具猜测。
- Cow 后续仍应按群聊意图精简工具，但这排在身份、timeline、judge 和温度之后。

## 6. 运行态证据

### 6.1 CowAgent 上下文块命中

2026-07-14 日志中抽取到 160 次微信群 Agent turn：

| 上下文块/策略 | 命中次数 | 命中率 | 解读 |
|---|---:|---:|---|
| persona | 160 | 100% | 固定人设不是缺失项 |
| mention policy | 160 | 100% | 触发与 @ 策略稳定进入 prompt |
| reply policy | 160 | 100% | 回复模式约束稳定进入 prompt |
| recent transcript | 97 | 60.6% | 约四成 turn 没有近期群聊原文 |
| archive/local summary | 90 | 56.3% | 仅上下文依赖场景进入 |
| focus | 117 | 73.1% | 焦点覆盖高，但可能替代最新消息 |
| memory/profile | 0 | 0% | stable/runtime 错位的直接运行证据 |
| style | 0 | 0% | 89 条 candidate 未形成生效闭环 |

这些是 prompt 块出现次数，不代表每个块内容都相关，也不代表模型一定正确使用。它们证明的是：固定人格一直在，真正缺失的是可命中的长期记忆和稳定的近场事实。

### 6.2 两边数据厚度

| 指标 | CowAgent | BaiLongmaPro |
|---|---:|---:|
| 去除明显异常后的群消息 | 约 18,761 | 30,713 |
| 数据时间范围 | 2026-07-02 至 2026-07-14 | 2026-06-03 至 2026-07-01 |
| 群记忆/成员记忆项 | 群记忆 1 条；画像 325 份但 stable 命中 0 | 4,401 条 active memory item |
| 风格数据 | 89 条，全部 candidate | 未按同结构对照 |
| 明显测试污染 | 223 条 `<Mock ...>` message type；约 233 条测试标记记录 | 本次未发现同口径数据 |

BaiLongmaPro 的 4,401 条记忆大致由以下内容构成：

- 成员发言素材 3,768 条。
- 自动事实 531 条。
- 人物总结 75 条。
- 别名、显式记忆等 27 条。

这不意味着 4,401 条都高质量。大量发言素材可能重复、过时或只是原话摘录，但“有可召回材料”和“真实注入为 0”的体验差异仍然非常大。

### 6.3 配置差异

| 配置 | CowAgent 当前值 | BaiLongmaPro 当前值 |
|---|---:|---:|
| 模型 | 相同模型名称 | 相同模型名称 |
| 温度 | 未显式配置；adapter 缺口使其可能回退 0.9 | 0.5 |
| recent 时间窗 | 60 分钟 | 24 小时 |
| recent 条数 | 100，但受历史门控 | 100，固定构建 |
| 自由回复档位 | `active` | `quiet` |
| 自由回复阈值 | 30 | 65 |
| style 自动应用 | 缺省 false | 非同构能力，未直接比较 |

一个容易误判的点是：CowAgent 模板默认 recent 为 1,440 分钟，但当前 `config.json` 已收紧到 60 分钟。因此阅读 `config-template.json` 得出的“也有 24 小时 100 条”并不等于当前真实运行行为。

## 7. 哪些并不是主要原因

### 7.1 不是 BaiLongmaPro 使用了更强的主模型

分析快照中，两边模型名称相同，服务入口也属于同一配置来源。模型本身不能解释稳定、持续的体感差异。

### 7.2 不是 CowAgent 没有人设 prompt

CowAgent 每次 Agent turn 都注入 persona，而且当前 persona 已明确要求自然、简短、接梗和适合群聊节奏。固定人设缺失不是问题；问题是事实现场、成员记忆和群体风格没有同时稳定生效。

### 7.3 不是自由回复越积极就越像真人

CowAgent 的阈值更低、候选更多，却因为二次判断输入不足和 JSON 不稳出现“想插话时很积极，真正该接时又沉默”。BaiLongmaPro 当前更保守，但它判断时读取近场消息。**精度比候选数量更影响真人感。**

### 7.4 不是简单增加工具数量就能解决

工具越多只代表能力入口越多，不代表意图识别越准。当前更缺的是确定性上下文、正确作用域和高频意图路由。

## 8. CowAgent 现有设计中更好的部分

这次对比不应得出“全面照搬 BaiLongmaPro”的结论。CowAgent 有几项基础设计更适合作为长期架构：

1. **稳定作用域设计更明确。**长期配置、权限、记忆、画像和焦点都计划按 stable room/member 隔离；当前问题是迁移没有闭环，不是方向错误。
2. **管理员权限是服务端硬门禁。**通道层、工具过滤和 prompt 三层约束比单靠模型自觉更可靠。
3. **增强 prompt 不污染长期 Agent 历史。**`wechat_group_user_content` 和原文替换逻辑可以防止 `<wechat-group-*>` 块在下一轮重复累积，见 `bridge/agent_bridge.py:1344-1353`。
4. **渠道与 Agent 边界更清楚。**Wechaty sidecar 负责协议和收发，最终回复复用 CowAgent 通用 Bridge、Agent、工具和知识库，没有另造一套独立 LLM loop。
5. **默认按需注入历史有隐私和成本优势。**问题是当前门控过于粗糙，应升级为分层选择，而不是退回无条件堆满历史。
6. **安全投影意识更强。**媒体路径、XML、base64、runtime ID 和内部块名都有明确的清洗边界。

这些能力说明 CowAgent 不需要推倒重来。优先把 identity、timeline、judge 和 adapter 接通，收益会比继续增加新模块更高。

## 9. BaiLongmaPro 当前方案的代价与风险

### 9.1 每轮厚上下文带来重复、陈旧信息和 token 成本

recent、quick summary、archive evidence、memory 和 semantic records 可能同时包含同一批事实。模型会重复加权，也可能被旧结论覆盖最新消息。长期运行后，成本和延迟会随数据厚度增长。

### 9.2 记忆数量不等于记忆质量

4,401 条中有 3,768 条属于成员发言素材。若缺少去重、时效、事实归属和冲突处理，机器人可能把玩笑当事实、把旧偏好当现状，或反复引用同一内容。

### 9.3 全局 focus/state 与并发群 worker 存在竞态风险

`src/core/turn.js:123-191` 在共享 state 上更新 focus，`src/core/loop.js:234` 启动并发微信群 worker。当前实现是否在所有路径都完成群级隔离，需要专项并发测试；否则存在焦点被其他群 turn 覆盖或状态串用的风险。本文没有发现已发生的跨群泄露证据，因此这里只定性为风险，不定性为现存事故。

### 9.4 前置路由集中在超大文件中，维护成本高

`wechaty-duty-group.js` 超过 4,000 行，高频意图直接分支虽然提升当前确定性，但新能力持续加入后容易出现顺序依赖、规则冲突和难以覆盖的组合路径。

### 9.5 更厚上下文扩大隐私面

每轮固定读取大量群聊、成员记忆和归档证据，意味着更多私人内容进入模型请求。CowAgent 应学习 Bai 的连续性，不应无条件复制其数据暴露范围。

## 10. 建议路线图

### 10.1 P0：先修“看不到”和“接不住”

#### A. 完成 stable identity 数据闭环

目标：抽取、存储、查询和权限统一使用 `stable_room_id + stable_member_id`。

必要工作：

- 为已确认的 runtime room/member 建立一次性可审计 backfill，不对歧义映射自动猜测。
- 画像抽取输入和返回 schema 改用 stable member，runtime ID 只保留为来源快照。
- 群记忆、画像和学习游标统一迁移到 stable room scope。
- 对 400 stable member / 325 旧画像建立迁移报告：成功、歧义、无映射分别计数。
- 增加 stable/runtime 混用和跨群泄露回归测试。

验收：

- 真实 Agent turn 的 memory/profile 注入不再长期为 0。
- 已迁移 stable member 与当前画像 subject 存在合理交集。
- 两个不同群使用相同昵称时，画像和记忆仍严格隔离。

#### B. 建立统一 room timeline

目标：recent、judge、stale revalidation 和滚动摘要使用同一种群聊事实流。

timeline 至少包含：

- 群友入站消息。
- 机器人已真实发送成功的回复。
- actor、addressee、引用对象、是否回复机器人、时间和安全正文。

验收：机器人回复后，群友发“那重启就行？”时，下一轮能看到机器人上一句；同时不能恢复无关的旧 Agent 话题。

#### C. 修复自由回复 judge

目标：让 judge 的输入足以判断群聊关系，并让协议确定性可控。

必要工作：

- 注入最近 3 至 5 条安全 timeline 和引用/mention 关系。
- 实现真实 wall-clock timeout，而不是只写 Context 字段。
- 支持 Markdown fence、前后说明和统一错误 envelope 的鲁棒 JSON 解析。
- judge 单独使用低温度；失败时按保守确定性规则降级。
- judge 后检查群聊是否已推进、问题是否已被回答，取消过时候选。

验收：`invalid_json` 低于 1%，明显两人互聊误插话率低于 2%，已经有人回答后的迟到回复率低于 2%。

#### D. 修复温度透传和错误可观测性

目标：`LLMRequest` 中的 temperature/max tokens 等调用参数真正到达自定义 Provider。

必要工作：

- adapter 显式转发 request temperature，并测试配置覆盖和请求级覆盖优先级。
- judge、抽取器、摘要器使用独立低温度；最终拟人化回复可保留适度随机性。
- 区分供应商错误、熔断拒绝、JSON 失败、工具失败和最终回复失败，不再只汇总为“Agent error”。

### 10.2 P1：把上下文从布尔开关升级为分层策略

已有 `plans/20260714_微信群上下文分层与滚动摘要优化.md` 的总体方向正确，建议按以下顺序实施：

1. `current_only`：真正独立、无需历史的问题。
2. `recent`：省略句、短追问、普通自由接话；读取少量统一 timeline。
3. `contextual`：引用、图片、“刚才/继续/什么意思”；加入滚动摘要和相关焦点。
4. `recall`：总结、查证、谁说过、历史约定；再启用归档证据。

同时将 Agent history 明确分为：

- `fresh`：独立 direct reply。
- `interactive_session`：明确继续机器人上一轮。
- `observe_only`：普通自由回复不恢复旧 Agent 对话，但保留审计和进化观察。

需要补入现有计划、但此前未充分覆盖的事项：

- stable identity 迁移必须先于记忆优化。
- judge JSON 失败率和温度透传必须作为验收指标。
- Provider 熔断和错误率必须进入真实群验收。

### 10.3 P1：让 style 从候选变成受控闭环

建议提供两种安全路径：

- 管理员审核 candidate 后启用。
- 达到证据数、跨时间重复和安全过滤阈值后自动启用，并允许一键停用。

不要直接把 89 条候选全部激活；先去重、合并同义表达，并排除一次性玩笑、攻击性内容和个人隐私。

### 10.4 P1：增加小型、受控的高频意图路由

首批只覆盖最明确且已有底层能力的意图：

- 群聊总结。
- 当前/引用图片理解。
- 视频理解。
- 生图。
- 已存图片/网络图片/表情包。

路由只负责分类、参数提取和选择既有服务；最终文本回复仍回到 CowAgent 统一 Bridge/Agent 或确定性 formatter，不在微信群通道重建第二套 Agent。

### 10.5 P2：精简工具、prompt 和记忆质量

- 根据当前群聊意图只暴露相关工具，减少 schema 体积和误选。
- 对群记忆做去重、时效、来源归属、置信度和冲突处理。
- 清理 `<Mock ...>`、测试标记和其他生产归档污染，测试数据库与生产数据目录彻底隔离。
- 对 archive、rolling summary、recent 和 focus 设置明确互斥/优先级，避免同一事实重复注入。

## 11. 不建议直接照搬的做法

### 11.1 不要每轮无条件注入 100 条历史

建议保留 BaiLongmaPro 带来的连续性目标，但使用：

- 最近 8 至 20 条关系型 timeline 作为事实基线。
- 更早内容用有游标的滚动摘要压缩。
- 只有显式回溯才读取 90 天归档。
- 对短句做服务端 deterministic context policy，不依赖关键词穷举。

### 11.2 不要把全部群聊能力堆进单一渠道文件

前置路由应该是小型 registry/strategy，调用现有 Vision、图片生成、归档、记忆和 Agent 能力，避免形成另一个 `wechaty-duty-group.js`。

### 11.3 不要用更多自动记忆掩盖身份主键错误

在 stable join key 修复前继续抽取，只会制造更多无法召回或可能串 scope 的旧主键数据。

### 11.4 不要通过提高自由回复频率追求真人感

真人感来自“知道现在在聊什么、知道谁在对谁说、在合适时机说一句合适的话”，不是来自更高的插话次数。

## 12. 建议的评测与验收体系

修复后应使用同一模型、同一温度、同一批去标识化群聊片段做离线回放，再做真实群灰度。建议至少建立以下数据集：

| 类别 | 示例结构 | 核心指标 |
|---|---|---|
| 隐式承接 | 上文讨论 X，当前只说“那怎么办” | 上下文选择正确率 |
| 机器人上一句 | 机器人先回答，群友短追问 | assistant timeline 命中率 |
| 两人互聊 | A mention B，B 引用 A | 自由回复误插话率 |
| 已有人回答 | 问题后群友给出答案 | 迟到回复率 |
| 群记忆 | 当前群约定、成员偏好、别名 | stable scope 召回准确率 |
| 跨群隔离 | 两群有同名成员或相似话题 | 跨群泄露必须为 0 |
| 高频意图 | 总结、识图、视频、生图、找图 | 路由准确率、工具成功率 |
| JSON 协议 | judge、画像、摘要结构化输出 | 解析失败率 |
| 拟人化 | 短句、玩梗、认真问答混合 | 盲评自然度、冗长度 |
| 可靠性 | 429、503、断连、熔断 | 用户可见失败率、恢复时间 |

建议的首轮目标值：

- 上下文依赖场景选择正确率不低于 95%。
- judge 结构化解析失败率低于 1%。
- 两人互聊误插话率低于 2%。
- 跨群记忆/画像泄露为 0。
- stable 身份已确认样本的画像召回率不低于 95%。
- 已有人回答后的迟到自由回复率低于 2%。
- @ 必回链路在排除上游故障后的成功率不低于 99%。
- 回复自然度使用双盲人工对比，不用“回复次数”作为替代指标。

## 13. 推荐实施顺序

```text
stable identity 修复与数据迁移
  -> 统一 inbound + assistant room timeline
  -> judge 近场上下文、真实超时、低温 JSON
  -> temperature 透传与故障指标
  -> layered context / rolling summary / history mode
  -> style 审核与生效闭环
  -> 高频意图前置路由
  -> 动态工具与长期记忆质量治理
  -> 同模型离线回放 + 真实群灰度
```

前三项完成前，不建议继续增加新的“拟人化模块”。当前最大的收益来自让已有能力真正看到正确的人、正确的群和正确的最近对话。

## 14. 最终判断

你的感觉基本准确，但更精确的说法是：

> BaiLongmaPro 当前更像一个“长期待在群里、每次开口前都翻一遍群记录、遇到常见任务直接走熟练流程”的机器人；CowAgent 当前更像一个“能力模块和安全规则很多，但经常只收到一句截断问题，长期记忆的钥匙又换了锁，最后还用偏高随机性临场判断”的通用 Agent。

CowAgent 的上限并不低，甚至在 stable scope、安全门禁、渠道边界和数据清洗方面更适合长期演进。当前差距主要是**集成闭环和运行策略差距**，不是需要更换大模型或推倒架构。按 P0 顺序修复后，最先改善的应当是：

1. 能接住省略句和机器人上一句。
2. 能真正认出当前群和当前成员。
3. 自由回复不再随机沉默或乱插话。
4. 同一意图更稳定地选择正确能力。
5. 供应商错误和结构化输出失败不再伪装成“理解能力差”。

## 15. 关键代码索引

### CowAgent

- 历史门控与上下文装配：`channel/wechat_group/wechat_group_humanized_context.py:72`、`:235`
- 共享 session 缺省行为：`channel/chat_channel.py:85`
- 自由回复 judge 输入与解析：`channel/wechat_group/wechat_group_free_reply_judge.py:20`、`:53`、`:108`
- 自由回复 worker 调用：`channel/wechat_group/wechat_group_free_reply_worker.py:198`
- 画像 runtime/stable ID 错位：`channel/wechat_group/wechat_group_profile_llm_extractor.py:86`、`channel/wechat_group/wechat_group_profile_evolution_executor.py:167`
- 风格仅读取 active：`channel/wechat_group/wechat_group_style_service.py:24`
- 默认加载工具：`bridge/agent_bridge.py:706`
- temperature 请求与 adapter：`agent/protocol/agent_stream.py:1098`、`bridge/agent_bridge.py:401`
- 原文持久化清洗：`bridge/agent_bridge.py:1344`
- 现有分层上下文计划：`plans/20260714_微信群上下文分层与滚动摘要优化.md`

### BaiLongmaPro

- 固定厚上下文：`src/social/wechat-groups.js:187-193`、`:369-374`
- 高频意图前置路由：`src/social/wechaty-duty-group.js:2697-2739`
- 群记忆混合召回：`src/social/wechat-group-memory.js:677-749`
- ambient 读取近场上下文：`src/social/wechat-ambient-reply.js:284-323`
- focus/state 更新：`src/core/turn.js:123-191`
- 群 worker 与主循环：`src/core/loop.js:234`
- 温度默认值与调用：`src/config.js:420`、`src/core/turn.js:440`
