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
- 历史桌面端归档：`desktop/`（停止维护，不参与构建发布）
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
- `desktop/`：已停止维护的 Electron 历史源码归档，不再开发、修复、构建或发布；Python 后端 `app.py` 不属于桌面端，继续作为项目主入口维护。
- `docs/`：英文、中文。涉及用户可见能力变更时，优先补充对应文档。
- `tests/`：`unittest` 风格回归测试，很多测试通过 stub/mocking 避免真实网络和外部服务。

## 本地运行与验证

默认在 Windows PowerShell 中工作。不要使用 `&&` 串联命令。

访问 GitHub 时如果直连请求超时或不稳定，可以使用本地代理 `http://192.168.3.5:1082` 重试；仅在网络访问场景使用该代理，不要把代理地址写入项目运行配置或代码默认值。

整理或创建 GitHub issue 时，一律提交到 `yideng966/LightAgent` 项目；标题和正文描述应使用简体中文，避免默认写英文；提交时必须注明合适的 label，至少明确是 `bug`、功能需求、文档或其他类型；不要默认使用当前 remote、fork 或其他仓库；docs\images目录不要提交开发过程截图。

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

开发任务的验证约束：

- 自动化回归继续使用 `python -m unittest ...` 等本地测试命令。
- 需要验证真实运行链路时，必须在当前本地仓库使用 `python app.py` 启动实际环境并完成验证。
- 不得把远端 Docker 部署环境作为本地开发测试环境；除非用户针对部署或运维另行明确授权，否则不得为验证代码而连接、更新、重启远端容器或操作远端数据。
- 下文 Docker 内容只作为构建与部署参考，不属于默认开发验证流程。

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

`desktop/` 已停止维护并仅作历史归档，不再作为本地开发或验证目标。源码运行继续使用 `python app.py`，图形管理入口使用随 Python 后端启动的 Web 控制台。

## Docker 构建与部署

> **连接实际部署环境**：如需登录已部署的服务器进行运维、日志调查或更新部署，请参考 [SERVER_ACCESS.md](./SERVER_ACCESS.md)。该文档包含 SSH 连接信息、Docker 容器管理命令及常见运维场景。

LightAgent 通过 `docker/Dockerfile.latest` 提供全功能 Docker 镜像，包含 Python 运行时、微信侧车 (Node.js Wechaty) 和可选的 Playwright/Chromium 浏览器引擎。简化的根 `Dockerfile` 基于预构建镜像 `ghcr.io/yideng966/lightagent:latest`，仅用于快速继承上游。

### 关键文件

| 文件 | 用途 |
|------|------|
| `Dockerfile`（根） | 基于上游预构建镜像的简化入口，仅设置 `ENTRYPOINT` |
| `docker/Dockerfile.latest` | 多阶段构建文件，从源码生成独立运行镜像 |
| `docker/docker-compose.yml` | 本地启动编排，映射端口 9899，挂载配置和数据卷 |
| `docker/entrypoint.sh` | 容器入口脚本，负责初始配置生成、密码管理和运行时目录准备 |
| `docker/build.latest.sh` | 构建脚本，从 `docker/` 目录运行 `cd .. && docker build -f docker/Dockerfile.latest ...` |
| `docker/.env.example` | 环境变量参考，可覆盖 Web 控制台密码 |
| `.dockerignore` | 排除 `.git`、`.worktrees/`、`node_modules`、`__pycache__`、日志、临时文件等 |

### 构建参数

`docker/Dockerfile.latest` 支持以下 `--build-arg`：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `INSTALL_BROWSER` | `true` | 是否安装 Playwright/Chromium。设为 `false` 可大幅减小镜像体积并加速构建 |
| `USE_CN_MIRROR` | `false` | 是否使用清华 apt/pip/Playwright 镜像（国内构建更快） |
| `TZ` | `Asia/Shanghai` | 容器时区 |
| `CHATGPT_ON_WECHAT_VER` | 无 | LightAgent 版本标签 |

### 构建镜像

**完整构建（含 Chromium，镜像约 2–3 GB，耗时 10–30 分钟）：**

```bash
docker build -f docker/Dockerfile.latest -t yideng966/lightagent .
```

**快速构建（跳过浏览器，适用于仅需 API/CLI/Web 功能的场景，镜像约 800 MB–1.2 GB）：**

```bash
docker build -f docker/Dockerfile.latest \
  --build-arg INSTALL_BROWSER=false \
  -t yideng966/lightagent .
```

**使用中国镜像加速（可选）：**

```bash
docker build -f docker/Dockerfile.latest \
  --build-arg INSTALL_BROWSER=false \
  --build-arg USE_CN_MIRROR=true \
  -t yideng966/lightagent .
```

### Docker Compose 启动（推荐）

1. 确保已构建或拉取镜像 `yideng966/lightagent:latest`
2. 进入 `docker/` 目录并启动：

```bash
cd docker
docker compose up -d
```

3. 查看启动日志，获取自动生成的 Web 控制台密码（如未通过 `WEB_PASSWORD` 环境变量预设）：

```bash
docker compose logs lightagent | grep "Web console password"
```

4. 浏览器访问 `http://localhost:9899`，使用上述密码登录 Web 控制台。

首次启动时，`docker compose` 会自动在宿主机 `docker/` 下创建 `config/` 和 `data/` 目录，分别映射到容器内的 `/home/agent/.lightagent` 和 `/home/agent/lightagent`。

### Docker CLI 直接启动

```bash
docker run -d \
  --name lightagent \
  --security-opt seccomp:unconfined \
  -p 9899:9899 \
  -e WEB_HOST="0.0.0.0" \
  -v ./docker/config:/home/agent/.lightagent \
  -v ./docker/data:/home/agent/lightagent \
  yideng966/lightagent:latest
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WEB_PASSWORD` | 自动生成并持久化 | Web 控制台登录密码。未设置时 entrypoint 用 `secrets.token_urlsafe(18)` 生成随机密码，写入 `config.json` 并打印到日志。 |
| `WEB_HOST` | `0.0.0.0` | Web 服务绑定地址 |
| `LIGHTAGENT_DATA_DIR` | `/home/agent/.lightagent` | 配置与运行时数据目录 |
| `CHATGPT_ON_WECHAT_PREFIX` | `/app` | 应用根目录 |
| `CHATGPT_ON_WECHAT_EXEC` | `python app.py` | 容器启动命令 |

其他 LLM API Key、渠道配置等环境变量（如 `OPEN_AI_API_KEY`、`OPEN_AI_PROXY` 等）可通过 `docker-compose.yml` 的 `environment` 段传入。完整变量列表见 `config-template.json` 和 `docker/entrypoint.sh` 中的注释段。

### 容器管理

```bash
# 查看实时日志
docker compose -f docker/docker-compose.yml logs -f lightagent

# 停止并移除容器
docker compose -f docker/docker-compose.yml down

# 重启容器
docker compose -f docker/docker-compose.yml restart

# 进入容器调试
docker exec -it lightagent bash
```

### 容器内目录结构

| 路径 | 说明 |
|------|------|
| `/app` | LightAgent 代码根目录 |
| `/home/agent/.lightagent/config.json` | 运行时配置（由 entrypoint 从 `config-template.json` 初始化） |
| `/home/agent/lightagent` | 运行时数据目录（logs、workspace、tmp 等） |
| `/app/channel/wechat_group/sidecar/node_modules` | 微信侧车 Node.js 依赖（从构建阶段复制） |
| `/app/ms-playwright` | Chromium 浏览器文件（仅 `INSTALL_BROWSER=true` 时存在） |
| `/entrypoint.sh` | 容器入口脚本 |

### entrypoint.sh 启动流程

1. 容器以 `root` 启动，执行 `prepare_runtime_dirs()`
2. 如果 `LIGHTAGENT_DATA_DIR/config.json` 不存在，从 `/app/config-template.json` 复制
3. `ensure_web_password()`：如果未设置 `WEB_PASSWORD` 环境变量，用 Python `secrets.token_urlsafe(18)` 生成随机密码，写入 `config.json`，打印到标准输出
4. 将配置和数据目录的权限归属到 `agent` 用户
5. 通过 `su agent` 降权，切换到 `/app`，执行 `python app.py`

### 镜像发布（CI）

GitHub Actions 在推送带版本号的标签（如 `v1.0.0`）时自动触发 `docker` 工作流，构建 `docker/Dockerfile.latest` 并推送到 Docker Hub `yideng966/lightagent`。本地手动发布可使用：

```bash
cd docker
bash build.latest.sh
docker push yideng966/lightagent:latest
```

### GitHub Release 说明

- 每个准备发布的 `v*` 标签必须在同一标签提交中包含 `docs/releases/<完整标签>.md`，例如 `v2.1.7` 对应 `docs/releases/v2.1.7.md`；从 `.github/RELEASE_NOTES_TEMPLATE.md` 复制后填写，禁止多个版本共用一个会被覆盖的说明文件。
- Release 标题由 `.github/workflows/release.yml` 统一生成，格式为 `LightAgent <去掉 v 前缀的版本号>`；正文不要重复一级标题。标签含连字符（如 `v2.1.7-rc.1`）时按预发布处理，不得覆盖稳定版 Latest。
- 正文必须使用简体中文并面向安装者、管理员和最终用户，不写成 Git 提交列表。先核对 `CHANGES.md`、上一个已发布标签到当前待发布提交的 Git 差异、已合并 PR/Issue 和实际验证结果；无法从代码或验证记录确认的能力、兼容性、性能数据不得写入。
- 固定开头为 `> LightAgent - <项目定位>`，随后用一到两句话概括本版本最重要的用户价值、主要修复及影响范围。
- 变更正文按实际内容从“新增功能”“优化改进”“Bug 修复”“安全修复”“破坏性变更”中选用，至少保留一个分类；空分类必须删除。存在不兼容变化时必须单列“破坏性变更”，说明受影响用户、旧行为、新行为和迁移步骤，不能埋在优化或修复条目中。
- 每个列表项只表达一项用户可感知的变化，优先写“解决什么问题、现在表现如何”；同一功能的代码、配置、测试和文档提交应合并为一个条目，不按文件或提交逐条展开。
- 正文不得包含内部计划、测试通过数量、文件清单、提交哈希、实现过程、未确认路线图、密钥或部署标识；贡献者致谢、关联 PR/Issue 仅在真实且有用户价值时补充。
- 末尾必须依次保留“安装”和“文档”章节。安装命令必须使用当前完整版本标签，至少给出 Docker Hub 与 GHCR 镜像；如发布 `skills-full`，应明确变体。文档链接必须指向 `yideng966/LightAgent` 的当前有效页面。
- 创建标签前必须先运行 `python scripts/validate_release_notes.py --tag <完整标签> docs/releases/<完整标签>.md`，并人工预览 Markdown；校验通过且说明文件已进入待打标签的提交后，才能推送标签。不得先打标签、后在默认分支补说明。
- `deploy-image.yml` 只能由 `v*` 标签推送触发，不得开放 `workflow_dispatch` 或从仓库内旧版本文件推导正式镜像版本；`docker/metadata-action` 必须关闭隐式 `latest`，基础版与 `skills-full` 只能通过矩阵中显式的浮动标签发布，避免完整技能版覆盖基础版 `latest`；Docker 发布构建必须在安装 Python 后端前调用 `scripts/stamp_release_version.py`，使用当前发布标签同时更新 `cli/VERSION` 与 `pyproject.toml`，避免 CLI/Web 版本与 `pip show lightagent` 不一致。
- Docker 多架构发布必须使用原生 AMD64 与 ARM64 GitHub Hosted Runner 分架构构建，按 canonical digest 汇集后分别为 Docker Hub 和 GHCR 创建 manifest，不得回退到在 AMD64 Runner 上通过 QEMU 执行 ARM64 重依赖安装；跨版本缓存必须使用按 `variant + arch` 隔离且可跨 `v*` 标签复用的 Registry Cache，不能依赖不同标签不可互访的 GitHub Actions Cache；`latest` 默认保留微信群图片报告所需的 Playwright Chromium。
- GHCR 未标记版本清理必须作为独立任务，在基础版与完整技能版的全部 manifest 成功发布后执行；任一变体发布失败时必须跳过清理，禁止从并行变体任务中提前删除 canonical digest 或 attestation 子 manifest。
- Dockerfile 中系统、Python、Playwright Chromium、Node.js 与微信群 sidecar 依赖等稳定重层必须位于应用源码复制之前；普通源码或版本号变更不得使这些重层失去直接缓存命中，构建上下文不得包含测试、文档、计划、历史桌面端、运行日志或服务器访问信息。
- 发布脚本的成功路径必须兼容非 UTF-8 标准输出编码，不得因中文状态文本导致构建失败；Docker 多架构构建中的 APT 获取必须配置有限重试，但不得用 `--fix-missing` 或无限重试掩盖真实依赖错误。
- `release.yml` 只校验版本化发行说明并创建或更新同标签 GitHub Release，不得安装桌面依赖、编译 Electron、运行 PyInstaller 或上传桌面资产；Docker 镜像由独立的 `deploy-image.yml` 发布。
- 工作流重跑必须更新原 Release，不得创建重复版本。
- 用户仅要求提交、推送或创建标签时，以对应 Git 引用成功推送为完成条件；除非用户明确要求远端发布验收，否则不要持续轮询或等待 GitHub Actions、镜像构建及其他远端编译任务，也不得因此阻塞结果交付。只有用户明确要求远端发布验收时，才通过 GitHub API 或页面核对工作流终态、Release 和镜像产物。

## 修改原则

- 修改前先读当前文件，禁止凭记忆改代码。
- 遵守最小修改原则：只改让当前需求成立的必要文件。
- 不顺手重构无关代码；发现无关问题时在回复里单独说明。
- 用户要求修改 UI、页面、布局、交互或样式时，默认且仅修改 Web 控制台（`channel/web/chat.html`、`channel/web/static/js/console.js`、`channel/web/static/css/console.css` 等）；`desktop/` 已停止维护，不再承接 UI 需求。
- Web 控制台开关使用绝对定位伪元素绘制滑块时，定位上下文必须放在开关轨道本身；`chat.html` 中的 `console.js` / `console.css` 地址不得预置查询参数，缓存时间戳统一由 `ChatHandler` 注入，避免形成重复查询串并继续加载旧资源。
- 仅在新增或修改代码并提交/交付代码变更时，才同步更新根目录 `CHANGES.md`，记录本次修改日期、任务背景、关键改动文件和验证结果；纯文档、计划、规则、配置说明等非代码变更不更新 `CHANGES.md`。
- 提交 Git 代码变更时，必须将根目录 `AGENTS.md` 与 `CHANGES.md` 纳入同一次提交范围；提交前检查两者状态，确保规则说明与变更记录不会遗漏。
- 面向本项目的开发计划、迁移计划、实施方案和阶段性任务文档必须使用简体中文编写；如需引用英文 API、命令、路径或错误信息，保留原文即可。
- `plans/` 目录下的计划文件名称必须使用 `YYYYMMDD_中文名.md` 格式，文件名主体使用简体中文描述任务，不再使用英文任务名。
- 跟进开发计划文档进行开发时，开发完成后必须回写对应开发计划文档，更新已完成进度、实际改动、验证结果与剩余事项，确保计划状态与代码交付一致。
- 优先沿用现有工厂、单例、配置读取和日志模式。
- 不要把真实密钥、token、cookie、部署 ID 写入仓库。
- 修改跨渠道逻辑时，评估 Web、IM 和 CLI 是否都会受影响；归档的 `desktop/` 不再作为兼容目标。
- 修改 `config.py` 默认配置时，同步检查 `config-template.json`、Web 设置页、文档和相关测试。
- 修改模型路由时，同步检查 `Bridge`、`models/bot_factory.py`、`common/const.py`、Web 模型管理接口和测试。
- 通用文本推理必须通过共享 `TextModelRouter` 使用同一主备顺序与熔断状态；视觉、生图、Embedding、ASR、TTS 保持独立路由，新增标题、总结、判断、画像等无状态文本任务时使用统一 `complete()` 入口；同步无工具请求的空正文必须在当前候选链内故障转移，不得将 `reasoning_content` 当作最终正文，也不得通过备用 Provider 绕过安全拒绝或把空正文计入临时故障熔断。每个候选必须从路由前的不可变规范化源快照重新创建完整 `LLMRequest`，不得只深拷贝已组装成品，也不得共享可被前一候选或 Provider 适配器修改的 `messages`、工具 schema、请求选项或响应。
- Agent 流式 `content` 中的 `<think>...</think>` 必须跨 SSE 分片有状态解析并归一到独立思考流；IM 渠道不得发送或持久化块内思考及残余标签，Web 仅按思考开关展示思考流；标准 `reasoning_content` 必须继续与最终正文隔离。微信群必须按当前请求的 `channel_type` 完整缓冲候选，临时错误、空/未知工具名、损坏工具参数或清洗后确无可发送正文时才允许丢弃候选并从同一源快照切换；`</s>`、`</analysis>`、文本化空 `<tool_calls>` 等已知 Provider 控制块或标签残片应在当前候选内确定性清洗，只要清洗后仍有可发送正文，就必须接受当前候选并标记模型健康，不得因标签本身切换备用模型。无效候选不得进入 Agent 历史、工具执行或渠道事件；工具调用轮次的中间正文不得发送或回放。工具执行后优先通过内部 `lightagent_finish` 提交最终答复；模型返回普通纯文本时不得据此切换候选，首段文本必须隐藏且不进入事件、历史或 Provider continuation，再在当前健康候选链上追加一次临时最终答复提示并取消完成工具强制，重试仍可调用真实工具，只有重试结果才能交付；临时提示必须在调用后删除。不得用自然语言正则猜测并截取无标签思考。微信群无原生工具调用时接受普通纯文本最终答复，并仅兼容提取 `<final_response>`、`<send><message>...</message></send>`、`<send message="...">` 或 `<send>` JSON 中的字符串 `message`；Provider 路径、JSON 的 `path` 及其他字段不得访问或发送。微信群主模型和备用模型默认统一跟随 `enable_thinking`；携带当前图片或已匹配图片理解上下文的请求是受控例外，必须通过不可变请求源设置 `reasoning_effort=none`，并向全部候选发送 `disabled` 思考控制。思考可在模型内部发生但不得发送或持久化；自定义 OpenAI 兼容端点必须把 `enabled` 或 `disabled` 思考控制传到实际请求，端点明确拒绝该字段时不得删除字段后无控制重试。微信群内部协议 422 等技术错误不得原样发送：明确触发请求只返回简短用户提示，ambient 请求静默丢弃。
- 修改语音路由时，同步检查 `voice/factory.py`、`Bridge`、Web ASR/TTS 能力接口、控制台选择器和语音测试；`custom:<id>` 必须按显式能力复用对应自定义 Provider 的 Key/Base，不能隐式回退到当前聊天 Provider。
- 确定性生图等需要跨容器重建保留的用户产物必须默认写入 `agent_workspace`；Docker 生图目录固定在 `/home/agent/lightagent/images`（宿主机 `./data/images`），不得回退到随镜像更新且不挂载的 `/app/images`。Web SSE 发送本地生图时必须同时产生可访问的 `image` 事件和结束请求的 `done` 事件。
- 修改 Agent 工具时，同步检查工具注册、工具 schema、异常返回格式、文档和安全测试。
- Skill Hub 安装必须以签名索引和 SHA-256 为信任边界；后备源只能安装与已验证索引中来源身份和哈希一致的产物，不得用后备源自身返回的哈希建立信任。
- Hub 技能不得覆盖内置技能或非 Hub 同名技能；更新、回滚和卸载必须保持配置与用户数据分离，声明的普通依赖与带 SHA-256 的下载依赖在安装时自动处理。
- 原技能广场未提供结构化依赖时，只能通过代码内人工审核的兼容清单补充依赖；不得解析或执行 `SKILL.md` 中的任意安装命令，依赖安装失败时不得写锁文件或替换现有技能。
- 原技能广场在 Web 和 CLI 中仅作为只读目录与介绍页跳转来源，不得提供一键安装、在线更新或批量管理入口；历史已安装技能只保留彻底卸载能力。
- 技能隔离依赖只能根据 `skills.lock.json` 中已安装的安全技能名称注入子进程环境；Python/npm 依赖保持按技能目录隔离，npm 安装不得默认执行第三方生命周期脚本。
- 官方 Skill Hub 的仓库与 Pages 地址以 `xiaoguiwucan/LightAgent-SkillHub` 为准；修改 Registry 默认地址时必须同步检查配置模板、CLI、Web 入口、文档和签名索引构建配置。
- Web 在线技能库必须公开展示官方 Skill Hub 源码仓库、贡献指南和 Pull Request 入口，方便社区投稿与共同维护；这些链接必须使用公开 GitHub 地址，不得指向本地预览服务。
- Schema v2 脚本技能必须声明结构化 `lightagent.entrypoints` 并通过 `skill_run` 执行；不得让 Agent 通过 Bash/Python/Node 命令字符串绕过 Runner。
- Skill Runner 第一阶段只是受控子进程边界，并非完整文件系统或网络沙箱；文档和页面必须显示“Runner 兼容隔离”，不得夸大安全边界。
- 技能系统能力只能使用 `requirements.capabilities` 稳定名称声明，系统包只在 Docker 构建或管理员部署阶段准备；技能安装和运行时不得执行 `sudo`、`apt` 或 `brew`。
- `.laskill-backup` 只允许包含单个技能的配置和用户数据；备份口令不得记录或持久化，恢复必须校验认证标签、技能名和解压路径。
- Web 技能页不得直接展开完整在线技能目录；在线技能统一通过独立二级弹窗按搜索、分类和分页浏览，主页面只展示本地技能与内置工具，避免 Registry 增长后撑长页面。

## 安全边界

本项目直接触达文件系统、Shell、浏览器、网络、MCP 子进程和外部消息平台，安全改动必须保守。

- `agent/tools/web_fetch/`、`agent/tools/browser/`、`agent/tools/bash/`、`agent/tools/read/`、`agent/tools/write/`、`agent/tools/edit/` 是高风险区域。
- SSRF、路径穿越、任意命令执行、任意文件读写、重定向到内网地址等问题必须有测试覆盖。
- 已有安全回归测试包括 `test_security_ssrf_web_fetch.py`、`test_security_ssrf_path_traversal.py`、`test_security_ssrf_browser_navigate.py`。
- 不要默认放宽 URL、文件路径、命令执行或 Web 文件服务根目录限制。
- `web_file_serve_root`、`agent_workspace`、`mcp_servers`、`mcpServers` 等配置可能扩大访问面，改动时要明确风险。

## 编码与风格

- Python 代码保持现有风格，优先小函数、明确异常处理和 `common.log.logger` 日志。
- 仓库贡献规范要求 issue、PR 和代码注释尽量使用中文；新增代码注释也应优先中文。Git 提交说明（commit message）必须使用简体中文，清晰概括本次变更。
- 用户对话可以使用中文，但写入项目代码和面向国际社区的文档时遵循仓库既有语言策略。
- 避免引入新的全局依赖；确需新增依赖时，同步更新 `requirements.txt` 或 `requirements-optional.txt`，并说明原因。
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
- 群永久记忆的唯一 Web 管理入口是「管理 → 记忆 → 群记忆」；「管理 → 知识」只管理全局 Markdown 知识库，「群聊」不得再提供重复的群永久记忆管理入口。群友画像及自主学习保留在「群聊 → 群友画像」；完整上下文注入预览已删除，不得恢复其 UI、状态、自动成员加载或公开 API。
- 群记忆管理、上下文注入和 Agent 查询必须统一绑定当前 `stable_room_id`，只允许列出 `wechat_group_stable_room_ids`，不得回退展示 runtime 群快照；群记忆工具 schema 不得接收模型传入的 `room_id`。内部历史类名、配置键和数据库表名可为兼容保留 knowledge 命名，但不得据此把群永久记忆重新展示为知识。
- 微信群归档按群查询必须优先严格匹配 `stable_room_id`；只有归档记录自身未绑定稳定群 ID 时，才允许使用 legacy `room_id` 兼容读取，不得用无条件 `stable_room_id OR room_id` 扩大检索范围。
- 微信群会话作用域由 `wechat_group_session_scope` 控制，默认按 `stable_room_id + stable_member_id` 隔离；仅旧配置缺少新键且显式 `group_shared_session = true` 时一次性兼容映射为 `room`。不要通过提高同一共享会话的 `concurrency_in_session` 解决阻塞，以免引入会话历史和回复顺序竞争。
- 微信群上下文引擎固定为 V2，不再读取、保存或展示 `wechat_group_context_engine_mode`，也不得恢复 Legacy 运行分支。V2 必须区分 room timeline、owner session、Agent thread、request 和 Provider transport；`new_thread` 不得清空或推进旧 session 的 `context_start_seq`，其他渠道未传 `thread_id` 时必须保持旧 session 语义。
- room timeline、24 小时 rolling summary 和归档证据必须按当前 `stable_room_id` 汇集本群所有成员的安全公开消息；`stable_member_id` 只用于身份、权限、画像、owner session 和成员私有 Agent thread，不能用于缩小群级上下文查询。其他成员消息可以进入当前请求，但不得写入当前成员的私有 thread。
- V2 thread 固定只持久化用户原文和最终助手文本，工具原始消息、thinking、增强 Prompt、runtime ID 与媒体路径不得进入可恢复历史；原文持久化不再由用户配置关闭。
- V2 Agent turn 必须以 sidecar `send_result` 为两阶段提交边界：生成完成后只能写模型/Web 均不可见的 pending 行；仅确认 `sent` 后才允许确认 thread、记录已发送 assistant timeline、保存工具 continuation capsule、确认 Provider continuation anchor 并刷新 Agent 缓存。发送失败、未知、超时、清洗为空、静默或 stale 抑制必须删除本请求 pending 状态且不创建或续期 thread；不得把“已交给 sidecar”当作发送成功。
- V2 自由回复的 room revision stale 抑制只允许作用于明确分类为 `observe_only` 的 ambient 请求；入站过期量必须按当前 `stable_room_id` 查询快照游标后的实际消息记录，不得用全局自增游标差值代替，默认允许 5 条且只在超过 `wechat_group_free_reply_stale_message_tolerance` 时抑制。助手回复游标变化仍须立即抑制旧 ambient 候选；`new_thread`、`resume_thread` 及缺少 session action 的请求不得仅因生成期间出现后续群消息而静默丢弃，仍须按 room single-flight 和 `send_result` 确认边界完成发送。
- Provider continuation 只是可选传输优化，默认关闭；只有 Provider 明确实现 capability、请求构造、锚点提取和锚点失效分类合同时才允许启用。锚点必须按 stable account、room、member、owner session、thread、Provider、model、endpoint 和权限指纹严格隔离，失效后同候选只允许无锚点本地重放一次，主备 Provider 不得共用锚点。
- rolling summary、归档证据、工具续接和 Provider 续接必须可独立关闭；无法获得稳定 outbound message ID 时不得按相似文本伪造 quote-to-thread anchor。
- Web「群聊 → 拟人化」只保留真实生效的 V2 参数，采用单一页面主滚动；不得加入 `<details>/<summary>` 折叠区、引擎模式选择或完整上下文注入预览，不支持 Provider 续接时不得展示无效开关。
- 身份恢复必须按 stable account -> stable room -> stable member 的顺序确认；未确认 account 不得确认 room，未确认 member 不得写入管理员 stable 配置或继承敏感权限。
- legacy runtime room/member 如果在多个 stable account 下产生歧义，必须返回未解析并要求人工确认，不得按最近记录任取；在线成员解析应优先使用当前运行中 room 的 stable 映射。
- 通道层管理员硬门禁、V2 安全降级上下文、生图额度和 scheduler 会话都必须使用 stable scope；runtime 字段只用于微信真实发送和 legacy 快照。
- `wechat_group_voice_interaction_mode = ignore` 表示群语音在 sidecar 下载并由 Python 写入群归档后立即短路；`voice` / `audio` 都不得进入音频转换、ASR、自由回复、Agent、LLM、TTS 或发送链路。该模式不改变 sidecar 媒体下载和归档生命周期；如需做到侧车零下载，必须先单独规划配置同步与 JSON Lines 协议变更。
- 群画像自主进化调用 LLM 时必须先识别模型错误 envelope（如 `{"error": true, "status_code": 503}`），HTTP 408/429/5xx 等临时供应商故障不得继续当作画像 JSON 正文解析；失败记录应保留可读 HTTP 状态且不推进归档游标。
- GitHub 仓库事件通知属于 Webhook 到微信群的固定消息投递适配：配置 UI 放在「群聊 -> 基础设置」，只接收配置仓库并按事件/action 规则筛选，目标群只能使用已选择的 `wechat_group_stable_room_ids`；Webhook 必须先做 HMAC-SHA256 验签和 delivery 去重，配置 API 不得回显真实 Secret，`LIGHTAGENT_GITHUB_WEBHOOK_SECRET` 存在时优先于本地配置；通知只能读取代码内白名单字段，不得保存或转发原始 payload、评论正文和 Secret 扫描敏感内容，也不得进入 LLM、Agent、归档、记忆或画像链路。
- 微信群成员进出事件必须通过 sidecar `room_join` / `room_leave` JSON Lines 事件接入，只对已选择且身份确认的 `wechat_group_stable_room_ids` 生效；机器人自身加入不欢迎自身，自身离群不尝试向原群发送，离群成员不得 mention。成员事件直接使用非阻塞渠道发送，不得构造聊天 `Context` 或进入 Bridge、Agent、插件、归档、记忆、画像和报告链路。
- 入群欢迎与离群通知的全局开关默认开启，Web“群聊 -> 进退群消息”必须分别提供开关并保存到 `config.json`；旧配置缺少开关字段时按开启处理，但显式 `false` 与按群 `disabled` 必须继续优先生效。
- wechat4u 已识别入群事件但未解析出成员 ID 时，sidecar 必须保留 runtime 群与事件时间并显式标记成员信息缺失；Python 仅可在稳定账号、稳定群和已选群门禁通过后发送不带 mention 的配置欢迎内容，模板成员名使用“新成员”、人数按 1 处理。离群成员 ID 缺失时继续 fail closed，不得发送无法确认对象的离群通知。
- 进退群文本模板只允许代码内白名单占位符做字面替换，不得执行表达式或暴露 runtime/stable ID、微信号、加入方式和离群原因；配置图片必须位于 `agent_workspace/images/wechat_group_membership`，上传、预览、保存和发送都要校验目录边界、大小、扩展名与 Pillow 实际格式。
- 群聊报告的统计、报告 revision、预览、投递、定时任务和日报记忆必须按 `stable_room_id` 隔离；legacy runtime 群只在身份服务明确确认的历史别名范围内兼容，禁止无条件按 `stable_room_id OR room_id` 扩大范围。
- 群聊报告仅复用现有归档、`TextModelRouter`、scheduler 和 Wechaty sidecar；群内手动生成必须经过通道、Tool 和 Prompt 三层管理员门禁，Web 预览和发送必须经过 Web 登录鉴权。
- 报告图片默认输出到 `agent_workspace/images/wechat_group_reports`，Docker 对应 `/home/agent/lightagent/images`；`image_preferred` 仅在图片尚未被确认发送且失败可判定时回退文字，`delivery_unknown` 或已有图片分片成功时不得补发全文。
- 报告链接抓取必须始终使用严格 SSRF 校验并逐跳校验重定向；自定义文字模板只允许白名单字段，不得执行表达式、访问本机文件或扩大 Web 文件服务根目录。
- Web 手动发送必须绑定当前群、当前报告且已完成的 `preview_id`；确认后的文字分段或 PNG 是不可变投递快照，已确认图片发送失败应保留失败状态并允许重试，不得发送用户未预览的文字回退。
- 默认 `wechat-group-report-cyber-intelligence` 是仓库随附的受控模板，工作区同名旧 Skill 不得覆盖其版本和视觉资源；其他自定义图片模板仍按普通 Skill 发现规则处理。
- 报告任务和投递轮询触发 Web 控制台重绘时必须保留当前报告滚动位置；连接状态只用于实时提示和服务端投递门禁，不能以过期离线快照禁用已完成预览后的发送动作。

1. 优先查看 `channel/wechat_group/wechat_group_channel.py`、`wechat_group_client.py`、`wechat_group_message.py`、`protocol.py` 和 `channel/wechat_group/sidecar/wechaty-sidecar.mjs`。
2. 扫码入口必须在通道管理中完成：`通道管理 -> 接入通道 -> 个人微信群`，由界面展示二维码；不要把“看日志扫码”作为主要交互路径。
3. Web 控制台入口涉及 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`；归档的桌面端不再同步接入能力。
4. 微信群回复 @ 用户时，正文不要手工拼接普通文本 `@昵称` 或 `@@id`；应将发送者 ID 作为 `mention_ids` 传给 sidecar，并由 Wechaty `room.say(text, ...mentions)` 执行真实 mention。
5. sidecar 只有在目标成员存在可读群昵称时才能执行 mention；昵称仍是十六进制成员编码、`wxid_` 或其他内部 ID 时必须丢弃 mention，并清除正文开头的不可读 ID 后直接发送正文。
6. sidecar 与 Python 之间只通过 JSON Lines 协议通信。新增事件或命令时，先更新 `protocol.py`，再同步 Python client、channel 和 `wechaty-sidecar.mjs`，并补充对应测试。
7. Wechaty 登录态、媒体目录等运行数据必须放在仓库外的数据目录，不能写入 Git 跟踪内容；新增 npm 依赖时同步检查 `channel/wechat_group/sidecar/package.json` 与 lock 文件。
8. 涉及群选择时优先使用 `wechat_group_stable_room_ids` 做精确限制；`wechat_group_room_ids` 只保留为 runtime legacy 快照；`group_name_white_list: ["ALL_GROUP"]` 只适合开发测试，不应作为长期生产默认。
9. 修改后至少运行 `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`。涉及二维码、连接状态或通道页时，在 Web 控制台完成对应验证。
10. 外部真实链路仍需手动验证：启动后打开通道管理，选择“个人微信群”，扫码登录，在目标群 @ 机器人确认能收到回复，并确认回复真实 @ 到发送者。

### 个人微信群 LLM 请求上下文链路

当前个人微信群通道不是替代 LightAgent 原有 Agent 主链路，而是在通用 `ChatChannel` 上下文构造之后叠加微信群专属上下文，再进入 `Channel.build_reply_content()` 和 `Bridge.fetch_agent_reply()`。

当前链路分为两层：第一层是 `Context` 元数据，用于服务端路由、权限和持久化判断；第二层是追加到当轮 `context.content` 前面的 prompt 块，用于让 LLM 理解微信群现场。两层都只服务当前请求，不能把微信群通道扩展成独立 Agent。

核心路径：

1. `WechatGroupChannel.handle_text()` 把 sidecar 消息包装为 `Context`。
2. `WechatGroupChannel._compose_context()` 先调用 `super()._compose_context()`，继续执行原 `ChatChannel` 群白名单、触发词、@ 去除、`session_id`、`receiver` 和插件事件逻辑。每个 `Context` 实例必须有独立 `kwargs`，不能复用可变默认字典，避免调度任务、自由回复等标记污染后续消息。
3. 微信群通道随后写入服务端元数据，例如 runtime/stable account、room、member 身份，`wechat_group_user_content`、`wechat_group_trigger_source`、`wechat_group_owner_session_id`、`wechat_group_thread_id`、`wechat_group_session_action`、`wechat_group_agent_history_mode`、`request_id` 和 `intent_requires_scheduler`。其中 `wechat_group_user_content` 必须保存用户原文，用于后续原文持久化。
4. `_record_inbound_message()` 先把本轮消息写入归档；随后 `WechatGroupHumanizedContextBuilder` 构造 prompt 时必须用 `exclude_message_id` 排除本轮消息，避免把用户刚问的问题当成证据。
5. 微信群通道通过 `WechatGroupHumanizedContextBuilder` 在 `context.content` 前追加微信群专属上下文，包括 `<wechat-group-admin-policy>`、`<wechat-group-mention-verification>`、`<wechat-group-reply-policy>`、`<wechat-group-persona>`、`<wechat-group-rolling-summary>`、`<recent-wechat-group-transcript>`、按需的 `<wechat-group-archive-evidence>`、`<wechat-group-focus>`、`<wechat-group-memory>`、安全工具续接、`<wechat-group-style>`、`<wechat-group-reference-policy>` 与 `<wechat-group-multimodal>`。
6. Builder 会把不可变 RequestSnapshot 和注入结果回填到 `context` 元数据，例如 `wechat_group_context_mode`、room revision、来源事件计数、rolling summary revision、`wechat_group_archive_evidence_injected`、`wechat_group_recent_context_injected`、`wechat_group_memory_injected`、`wechat_group_multimodal_diagnostics` 和 `wechat_group_multimodal_matched_images`，供发送复核、去重、诊断和测试使用。
7. `ChatChannel._generate_reply()` 调用 `super().build_reply_content(context.content, context)`。
8. 当 `agent` 配置为 `true` 时，`Channel.build_reply_content()` 进入 `Bridge.fetch_agent_reply()`，由 Agent 模式请求 LLM。
9. `AgentBridge` 固定使用 `wechat_group_user_content` 预持久化用户原文；`new_thread` 使用新的成员私有 thread，`resume_thread` 只恢复同 stable room/member 已确认的 active thread，`observe_only` 不读取或推进交互 thread。内部 `fresh / interactive_session / observe_only` 只负责兼容 Agent 执行历史，不改变 V2 thread 所有权。
10. TextModelRouter 默认每轮从不可变请求源重建完整本地 messages；只有显式支持且开启的 Provider adapter 才可附加远端续接锚点。最终非工具响应消费完成后只暂存 pending anchor，仍需微信确认发送成功后才能提交。

按意图注入历史的规则：

- `WechatGroupContextPolicy` 固定选择 `minimal / recent / contextual / recall` 深度；这些是 V2 内部策略，不是用户可选引擎。确定性命令使用 minimal，普通 direct 和 ambient 使用 recent，引用机器人、图片、多模态、明确继续和上下文短问句使用 contextual，显式总结或历史回溯使用 recall。
- recent transcript、rolling summary 和 archive evidence 的查询作用域始终是当前 `stable_room_id` 下所有成员的安全消息，并排除当前 `message_id`；当前发言人的 stable member 不能成为群级消息过滤条件。recent、summary、archive 和当前成员 thread 必须按 `source_event_id` 去重。
- V2 原文窗口固定由 policy 控制：minimal 最多 4 条/10 分钟，recent 最多 12 条/30 分钟，contextual 最多 24 条/2 小时，recall 最多 20 条/24 小时，并各自受字符预算约束；不得恢复全局“最近条数/分钟”配置。
- recent、contextual 和 recall 可以注入当前群最近 24 小时 rolling summary，minimal 不注入。摘要从最多 500 个安全事件重建并保留最新 12 条原文尾部，最多 1200 字符；超过 1 小时未刷新视为不可用，生成失败不得阻塞当前回复或推进摘要 revision。
- `<wechat-group-archive-evidence>` 仅在 recall 或明确语义需要时读取当前稳定群的相关旧证据，默认限制 90 天、12 条和统一字符预算；不得用固定厚历史替代相关性检索，也不得混入已被 recent、summary 或 thread 覆盖的来源事件。
- 普通 `free_reply` 与 direct 共用 V2 recent + 可用 rolling summary，但不自动打开 archive evidence 或旧焦点；其他成员刚刚说过的话属于群现场，可以进入本轮上下文，但不会写入触发成员的私有 Agent thread。
- 自由回复本地判定必须先分析近场收件人关系。“另一名群友刚陈述结果 -> 当前成员发无明确对象的短问句”命中 `likely_human_followup` 后硬抑制，Scorer、legacy Judge、active/crazy 档位均不得覆盖；“大家/谁能/有没有人”等明确开放群问题和明确机器人目标除外。
- Scorer 与兼容 Judge 只能读取统一的安全近场投影：actor 使用当轮 opaque token，正文清洗并截断，不得携带 stable/runtime ID、XML、媒体路径、完整 URL 参数或原始 quote payload。
- Builder 异常时只能降级为 V2 最小安全上下文：保留权限、收件人、回复策略、人设、用户原文以及当前 stable room 最近 4 条/10 分钟安全事件；不得切换 Legacy、恢复废弃配置或读取其他群。

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

  <wechat-group-rolling-summary>
  当前 stable_room_id 内所有成员最近 24 小时、排除最新原文尾部后的安全滚动摘要；有 freshness、来源事件和字符预算约束。
  </wechat-group-rolling-summary>

  <recent-wechat-group-transcript>
  当前 stable_room_id 所有成员的有界最近群聊原文，窗口由 V2 policy 决定；排除当前消息以及已由摘要或当前成员 thread 覆盖的来源事件。
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

  <wechat-group-multimodal>
  当前图片、引用图片、视频、转发或链接等多模态上下文摘要。真实 media_path 只传给 Vision 或相关服务，不写入 prompt。
  </wechat-group-multimodal>

  用户本次去掉开头 @ 后的真实问题
```

增强块只进入当前轮 LLM 请求。`AgentBridge` 固定只把用户原文写入 V2 可恢复 thread，避免上一轮 `<wechat-group-*>` 块污染下一轮历史；该行为不再提供关闭配置。这里的“用户原文”指 `_compose_context()` 增强前写入 `context["wechat_group_user_content"]` 的文本，通常是去掉开头 @ 后的真实问题。

4.3 群永久记忆与群友画像的注入规则：

- 当前群记忆按 `scope_type = wechat_group`、`scope_id = room_id`、`channel_type = wechat_group` 召回，只允许进入当前群回复。
- 当前发言人的群友画像按 `scope_type = wechat_group_member_profile`、`scope_id = room_id`、`subject_id = sender_id`、`channel_type = wechat_group` 召回。
- 本次发言被 @ 的群友画像从 `at_list` 中排除机器人自身和当前发言人后召回；首轮只处理明确 @ 到的成员，不把普通文本昵称匹配作为强需求。
- 群友画像 prompt 中的 `reply_name`、`primary_nickname` 和 `aliases` 必须优先使用当前 `room_id` 的群昵称或当前群 name record；不得把其他群学到的别名回退注入当前群回复。
- `wechat_group_profile_get` 等 Agent 画像工具必须由服务端绑定当前 `room_id`；查询、精确读取和列表模式都只能返回当前群画像，不能接受模型传入的跨群 room 参数。
- 群友画像不是多条零散记忆拼接；每个 `stable_room_id + stable_member_id` 最多注入一份当前生效画像，历史版本和来源只用于审计。
- 所有群记忆和画像召回必须先按 `stable_room_id` 或 `stable_room_id + stable_member_id` 强过滤，再排序；legacy runtime 字段只能用于兼容回查，不允许跨群泄露。
- 群记忆显式查询必须应用真实相关性分数和 `min_score`，无相关结果返回空；最近记忆只能通过明确的 recent 读取策略使用，不得作为显式查询的无命中兜底。
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

### 个人微信群自由回复链路

- 自由回复负责判断普通非 @ 群消息“要不要接话”。默认配置 `wechat_group_free_reply_enabled = false`，只有开启后且当前群命中 `wechat_group_free_reply_stable_room_ids`（或迁移期 legacy runtime 快照）时，普通非 @ 文本才会进入自由回复判定；`wechat_group_free_reply_names` 只用于发现待确认候选，不得直接放行自由回复。
- 单群自由回复档位使用 `wechat_group_free_reply_stable_room_activity_levels` 按 `stable_room_id` 精确覆盖；未配置单群档位时回退全局 `wechat_group_free_reply_activity_level`，再回退 `normal`。runtime room ID 和群名不得作为新映射键；四套 `wechat_group_free_reply_profiles` 仍为全局共享参数，群只选择档位，不复制或覆盖 profile 数值。
- 任意群成员真实 @ 机器人且去除机器人 @ 前缀后文本精确等于“闭嘴”时，通道必须静默消费命令，并按当前 stable room 暂停普通自由回复；稳定群不可用时才回退 runtime room。禁言时长读取 `wechat_group_free_reply_mute_minutes`（默认 10 分钟，范围 1–1440）；`wechat_group_free_reply_mute_mentions_enabled` 默认关闭，开启后禁言有效期内的新 @ 消息也必须静默忽略，但引用和拍一拍不受影响。命令识别必须先于 @ 禁言门禁，本地评分和 worker 最终放行处也必须检查禁言状态，确保重复命令可续期并避免已排队候选延迟发言。
- 普通非 @ 文本先经过 `evaluate_wechat_group_free_reply()` 本地评分、群范围、冷却、小时上限、连续上限、低信息和风险抑制；本地通过后进入 `WechatGroupFreeReplyWorkerPool`，再由 `WechatGroupFreeReplyJudge` 做轻量 LLM JSON 二次判定。
- 自由回复 LLM Scorer 必须复用共享 `TextModelRouter.complete()`，并通过 Web 控制台「模型管理 -> LLM Scorer」能力卡单独选择 Provider 和模型；微信群通道只负责提示词装配、严格 JSON 解析与失败回落，不得维护独立 API Base、API Key、超时、Temperature 或模型 HTTP 调用。
- Scorer 显式选择的 `custom:<id>` 不存在或缺少 API Base 时必须失败闭合，不得隐式回退到主聊天 Provider；自定义 Provider 被 Scorer 使用时，Web 模型管理必须阻止删除并提示先切换 Scorer Provider。模型管理更新凭据并重置共享 Router 后，Scorer 下一次请求必须重新获取当前 Router，不得长期持有旧 Bot 或旧凭据。
- Scorer 为旁路 `below_threshold` 保存的候选必须保留介入前的 `local_rule_triggered`；Scorer 失败且允许规则回落、旧 LLM Judge 又关闭时，只能恢复该本地判定，不得把原本低于阈值的消息直接放行。
- Scorer 的请求级禁用思考只能覆盖当前调用，不得修改全局思考配置；OpenAI-compatible Provider 可使用白名单 JSON Mode 参数，其他 Provider 必须依赖严格 JSON Prompt、解析校验和失败回落，UI 与文档不得宣称所有 Provider 都原生支持同一种结构化输出参数。
- 自由回复 worker 必须按 `room_id` 做短暂防抖和 pending 合并；同一群窗口内只把最新普通候选送入 LLM judge，不同群互不影响。不要在候选入队时提前写入已回复冷却，冷却应在 worker 判定通过并进入回复上下文后记录。
- worker 判定通过后，通道用 `wechat_group_force_reply = true` 重新走 `_compose_context()` / `produce()`，绕过通用群聊“必须 @ / 前缀 / 关键词”的过滤，但最终回复仍复用 `ChatChannel`、`Bridge` 和 Agent 主链路。
- 默认生图触发词必须保守；不要使用 `看`、`找` 这类容易命中“看看”“找到”“找不到”等普通群聊文本的单字前缀，避免自由回复候选被误转成 `ContextType.IMAGE_CREATE`。
- 确定性 `ContextType.IMAGE_CREATE` 请求必须保留去前缀后的 `wechat_group_user_content` 原文并绕过文本型 V2 上下文增强；报告、权限和其他文本门禁只能扫描该原文，不能扫描包含 rolling summary、人设或近期群聊的增强 Prompt，避免生图被误判为群聊报告。
- 自由回复发送时设置 `suppress_mention = true` 和 `no_need_at = true`，因此默认不真实 mention 原发送者；@ 机器人或引用机器人回复仍走直接回复链路，不进入自由回复 worker。
- 模型判断当前消息并非在问机器人且无需接话时，相关内部判断只能表示静默，不能作为普通文本发到群里。发送层短文本兜底至少要覆盖“没/未 @ 我、不是在问我”与“不用/无需插嘴、接话、回复、回应”等组合，并保留正常长文本解释不会被误拦截的回归测试。
- 微信群不再维护独立情绪状态、时段主动性规则或打字延迟，也不向当前消息注入情绪块；自由回复只能由现有本地规则、Scorer、兼容 Judge 和 worker 决定。后续若要扩大主动发言能力，必须先更新本节规则和对应计划文档，并补充防刷屏、跨群隔离和 @ 必回不受影响的回归测试。

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
- Agent 模式不得把微信群增强后的 `context.content` 持久化为历史；预持久化、V2 pending turn 和运行后内存清洗都固定使用 `context["wechat_group_user_content"]` 原文，不再提供持久化增强 query 的回退配置。
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

桌面端归档边界：

1. `desktop/` 只保留历史源码，不再新增功能、修复问题或同步后端能力。
2. GitHub Actions、发布验证和用户安装说明不得重新引入桌面编译或安装包。
3. `app.py` 是独立的 Python 后端主入口，继续正常开发、运行和发布。

## 前端 UI 开发规则

所有 UI 需求落在 Web 控制台，主要文件是 `channel/web/chat.html`、`channel/web/static/js/console.js` 与 `channel/web/static/css/console.css`。优先沿用现有结构、组件、语义颜色、交互状态和响应式布局；修改后执行 JavaScript 语法检查，并按影响范围使用 `python app.py` 完成真实页面验证。

### 微信群机器人 UI 边界

- 阶段一只做最小运维面板：启用/停用、扫码状态、二维码、刷新群列表、选择目标群、保存配置、最近事件和错误提示。
- 阶段一的二维码必须嵌入通道接入流程，不再要求用户从后端日志复制扫码链接。
- 不在阶段一实现完整社交工作台、群统计、群记忆编辑、群友记忆编辑、战报、图片库或备份导入 UI。
- 微信群机器人设置应优先复用渠道页/设置页现有模式；如果 UI 改动范围过大，先保证配置文件、状态接口和日志可用，再单独规划 UI 小阶段。

## 验证策略

优先运行与改动直接相关的最小测试，再按风险扩大范围。

- 纯文档：检查文档是否能直接指导开发，无需运行测试。
- 配置/路由：运行对应 `tests/test_*` 单测。
- 微信群通道：运行 `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`；涉及 Web 通道接入或二维码弹窗时，再启动 `python app.py` 完成页面验证。
- 安全相关：运行相关安全回归测试，必要时新增测试。
- 跨模块核心逻辑：运行 `python -m unittest discover -s tests`。

如果无法运行测试，必须在交付说明中写明原因和未验证风险。

## 交付说明要求

最终回复应说明：

- 改了哪些文件。
- 为什么这样改。
- 做了什么验证。
- 如果存在未验证项，明确列出原因。

不要声称“已修复”“已通过”而没有对应命令或检查结果。
