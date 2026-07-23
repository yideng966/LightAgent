# LightAgent 项目协作指南

本文件面向在本仓库内工作的 AI Agent 与开发者。目标是先理解项目边界，再用最小改动完成需求，并保留可验证、可回退的交付路径。

## 项目概览

LightAgent 是一个以 Python 为主的多渠道 Agent Harness 项目，包含：

- 后端运行入口：`app.py`
- 配置中心：`config.py`、`config-template.json`
- 消息渠道层：`channel/`
- 模型、语音、翻译路由：`bridge/`、`models/`、`voice/`、`translate/`
- Agent 核心协议、工具、技能、记忆、知识库：`agent/`
- 插件系统：`plugins/`
- CLI：`cli/`
- Electron + Vite + React 桌面端：`desktop/`
- 文档站内容：`docs/`
- 回归测试：`tests/`

项目核心数据流：

1. `app.py` 加载配置并启动 `ChannelManager`。
2. `channel/channel_factory.py` 根据 `channel_type` 创建 Web、IM 或终端渠道。
3. 渠道把消息包装为 `bridge.context.Context`。
4. `bridge/bridge.py` 根据配置选择聊天模型、语音、翻译或 Agent 模式。
5. Agent 模式通过 `bridge/agent_bridge.py` 进入 `agent/`，按工具、技能、记忆与知识库上下文执行任务。
6. 回复通过原渠道发送回用户。

## 主要目录职责

- `agent/protocol/`：Agent 执行协议、流式执行、动作与结果模型。
- `agent/tools/`：内置工具实现。新增工具时优先继承 `BaseTool`，并确认 `agent/tools/__init__.py` 与 `ToolManager` 加载路径。
- `agent/tools/mcp/`：MCP 客户端与动态工具注册。修改时注意并发加载、热更新和子进程生命周期。
- `agent/skills/`：技能加载、过滤、启停配置与 prompt 格式化。内置技能在根目录 `skills/`，用户技能通常在 workspace 的 `skills/`。
- `agent/memory/`、`agent/knowledge/`：长期记忆、向量/关键词索引、知识库服务。
- `bridge/`：模型、语音、翻译、Agent 模式的统一路由层。改动这里会影响所有渠道。
- `channel/`：不同平台渠道。公共逻辑在 `channel/channel.py`、`channel/chat_channel.py`；新增渠道需接入 `channel/channel_factory.py`。
- `channel/wechat_group/`：个人微信群通道实现。Python 层负责 LightAgent 渠道适配、配置读取、上下文包装和回复发送；`sidecar/` 下的 Node.js Wechaty 进程负责扫码登录、群列表、群消息事件和微信侧真实发送。
- `models/`：不同 LLM Provider 的 Bot 与 Session。新增 Provider 要同步 `common/const.py`、`models/bot_factory.py` 和相关配置/文档。
- `plugins/`：聊天命令插件与插件管理器。不要把 Agent 工具和插件混为一类。
- `voice/`、`translate/`：ASR/TTS 与翻译 Provider。
- `desktop/`：Electron 主进程、React 渲染端和桌面打包配置。桌面后端默认由 `desktop/src/main/python-manager.ts` 管理。
- `docs/`：英文、中文、日文文档。涉及用户可见能力变更时，优先补充对应文档。
- `tests/`：`unittest` 风格回归测试，很多测试通过 stub/mocking 避免真实网络和外部服务。

## 本地运行与验证

默认在 Windows PowerShell 中工作。不要使用 `&&` 串联命令。

访问 GitHub 时如果直连请求超时或不稳定，可以使用本地代理 `http://192.168.3.5:1082` 重试；仅在网络访问场景使用该代理，不要把代理地址写入项目运行配置或代码默认值。

整理或创建 GitHub issue 时，一律提交到 `yideng966/LightAgent` 项目；标题和正文描述应使用简体中文，避免默认写英文；提交时必须注明合适的 label，至少明确是 `bug`、功能需求、文档或其他类型；不要默认使用当前 remote、fork 或其他仓库。

后端依赖：

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-optional.txt
python -m pip install -e .
```

启动后端：

```powershell
python app.py
```

或安装 CLI 后：

```powershell
lightagent start
lightagent status
lightagent logs
```

运行全部 Python 测试：

```powershell
python -m unittest discover -s tests
```

运行单个测试文件：

```powershell
python -m unittest tests.test_models_handler
```

桌面端：

```powershell
Set-Location -LiteralPath .\desktop
npm install
npm run build
npm run dev
```

桌面端热开发：

```powershell
Set-Location -LiteralPath .\desktop
npm run dev:hot
```

## 修改原则

- 修改前先读当前文件，禁止凭记忆改代码。
- 遵守最小修改原则：只改让当前需求成立的必要文件。
- 不顺手重构无关代码；发现无关问题时在回复里单独说明。
- 用户要求修改 UI、页面、布局、交互或样式但未明确指定端时，默认只修改 Web 控制台（`channel/web/chat.html`、`channel/web/static/js/console.js`、`channel/web/static/css/console.css` 等）；不要同时修改桌面端 `desktop/`。只有用户明确要求“桌面端”“Electron”“桌面应用”或指定 `desktop/` 文件时，才修改桌面端 UI。
- 仅在新增或修改代码并提交/交付代码变更时，才同步更新根目录 `CHANGES.md`，记录本次修改日期、任务背景、关键改动文件和验证结果；纯文档、计划、规则、配置说明等非代码变更不更新 `CHANGES.md`。
- 提交 Git 代码变更时，必须将根目录 `AGENTS.md` 与 `CHANGES.md` 纳入同一次提交范围；提交前检查两者状态，确保规则说明与变更记录不会遗漏。
- 面向本项目的开发计划、迁移计划、实施方案和阶段性任务文档必须使用简体中文编写；如需引用英文 API、命令、路径或错误信息，保留原文即可。
- `plans/` 目录下的计划文件名称必须使用 `YYYYMMDD_中文名.md` 格式，文件名主体使用简体中文描述任务，不再使用英文任务名。
- 跟进开发计划文档进行开发时，开发完成后必须回写对应开发计划文档，更新已完成进度、实际改动、验证结果与剩余事项，确保计划状态与代码交付一致。
- 优先沿用现有工厂、单例、配置读取和日志模式。
- 不要把真实密钥、token、cookie、部署 ID 写入仓库。
- 修改跨渠道逻辑时，评估 Web、IM、CLI、桌面端是否都会受影响。
- 修改 `config.py` 默认配置时，同步检查 `config-template.json`、Web 设置页、文档和相关测试。
- 修改模型路由时，同步检查 `Bridge`、`models/bot_factory.py`、`common/const.py`、Web 模型管理接口和测试。
- 修改语音路由时，同步检查 `voice/factory.py`、`Bridge`、Web ASR/TTS 能力接口、控制台选择器和语音测试；`custom:<id>` 必须按显式能力复用对应自定义 Provider 的 Key/Base，不能隐式回退到当前聊天 Provider。
- 修改 Agent 工具时，同步检查工具注册、工具 schema、异常返回格式、文档和安全测试。
- 修改桌面后端启动逻辑时，特别注意端口、数据目录、打包后路径和 Windows 行为。

## 安全边界

本项目直接触达文件系统、Shell、浏览器、网络、MCP 子进程和外部消息平台，安全改动必须保守。

- `agent/tools/web_fetch/`、`agent/tools/browser/`、`agent/tools/bash/`、`agent/tools/read/`、`agent/tools/write/`、`agent/tools/edit/` 是高风险区域。
- SSRF、路径穿越、任意命令执行、任意文件读写、重定向到内网地址等问题必须有测试覆盖。
- 已有安全回归测试包括 `test_security_ssrf_web_fetch.py`、`test_security_ssrf_path_traversal.py`、`test_security_ssrf_browser_navigate.py`。
- 不要默认放宽 URL、文件路径、命令执行或 Web 文件服务根目录限制。
- `web_file_serve_root`、`agent_workspace`、`mcp_servers`、`mcpServers` 等配置可能扩大访问面，改动时要明确风险。

## 编码与风格

- Python 代码保持现有风格，优先小函数、明确异常处理和 `common.log.logger` 日志。
- 仓库贡献规范要求 issue、PR 和代码注释尽量使用英文；新增代码注释也应优先英文。Git 提交说明（commit message）必须使用简体中文，清晰概括本次变更。
- 用户对话可以使用中文，但写入项目代码和面向国际社区的文档时遵循仓库既有语言策略。
- 避免引入新的全局依赖；确需新增依赖时，同步更新 `requirements.txt`、`requirements-optional.txt` 或 `desktop/package.json`，并说明原因。
- README 或文档中如出现编码异常，先确认文件实际编码，不要盲目整体重写。

## 常见开发路径

新增或修改渠道：

1. 查看 `channel/channel.py`、`channel/chat_channel.py` 和相邻渠道实现。
2. 修改具体 `channel/<name>/`。
3. 必要时更新 `channel/channel_factory.py`、`common/const.py`、配置模板和文档。
4. 用 mock/stub 覆盖消息解析、鉴权、回复发送和异常路径。

修改个人微信群通道：

定位与开发范围：

- 个人微信群在 LightAgent 中只定位为一个消息渠道，不是一套独立 Agent、独立机器人产品或社交工作台。
- Wechaty 侧车只负责微信登录、群列表、群消息监听、微信侧收发、媒体下载/发送和 Wechaty 运行细节；不要把 LightAgent 的模型调用、工具调用、记忆检索或 Agent 执行逻辑搬到侧车里。
- Python 微信群通道只负责侧车进程管理、消息去重、自发消息过滤、`ChatMessage` / `Context` 转换、群白名单、触发规则、上下文增强、回复目标锁定和发送适配。
- 文本回复、Agent、工具、插件、模型路由、图像理解、图像生成、语音识别、语音合成、长期记忆、知识库和上下文压缩必须优先复用 LightAgent 既有 `ChatChannel`、`Bridge`、`agent/`、`plugins/`、`voice/`、`agent/memory` 和 `agent/knowledge` 链路。
- 不要在 `channel/wechat_group/` 内重写独立模型调用、独立工具执行器、独立 Agent loop、独立长期记忆系统或绕过 `Bridge.fetch_agent_reply()` 的回复链路；确需新增适配层时，应只做微信群作用域校验、提示词装配或协议转换。
- 微信群专属能力应作为当前用户消息的上下文增强进入既有主链路，例如 `<wechat-group-persona>`、`<recent-wechat-group-transcript>`、`<wechat-group-focus>`、`<wechat-group-memory>`；这些块不能替代 LightAgent 通用系统提示词、技能、工具 schema、知识库规则或 Agent 会话历史。
- 新增微信群多模态能力时，优先映射到现有 `ContextType`、`ReplyType` 和渠道回复机制；只有现有抽象无法表达微信侧协议细节时，才在微信群通道内补充最小适配。
- 群永久记忆和群友画像必须进入 LightAgent 统一作用域记忆体系，通过 `WechatGroupMemoryService` 或等价适配层携带 `room_id` / `sender_id` 强过滤后召回；不允许另建绕过通用记忆管理的长期记忆孤岛。
- 默认开发范围聚焦稳定渠道闭环：扫码登录、群列表、目标群选择、@ 触发、真实发送人身份、回复回原群并真实 mention、最近群上下文、群记忆隔离、多模态基础映射、安全守卫和最小运维 UI。
- 未经单独计划确认，不在个人微信群通道内扩展完整社交工作台、战报、图库、备份迁移中心、跨群身份合并、复杂人设市场、群友在线改人设、完全无人值守自动记忆系统或与渠道职责无关的大型业务 UI。
- 如果后续需求会扩大个人微信群职责边界，必须先更新对应计划文档和本节规则，再按最小可验证步骤实施，并补充防止能力分叉、跨群泄露和绕过主链路的回归测试。
- 微信群管理员权限必须按 `stable_room_id + stable_member_id` 精确生效；旧 `room_id + sender_id` 仅作为 runtime legacy 快照兼容，不要把某个成员在一个群的管理员身份扩展到其他群。
- `wechat_group_admin_members` 是新 UI 和新逻辑的主配置；`wechat_group_admin_sender_ids` 仅作为旧配置兼容 fallback，不作为新功能默认写入目标。
- 普通群成员可以问答、查询、总结和读取上下文，但不能触发知识库写入、永久记忆写入、群记忆写入、群友画像写入、自主进化、workspace 文件写入/编辑、定时任务修改或微信群配置修改。
- 管理员门禁必须同时包含通道层拒绝、Agent 工具过滤和 Prompt 权限提示；不能只依赖模型自觉遵守提示词。
- 微信群稳定身份改造后，`wechat_group_room_id` / `wechat_group_sender_id` 继续表示当前 Wechaty 登录态 runtime ID；长期配置、权限、会话、归档、记忆、画像、焦点、情绪、风格、表情和 scheduler 必须优先使用显式 stable 字段。
- 身份恢复必须按 stable account -> stable room -> stable member 的顺序确认；未确认 account 不得确认 room，未确认 member 不得写入管理员 stable 配置或继承敏感权限。
- legacy runtime room/member 如果在多个 stable account 下产生歧义，必须返回未解析并要求人工确认，不得按最近记录任取；在线成员解析应优先使用当前运行中 room 的 stable 映射。
- 通道层管理员硬门禁、humanized 降级上下文、生图额度和 scheduler 会话都必须使用 stable scope；runtime 字段只用于微信真实发送和 legacy 快照。
- 群画像自主进化调用 LLM 时必须先识别模型错误 envelope（如 `{"error": true, "status_code": 503}`），HTTP 408/429/5xx 等临时供应商故障不得继续当作画像 JSON 正文解析；失败记录应保留可读 HTTP 状态且不推进归档游标。
- GitHub 提交通知属于 Webhook 到微信群的固定消息投递适配：配置 UI 放在「群聊 -> 基础设置」，目标群只能使用已选择的 `wechat_group_stable_room_ids`；Webhook 必须先做 HMAC-SHA256 验签和 delivery 去重，配置 API 不得回显真实 Secret，`LIGHTAGENT_GITHUB_WEBHOOK_SECRET` 存在时优先于本地配置。

1. 优先查看 `channel/wechat_group/wechat_group_channel.py`、`wechat_group_client.py`、`wechat_group_message.py`、`protocol.py` 和 `channel/wechat_group/sidecar/wechaty-sidecar.mjs`。
2. 扫码入口必须在通道管理中完成：`通道管理 -> 接入通道 -> 个人微信群`，由界面展示二维码；不要把“看日志扫码”作为主要交互路径。
3. Web 控制台入口涉及 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`；桌面端入口涉及 `desktop/src/renderer/src/pages/ChannelsPage.tsx`、`components/QrLoginModal.tsx`、`api/client.ts` 和 `i18n.ts`。
4. 微信群回复 @ 用户时，正文不要手工拼接普通文本 `@昵称` 或 `@@id`；应将发送者 ID 作为 `mention_ids` 传给 sidecar，并由 Wechaty `room.say(text, ...mentions)` 执行真实 mention。
5. sidecar 与 Python 之间只通过 JSON Lines 协议通信。新增事件或命令时，先更新 `protocol.py`，再同步 Python client、channel 和 `wechaty-sidecar.mjs`，并补充对应测试。
6. Wechaty 登录态、媒体目录等运行数据必须放在仓库外的数据目录，不能写入 Git 跟踪内容；新增 npm 依赖时同步检查 `channel/wechat_group/sidecar/package.json` 与 lock 文件。
7. 涉及群选择时优先使用 `wechat_group_stable_room_ids` 做精确限制；`wechat_group_room_ids` 只保留为 runtime legacy 快照；`group_name_white_list: ["ALL_GROUP"]` 只适合开发测试，不应作为长期生产默认。
8. 修改后至少运行 `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`。涉及桌面二维码、连接状态或通道页时，还要在 `desktop` 目录运行 `npm run build`。
9. 外部真实链路仍需手动验证：启动后打开通道管理，选择“个人微信群”，扫码登录，在目标群 @ 机器人确认能收到回复，并确认回复真实 @ 到发送者。

### 个人微信群 LLM 请求上下文链路

当前个人微信群通道不是替代 LightAgent 原有 Agent 主链路，而是在通用 `ChatChannel` 上下文构造之后叠加微信群专属上下文，再进入 `Channel.build_reply_content()` 和 `Bridge.fetch_agent_reply()`。

当前链路分为两层：第一层是 `Context` 元数据，用于服务端路由、权限和持久化判断；第二层是追加到当轮 `context.content` 前面的 prompt 块，用于让 LLM 理解微信群现场。两层都只服务当前请求，不能把微信群通道扩展成独立 Agent。

核心路径：

1. `WechatGroupChannel.handle_text()` 把 sidecar 消息包装为 `Context`。
2. `WechatGroupChannel._compose_context()` 先调用 `super()._compose_context()`，继续执行原 `ChatChannel` 群白名单、触发词、@ 去除、`session_id`、`receiver` 和插件事件逻辑。每个 `Context` 实例必须有独立 `kwargs`，不能复用可变默认字典，避免调度任务、自由回复等标记污染后续消息。
3. 微信群通道随后写入服务端元数据，例如 `wechat_group_room_id`、`wechat_group_sender_id`、`wechat_group_bot_sender_id`、`wechat_group_user_content`、`wechat_group_trigger_source`、`wechat_group_is_free_reply` 和 `intent_requires_scheduler`。其中 `wechat_group_user_content` 必须保存用户原文，用于后续原文持久化。
4. `_record_inbound_message()` 先把本轮消息写入归档；随后 `WechatGroupHumanizedContextBuilder` 构造 prompt 时必须用 `exclude_message_id` 排除本轮消息，避免把用户刚问的问题当成证据。
5. 微信群通道通过 `WechatGroupHumanizedContextBuilder` 在 `context.content` 前追加微信群专属上下文，包括 `<wechat-group-admin-policy>`、`<wechat-group-mention-verification>`、`<wechat-group-reply-policy>`、`<wechat-group-persona>`、`<wechat-group-archive-evidence>`、`<local-extractive-summary>`、`<recent-wechat-group-transcript>`、`<wechat-group-focus>`、`<wechat-group-memory>`、`<wechat-group-style>`、`<wechat-group-emotion>`、`<wechat-group-reference-policy>` 与 `<wechat-group-multimodal>`。
6. Builder 会把注入结果回填到 `context` 元数据，例如 `wechat_group_contextual_history`、`wechat_group_archive_evidence_injected`、`wechat_group_recent_context_injected`、`wechat_group_memory_injected`、`wechat_group_multimodal_diagnostics` 和 `wechat_group_multimodal_matched_images`，供发送、诊断和测试使用。
7. `ChatChannel._generate_reply()` 调用 `super().build_reply_content(context.content, context)`。
8. 当 `agent` 配置为 `true` 时，`Channel.build_reply_content()` 进入 `Bridge.fetch_agent_reply()`，由 Agent 模式请求 LLM。
9. `AgentBridge` 默认使用 `wechat_group_user_content` 预持久化用户原文；Agent 运行结束后再把 `agent.messages` 与 `_last_run_new_messages` 中的当轮增强文本替换回原文，防止 `<wechat-group-*>` 块进入下一轮会话历史。

按意图注入历史的规则：

- `should_include_contextual_history()` 是归档证据、本地摘要和普通 recent transcript 的主要门控。`free_reply`、`quote_self`、`image_message` 默认需要历史；文本中出现“刚才、上面、之前、谁说、总结、继续、引用、图片、照片、这张、链接、啥意思、什么意思”等上下文依赖表达时也需要历史。
- 独立 direct reply 或 standalone @ 默认不注入大段旧聊天；它仍可以注入管理员策略、触发/回复策略、人设、群记忆、风格、情绪、引用策略和多模态块，但不得为了“补上下文”自动塞入大量 recent transcript。
- `<recent-wechat-group-transcript>` 优先使用焦点栈命中的消息；没有焦点消息时，只有上下文依赖场景才从当前 `room_id` 归档按 `wechat_group_recent_context_limit` 与 `wechat_group_recent_context_minutes` 拉取最近消息。
- `<wechat-group-archive-evidence>` 和 `<local-extractive-summary>` 只在上下文依赖场景注入，并且必须先按当前 `room_id` 过滤，再排除当前 `message_id`。
- 如果 `wechat_group_humanized_context_enabled = false` 或 builder 异常，通道会降级到旧的轻量拼装路径；该降级只用于运行时兜底，不是新的目标链路。

因此 LLM 最终看到的是“通用 Agent 系统上下文 + Agent 会话历史 + 微信群增强后的当前用户消息”：

```text
system:
  Agent 工具、技能、记忆规则、知识库规则、工作空间说明、
  AGENT.md / USER.md / RULE.md / MEMORY.md、运行时信息等。

messages:
  同一 session_id 下恢复的历史 user / assistant / tool 消息。

 current user message:
  <wechat-group-admin-policy>
  当前群的管理员权限规则。说明普通成员不能写入知识库、永久记忆、群画像、workspace、定时任务或微信群配置；
  管理员判断必须按 stable_room_id + stable_member_id 精确生效，runtime room_id / sender_id 只用于发送和 legacy 兼容。
  </wechat-group-admin-policy>

  <wechat-group-mention-verification>
  当前触发来源、是否 @ 机器人、是否引用机器人回复；只用于约束回复路由，不应外显。
  </wechat-group-mention-verification>

  <wechat-group-reply-policy>
  当前轮回复策略。区分 direct reply、quote self、free reply 和 image message，约束是否短句接话、是否默认 mention、是否直接承接问题。
  </wechat-group-reply-policy>

  <wechat-group-persona>
  当前微信群人设。来自 wechat_group_persona_prompt；
  为空时使用 wechat_group_persona_preset_id 对应的默认人设。
  </wechat-group-persona>

  <wechat-group-archive-evidence>
  当前 room_id 归档中按时间窗口和关键词检索出的证据；必须排除本轮消息，且不得暴露 message_id、media_path、本机路径、XML 或 base64。
  </wechat-group-archive-evidence>

  <local-extractive-summary>
  当前 room_id 短窗口内的本地抽取式摘要候选；只用于帮助模型组织总结，不替代长期记忆。
  </local-extractive-summary>

  <recent-wechat-group-transcript>
  当前 room_id 最近群聊归档，默认窗口 1440 分钟、最多 100 条。
  standalone @ 默认不注入；上下文依赖、引用、自由回复、图片/文件理解等请求才按需注入。
  </recent-wechat-group-transcript>

  <wechat-group-focus>
  当前 room_id 的运行时焦点栈摘要。焦点栈替代旧话题追踪，只影响个人微信群通道。
  standalone @ 默认不注入旧焦点消息；总结刚才、上面、继续、引用和图片理解等上下文依赖请求才会召回当前群相关焦点消息。
  </wechat-group-focus>

  <wechat-group-memory>
  [group_memory]
  当前 room_id 的群永久记忆，例如群规、长期项目、群偏好、群内约定。

  [speaker_profile sender_id="..."]
  本次发言人在当前 room_id 下的一份当前生效群友画像。

  [mentioned_profile sender_id="..."]
  本次发言中被 @ 的群友在当前 room_id 下的一份当前生效群友画像。
  可有多份；首轮只注入本轮明确 @ 到的成员画像。
  </wechat-group-memory>

  <wechat-group-reference-policy>
  引用、图片和链接回复策略。引用优先于全群最近图片；链接未被工具读取前不得编造网页内容。
  </wechat-group-reference-policy>

  <wechat-group-style>
  当前群近期形成的表达风格和语气偏好。只影响回复风格，不替代事实、权限或记忆。
  </wechat-group-style>

  <wechat-group-emotion>
  当前群运行时情绪状态，例如 valence、energy、sociability 和最近回复节奏。只用于调节语气和接话倾向。
  </wechat-group-emotion>

  <wechat-group-multimodal>
  当前图片、引用图片、视频、转发或链接等多模态上下文摘要。真实 media_path 只传给 Vision 或相关服务，不写入 prompt。
  </wechat-group-multimodal>

  用户本次去掉开头 @ 后的真实问题
```

增强块只进入当前轮 LLM 请求。默认配置 `wechat_group_context_persist_raw_user_only = true` 时，`AgentBridge` 会在预持久化和本轮运行后的 Agent 内存中只保留用户原文，避免上一轮 `<wechat-group-*>` 块污染下一轮历史；关闭该配置可临时回退为旧持久化行为。这里的“用户原文”指 `_compose_context()` 增强前写入 `context["wechat_group_user_content"]` 的文本，通常是去掉开头 @ 后的真实问题。

4.3 群永久记忆与群友画像的注入规则：

- 当前群记忆按 `scope_type = wechat_group`、`scope_id = room_id`、`channel_type = wechat_group` 召回，只允许进入当前群回复。
- 当前发言人的群友画像按 `scope_type = wechat_group_member_profile`、`scope_id = room_id`、`subject_id = sender_id`、`channel_type = wechat_group` 召回。
- 本次发言被 @ 的群友画像从 `at_list` 中排除机器人自身和当前发言人后召回；首轮只处理明确 @ 到的成员，不把普通文本昵称匹配作为强需求。
- 群友画像 prompt 中的 `reply_name`、`primary_nickname` 和 `aliases` 必须优先使用当前 `room_id` 的群昵称或当前群 name record；不得把其他群学到的别名回退注入当前群回复。
- `wechat_group_profile_get` 等 Agent 画像工具必须由服务端绑定当前 `room_id`；查询、精确读取和列表模式都只能返回当前群画像，不能接受模型传入的跨群 room 参数。
- 群友画像不是多条零散记忆拼接；每个 `stable_room_id + stable_member_id` 最多注入一份当前生效画像，历史版本和来源只用于审计。
- 所有群记忆和画像召回必须先按 `stable_room_id` 或 `stable_room_id + stable_member_id` 强过滤，再排序；legacy runtime 字段只能用于兼容回查，不允许跨群泄露。
- LightAgent 全局 shared memory 仍属于通用 Agent 记忆能力，不放进 `<wechat-group-memory>`；全局 shared memory 只能作为通用背景，不能反向泄露其他群信息。

焦点栈维护约束：

- `wechat_group_topic_*` 话题追踪已废弃，旧 `wechat_group_topic_threads`、`wechat_group_topic_message_refs`、`wechat_group_topic_summary_history` 数据不迁移、不保留。
- 焦点栈只按 `room_id` 生效；即使 `group_shared_session = true`，不同微信群也不能共享焦点栈或焦点消息引用。
- `<wechat-group-focus>` 不替代 Agent 会话恢复、记忆注入、知识库或其他渠道上下文，只控制个人微信群 recent transcript 的焦点选择。
- standalone @ 或普通独立触发不得为了“补上下文”自动注入旧焦点消息；只有显式上下文依赖、引用、图片/文件理解等场景才允许召回当前群焦点消息。

通用 LightAgent 能力仍然生效：

- `MEMORY.md` 会作为工作空间上下文自动加载；每日记忆和完整记忆按需通过 `memory_search` / `memory_get` 工具检索。
- `knowledge` 开启时，知识库规则和 `knowledge/index.md` 会进入系统提示词；具体知识页按需通过 `read` 或 `memory_search` 查询。
- 技能、工具 schema、运行时信息和上下文压缩逻辑仍由 Agent 主链路处理。
- 自主进化仍会记录微信群用户轮次并参与 idle evolution；群聊场景通常不设置主动推送 `receiver`，避免进化结果主动打扰群。

### 个人微信群自由回复与情绪主动性链路

微信群自由回复和“情绪与主动性”不是两套互相竞争的回复引擎，而是串联关系：

- 自由回复负责判断普通非 @ 群消息“要不要接话”。默认配置 `wechat_group_free_reply_enabled = false`，只有开启后且当前群命中 `wechat_group_free_reply_stable_room_ids`（或迁移期 legacy runtime 快照）时，普通非 @ 文本才会进入自由回复判定；`wechat_group_free_reply_names` 只用于发现待确认候选，不得直接放行自由回复。
- 任意群成员真实 @ 机器人且去除机器人 @ 前缀后文本精确等于“闭嘴”时，通道必须静默消费命令，并按当前 stable room 暂停普通自由回复；稳定群不可用时才回退 runtime room。禁言时长读取 `wechat_group_free_reply_mute_minutes`（默认 10 分钟，范围 1–1440）；`wechat_group_free_reply_mute_mentions_enabled` 默认关闭，开启后禁言有效期内的新 @ 消息也必须静默忽略，但引用和拍一拍不受影响。命令识别必须先于 @ 禁言门禁，本地评分和 worker 最终放行处也必须检查禁言状态，确保重复命令可续期并避免已排队候选延迟发言。
- 情绪与主动性负责维护当前群的运行时情绪状态，并影响自由回复概率、回复节奏和最终 LLM 上下文。默认配置 `wechat_group_emotion_enabled = true`；它本身不会独立发起群消息，也不绕过自由回复或 @ 必回链路。
- 普通非 @ 文本先经过 `evaluate_wechat_group_free_reply()` 本地评分、群范围、冷却、小时上限、连续上限、低信息和风险抑制；本地通过后进入 `WechatGroupFreeReplyWorkerPool`，再由 `WechatGroupFreeReplyJudge` 做轻量 LLM JSON 二次判定。
- 自由回复 worker 必须按 `room_id` 做短暂防抖和 pending 合并；同一群窗口内只把最新普通候选送入 LLM judge，不同群互不影响。不要在候选入队时提前写入已回复冷却，冷却应在 worker 判定通过并进入回复上下文后记录。
- worker 判定通过后，通道用 `wechat_group_force_reply = true` 重新走 `_compose_context()` / `produce()`，绕过通用群聊“必须 @ / 前缀 / 关键词”的过滤，但最终回复仍复用 `ChatChannel`、`Bridge` 和 Agent 主链路。
- 默认生图触发词必须保守；不要使用 `看`、`找` 这类容易命中“看看”“找到”“找不到”等普通群聊文本的单字前缀，避免自由回复候选被误转成 `ContextType.IMAGE_CREATE`。
- 自由回复发送时设置 `suppress_mention = true` 和 `no_need_at = true`，因此默认不真实 mention 原发送者；@ 机器人或引用机器人回复仍走直接回复链路，不进入自由回复 worker。
- 模型判断当前消息并非在问机器人且无需接话时，相关内部判断只能表示静默，不能作为普通文本发到群里。发送层短文本兜底至少要覆盖“没/未 @ 我、不是在问我”与“不用/无需插嘴、接话、回复、回应”等组合，并保留正常长文本解释不会被误拦截的回归测试。
- 情绪服务在消息进入主链路前调用 `observe_message()` 更新 `valence / energy / sociability`；在自由回复本地判定后调用 `adjust_free_reply_decision()` 叠加低社交、低能量、负面情绪加阈值和时段规则等修正。
- 情绪状态会通过 `<wechat-group-emotion>` 块注入当前 user message，影响模型语气与接话状态感知；每次成功发送回复后调用 `mark_replied()` 记录回复次数并降低 energy，减少连续插话倾向。
- `wechat_group_free_reply_time_rules_enabled` 与 `wechat_group_free_reply_time_rules` 只作为自由回复调度的时段门控；规则不命中时会给自由回复判定增加 `time_rule_blocked` 抑制，不影响 @ 必回。
- `wechat_group_free_reply_typing_delay_enabled` 和 `wechat_group_free_reply_typing_chars_per_second` 当前在微信群文本发送路径统一生效，不只影响自由回复；如需限定为自由回复专属延迟，需要单独改造发送上下文判断。
- 两者的设计边界是“自由回复决定是否接话，情绪主动性只调节接话门槛、时段和上下文”。后续不要新增第二套独立主动发言调度器；若要扩大主动发言能力，必须先更新本节规则和对应计划文档，并补充防刷屏、跨群隔离和 @ 必回不受影响的回归测试。

### 个人微信群图片理解链路

微信群图片理解仍然是渠道适配能力，不是一套独立视觉模型链路。sidecar 只负责识别微信图片消息、下载媒体文件并上报 `message_type = image`、`file_path` / `media_path` 等事件字段；Python 通道负责把图片转换为当前消息的上下文增强，视觉理解必须复用既有 `agent.tools.vision.vision.Vision` 能力。

当前图片和引用、转发、视频等多模态信息进入 LLM 的统一形式是 `<wechat-group-multimodal>` 块。图片理解摘要由 `WechatGroupMultimodalContextService` 统一选择候选图片、调用 `Vision().execute({"image": image_path, "question": question})`、缓存摘要并格式化 prompt；真实 `media_path` 只传给 Vision，不写入 prompt、诊断状态或 recent transcript。该块作为当前 user message 的补充上下文进入既有 `ChatChannel` / `Bridge` / Agent 主链路，不绕过 `Bridge.fetch_agent_reply()`，也不在微信群通道内重复实现模型调用。

识图触发规则：

- 当群内直接发送图片并触发机器人回复时，`WechatGroupChannel` 只负责把本轮转换为文本回复上下文并进入 `_compose_context()`；当前图片由 `WechatGroupMultimodalContextService` 作为 `current_image` 优先生成视觉摘要并注入 `<wechat-group-multimodal>`。
- Wechaty 对图片或贴纸上报的 `message.text()` 可能是含 `aeskey`、`cdnthumburl`、`hevc_mid_size` 等字段的传输层 XML；该原文只允许用于协议处理和归档，不得作为 `context.content`、`wechat_group_user_content` 或 Agent 会话用户消息。图片当前轮用户内容必须使用显式语义文本，视觉事实只来自统一多模态摘要。
- 微信群表情包素材的 `description` 不得持久化传输层 XML、纯数字消息 ID 或长哈希文件名；无法同步生成语义时使用安全占位描述。历史素材批量生成语义必须复用现有 `Vision`，执行前备份 SQLite，逐条条件更新且失败项保持原值以支持续跑；GIF 应先转换为静态多帧联系图，避免兼容接口直接解析动画失败。
- `wechat_group_sticker_send` 成功后只发送表情包媒体；即使 Agent 最终文本包含文件名或占位说明，也不得作为 `text_content` 先发。该规则不影响普通图片或文件的显式图文回复。
- 上述边界同样适用于引用消息、recent transcript、焦点栈、画像 LLM 提取及贴纸 Agent 工具；即使媒体下载失败或既有数据库已保存污染内容，媒体消息也必须投影为语义占位符，不能回退注入原始 `text` 或 XML。历史归档可能把图片/贴纸 XML 误标为 `message_type = text`，模型边界不得只信任类型字段，还必须识别正文中的微信媒体传输载荷。
- 最近图片识别只处理文本消息，且必须直接触发机器人回复：`is_at = true` 或 `is_quote_self = true`。未 @ 机器人、未引用机器人回复的普通文本，不会直接进入最近图片识别链路，而是按自由回复或普通文本逻辑处理。
- 当用户发送文本类识图请求，例如“识别这张图”“看看这张图片”“图里有什么”“图片上是什么”“啥意思”“什么意思”“这是真的吗”，通道不会盲目下载文本消息文件；多模态服务会在当前群归档中选择目标图片，并只把 `message_id`、发送者、命中原因、时间和视觉摘要注入 `<wechat-group-multimodal>`。
- 文本识图意图当前由 `wechat_group_multimodal_context_service._looks_like_image_reference_question()` 判断；后续扩展意图词时应在该服务和对应测试中完成，不要在 `WechatGroupChannel` 中恢复独立判断。
- 直接图片没有附带文本时，是否自动评论由 `wechat_group_image_understanding_comment_enabled` 控制；总开关由 `wechat_group_image_understanding_enabled` 控制。
- 图片理解 prompt 来自 `wechat_group_image_understanding_prompt`，为空时使用默认简洁描述提示；相同 `image_path + question` 的结果由 `WechatGroupMultimodalContextService` 按 `wechat_group_image_understanding_cache_minutes` 做短期缓存。

文本识图请求的图片定位优先级：

1. 如果当前消息本身就是图片且已经决定回复，优先绑定当前图片，命中原因为 `current_image`。
2. 如果本条文本是回复引用消息，且 `quote.message_id` 存在，先按 `room_id + message_id` 精确查找归档图片；命中后只识别被引用的那张图片，命中原因为 `quoted_image`。
3. 如果引用消息 ID 查不到图片，再按引用发送者 `quote.sender_id` 或 `quote.sender_name` 在当前群最近 `wechat_group_multimodal_quote_sender_window_minutes` 分钟、最多 `wechat_group_multimodal_max_recent_messages` 条归档消息中倒序查找该发送者最近发过的图片。
4. 如果文本是图片指代问题，再在当前群短窗口中优先绑定同一发送者最近图片，命中原因为 `same_sender_recent_image`。
5. 如果短窗口内只有一张群内近图，可绑定该唯一近图，命中原因为 `unique_recent_image`。
6. 如果短窗口内多张图片且无法通过引用或同发送者规则消歧，必须不绑定，诊断原因为 `ambiguous_recent_images`。
7. 候选图片必须是当前群归档中的 `message_type = image`，且 `media_path` 非空；所有候选查找必须先按 `room_id` 过滤。

维护约束：

- 回复引用图片的优先级高于“最近图片”回退；后续修复识图问题时，不能把引用关系退化成全群最近图片匹配。
- 图片归档查找必须始终带 `room_id` 过滤，不能跨群复用图片或引用消息。
- `WechatGroupChannel` 不能重新引入 `_build_recent_image_understanding_content()`、`_build_image_understanding_content()`、`<wechat-group-image>` 或直接调用 `Vision()`；图片选择、摘要、缓存、路径脱敏和诊断必须统一在 `WechatGroupMultimodalContextService` 内完成。
- Vision 失败、空结果和异常信息不得把本机绝对路径写入 prompt、`diagnostics`、`matched_images` 或 Web 状态；`summary_generated` 只能表示真实成功摘要，不得把失败 fallback 文案标为成功。
- sidecar 遇到文本消息不能调用 `toFileBox()` 下载文件；只有图片等真实媒体消息才进入媒体下载逻辑，避免 `text message no file` 类错误。
- 新增图片类型、引用字段或 sidecar 事件字段时，需要同步更新 JSON Lines 协议、Python message/archive/channel 解析和对应测试。

当前实现边界：

- 当前微信群 `_compose_context()` 通过 `WechatGroupHumanizedContextBuilder` 统一装配当轮增强块；管理员策略、触发校验、回复策略、人设、归档证据、recent transcript、焦点、记忆、风格、情绪、引用策略和多模态都作为当前 user message 的前缀进入主链路。
- `<wechat-group-memory>` 必须通过 `WechatGroupContextService` 或等价适配层装配，统一从 LightAgent 作用域记忆读取已过滤结果，不允许在通道层绕过 `room_id` / `sender_id` 校验直接拼接原始记忆；旧 `<wechat-group-knowledge>` 仅作为内部兼容输入，不作为新 prompt 输出目标。
- 旧 `wechat_group_topics.db` 或旧 topic 表属于废弃数据；焦点栈初始化或首次使用时允许删除旧库或 drop 旧表，不提供历史话题恢复能力。
- Agent 模式默认不再把微信群增强后的 `context.content` 持久化为历史；`wechat_group_context_persist_raw_user_only = true` 时，预持久化和运行后内存清洗都使用 `context["wechat_group_user_content"]` 原文。只有显式关闭该配置时，才会回退为持久化增强后 `query` 的旧行为。
- 正文别名自动学习当前只允许在归档学习阶段处理“一个非机器人目标成员 + 一个非机器人显式 `@称呼` 文本”的高置信场景；不把普通文本昵称猜测、多目标映射或跨群自由匹配作为默认能力。
- 当前正文别名自动学习的内部逻辑如下：
  - 数据来源只看归档文本消息：`message_type = text`，且消息里必须同时具备有效 `sender_id`、正文 `text`，以及 `metadata.at_list`；机器人自身 ID 来自 `metadata.self_id`，机器人展示名来自 `metadata.self_display_name`。
  - 目标成员筛选先基于 `at_list` 做强约束：从 `at_list` 中排除当前发言人 `sender_id` 和机器人 `self_id` 后，必须只剩 1 个目标成员；如果剩余为 0 个或大于 1 个，整条消息直接放弃正文别名学习。
  - 正文称呼抽取只识别显式 mention 片段：使用 `@` / `＠` 起始的文本片段作为候选称呼，按现有正则规则截取连续非空白、非常见中文标点的内容，不从普通自然语言里猜测昵称。
  - 机器人 mention 会被二次排除：抽取出的显式称呼在归一化后若等于 `self_display_name`，视为机器人称呼，不计入候选；只有“非机器人显式称呼”最终也恰好只剩 1 个时，才继续学习。
  - 别名归一化会做最小清洗：统一空白、移除开头 `@`、裁掉两侧常见标点、限制最大长度，并拒绝原始 ID 形态（如 `wxid_*`、与 `sender_id` 相同的串、明显账号串）以及单个无意义符号。
  - 入库映射不做猜测：唯一保留的 runtime 目标成员必须先在当前 `stable_room_id` 内解析为 canonical `stable_member_id`，再与唯一显式称呼 alias 一一对应；不存在多目标 mention 与多个正文称呼之间的推断映射。
  - 画像更新只合并当前群 alias，不覆盖既有画像主体字段：`merge_learned_aliases()` 仅更新当前群观察时间，并在主昵称为空时才允许用 alias 兜底 `primary_nickname`；已有 `speak_style`、`interests`、`common_words`、分数统计保持不变。
  - alias 持久化统一写入 `wechat_group_member_profile_names`，主键作用域为 `stable_room_id + stable_member_id`，学习来源使用 `source_kind = learning`；不得写入 runtime sender 主键或其他群的名称记录。
  - 学习结果与发言人画像学习结果按 canonical `stable_member_id` 去重合并：同一轮 learner 既可能更新发言人自己的画像，也可能更新被 @ 成员的 alias；最终在当前群内合并成一份结果，避免重复计数同一画像。

新增或修改模型 Provider：

1. 查看相近 Provider 的 Bot 与 Session。
2. 在 `models/<provider>/` 实现最小必要适配。
3. 更新 `models/bot_factory.py`、`bridge/bridge.py` 的路由规则和 `config.py` 配置键。
4. 覆盖模型选择、参数持久化、错误返回和兼容模式测试。

新增或修改 Agent 工具：

1. 查看 `agent/tools/base_tool.py` 和现有工具实现。
2. 保持工具输入 schema、返回状态和错误文本稳定。
3. 更新 `agent/tools/__init__.py` 或相关动态加载配置。
4. 高风险工具必须补充安全回归测试。

新增或修改技能：

1. 内置技能放在根目录 `skills/<skill-name>/SKILL.md`。
2. 保持 frontmatter 元数据清晰，避免把大量业务逻辑塞进 prompt。
3. 如果提供脚本，放在技能目录下的 `scripts/`。
4. 可用 `skills/skill-creator/scripts/quick_validate.py` 做最小校验。

修改桌面端：

1. 主进程在 `desktop/src/main/`，渲染端在 `desktop/src/renderer/src/`。
2. 后端端口和启动流程集中在 `desktop/src/main/python-manager.ts`。
3. UI 状态优先沿用现有 Zustand store 和组件风格。
4. 修改后至少运行 `npm run build`。

## 前端 UI 开发规则

默认界面修改目标是 Web 控制台。除非用户明确指定桌面端，所有 UI 需求优先落在 `channel/web/chat.html`、`channel/web/static/js/console.js` 与 `channel/web/static/css/console.css`；桌面端规则仅在任务明确涉及 Electron / `desktop/` 时适用。

本项目桌面端当前技术栈是 Electron + Vite + React 18 + TypeScript + Tailwind CSS + Zustand + `lucide-react`。新增或修改 UI 时必须优先贴合现有实现，不要引入新的 UI 框架、组件库或设计系统，除非需求明确且已说明必要性。

### 结构与复用

- 渲染端代码位于 `desktop/src/renderer/src/`，按现有目录拆分：`pages/` 放页面、`components/` 放通用组件、`layout/` 放框架布局、`store/` 放 Zustand 状态、`api/` 放后端请求封装。
- 设置页能力优先复用 `desktop/src/renderer/src/pages/settings/primitives.tsx` 中的 `Card`、`Field`、`Dropdown`、`Toggle`、`TextInput`、`SaveRow`、`Modal`、`Btn`，不要为同类表单控件重复造一套样式。
- 渠道相关 UI 优先参考 `ChannelsPage.tsx` 的 `ChannelCard`、`ChannelDropdown`、`QrLoginModal` 交互模式；模型/配置类 UI 优先参考 `SettingsPage.tsx`、`BasicSettings.tsx`、`ModelsTab.tsx`。
- 图标优先使用 `lucide-react`，只有项目已有自定义图标如 `components/icons.tsx` 不足时才新增；不要使用 emoji 作为结构性图标或按钮图标。
- 文案必须走现有 `i18n.ts` 的 `t()` / `localizedLabel()` 体系；新增可见文案要同步补充中英文键值，避免硬编码在组件里。

### 视觉与主题

- 必须使用 `index.css` 中已有语义 token 和 Tailwind 语义类，例如 `bg-base`、`bg-surface`、`bg-surface-2`、`bg-elevated`、`bg-inset`、`text-content`、`text-content-secondary`、`text-content-tertiary`、`border-default`、`border-strong`、`bg-accent`、`text-accent`。
- 不要在组件里随意新增硬编码颜色；确需新增颜色时，优先在 `index.css` 中定义语义变量，并同时考虑 `.dark` 主题。
- 保持当前克制、工具型、信息密度适中的桌面应用风格。设置页和运维面板应使用清晰表单、状态徽标、列表/表格和少量卡片，不做营销式 hero、大面积插画、装饰性渐变或复杂动效。
- 圆角、间距和层级沿用现有约定：`rounded-btn`、`rounded-card`、`border-default`、`shadow-lg`、`px-6`、`py-5`、`space-y-*` 等。不要在同一页面混用一套新的圆角/阴影体系。
- 组件必须同时适配浅色和深色主题；不能只在当前主题下看起来正常。

### 布局与交互

- 桌面端页面优先采用现有框架：外层 `flex-1`、`min-h-0`、必要区域 `overflow-y-auto`，内容宽度通常控制在 `max-w-3xl` 或与相邻页面一致。
- 表单字段必须有可见 label，不要只靠 placeholder 表达含义；复杂字段应提供短 hint。
- 按钮、开关、下拉、图标按钮必须有明确 hover / disabled / loading 状态；异步操作期间按钮应禁用并显示 `Loader2` 或等价反馈。
- 弹窗沿用现有 `Modal` 或 `QrLoginModal` 模式，必须有明确关闭路径；涉及破坏性操作时使用 danger 样式并二次确认。
- 状态展示要可诊断：连接中、成功、失败、空状态、加载中都要有明确 UI，不允许静默失败或只写 `console.error`。
- 长文本、路径、room ID、模型名等必须可换行或截断，使用 `min-w-0`、`truncate`、`break-words`、`font-mono` 等现有模式，避免撑破布局。
- 动画只用于状态反馈或内容出现，沿用 `transition-colors`、`animate-spin`、`animate-reveal`、`skeleton` 等轻量模式，并尊重 `prefers-reduced-motion`。

### 可访问性与质量

- 交互控件必须使用语义元素：按钮用 `<button>`，输入用 `<input>` / `<textarea>`，开关保留 `role="switch"` 和 `aria-checked`。
- 图标按钮需要 `title` 或 `aria-label`；图片需要有意义的 `alt`。
- 颜色不能是唯一状态表达，重要状态需要结合文本或图标。
- 正文和表单文字保持可读对比度，优先使用现有 `text-content*` token，不要使用低对比灰色。
- 修改 UI 后至少运行 `Set-Location -LiteralPath .\desktop` 再运行 `npm run build`。涉及窗口布局、二维码、连接状态、设置页或渠道页时，还应启动 `npm run dev` 或 `npm run dev:hot` 做手动验证；如无法验证必须说明原因。

### 微信群机器人 UI 边界

- 阶段一只做最小运维面板：启用/停用、扫码状态、二维码、刷新群列表、选择目标群、保存配置、最近事件和错误提示。
- 阶段一的二维码必须嵌入通道接入流程，不再要求用户从后端日志复制扫码链接。
- 不在阶段一实现完整社交工作台、群统计、群记忆编辑、群友记忆编辑、战报、图片库或备份导入 UI。
- 微信群机器人设置应优先复用渠道页/设置页现有模式；如果 UI 改动范围过大，先保证配置文件、状态接口和日志可用，再单独规划 UI 小阶段。

## 验证策略

优先运行与改动直接相关的最小测试，再按风险扩大范围。

- 纯文档：检查文档是否能直接指导开发，无需运行测试。
- 配置/路由：运行对应 `tests/test_*` 单测。
- 微信群通道：运行 `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`；如改动桌面通道接入或二维码弹窗，再运行 `Set-Location -LiteralPath .\desktop` 后执行 `npm run build`。
- 安全相关：运行相关安全回归测试，必要时新增测试。
- 桌面端：运行 `npm run build`，涉及启动流程时再手动启动验证。
- 跨模块核心逻辑：运行 `python -m unittest discover -s tests`。

如果无法运行测试，必须在交付说明中写明原因和未验证风险。

## 交付说明要求

最终回复应说明：

- 改了哪些文件。
- 为什么这样改。
- 做了什么验证。
- 如果存在未验证项，明确列出原因。

不要声称“已修复”“已通过”而没有对应命令或检查结果。
