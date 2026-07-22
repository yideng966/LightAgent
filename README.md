<p align="center">
  <a href="https://github.com/yideng966/LightAgent/blob/master/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
  <a href="https://github.com/yideng966/LightAgent"><img src="https://img.shields.io/github/stars/yideng966/LightAgent?style=flat-square&cacheSeconds=3600" alt="Stars"></a>
  <a href="https://github.com/yideng966/LightAgent/tree/master/docs"><img src="https://img.shields.io/badge/Docs-repository-blue?style=flat&logo=readthedocs&logoColor=white" alt="Docs"></a>
</p>

# LightAgent

<h3 align="center">项目交流群</h3>

<p align="center">
  <a href="docs/images/wechat-group-qr.png">
    <img src="docs/images/wechat-group-qr.png" alt="扫码加入 LightAgent 项目交流群" width="420">
  </a>
</p>

LightAgent 是一个以 Python 为主的多渠道 Agent Harness 项目。它把 Web 控制台、即时通信平台、终端、桌面端、模型路由、工具调用、技能、长期记忆、知识库和个人微信群通道组合成一套可长期运行的 AI 助手框架。

它不是单一聊天机器人，也不是只绑定某一个模型厂商的客户端。LightAgent 的核心目标是把“用户从任意渠道发来的消息”转成统一上下文，再通过普通聊天模型或 Agent 模式处理，最后把文本、图片、语音、文件或工具执行结果发回原渠道。

## 核心定位

- 多渠道入口：Web、终端、个人微信、个人微信群、微信公众号、微信客服、企业微信应用、企业微信智能机器人、飞书、钉钉、QQ、Telegram、Slack、Discord。
- 多模型路由：OpenAI / OpenAI-compatible、自定义模型渠道、Claude、Gemini、DeepSeek、Qwen / DashScope、GLM、Kimi / Moonshot、MiniMax、Doubao、Qianfan / ERNIE、MiMo、ModelScope、LinkAI、讯飞、百度文心等。
- 多模态能力：文本对话、图片理解、图片生成、语音识别、语音合成、文件发送、翻译。
- Agent 能力：多轮工具调用、流式事件、任务规划、上下文压缩、工具结果回填、取消执行、定时任务、自主进化。
- 知识与记忆：会话持久化、长期记忆、每日记忆、知识库 Markdown 组织、关键词与向量检索、微信群专属群记忆与群友画像。
- 扩展体系：内置工具、MCP 动态工具、插件命令、技能系统、Skill Hub / GitHub / 本地技能安装。
- 运维界面：Web 控制台和 Electron 桌面端可管理模型、渠道、群聊、知识库、记忆、定时任务和技能。

## 快速启动

### 一键安装

Linux / macOS:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/yideng966/LightAgent/master/run.sh)
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/yideng966/LightAgent/master/scripts/run.ps1 | iex
```

Docker:

```bash
curl -O https://raw.githubusercontent.com/yideng966/LightAgent/master/docker/docker-compose.yml
docker compose up -d
```

启动后访问：

```text
http://localhost:9899
```

Web 控制台默认端口是 `9899`。如果部署在服务器上，需要在 `config.json` 中将 `web_host` 设置为 `0.0.0.0`，并设置 `web_password` 保护控制台，同时开放对应端口。

### 从源码运行

后端依赖：

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-optional.txt
python -m pip install -e .
```

个人微信群 sidecar 依赖（仅在需要接入 `wechat_group` 渠道时执行）：

```powershell
Set-Location -LiteralPath .\channel\wechat_group\sidecar
npm install
Set-Location -LiteralPath ..\..\..
```

这一步会安装 `channel/wechat_group/sidecar/package.json` 中声明的 Wechaty 相关依赖，包括 `wechaty`、`wechaty-puppet-wechat4u`、`file-box` 等。Python 通道启动时会在该目录运行 `node wechaty-sidecar.mjs`；如果 `node` 不在 `PATH` 中，可在 `config.json` 中把 `wechat_group_sidecar_node` 配置为 Node.js 可执行文件路径。

启动后端：

```powershell
python app.py
```

终端模式：

```powershell
python app.py --cmd
```

CLI 管理：

```powershell
lightagent start
lightagent stop
lightagent restart
lightagent status
lightagent logs
lightagent update
lightagent skill install <name>
lightagent install-browser
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

## 项目架构

LightAgent 的主链路由五层组成：

```text
用户 / 平台消息
  -> channel/* 渠道适配
  -> bridge.context.Context
  -> bridge.Bridge 路由聊天 / 语音 / 翻译 / Agent
  -> models/*、voice/*、translate/* 或 agent/*
  -> bridge.reply.Reply
  -> 原渠道发送回复
```

核心执行流程：

1. `app.py` 调用 `load_config()` 读取 `config.json` 或 `config-template.json`。
2. `ChannelManager` 解析 `channel_type`，支持单渠道、逗号分隔多渠道和列表多渠道。
3. 如果 `web_console` 未关闭，Web 控制台会随主进程自动启动。
4. 每个渠道通过 `channel/channel_factory.py` 创建实例，并在独立守护线程中运行。
5. 渠道把平台消息标准化为 `bridge.context.Context`，包含消息类型、会话 ID、发送人、接收人、渠道类型和附加参数。
6. `channel/chat_channel.py` 处理触发词、群白名单、会话隔离、插件事件、语音转文字、图片生成、文件发送等公共逻辑。
7. `bridge/bridge.py` 根据 `model`、`bot_type`、语音配置和翻译配置选择具体 Provider。
8. 普通聊天模式调用 `Bridge.fetch_reply_content()`，Agent 模式调用 `Bridge.fetch_agent_reply()`。
9. `bridge/agent_bridge.py` 为每个 `session_id` 初始化独立 Agent，加载系统提示词、技能、工具、记忆、知识库和运行时信息。
10. `agent/protocol/agent_stream.py` 执行“LLM -> tool_use -> tool_result -> LLM”的多轮循环，直到模型完成回复、达到步数上限或用户取消。
11. 回复被转换成 `ReplyType.TEXT`、`IMAGE`、`IMAGE_URL`、`VOICE`、`FILE` 等类型，并由原渠道发送。

## 目录结构

| 路径 | 职责 |
| --- | --- |
| `app.py` | 进程入口、配置加载、渠道生命周期、MCP 和调度器预热 |
| `config.py` / `config-template.json` | 全局配置、默认键、环境变量覆盖、敏感值脱敏 |
| `channel/` | Web、IM、终端等渠道适配 |
| `bridge/` | 聊天、Agent、语音、翻译的统一路由层 |
| `models/` | 各模型 Provider 的 Bot 与会话实现 |
| `agent/protocol/` | Agent 执行协议、流式循环、消息压缩、取消机制 |
| `agent/tools/` | 内置工具、MCP 工具、工具管理器 |
| `agent/skills/` | 技能加载、过滤、启停和 prompt 组装 |
| `agent/memory/` | 会话持久化、长期记忆、作用域记忆、Embedding 检索 |
| `agent/knowledge/` | 个人知识库、Markdown 知识组织和索引 |
| `plugins/` | 聊天命令插件，与 Agent 工具分离 |
| `voice/` | ASR / TTS Provider |
| `translate/` | 翻译 Provider |
| `desktop/` | Electron + Vite + React 桌面端 |
| `docs/` | 文档站内容 |
| `skills/` | 项目内置技能，启动时同步到 workspace |
| `tests/` | `unittest` 回归测试 |
| `plans/` | 开发计划、迁移计划和阶段性任务记录 |

## 配置与数据目录

主要配置文件是 `config.json`。没有该文件时，程序会回退读取 `config-template.json`。

关键配置：

- `lightagent_lang`：界面、日志、提示词和错误文案语言，支持 `auto`、`zh`、`en`。
- `channel_type`：启动渠道，支持 `"web"`、`"feishu,dingtalk"` 或 `["web", "telegram"]`。
- `web_console`：是否自动启动 Web 控制台。
- `web_host` / `web_port` / `web_password`：Web 控制台绑定地址、端口和密码。
- `model` / `bot_type`：模型名和 Provider 路由。`bot_type` 为空时按模型名前缀自动推断。
- `custom_providers`：多个 OpenAI-compatible 自定义 Provider。
- `agent`：是否启用 Agent 模式。
- `agent_workspace`：Agent 工作目录，默认 `~/lightagent`，用于存放技能、记忆、知识库、MCP 配置等。
- `agent_max_context_tokens` / `agent_max_context_turns` / `agent_max_steps`：Agent 上下文和执行步数限制。
- `enable_thinking` / `reasoning_effort`：支持推理模型的思考模式开关和强度。
- `knowledge`：是否启用知识库。
- `self_evolution_enabled`：是否启用空闲会话自主进化。
- `tools`：内置工具运行时配置，例如 `web_search` Provider 与 API key。
- `mcp_servers`：MCP 服务配置，支持 stdio 和 SSE。

环境变量会覆盖同名配置键，适合云部署或避免把密钥写入文件。

## 模型路由

`bridge/bridge.py` 和 `models/bot_factory.py` 负责模型路由。当前代码支持：

- OpenAI 官方接口：`openAI`
- OpenAI-compatible：`openai`、`custom`、`custom:<id>`
- Azure OpenAI：`chatGPTOnAzure`
- Claude：`claudeAPI`
- Gemini：`gemini`
- DeepSeek：`deepseek`
- Qwen / DashScope：`dashscope`
- GLM / 智谱：`zhipu`
- Kimi / Moonshot：`moonshot`
- MiniMax：`minimax`
- Doubao / 火山方舟：`doubao`
- Qianfan / ERNIE：`qianfan`
- MiMo：`mimo`
- ModelScope：`modelscope`
- LinkAI：`linkai`
- 百度文心、讯飞 Spark 等兼容旧路由。

路由规则：

- 如果显式配置 `bot_type`，优先使用该 Provider。
- 如果只配置 `model`，按模型名或前缀推断，例如 `qwen*` 走 DashScope，`gemini*` 走 Gemini，`glm*` 走智谱，`claude*` 走 Claude，`deepseek*` 走 DeepSeek，`kimi*` 走 Moonshot。
- `custom:<id>` 会从 `custom_providers` 中读取对应的 API key、base URL 和模型。
- `use_linkai` 且配置了 `linkai_api_key` 时，可统一接管聊天、语音识别、语音合成和多模型能力。

## 渠道能力

当前 `channel/channel_factory.py` 支持的渠道：

| 渠道类型 | 说明 |
| --- | --- |
| `web` | 默认 Web 控制台，支持聊天、配置、模型、渠道、技能、记忆、知识库、定时任务和群聊管理 |
| `terminal` | 命令行交互模式，通过 `python app.py --cmd` 进入 |
| `weixin` / `wx` | 个人微信渠道 |
| `wechat_group` | 个人微信群渠道，基于 Python 通道层 + Node.js Wechaty sidecar |
| `wechatmp` / `wechatmp_service` | 微信公众号被动/服务模式 |
| `wechat_kf` | 微信客服 |
| `wechatcom_app` | 企业微信应用 |
| `wecom_bot` | 企业微信智能机器人，支持 websocket 或 webhook 模式 |
| `feishu` | 飞书 / Lark，支持 webhook 或 websocket，支持流式卡片回复 |
| `dingtalk` | 钉钉机器人 |
| `qq` | QQ 渠道 |
| `telegram` | Telegram Bot |
| `slack` | Slack Socket Mode |
| `discord` | Discord Gateway |

多渠道可以同时运行：

```json
{
  "channel_type": "web,telegram,slack"
}
```

或：

```json
{
  "channel_type": ["web", "wechat_group"]
}
```

## Web 控制台

Web 控制台是默认入口，启动后访问 `http://localhost:9899`。

主要能力：

- 多会话聊天和 Agent 流式事件展示。
- 模型与自定义 Provider 管理。
- 语音识别、语音合成、图片生成、图片理解相关配置。
- 渠道接入、启停、扫码状态和二维码轮询。
- 个人微信群独立群聊管理页。
- 知识库管理、分类、索引和 Web API。
- 记忆、群记忆、按群隔离的群友画像、学习运行记录管理。
- 定时任务管理。
- 技能安装、刷新和环境变量同步。
- 会话消息持久化、消息编辑/删除后同步 Agent 内存。
- 文件服务接口，受 `web_file_serve_root` 限制。

## 桌面端

桌面端位于 `desktop/`，技术栈是 Electron + Vite + React 18 + TypeScript + Tailwind CSS + Zustand + `lucide-react`。

桌面端职责：

- 管理内置 Python 后端进程。
- 提供聊天、设置、渠道、群聊等图形界面。
- 使用 `desktop/src/main/python-manager.ts` 管理后端启动、端口和数据目录。
- 打包时将后端资源放入 Electron 应用资源目录。

常用命令：

```powershell
Set-Location -LiteralPath .\desktop
npm run build
npm run dev
npm run dev:hot
npm run dist:win
```

## Agent 内部逻辑

Agent 模式由 `bridge/agent_bridge.py` 与 `agent/protocol/` 组成。

执行逻辑：

1. 按 `session_id` 创建或复用 Agent，保证不同用户和不同会话隔离。
2. 初始化系统提示词，加载工作空间说明、工具 schema、技能、记忆规则、知识库规则和运行时信息。
3. 读取持久化会话历史，恢复最近上下文。
4. 把当前用户消息预写入会话库，保证刷新页面或切换会话时能看到进行中的用户消息。
5. 调用支持工具调用的模型接口。
6. 如果模型返回 `tool_use`，执行对应工具，把 `tool_result` 写回消息列表。
7. 循环调用模型，直到没有工具调用、达到 `agent_max_steps` 或被取消。
8. 对过长工具结果和历史消息做分层压缩，必要时触发记忆 flush 和摘要注入。
9. 将 assistant 回复、工具结果、文件信息、图片信息和思考块按配置持久化。
10. 如果工具生成了可发送文件，转换为图片或文件类型回复。

Agent 还支持：

- per-session Agent 实例隔离。
- 用户取消执行，自动补齐未完成的 tool result，避免下次请求消息链损坏。
- thinking 模式在 Web 端展示，IM 渠道默认过滤原始 `<think>` 标签。
- 定时任务输出注入目标会话，并限制每个会话保留的调度任务消息数量。
- 会话清理、全部 Agent 清理、技能和条件工具热刷新。

## 工具系统

内置工具由 `agent/tools/__init__.py` 和 `ToolManager` 注册。

当前工具包括：

- `read`：读取文件。
- `write`：写入文件。
- `edit`：编辑文件。
- `ls`：列目录。
- `bash`：执行 Shell 命令。
- `send`：发送文件。
- `memory_search` / `memory_get`：检索和读取记忆。
- `evolution_undo`：回滚自主进化产生的变更。
- `env_config`：管理环境变量。
- `scheduler`：创建和执行定时任务。
- `web_search`：联网搜索，按配置选择 Provider。
- `web_fetch`：抓取网页内容。
- `vision`：图片理解。
- `browser`：浏览器自动化，需要 Playwright 和 Chromium。
- `mcp`：动态接入 MCP 服务器工具。

MCP 逻辑：

- 优先读取 `~/lightagent/mcp.json`，支持 `mcpServers` 和 `mcp_servers` 两种格式。
- 没有工作区 MCP 配置时，回退读取 `config.json` 中的 `mcp_servers`。
- 支持 stdio 和 SSE。
- 启动时后台加载，不阻塞第一条消息。
- 支持 `mcp.json` 签名检测、热更新、增量新增、移除和重启服务器。
- MCP 工具按服务名隔离，失败的服务不会阻塞其他服务。

## 技能系统

技能是比工具更高层的工作流说明。项目内置技能在根目录 `skills/`，启动时会同步到 `agent_workspace` 下的 `skills/`。

当前内置技能目录：

- `image-generation`
- `knowledge-wiki`
- `skill-creator`

技能能力：

- 通过 `SKILL.md` 定义触发条件、流程和工具使用方式。
- 支持技能启停配置。
- 支持通过 CLI 或聊天命令安装技能。
- 支持 Skill Hub、GitHub、本地目录等来源。
- Agent 在执行时可以把技能说明注入上下文，按技能要求调用工具。

常用命令：

```bash
/skill list
/skill search <keyword>
/skill install <name>
lightagent skill install <name>
```

## 记忆与知识库

LightAgent 同时提供会话记忆、长期记忆和知识库能力。

会话层：

- 会话消息按 `session_id` 持久化。
- Agent 实例从会话库恢复历史。
- Web 控制台编辑或删除消息后，可同步 Agent 内存。
- 上下文过长时，按完整轮次压缩或截断，避免 tool_use / tool_result 链断裂。

长期记忆：

- 支持 `memory_search` 和 `memory_get` 工具。
- 支持作用域记忆，用于区分全局记忆、群记忆、成员画像等。
- 支持在上下文压力或空闲复盘时把历史消息 flush 到记忆。

知识库：

- `knowledge` 开启时，知识库规则和索引会进入系统提示词。
- 具体知识内容可通过工具按需读取或检索。
- Web 控制台提供知识库管理、分类和索引能力。

自主进化：

- `self_evolution_enabled` 控制总开关，`config-template.json` 中只暴露该开关的示例值；运行时完整解析在 `config.py` 与 `agent.evolution.config` 中完成。未配置时的 fallback 默认值是关闭，`self_evolution_idle_minutes` 为空闲 10 分钟，`self_evolution_min_turns` 为至少 6 个真实用户轮次。上下文压力过高时也可能提前触发复盘。
- 自主进化只作用于 Agent 模式主链路。`agent=false` 时，渠道会走普通聊天回复，不会进入 `AgentBridge` 的自主进化轮次记录、空闲扫描和 review agent 执行链路。
- `bridge/agent_bridge.py` 初始化 `AgentBridge` 时会启动 `agent.evolution.trigger` 的后台扫描器；`AgentBridge.agent_reply` 在每轮 Agent 执行前后调用 `mark_run_active`，避免空闲扫描和正在运行的用户请求并发修改同一会话。
- 普通 Agent 主链路完成一轮真实用户消息后会调用 `note_user_turn` 记录会话活跃时间、轮次数、渠道类型和可选的主动推送目标。`agent.chat.service` 的 Web streaming 路径会做同样记录，因为该路径不经过 `AgentBridge.agent_reply`。
- 后台扫描器在会话空闲、未运行中且满足轮次或上下文压力条件时，调用 `agent.evolution.executor.run_evolution_for_session()`。
- `agent.evolution.executor` 会创建隔离 review agent，复用当前模型，但只开放受限工具集合，并对写入类工具加工作空间边界；MCP 动态工具不会被自动重新注入到自主进化 review agent。
- review agent 只在发现明确、可落地的长期收益时修改工作空间中的记忆、用户技能或知识内容；无收益或没有真实文件变化时保持静默。
- 产生真实改动时，会先创建备份，再把结果写入 `memory/evolution/YYYY-MM-DD.md`，并通过 `remember_scheduled_output` 向原会话注入 `[EVOLUTION]` 记录，后续可用 `evolution_undo` 回滚对应备份。
- 只有同时存在 `channel_type` 和单聊 `receiver` 时才会主动推送进化摘要；群聊不会设置主动推送 receiver，避免在群里无人提问时主动打扰。

微信群与群聊复用自主进化：

- 个人微信群通道没有独立实现第二套自主进化系统。`WechatGroupChannel` 仍按 `ChatChannel -> Bridge.fetch_agent_reply -> AgentBridge.agent_reply` 进入 LightAgent Agent 主链路，因此复用自主进化的用户轮次记录、空闲扫描、隔离 review agent、备份、`[EVOLUTION]` 注入和 `evolution_undo` 回滚能力。
- `wechat_group` 上下文会被记录为群聊会话轮次，但 `AgentBridge.agent_reply` 会在 `isgroup=true` 时调用 `note_user_turn(agent, channel_type=ch, receiver="")`，即记录可进化信号但不设置主动推送 receiver。
- 这意味着微信群可以在空闲后沉淀长期记忆、技能或知识修正，但进化摘要不会主动发到群里；用户后续继续对话时，主链路可通过会话中的 `[EVOLUTION]` 记录感知进化结果。

## 插件系统

`plugins/` 是聊天命令插件体系，不等同于 Agent 工具。

插件特点：

- 使用 `plugin_trigger_prefix` 触发，默认 `$`。
- 启动时由 `PluginManager().load_plugins()` 加载。
- 可用于命令式管理、状态查询或平台扩展。
- Web/IM 渠道进入回复链路前会触发相关插件事件。

## 定时任务

调度器工具由 `agent.tools.scheduler` 提供。

能力：

- 支持创建定时提醒、周期任务、定期播报等 Agent 任务。
- `app.py` 启动时会预热 AgentBridge，使调度器不必等第一条用户消息才启动。
- 调度任务使用隔离会话执行，避免内部工具链污染用户主会话。
- 可把最终可见结果注入目标用户会话，便于后续追问。
- Web 控制台提供定时任务管理 UI。

## 个人微信群通道

个人微信群是本仓库近期重点能力。它定位为 LightAgent 的一个消息渠道，不是独立 Agent 产品。

### 组件边界

- Python 通道层：`channel/wechat_group/`
  - 管理 sidecar 进程。
  - 读取配置。
  - 过滤目标群、发送人、触发规则和自发消息。
  - 将 sidecar 事件转换为 `Context`。
  - 注入微信群专属上下文。
  - 复用 LightAgent 原有 `ChatChannel`、`Bridge`、Agent、工具、记忆、知识库和回复链路。
- Node.js sidecar：`channel/wechat_group/sidecar/`
  - 使用 Wechaty 登录微信。
  - 维护群列表。
  - 监听群消息。
  - 下载真实媒体文件。
  - 执行微信侧文本、图片、文件、语音、表情包发送。
  - 与 Python 仅通过 JSON Lines 协议通信。

### 接入流程

1. 在 `config.json` 中启用或选择 `wechat_group` 渠道。
2. 按“个人微信群 sidecar 依赖”步骤安装 Wechaty sidecar 的 npm 依赖。
3. 启动 LightAgent。
4. 打开 Web 控制台。
5. 进入“通道管理 -> 接入通道 -> 个人微信群”。
6. 在界面中查看二维码并扫码登录。
7. 刷新群列表，选择目标群或填写群名兜底。
8. 在目标群中 @ 机器人验证收发。

### 上下文注入顺序

微信群消息进入主链路前，会在用户原始问题前注入多个 XML 风格上下文块。最终 LLM 看到的是：

```text
通用 Agent 系统上下文
历史 user / assistant / tool 消息
当前 user message:
  <wechat-group-persona>...</wechat-group-persona>
  <recent-wechat-group-transcript>...</recent-wechat-group-transcript>
  <wechat-group-topic>...</wechat-group-topic>
  <wechat-group-style>...</wechat-group-style>
  <wechat-group-knowledge>...</wechat-group-knowledge>
  <wechat-group-emotion>...</wechat-group-emotion>
  <wechat-group-multimodal>...</wechat-group-multimodal>
  <wechat-group-image>...</wechat-group-image>
  用户本次去掉开头 @ 后的真实问题
```

不同块由配置控制，异常时跳过对应块，不绕过 LightAgent 主链路。

### 已实现能力

- 扫码登录、登录状态和二维码轮询。
- 群列表刷新、目标群精确选择、群名兜底过滤。
- 群消息标准化解析：文本、图片、文件、音频、视频、引用、合并转发、表情包等元数据。
- 群白名单、管理员、黑名单、自发消息过滤。
- @ 触发、关键词触发、群内会话隔离。
- 回复回原群，并优先通过 Wechaty `room.say(text, ...mentions)` 真实 mention 发送者。
- `wechaty-puppet-wechat4u` 下提供可见 `@昵称` 文本兜底。
- 当前群最近上下文归档，按 `room_id` 隔离。
- 人设预设和自定义人设，支持管理员配置请求跳过人设注入。
- 群记忆和按 `stable_room_id + stable_member_id` 隔离的群友画像，只注入当前群回复上下文。
- 群友画像学习、常用词噪声过滤、按群展示画像出现范围。
- 话题追踪：活动话题持久化、消息归属、摘要历史、上下文注入。
- 风格卡片：候选学习、审核启用、上下文注入。
- 情绪与主动性：群情绪状态、能量衰减、时段规则、typing delay、自由回复压制。
- 表情包资产：自动收集、哈希去重、按群搜索、人工编辑描述、Vision 批量补全、线上候选补充、停用、每日发送限制、Agent scoped tools。
- 图片理解：复用 `agent.tools.vision.vision.Vision`，生成 `<wechat-group-image>`。
- 文本识图请求可按引用消息、引用发送者、最近图片三层优先级定位目标图片。
- 多模态上下文：引用消息、合并转发预览、视频文本上下文。
- 自由回复：非 @ 消息进入队列，按活跃档位、本地规则、LLM 判断、情绪和时间规则决定是否回复。
- 自由回复图片理解独立开关，默认关闭，避免自动增加视觉模型调用。
- Web 群聊管理页：基础设置、群聊开关、人设、永久记忆、群友画像、话题、风格、情绪、表情包、图片与多模态配置。

### 表情包检索与发送

表情包能力仍走 LightAgent 主链路。群内真实表情包消息会先按 `room_id` 自动收集到本地素材库；Agent 回复时可调用 `wechat_group_sticker_search` 检索当前群本地表情包，本地不足或不匹配时再补充线上候选，并通过 `wechat_group_sticker_send` 使用 `sticker_id` 或 `online_id` 发送。

线上候选不会把原始图片 URL 暴露给模型或群聊。服务端只返回受控 `online_id`，发送前再按允许域名、HTTPS、GIF 开关、大小上限、冷却时间和每日上限校验，下载到本地缓存后复用现有图片发送链路。

Web 使用路径：

1. 打开 Web 控制台。
2. 进入“群聊 -> 表情包”。
3. 选择目标群，查看本地表情包列表；可以按描述或文件名搜索、人工编辑本地描述或停用素材。
4. 列表顶部会显示当前群“待理解”和“可处理”数量。点击“图片理解补全描述”并确认后，系统先备份表情包 SQLite，再在后台复用现有 `Vision` 批量补全空值、占位、XML、纯数字和长哈希描述。
5. 在“表情包设置”中配置线上检索开关、接口、允许域名、候选数、GIF 开关、发送冷却和存储目录。
6. 使用“测试线上检索”输入关键词预览线上候选，确认当前运行环境已经包含表情包优化代码。

新表情包自动收藏不会同步调用 Vision，避免阻塞群消息和产生不可控模型调用；无法从文件名得到语义时先使用“群聊表情包”占位，后续由管理员在 Web UI 人工修改或主动启动批量图片理解。批量任务只处理当前选中的稳定群和明确的待理解项，不覆盖已有正常语义或处理期间新保存的人工描述。

### 重要边界

- 不在 `channel/wechat_group/` 内重写独立模型调用、独立 Agent loop 或独立长期记忆系统。
- 群记忆和群友画像必须按 `room_id` / `sender_id` 强过滤，不能跨群泄露。
- sidecar 遇到文本消息不能调用 `toFileBox()` 下载文件；只有真实媒体消息才下载。
- Web 微信 / `wechaty-puppet-wechat4u` 不能稳定触发系统级“有人@我”提醒，当前保证的是回复回同一群且文本中可见 @ 到真实发送者。
- 真实扫码、入群、真实 mention 和跨群隔离仍需要人工链路验证。

## 多模态

文本：

- 普通对话、Agent 工具调用、技能执行、插件命令。

图片：

- 图片理解通过 `vision` 工具。
- 图片生成通过 `text_to_image`、模型 Provider 或自定义 Provider。
- Web、IM、微信群等渠道按能力发送图片 URL、图片文件或媒体消息。

语音：

- `voice_to_text` 支持 OpenAI、百度、Google、Azure、讯飞、阿里、DashScope、智谱、LinkAI 等目录中的 Provider。
- `text_to_voice` 支持 OpenAI、百度、Google、Azure、讯飞、阿里、pytts、ElevenLabs、Edge、腾讯、MiniMax、MiMo 等实现。
- 群语音识别、始终语音回复、语音回复开关均由配置控制。
- 微信群 `.sil` / `.silk` / `.slk` 语音转 WAV 需要可选依赖 `pysilk-mod>=1.6.4`（发行包名为 `pysilk-mod`，Python 导入名为 `pysilk`）。Silk 转换不依赖 `ffmpeg`；MP3、M4A、OGG 等通过 `pydub` 转换的格式仍需系统可执行的 `ffmpeg`。
- 自定义 OpenAI-compatible Provider（`custom:<id>`）可在 Web 控制台中独立用于 ASR/TTS，并复用该 Provider 的 `api_key` 与 `api_base`。ASR 通过 `/audio/transcriptions` 完成转写；通用 TTS 通过 `/audio/speech` 返回 MP3，`mimo-v2.5-tts*` 模型通过 `/chat/completions` 返回 base64 WAV。语音模型必须单独填写，不能直接沿用聊天模型。
- Web 控制台内置 ASR Provider 为 `openai`、`dashscope`、`zhipu`、`linkai`，内置 TTS Provider 为 `openai`、`minimax`、`dashscope`、`mimo`、`linkai`，两者都会追加凭据完整的 `custom:<id>`。Custom TTS 没有预置音色目录时可直接填写 voice ID；不存在、缺少 Key/Base 或未填写对应语音模型的自定义 Provider 会在保存前被拒绝。

文件：

- Agent 工具可以生成文件。
- `send` 工具和 AgentBridge 会把文件转换为渠道可发送类型。
- Web 文件服务受 `web_file_serve_root` 限制。

翻译：

- `translate/` 当前包含百度和有道。
- `Bridge.fetch_translate()` 按 `translate` 配置选择 Provider。

## 安全边界

LightAgent 会触达文件系统、Shell、浏览器、网络、MCP 子进程和外部消息平台，因此默认安全边界必须保守。

高风险区域：

- `agent/tools/bash/`
- `agent/tools/read/`
- `agent/tools/write/`
- `agent/tools/edit/`
- `agent/tools/web_fetch/`
- `agent/tools/browser/`
- `agent/tools/mcp/`
- `web_file_serve_root`
- `agent_workspace`
- `mcp_servers` / `mcpServers`

已有安全回归测试覆盖 SSRF、路径穿越、浏览器导航限制等场景：

```powershell
python -m unittest tests.test_security_ssrf_web_fetch
python -m unittest tests.test_security_ssrf_path_traversal
python -m unittest tests.test_security_ssrf_browser_navigate
```

## 测试与验证

运行全部 Python 测试：

```powershell
python -m unittest discover -s tests
```

运行单个测试文件：

```powershell
python -m unittest tests.test_models_handler
```

微信群通道相关最小回归：

```powershell
python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web
```

微信群拟人化、记忆、画像和多模态相关扩展回归：

```powershell
python -m unittest tests.test_wechat_group_context tests.test_wechat_group_topic_service tests.test_wechat_group_style_service tests.test_wechat_group_emotion_service tests.test_wechat_group_sticker_service tests.test_wechat_group_memory_ui
```

前端脚本静态检查：

```powershell
node --check .\channel\web\static\js\console.js
```

桌面端构建：

```powershell
Set-Location -LiteralPath .\desktop
npm run build
```

## 常见开发路径

新增渠道：

1. 参考 `channel/channel.py` 和 `channel/chat_channel.py`。
2. 在 `channel/<name>/` 实现渠道。
3. 更新 `channel/channel_factory.py`。
4. 必要时更新 `common/const.py`、`config.py`、`config-template.json`、Web 控制台和测试。

新增模型 Provider：

1. 参考 `models/<provider>/` 中相近实现。
2. 在 `models/` 中实现 Bot 和 Session。
3. 更新 `models/bot_factory.py`。
4. 必要时更新 `bridge/bridge.py`、`common/const.py`、Web 模型管理和测试。

新增 Agent 工具：

1. 继承 `agent/tools/base_tool.py` 的 `BaseTool`。
2. 保持工具名称、输入 schema、返回状态和错误格式稳定。
3. 更新 `agent/tools/__init__.py` 或相关动态加载配置。
4. 高风险工具必须补充安全测试。

新增技能：

1. 放在 `skills/<skill-name>/SKILL.md`。
2. 保持 frontmatter 元数据清晰。
3. 脚本放在技能目录下的 `scripts/`。
4. 避免把大量业务逻辑硬塞进 prompt。

## 近期主要变更摘要

近期 `CHANGES.md` 记录的重点能力：

- 2026-07-01：新增个人微信群通道闭环，包括扫码、群列表、真实 @、人设和 Web/桌面接入。
- 2026-07-02：新增 Web 群聊管理页、4.2 最近上下文、桌面端群聊页和 4.3 记忆计划细化。
- 2026-07-04：完成微信群全局画像与群记忆重构、话题、风格、情绪、表情包、多模态、Web 管理 UI 和阶段回归。
- 2026-07-05：修复微信群自由回复图片理解开关、表情包误收集、画像常用词噪声、WebUI 中文化和自由回复参数布局。
- 近期同时补充了 Agent LLM 请求上下文日志、聊天历史迁移、自定义 Provider、知识库和安全回归测试。

完整变更以根目录 `CHANGES.md` 为准。

## 贡献说明

欢迎提交功能、修复、文档和测试。开始前请阅读：

- `AGENTS.md`
- `CONTRIBUTING.md`
- `CHANGES.md`

项目协作原则：

- 先读上下文，再改文件。
- 最小改动，避免顺手重构。
- 涉及代码、配置或文档交付时，按项目规则记录变更。
- 高风险能力必须有测试覆盖。
- 不要提交真实密钥、token、cookie 或部署 ID。

## 免责声明

1. 本项目基于 MIT License 开源，主要用于技术研究、学习和自托管实践。使用者需自行遵守所在地法律法规。
2. Agent 模式可能消耗更多 token，也可能访问本地文件、Shell、浏览器和网络资源，请只在可信环境部署。
3. 使用外部模型、IM 平台、云服务、MCP 服务或第三方 API 时，请自行承担账号、费用、合规和数据安全责任。
4. LightAgent 是纯开源项目，不参与、不授权、不发行任何加密货币或投资产品。

## 上游项目与许可证

LightAgent 基于 `zhayujie/CowAgent` 进行二次开发。上游项目采用 MIT License，本仓库完整保留根目录 `LICENSE` 中的原始版权声明与许可文本；复制、修改、发布或分发本项目时，应继续附带该版权声明和许可文本。

鸣谢项目：https://github.com/zhayujie/CowAgent.git

## 项目更名说明

本仓库在上游项目基础上以 `LightAgent` 名称继续开发。已有本地仓库可以按需更新远端地址：

```bash
git remote set-url origin https://github.com/yideng966/LightAgent.git
```
