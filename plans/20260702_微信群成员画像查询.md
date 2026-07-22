# 微信群群友画像手动录入检索计划

## 背景

当前 Web 控制台“群聊 -> 永久记忆 -> 群友画像”手动新增画像时，需要直接录入 `sender_id`。实际运维时管理员更容易记住微信 ID 或昵称，因此需要在录入画像前支持检索并回填成员信息。

## 目标

- 在当前选中 `room_id` 下，支持按微信 ID / sender ID / 昵称检索群友。
- 从检索结果中选择成员后，自动回填画像表单的 `sender_id` 与昵称。
- 保留手动输入兜底，不阻断未知成员或历史归档中不存在的成员。

## 最小实现方案

1. 后端复用 `WechatGroupArchive` 的 `wechat_group_messages` 归档表作为检索源。
   - 按 `room_id` 强过滤，避免跨群泄露。
   - 从历史消息中聚合 `sender_id` 与 `sender_nickname`。
   - 支持 `q` 同时匹配 `sender_id`、昵称以及后续可能扩展的微信 ID 字段。
2. 在 `WechatGroupMemoriesHandler.GET()` 增加 `members` 子动作。
   - 路径形态：`/api/wechat-group/memories/members?room_id=...&q=...`
   - 返回：`{"status":"success","members":[{"sender_id":"...","sender_nickname":"...","last_seen_at":...,"message_count":...}]}`
3. 前端在群友画像表单顶部增加一个检索输入框与结果列表。
   - 输入微信 ID / sender ID / 昵称后点击搜索。
   - 点击结果回填 `groups-memory-profile-sender-id` 与 `groups-memory-profile-nickname`。
   - 空结果时展示明确提示，仍允许手动录入。
4. 补充测试。
   - `WechatGroupArchive`：按群、关键字、去重和排序检索成员。
   - `WechatGroupMemoriesHandler`：`members` API 调用归档检索并返回 JSON。
   - `test_wechat_group_memory_ui.py`：确认 UI 暴露检索入口、API 路径和回填函数。

## 不做项

- 不新增实时 Wechaty 群成员枚举协议。
- 不改 sidecar JSON Lines 协议。
- 不把其他群成员或全局联系人用于当前群画像检索。
- 不强制移除手动 `sender_id` 输入能力。

## 验证命令

```powershell
python -m unittest tests.test_wechat_group_memory_ui tests.test_wechat_group_web
python -m py_compile channel\wechat_group\wechat_group_archive.py channel\web\web_channel.py tests\test_wechat_group_web.py tests\test_wechat_group_memory_ui.py
node --check .\channel\web\static\js\console.js
```

## 待确认

已确认并按“先基于聊天归档检索已发言成员”的方案完成实现。

## 实施结果

- 已在 `WechatGroupArchive` 中新增 `list_members()`，按当前 `room_id` 从归档消息聚合群友信息。
- 已在 `WechatGroupMemoriesHandler` 中新增 `members` GET 子动作，路径为 `/api/wechat-group/memories/members`。
- 已在 Web 控制台群友画像表单顶部新增群友检索输入、结果列表和一键回填。
- 已保留原手动 `sender_id` 输入，不阻断归档中不存在的群友。
- 已同步更新 `console.js` 缓存版本和 `CHANGES.md`。

## 验证结果

```powershell
python -m unittest tests.test_wechat_group_context.WechatGroupRecentContextTest.test_archive_lists_members_by_room_and_query
python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_wechat_group_memory_members_api_uses_archive
python -m unittest tests.test_wechat_group_memory_ui.WechatGroupMemoryUiTest.test_groups_page_exposes_memory_management_section
python -m unittest tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_memory_ui
node --check .\channel\web\static\js\console.js
python -m py_compile channel\wechat_group\wechat_group_archive.py channel\web\web_channel.py tests\test_wechat_group_context.py tests\test_wechat_group_web.py tests\test_wechat_group_memory_ui.py
python -m unittest tests.test_wechat_group_web
python -m py_compile channel\web\web_channel.py
python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_memory_ui
```

以上命令均已通过。

## 剩余事项

- 真实微信群链路仍需手动验证：启动 Web 控制台，进入“群聊 -> 永久记忆 -> 群友画像”，选择已有聊天归档的群，输入昵称或 `sender_id` 检索并确认回填结果。
- 当前方案只覆盖已在当前群归档中出现过的成员；未发言或未归档成员仍需手动输入 `sender_id`。
