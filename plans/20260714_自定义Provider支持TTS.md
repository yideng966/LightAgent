# 自定义 Provider 支持 TTS 实施计划

## 一、任务背景

仓库曾在未提交工作树中实现 `custom:<id>` TTS，但在 2026-07-14 拆分提交前被误撤回，最终提交仅保留了自定义 ASR。当前运行配置仍可能使用 `text_to_voice=custom:<id>`，后端会把它标记为无效 Provider，Web 控制台因此持续显示错误提示。

用户现已明确确认：自定义 Provider 必须同时支持 ASR 与 TTS，并要求完成代码、验证、提交和推送。

## 二、已验证协议

### 2.1 通用 OpenAI-compatible TTS

- 端点：`POST {api_base}/audio/speech`
- 鉴权：`Authorization: Bearer {api_key}`
- 请求字段：`model`、`input`、`voice`、`response_format`
- 默认输出格式：`mp3`
- 成功响应：二进制音频

OpenAI 官方文档 MCP 已在本机注册，但当前会话未暴露对应调用工具；官方网页抓取返回 403。本次通过 OpenAI OpenAPI 镜像文档核对上述字段，并与仓库现有 `OpenaiVoice` 实现交叉验证。

### 2.2 MiMo TTS

- 匹配模型：`mimo-v2.5-tts*`
- 端点：`POST {api_base}/chat/completions`
- 待合成文本放入 `assistant` 消息
- `audio` 指定 `format=wav` 与 `voice`
- 成功响应：`choices[0].message.audio.data` 中的 base64 WAV

该契约已通过 Context7 的 Xiaomi MiMo 官方文档镜像核对，并与仓库现有 `MimoVoice` 实现交叉验证。

## 三、实施范围

1. 扩展 `CustomVoice`，恢复通用 TTS 与 MiMo TTS，并保持现有自定义 ASR 行为。
2. 让 `voice.factory.create_voice()` 和 `Bridge.get_bot()` 按显式能力创建 Custom TTS。
3. 让 `ModelsHandler` 对凭据完整的 `custom:<id>` 正确反显、保存和热刷新 TTS 配置。
4. Web 控制台在 Custom TTS 没有预置音色目录时仍显示自定义 voice 输入。
5. 补充运行时、后端和 UI 回归测试；错误日志不得泄露 Key/Base，JSON 错误不得保存为音频文件。
6. 更新 `README.md`、`AGENTS.md` 与 `CHANGES.md`。

## 四、范围边界

- 不新增独立于 `Bridge` 的语音链路。
- 不修改桌面端 Electron UI。
- 不自动迁移或清空现有语音配置。
- 不为未知私有 TTS 协议增加猜测性分支；非 MiMo 模型统一按 OpenAI-compatible `/audio/speech` 处理。
- 不改动当前工作树中与本任务无关的微信群协议、sidecar 和模型控制台测试修改。

## 五、验证计划

```powershell
python -m unittest tests.test_custom_voice tests.test_voice_factory tests.test_models_handler
python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_models_console_surfaces_invalid_voice_provider_warning
python -m unittest tests.test_chat_channel_voice tests.test_wechat_group_channel
node --check .\channel\web\static\js\console.js
python -m compileall voice bridge channel\web
git diff --check
```

如当前环境能安全访问已配置的真实自定义 TTS 网关，再补一次最小真实合成验证；否则保留真实微信群语音回复为人工验证项。

## 六、实施状态

- [x] 核对当前代码、Git 历史和撤回记录。
- [x] 核对 OpenAI-compatible 与 MiMo TTS 协议。
- [x] 实现 Custom TTS 运行时与路由。
- [x] 实现 Web 能力配置与自定义音色输入。
- [x] 补充自动化测试。
- [x] 更新项目文档与变更记录。
- [x] 完成自动化验证。
- [x] 完成提交并推送。

## 七、实际改动

- `voice/custom/custom_voice.py`：增加通用 `/audio/speech` MP3 与 MiMo `/chat/completions` WAV 合成，补充错误响应识别、WAV 校验、临时文件落盘和日志脱敏。
- `voice/factory.py`、`bridge/bridge.py`：显式传递 `text_to_voice` 能力并创建 `CustomVoice`。
- `channel/web/web_channel.py`：Custom TTS 参与能力反显、Provider 列表与保存校验。
- `channel/web/static/js/console.js`：Custom TTS 没有预置音色目录时默认展示自定义 voice 输入。
- `tests/test_custom_voice.py`、`tests/test_voice_factory.py`、`tests/test_models_handler.py`、`tests/test_wechat_group_web.py`：覆盖协议、路由、持久化与 UI 状态。
- `README.md`、`AGENTS.md`、`CHANGES.md` 及历史计划：更新能力说明并纠正此前误撤回记录。

## 八、验证结果

- 定向运行时与后端：40 个测试通过。
- Web 状态定向：1 个测试通过。
- 语音、模型管理与微信群相关回归：260 个测试通过。
- 全量 Python 回归：772 个测试通过。
- JavaScript 语法、Python 编译和 `git diff --check` 通过。

## 九、剩余事项

- 当前 `127.0.0.1:9901` 已有实例监听，为避免打断微信群登录态，本次未主动重启。
- 部署或重启到本提交后，需要在目标微信群触发一次语音回复，确认真实自定义网关合成及微信侧发送闭环。
