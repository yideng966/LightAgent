# 微信群自由回复图片理解开发计划

## 目标

在 Web 控制台「群聊 / 图片与生图」页面增加「启用自由回复图片理解」开关，并在后台支持非 @ 图片消息经过自由回复门控和大模型判定后，再复用现有图片理解能力生成回复。

## 设计原则

- 默认关闭，避免升级后自动增加视觉模型调用成本。
- 先门控、后识图：只有自由回复候选通过本地评分、队列和大模型判定后，才调用 `Vision().execute()`。
- 复用现有 `<wechat-group-image>` 上下文、图片摘要缓存、自由回复队列和回复发送链路。
- 不改变现有 @ 图片必答、@ 文本识图、引用图片识图和最近图片识图逻辑。
- 自由回复图片回复不强制 @ 发送者，保持当前自由回复语义。

## 涉及文件

- `config.py`：新增默认配置 `wechat_group_free_reply_image_understanding_enabled`。
- `config-template.json`：同步新增配置模板。
- `channel/web/web_channel.py`：把新配置暴露到微信群 `extra.image`，允许 Web 保存，并按布尔值归一化。
- `channel/web/static/js/console.js`：在「图片与生图」面板新增开关、读写新字段、补充中英文文案。
- `channel/wechat_group/wechat_group_channel.py`：让非 @ 图片在开关开启时进入自由回复候选；自由回复通过后再生成图片理解上下文。
- `tests/test_wechat_group_channel.py`：覆盖默认关闭不触发、开启后先入队、通过判定后才调用视觉工具并产出自由回复上下文。
- `tests/test_wechat_group_web.py`：覆盖 Web extra、保存配置和控制台字段。
- `CHANGES.md`：记录本次代码变更和验证结果。

## 任务清单

- [x] 确认现有相关测试基线：`python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_free_reply`。
- [x] 编写失败测试：Web 配置暴露/保存/控制台字段。
- [x] 编写失败测试：非 @ 图片默认关闭时仍不进入自由回复。
- [x] 编写失败测试：开关开启后非 @ 图片进入自由回复队列，但不在入队前调用视觉工具。
- [x] 编写失败测试：Worker/LLM 批准后调用图片理解，并产出 `wechat_group_free_reply_triggered` 与 `wechat_group_image_understanding_triggered` 上下文。
- [x] 实现默认配置、模板配置和 Web 配置读写。
- [x] 实现 UI 开关和中英文文案。
- [x] 实现后台非 @ 图片自由回复门控与批准后识图。
- [x] 运行相关单测并修复失败。
- [x] 更新本计划实际进度和 `CHANGES.md`。
- [x] 检查 git diff，提交并推送。

## 实际改动

- 新增 `wechat_group_free_reply_image_understanding_enabled` 配置，默认关闭。
- Web 控制台「群聊 / 图片与生图」新增「启用自由回复图片理解」开关，并接入 `/api/channels` 读取与保存。
- 非 @ 图片在开关关闭时保持旧行为；开关开启后先通过自由回复本地规则、队列和大模型判定，批准后才调用现有视觉工具。
- 自由回复图片上下文复用 `<wechat-group-image>`，并保留 `suppress_mention` / `no_need_at` 的自由回复行为。

## 验证结果

- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_non_at_image_message_is_archived_without_reply_context tests.test_wechat_group_channel.WechatGroupChannelTest.test_non_at_image_message_queues_free_reply_when_image_switch_enabled tests.test_wechat_group_channel.WechatGroupChannelTest.test_worker_approved_image_free_reply_injects_vision_summary tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_lists_wechat_group_as_qr_channel tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_image_config tests.test_wechat_group_web.WechatGroupWebTest.test_console_contains_wechat_group_image_settings`：通过。
- `python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_free_reply`：89 个测试通过。
- `node --check .\channel\web\static\js\console.js`：通过。

## 验证命令

```powershell
python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_free_reply
```

如只验证 Web 配置和 UI 字段：

```powershell
python -m unittest tests.test_wechat_group_web
```

如只验证微信群渠道逻辑：

```powershell
python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_free_reply
```
