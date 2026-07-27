# 微信群引用机器人消息触发开发计划

## 背景

个人微信群通道当前只把真实 `@` 识别为必回触发。微信客户端支持“引用回复”机器人发出的消息，但 Wechaty 标准 `Message.text()` 会把引用消息降级成普通文本，当前 sidecar 没有把底层引用元数据传给 Python。

## 目标

当群成员引用机器人自己发出的消息并回复时，CowAgent 将该消息按“被 @”同等处理，进入原有必回链路；普通引用其他人的消息不触发该行为。

## 方案

1. 在 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs` 新增纯函数解析 raw wechat4u `appmsg type=57` 的 `refermsg`。
2. 在 `channel/wechat_group/sidecar/wechaty-sidecar.mjs` 收到群消息时，通过 `state.bot.puppet.messageRawPayload(message.id)` 读取 raw payload，解析 `refermsg.fromusr`。
3. 当 `refermsg.fromusr === self.id` 时，上报 `is_quote_self: true` 与 `quote` 摘要字段；失败时降级为空，不影响原消息链路。
4. 在 `WechatGroupMessage` 中保存 `is_quote_self` 和 `quote`。
5. 在 `WechatGroupChannel.handle_text()` 中把 `is_at or is_quote_self` 作为直接回复触发条件，绕过自由回复评分。
6. 补充 Node 和 Python 回归测试，覆盖引用机器人、引用他人、解析失败降级和通道触发路径。

## 影响范围

- 修改 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`
- 修改 `channel/wechat_group/sidecar/wechaty-sidecar.mjs`
- 修改 `channel/wechat_group/wechat_group_message.py`
- 修改 `channel/wechat_group/wechat_group_channel.py`
- 修改 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`
- 修改 `tests/test_wechat_group_message.py`
- 修改 `tests/test_wechat_group_channel.py`
- 更新 `CHANGES.md`

## 验证计划

- `node --test .\wechaty-sidecar-core.test.mjs`，在 `channel/wechat_group/sidecar` 目录执行。
- `node --check .\wechaty-sidecar.mjs`
- `node --check .\wechaty-sidecar-core.mjs`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile channel\wechat_group\wechat_group_message.py channel\wechat_group\wechat_group_channel.py`

## 执行状态

- [x] 计划已创建
- [x] sidecar 引用消息解析测试已补充
- [x] sidecar raw refermsg 解析已实现
- [x] Python 消息字段与通道触发测试已补充
- [x] Python 消息字段与通道触发已实现
- [x] CHANGES 已更新
- [x] 验证已完成
- [x] Git 提交与推送已完成

## 实际改动

- `wechaty-sidecar-core.mjs` 新增 `extractQuotedMessageFromRawPayload()`，解析 wechat4u raw `appmsg type=57` 中的 `refermsg`，仅在 `refermsg.fromusr` 与当前机器人 ID 完全一致时标记 `is_quote_self`。
- `wechaty-sidecar.mjs` 在收到群消息时读取 `messageRawPayload(message.id)`，把 `is_quote_self` 与引用摘要透传给 Python。
- `WechatGroupMessage` 保存 `is_quote_self` 与 `quote` 字段。
- `WechatGroupChannel` 将 `is_quote_self=True` 的消息视为直接触发，并设置 `wechat_group_force_reply`，避免被通用引用文本过滤逻辑跳过。
- `ChatChannel` 的引用文本过滤保留原行为，但允许微信群强制回复上下文通过。

## 验证结果

- `node --test .\wechaty-sidecar-core.test.mjs`
- `node --check .\wechaty-sidecar.mjs`
- `node --check .\wechaty-sidecar-core.mjs`
- `python -m py_compile channel\chat_channel.py channel\wechat_group\wechat_group_message.py channel\wechat_group\wechat_group_channel.py`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

## 剩余事项

- 需要在真实微信群中手动验证：机器人发言后，群成员引用该消息回复，确认 sidecar 上报 `is_quote_self=true` 且 CowAgent 进入必回链路。

## 风险与回退

- 风险：真实微信 raw payload 中 `refermsg.fromusr` 与 `self.id` 可能格式不一致。实现仅在完全匹配时触发，避免误触发。
- 回退：删除新增 `is_quote_self` 解析与 Python 判断后，原 `@` 触发链路不受影响。
