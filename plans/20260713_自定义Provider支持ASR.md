# 自定义 Provider 支持 ASR 实施计划

## 一、任务背景

当前实例把 `voice_to_text` 配置为 `custom:a838bee2`，但语音工厂只支持内置 Provider，导致语音消息进入 `Bridge.fetch_voice_to_text()` 后返回：

```text
Unsupported voice_to_text provider: custom:a838bee2
```

用户要求让现有 `custom:<id>` 自定义 Provider 支持 ASR。目标是复用 `custom_providers` 中已保存的 `api_key` 与 `api_base`，按已验证的音频协议调用自定义网关，同时保持 CowAgent 现有跨渠道语音主链路不变。本计划交付时曾误把范围收缩为仅保留 ASR；后续已确认 Custom TTS 也属于真实需求，并由 `plans/20260714_自定义Provider支持TTS.md` 单独恢复。

## 二、已确认现状

1. `models/custom_provider.py` 已集中管理 `custom_providers`，但现有 `resolve_custom_credentials()` 只根据聊天配置 `bot_type` 解析，不能安全解析独立的 `voice_to_text=custom:<id>`。
2. `voice/factory.py` 当前对任何 `custom` / `custom:<id>` 都抛出 `UnsupportedVoiceProviderError`。
3. `Bridge.get_bot()` 创建 ASR 实例时没有把能力类型传给语音工厂，需要显式区分自定义 ASR，并继续拒绝自定义 TTS。
4. Web 模型管理接口会把 `custom:<id>` 标为无效 ASR Provider，保存接口也会拒绝它。
5. Web 模型选择器已经支持自由输入模型名，但当前会回退展示自定义 Provider 的聊天模型；ASR 场景不能默认复用聊天模型。
6. 当前实例的 `voice_to_text_model=mimo-v2.5`。自定义网关 `/models` 的只读结果没有发现名称含 `whisper`、`transcribe` 或 `asr` 的模型，因此尚未确认该网关实际可用的 ASR 模型 ID。
7. OpenAI 官方文档 MCP 已注册，但当前会话无法热加载；官方文档网页请求也返回 403。本计划仅采用仓库现有 OpenAI/智谱语音实现共同使用的兼容契约，不扩展未验证参数。
8. 2026-07-13 使用本地合成的 `hello world` 短 WAV 做了真实网关探测：`mimo-v2.5-free` 存在于 `/models`，但请求 `/audio/transcriptions` 返回 HTTP 404、`bad_response_status_code/openai_error`，没有转写文本。
9. 同一端点使用 `whisper-1` 返回 HTTP 503、`new_api_error/model_not_found`，明确提示默认分组没有该模型的可用渠道。这证明网关识别 `/audio/transcriptions` 路由，但当前分组没有已验证可用的 ASR 模型；`mimo-v2.5-free` 不能替代 ASR 模型。
10. `TeleAI/TeleSpeechASR` 真实请求 `/audio/transcriptions` 返回 HTTP 200，本地合成的 `hello world` 被识别为 `Hello, world`。

## 三、目标与边界

### 3.1 本次目标

- 允许 `voice_to_text=custom:<id>` 选择已配置的自定义 Provider。
- 使用该 Provider 的 `api_key`、`api_base` 请求 `POST {api_base}/audio/transcriptions`。
- 以 `multipart/form-data` 提交 `file` 与 `model`，从 JSON 响应的 `text` 字段读取转写结果。
- ASR 模型必须来自 `voice_to_text_model`，不得回退到自定义 Provider 的聊天默认模型。
- Web 控制台可选择现有自定义 Provider 并输入 ASR 模型名，保存后立即刷新 Bridge 语音缓存。
- 未找到 Provider、缺少 Key/Base/模型、HTTP 错误、非 JSON 或缺少 `text` 时安全失败，不泄露密钥和完整响应敏感信息。

### 3.2 不在本次范围

- 不猜测 `mimo-v2.5` 能执行语音识别。
- 不新增独立于 `ChatChannel` / `Bridge` 的微信群 ASR 链路。
- 不修改语音触发、@、自由回复、会话或 Agent 逻辑。
- 不为 `custom:<id>` 新增 TTS 能力，现有内置 TTS Provider 行为保持不变。
- 不自动安装 `ffmpeg`，该依赖问题单独处理。

## 四、协议确认结果

推荐按以下 OpenAI-compatible 契约实施：

```text
POST {custom.api_base}/audio/transcriptions
Authorization: Bearer {custom.api_key}
Content-Type: multipart/form-data

file=<audio binary>
model=<voice_to_text_model>
```

成功响应：

```json
{"text": "转写内容"}
```

实施前确认项已完成：

1. 自定义网关是否确实兼容上述端点与响应结构。真实探测已确认网关能够路由该端点，但成功响应仍需有效 ASR 渠道验证。
2. 该网关真实可用的 ASR 模型 ID；`mimo-v2.5` 与 `mimo-v2.5-free` 均不能继续作为 ASR 假设。

## 五、设计方案

### 5.1 显式解析自定义 Provider

在 `models/custom_provider.py` 增加按显式 `custom:<id>` 解析 Provider 的只读函数，返回对应配置或明确的未找到结果。保留现有 `resolve_custom_credentials()` 行为，避免影响聊天模型路由。

### 5.2 新增自定义语音适配器

新增 `voice/custom/custom_voice.py`：

- 继承 `Voice`，构造时接收显式 Provider 标识。
- 通过集中解析器读取 Key/Base，不复制配置查找逻辑。
- 检查文件、Key/Base 与 `voice_to_text_model`。
- 使用连接/读取超时调用 `/audio/transcriptions`。
- ASR 返回 `ReplyType.TEXT` 或 `ReplyType.ERROR`。
- 日志只记录 Provider ID、模型、HTTP 状态和截断后的安全错误摘要，不记录 Key、音频正文或完整本机路径。

### 5.3 让语音工厂感知能力

给 `create_voice()` 增加可选能力参数。`Bridge.get_bot()` 创建 ASR 时传入 `voice_to_text`：

- `custom:<id> + voice_to_text`：创建自定义 ASR 适配器。
- `custom:<id> + text_to_voice`：继续返回不支持错误。
- 所有内置 Provider 保持现有行为。

### 5.4 Web 能力与保存校验

修改 `ModelsHandler`：

- ASR Provider 列表追加已配置的 `custom:<id>` 卡片。
- 当前 `custom:<id>` 只有在 Provider 存在且 Key/Base 完整时才视为有效。
- `_set_asr()` 接受存在的自定义 Provider，并要求非空 ASR 模型。
- 未知 ID、缺少 Key/Base 或模型时，在任何配置写入前拒绝。
- `provider_models.custom=[]`，让前端直接展示自定义模型输入，不把聊天模型当成 ASR 推荐值。
- TTS Provider 列表和保存校验保持现状，不追加 `custom:<id>`。

## 六、预计修改文件

- 修改：`models/custom_provider.py`
- 新增：`voice/custom/__init__.py`
- 新增：`voice/custom/custom_voice.py`
- 修改：`voice/factory.py`
- 修改：`bridge/bridge.py`
- 修改：`channel/web/web_channel.py`
- 修改：`channel/web/static/js/console.js`
- 修改：`tests/test_custom_provider.py`
- 修改：`tests/test_voice_factory.py`
- 新增：`tests/test_custom_voice.py`
- 修改：`tests/test_models_handler.py`
- 修改：`tests/test_models_console.py`
- 修改：`CHANGES.md`
- 回写：本计划文档

## 七、测试方案

### 7.1 自定义 Provider 解析

- 精确解析存在的 `custom:<id>`。
- 未知 ID 不回退到当前聊天 Provider或 legacy Key。
- 不在异常与日志中暴露 Key/Base。

### 7.2 ASR HTTP 适配

- 请求 URL、Bearer Header、`file`、`model` 和超时正确。
- 成功 JSON `text` 转为 `ReplyType.TEXT`。
- 缺少配置、空文本、HTTP 4xx/5xx、超时、非 JSON 安全返回错误。

### 7.3 Factory 与 Bridge

- `custom:<id>` 仅在 `voice_to_text` 能力下创建自定义语音适配器，`text_to_voice` 继续拒绝。
- 未声明语音能力的旧工厂调用仍保持拒绝，避免隐式扩大行为。
- Web 保存后 `refresh_voice()` 清除旧缓存并使用新 Provider。

### 7.4 Web 能力

- 已配置自定义 Provider 出现在 ASR 列表并可保存。
- 未知、缺 Key/Base、缺模型时无配置副作用。
- 自定义 TTS 仍不可保存。
- API 响应不包含密钥与 Base URL。

### 7.5 验证命令

```powershell
python -m unittest tests.test_custom_provider tests.test_custom_voice tests.test_voice_factory tests.test_models_handler tests.test_models_console tests.test_wechat_group_web
python -m unittest tests.test_audio_convert tests.test_chat_channel_voice tests.test_wechat_group_message tests.test_wechat_group_channel
node --check .\channel\web\static\js\console.js
python -m unittest discover -s tests
git diff --check
```

真实链路还需使用已确认的 ASR 模型，在目标微信群发送短语音，确认出现转写文本且不再出现 `Unsupported voice_to_text provider`。

## 八、实施状态

- [x] 完成日志、配置、语音工厂、自定义 Provider 与 Web 能力现状核查。
- [x] 完成 OpenAI 官方文档通道检查；记录当前会话 MCP 不可热加载及网页 403 限制。
- [x] 只读检查当前自定义网关模型列表，未发现可直接识别的 ASR 模型名。
- [x] 真实探测确认网关识别 `/audio/transcriptions`，但当前分组没有已验证可用的 ASR 模型。
- [x] 验证 `mimo-v2.5-free` 不能用于当前 ASR 端点。
- [x] 用户确认采用 OpenAI-compatible 转写契约进行探测。
- [x] 用户确认真实 ASR 模型 `TeleAI/TeleSpeechASR`，真实转写成功。
- [x] 实现自定义 ASR 代码与定向测试。
- [x] 运行实例 Web ASR 闭环成功。
- [x] 更新 README、`CHANGES.md` 与本计划实际结果。
- [x] 全量自动化回归完成，762 个测试通过；重启后的 9901 Web ASR 完整闭环通过。
- [x] 2026-07-14 拆分提交阶段误撤回自定义 TTS 增量；后续确认并非用户真实意图，转由 `plans/20260714_自定义Provider支持TTS.md` 恢复。
- [ ] 在真实目标微信群发送语音，人工确认微信侧收取、转写和文本回复。
