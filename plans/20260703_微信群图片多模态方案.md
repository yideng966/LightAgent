# 微信群图片理解与生图限流开发计划

> 本计划只论证开发方案，不执行代码开发。计划文档依据当前仓库代码编写，后续实施时需按任务逐步更新本文状态、实际改动、验证结果与剩余事项。

## 目标

1. 微信群内用户发送图片并直接触发机器人时，机器人能理解图片内容，并将图片理解结果注入当前回复上下文，必要时对图片做简短评论。
2. 微信群内用户提出生图请求时，继续复用既有 Agent、`ContextType.IMAGE_CREATE`、模型路由或 `skills/image-generation` 能力生成图片，并能发送回原群。
3. 微信群生图必须有每小时生成上限，且该上限可在 Web 控制台 UI 中配置。
4. 不新增独立图片理解模型调用器，不新增独立生图框架，不绕过 CowAgent 既有 `ChatChannel`、`Bridge`、`Agent`、工具、技能和回复发送链路。

## 当前代码事实

- `channel/wechat_group/sidecar/wechaty-sidecar.mjs` 当前 `handleMessage()` 固定发送 `message_type: "text"`，没有下载图片，也没有向 Python 传递 `file_path`。
- `channel/wechat_group/wechat_group_message.py` 已经能把 `"image"` 映射为 `ContextType.IMAGE`，并读取 `file_path` 到 `media_path` / `content`，但目前 sidecar 没有提供这些字段。
- `channel/chat_channel.py` 对 `ContextType.IMAGE` 的默认行为只是写入 `common.memory.USER_IMAGE_CACHE`，不会自动进入 LLM 上下文。
- `channel/wechat_group/wechat_group_channel.py` 已有微信群专属 `_compose_context()`，会在文本上下文前注入人设、最近群聊、群记忆块，是插入图片理解块的合适位置。
- `agent/tools/vision/vision.py` 已提供本地图片和 URL 图片理解能力，支持多 Provider fallback、SSRF 防护和本地图片 base64 转换。
- `skills/image-generation/SKILL.md` 已提供图像生成/编辑技能；`channel/web/web_channel.py` 的模型配置能力也已有 image capability。
- `ChatChannel._compose_context()` 已根据 `image_create_prefix` 将文本生图请求转换为 `ContextType.IMAGE_CREATE`；多个模型 Bot 已支持 `IMAGE_CREATE` 返回 `ReplyType.IMAGE_URL`。
- 微信群通道 `send()` 已支持 `ReplyType.IMAGE` / `ReplyType.IMAGE_URL` 并调用 `WechatGroupClient.send_image()`；sidecar 已把 `send_image` 复用为 `FileBox.fromFile(...)` 发送。
- Web 控制台 `/api/channels` 的 `ChannelsHandler` 已有 `wechat_group` extra 配置、保存分支和 `console.js` 的微信群设置面板。

## 推荐方案

### 方案 A：通道层预理解图片，再走既有 LLM 链路（推荐）

微信群收到图片后，sidecar 下载图片到 `wechat_group_media_dir`，Python 层识别为 `ContextType.IMAGE`。当该图片消息是 @ 机器人或引用机器人时，微信群通道调用既有 `Vision` 工具得到图片摘要，然后构造一条文本上下文：

```text
<wechat-group-image>
图片文件: <本地路径>
发送者: <sender_id / nickname>
视觉摘要: <Vision 工具返回内容>
</wechat-group-image>

用户附带文本或默认问题
```

随后仍走 `WechatGroupChannel._compose_context()`、`ChatChannel._generate_reply()`、`Channel.build_reply_content()`、`Bridge.fetch_agent_reply()`。这样图片理解结果能稳定进入上下文，直接评论也由主 LLM/Agent 生成，不在微信群通道里重写对话逻辑。

优点：确定性强；非 Agent 模式也可拿到视觉摘要；完全复用 `Vision` 工具和主回复链路。  
缺点：每次触发图片理解都会额外调用一次视觉模型，需要配置启停与失败降级。

### 方案 B：只把图片路径注入 Agent，让 Agent 自行调用 `vision` 工具

微信群通道只注入图片路径和提示，实际是否调用 `vision` 由 Agent 决定。

优点：通道层更薄，最大化复用 Agent 自主工具调用。  
缺点：无法保证每次图片都被理解；非 Agent 模式不生效；用户要求“直接评论图片”时稳定性较差。

### 方案 C：在微信群通道内新建图片理解/生图服务

通道层直接接各 Provider 的多模态/生图 API。

优点：短期可控。  
缺点：明显重复造轮子，绕开现有工具、技能、Provider fallback 和安全处理，不符合项目边界。

结论：采用方案 A。方案 B 可作为未来优化项，方案 C 不采用。

## 配置设计

新增配置键放在根配置，与现有 `wechat_group_*` 保持一致：

- `wechat_group_image_understanding_enabled`: 默认 `true`。是否在直接触发机器人时理解微信群图片。
- `wechat_group_image_understanding_comment_enabled`: 默认 `true`。纯图片 @ 机器人时是否让机器人基于图片摘要直接评论。
- `wechat_group_image_understanding_prompt`: 默认 `"请简洁描述这张图片中的关键信息，并指出可能需要回复的内容。"`。
- `wechat_group_image_understanding_cache_minutes`: 默认 `30`。同一图片消息的视觉摘要缓存时间，避免重复触发。
- `wechat_group_image_create_hourly_limit`: 默认 `5`。每个已接入微信群每小时最多成功受理的生图请求数；`0` 表示关闭微信群生图。

保留现有全局配置：

- `image_create_prefix` 继续决定哪些文本前缀触发生图。
- `skills.image-generation.{provider,model}` 继续决定 Agent 技能生图路由。
- `text_to_image` / `rate_limit_dalle` 继续服务普通 Bot 的旧生图链路。

## 数据流设计

### 图片理解入站

1. sidecar 判断 Wechaty 消息类型。
2. 若为图片，下载到 `media_dir/<room_id>/<message_id>.<ext>`，输出 JSON Lines 事件：

```json
{
  "type": "message",
  "message_type": "image",
  "file_path": "D:/.../media/room@@abc/msg-1.jpg",
  "text": "",
  "room_id": "room@@abc",
  "sender_id": "wxid_alice",
  "is_at": true
}
```

3. `WechatGroupMessage` 继续使用现有映射转为 `ContextType.IMAGE`。
4. `WechatGroupChannel.handle_text()` 扩展为支持图片直接触发；非 @ 图片默认只归档，不主动消耗视觉模型。
5. 微信群通道调用 `agent.tools.vision.vision.Vision.execute()`，复用现有本地图片处理、Provider fallback 和安全策略。
6. 将视觉摘要封装为 `<wechat-group-image>` 块，再作为文本上下文进入现有 `_compose_context()`。
7. 回复仍由既有 `Bridge` / `Agent` 生成，发送仍走 `WechatGroupChannel.send()`。

### 生图出站

1. 用户在微信群发送符合 `image_create_prefix` 的文本，例如 `画 一只赛博牛`。
2. `ChatChannel._compose_context()` 继续转为 `ContextType.IMAGE_CREATE`。
3. `WechatGroupChannel` 在进入生成前检查 `wechat_group_image_create_hourly_limit`。
4. 未超限时继续走既有 `super()._generate_reply()`，由 Agent 技能或 Bot 生图链路生成 `ReplyType.IMAGE_URL` / 图片文件。
5. 超限时直接返回 `ReplyType.ERROR` 或 `ReplyType.TEXT`，说明当前群本小时生图额度已用完。
6. 微信群 `send()` 继续使用 `send_image()` 发回原群。

## 限流设计

首版使用 SQLite 持久化计数，复用 `WechatGroupArchive` 所在数据目录，避免重启绕过小时限制。

新增表建议：

```sql
CREATE TABLE IF NOT EXISTS wechat_group_image_create_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  room_id TEXT NOT NULL,
  sender_id TEXT,
  prompt TEXT,
  status TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
```

计数规则：

- 统计窗口：`created_at >= 当前时间 - 3600`。
- 范围：按 `room_id` 计数。
- 只在请求被受理时写入 `status='accepted'`；失败请求可写 `status='failed'` 供诊断，但不计入额度。
- `wechat_group_image_create_hourly_limit = 0` 时直接拒绝微信群生图。
- UI 限制输入范围建议 `0..100`。

## UI 设计

只修改 Web 控制台，不修改桌面端。

落点：

- `channel/web/web_channel.py`
  - `_wechat_group_extra()` 返回图片理解和生图限流配置。
  - `_apply_wechat_group_config()` 允许保存新增配置，并做类型归一和范围裁剪。
- `channel/web/static/js/console.js`
  - 在现有微信群设置面板增加“图片与生图”区域。
  - 控件包括：图片理解开关、纯图片评论开关、图片理解提示词、视觉摘要缓存分钟数、生图每小时上限。
  - `saveWechatGroupSettings()` 将新增字段提交到 `/api/channels`。
- `channel/web/static/css/console.css`
  - 仅在现有样式不足时补最小样式；优先复用现有 Tailwind/class 模式。

## 预计修改文件

- `config.py`：新增默认配置。
- `config-template.json`：同步新增配置模板。
- `channel/wechat_group/sidecar/wechaty-sidecar.mjs`：识别图片消息、下载媒体文件、输出 `message_type` / `file_path`。
- `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`：抽出媒体类型判断和安全文件名逻辑，便于 Node 单测覆盖。
- `channel/wechat_group/protocol.py`：若需要新增媒体字段说明或 helper，在这里补充；不改变 JSON Lines 基本协议。
- `channel/wechat_group/wechat_group_message.py`：补充图片消息字段解析测试驱动下的最小适配。
- `channel/wechat_group/wechat_group_channel.py`：支持 `ContextType.IMAGE` 的触发、视觉摘要注入、生图限流检查。
- `channel/wechat_group/wechat_group_archive.py`：新增生图使用记录表和计数方法。
- `channel/web/web_channel.py`：新增配置读取、保存和接口返回。
- `channel/web/static/js/console.js`：新增 UI 控件和保存逻辑。
- `tests/test_wechat_group_message.py`：覆盖图片事件解析。
- `tests/test_wechat_group_channel.py`：覆盖图片理解上下文注入、非 @ 图片不触发、限流拒绝、未超限放行。
- `tests/test_wechat_group_web.py`：覆盖新增配置出现在 extra 且可保存。
- `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`：覆盖媒体类型判断、文件名规整、图片下载命令输出。
- `CHANGES.md`：实施代码变更时再更新；本计划文档本身不更新。

## 分阶段实施计划

### 阶段 1：补齐微信群图片入站

- 增加 Node 侧媒体类型识别与图片下载。
- 保证下载目录来自 `wechat_group_media_dir` 或默认 `~/.cow/wechat_group/media`，不写入仓库。
- Python 侧确认 `WechatGroupMessage` 对 `message_type="image"`、`file_path`、`content` 的解析稳定。
- 验证：图片事件可被归档，非 @ 图片不会触发 LLM。

### 阶段 2：图片理解上下文注入

- 新增小型适配函数，只负责调用既有 `Vision` 工具并格式化 `<wechat-group-image>` 块。
- 修改 `WechatGroupChannel.handle_text()`，对直接触发的图片生成文本上下文。
- 视觉失败时降级为文本提示，不阻断群聊主流程。
- 验证：@ 图片后进入 `produce()` 的 context 包含 `<wechat-group-image>`、图片路径和视觉摘要。

### 阶段 3：微信群生图限流

- 在 `WechatGroupArchive` 增加按 room 统计最近 1 小时生图受理次数的方法。
- 在微信群通道生成前检查 `wechat_group_image_create_hourly_limit`。
- 超限回复明确提示，不调用下游生图 Provider 或技能。
- 验证：额度内调用原链路；额度外不调用原链路并返回提示。

### 阶段 4：Web 控制台配置

- 在微信群配置 extra 中返回新增配置。
- 在微信群设置 UI 增加“图片与生图”配置区。
- 保存时同步写入 `config.json`。
- 验证：GET 能看到默认值，POST 后 `conf()` 和文件配置都更新。

### 阶段 5：联调与文档回写

- 运行最小相关测试。
- 手动验证真实微信群：扫码登录，目标群 @ 机器人发图片，确认能评论图片；发送生图请求，确认额度内出图、额度外拒绝。
- 开发完成后回写本计划的实际改动、验证结果和剩余事项，并更新 `CHANGES.md`。

## 验证命令

Python 最小回归：

```powershell
python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web
```

sidecar 单测：

```powershell
Set-Location -LiteralPath .\channel\wechat_group\sidecar
npm test
```

如 UI 改动影响 Web 控制台静态资源，运行相关 Python Web 测试；本任务默认不修改桌面端，因此不需要 `desktop npm run build`。

真实链路手动验证：

1. 启动 CowAgent。
2. 打开 Web 控制台 `通道管理 -> 接入通道 -> 个人微信群`。
3. 扫码登录，选择目标群并保存。
4. 在目标群 @ 机器人发送图片，确认收到基于图片内容的回复。
5. 在目标群发送生图请求，确认生成图片能回到原群。
6. 连续触发生图直到超过 UI 配置的每小时上限，确认后续请求被拒绝且不调用生图链路。

## 非目标

- 不新增完整社交工作台、图库、图片审核后台或复杂素材管理。
- 不修改桌面端 Electron UI。
- 不新增新的图片理解 Provider 或生图 Provider。
- 不绕过 `Bridge.fetch_agent_reply()`、`agent/tools/vision` 或 `skills/image-generation`。
- 不把微信群图片内容写入长期记忆；如未来要做图片记忆，应另行设计隐私、容量和召回策略。

## 风险与缓解

- Wechaty 不同 puppet 的图片下载 API 可能有差异：优先在 sidecar 封装媒体下载，失败时发送 `error` 事件并保留文本链路。
- 视觉模型调用成本较高：默认只处理直接触发机器人的图片，且增加摘要缓存。
- 本地媒体文件可能膨胀：首版只放到外部数据目录；后续可单独计划清理策略。
- 生图返回远程 URL 时，`FileBox.fromFile` 可能无法直接发送：实施时需确认 `send_image()` 对 `file://`、本地路径、HTTP URL 的兼容；必要时只做最小下载到媒体目录后发送。

## 实施回写

### 实际改动

- `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`、`wechaty-sidecar.mjs`：新增媒体类型识别、媒体文件名规整和图片下载到外部媒体目录，并在消息事件中上报 `message_type` 与 `file_path`。
- `channel/wechat_group/wechat_group_channel.py`：支持直接触发的微信群图片消息；调用既有 `agent.tools.vision.vision.Vision` 生成视觉摘要，按图片路径和提示词缓存摘要，再把 `<wechat-group-image>` 块作为文本上下文送入既有回复链路；对 `ContextType.IMAGE_CREATE` 增加每群每小时限流。
- `channel/wechat_group/wechat_group_channel.py`：根据真实群聊验证补齐“回复引用图片，再 @ 机器人识别这张图”的文本识图链路；文本触发时会优先使用引用消息指向的图片，引用 ID 查不到时按引用发送者匹配当前群最近图片，最后才回退到当前群 10 分钟内最近一张已归档图片。
- `channel/wechat_group/wechat_group_archive.py`：新增 `wechat_group_image_create_usage` 表、记录方法和最近 1 小时计数方法。
- `config.py`、`config-template.json`、`channel/web/web_channel.py`、`channel/web/static/js/console.js`：新增微信群图片理解、纯图片评论、视觉摘要缓存分钟数和生图每小时上限配置；Web 控制台新增“图片与生图”设置区并保存到既有 `/api/channels`。
- `tests/test_wechat_group_channel.py`、`tests/test_wechat_group_web.py`、`channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`：覆盖图片上下文注入、非 @ 图片不触发回复、视觉摘要缓存、生图限流记录、Web 配置读写和 sidecar 媒体路径安全。

### 验证结果

- `python -m unittest tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_context`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `npm test`（在 `channel/wechat_group/sidecar` 目录）
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_text_image_request_uses_recent_group_image`
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_text_image_request_prefers_quoted_image`
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_text_image_request_uses_quoted_sender_when_quote_id_missing`

### 剩余事项

- 未执行真实微信群手动联调；仍需扫码登录后在目标群验证 @ 图片评论、生图返回和超额拒绝。
- 未单独增强 `send_image()` 对远程 HTTP 图片 URL 的兼容；当前仍沿用既有 `WechatGroupClient.send_image()` / sidecar 发送链路，真实 Provider 返回远程 URL 时需实测确认。
- 媒体文件清理策略不在本次范围内；图片会保存到配置的数据目录，后续如容量增长明显再单独设计清理任务。
