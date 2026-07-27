# 微信群运行时群友画像昵称兜底计划

## 背景

当前微信群运行时 `<wechat-group-memory>` 只会根据真实微信 `@` 解析出的 `at_list` 注入被 @ 群友画像。用户在群里常见表达是“@机器人 某某 是什么人”，其中“某某”只是正文昵称，不会进入 `at_list`，因此不会命中已维护的群友画像。

## BaiLongmaPro 对照结论

BaiLongmaPro 的运行时命中链路有两个关键点：

- `wechaty-duty-group.js` 中 `getMentionedGroupMembers()` 先用 `message.mentionList()` 解析真实 @；如果解析为空，会从原始文本里的 `@昵称` 做兜底，避免完全依赖 Wechaty 结构化 mention。
- `wechat-groups.js` 每轮都会调用 `getWeChatGroupMemoryContext({ groupId, senderId, senderName, query: text })`，而 `wechat-group-memory.js` 会同时查当前群本地群记忆、群友记忆、成员身份别名、FTS/语义聊天记录和最近聊天记录。

CowAgent 本次先做最小可控修复：不引入 BaiLongmaPro 的完整 identity/FTS/语义聊天记录体系，只修正“`at_list` 为空时跳过昵称画像兜底”的问题。

## 目标

- 保持真实 `at_list` 优先，继续按 `room_id + sender_id` 精确隔离读取画像。
- 当过滤后的真实被 @ 成员为空时，无论原始 `at_list` 是否为空，都从当前群 active 群友画像中按昵称做唯一精确兜底。
- 唯一命中时注入 `[mentioned_profile ... matched_by="nickname"]`。
- 多个画像同名、未命中或画像功能关闭时不自动注入，返回可诊断的 `filtered_reasons`。

## 不做项

- 不解析图片/OCR。
- 不使用大模型猜测昵称。
- 不做模糊匹配、拼音匹配或跨群联系人检索。
- 不改变 sidecar JSON Lines 协议。

## 实施步骤

1. 在 `tests/test_wechat_group_memory.py` 增加 RED 用例：
   - 机器人 ID 是唯一真实 `at_list` 项。
   - 当前群存在 `sender_nickname="粉嘟嘟."` 的 active profile。
   - query 包含“粉嘟嘟. 是什么人”。
   - 期望注入 `matched_by="nickname"` 的 `mentioned_profile`。
2. 增加歧义用例：
   - 当前群存在两个相同昵称 active profile。
   - query 命中该昵称。
   - 期望不注入画像，并返回 `nickname match ambiguous: <nickname>`。
3. 在 `channel/wechat_group/wechat_group_memory.py` 中实现最小 helper：
   - 当前群列出 active member profiles。
   - 从 metadata 的 `sender_nickname` 做规范化精确包含匹配。
   - 排除当前发言人、机器人和已真实 @ 过的 sender_id。
4. 运行相关验证并回写本计划与 `CHANGES.md`。

## 验证命令

```powershell
python -m unittest tests.test_wechat_group_memory
python -m unittest tests.test_wechat_group_context
python -m py_compile channel\wechat_group\wechat_group_memory.py tests\test_wechat_group_memory.py
```

## 实施结果

- 已在 `WechatGroupMemoryService.preview_prompt_memories()` 中保持真实 `at_list` 优先。
- 已新增昵称兜底：当过滤后没有真实群友 ID 时，无论 `at_list` 是否为空，都会按当前群 active 群友画像的 `sender_nickname` 做唯一精确匹配。
- 唯一命中时注入 `[mentioned_profile sender_id="..." matched_by="nickname"]`。
- 同名多画像时不注入，并返回 `nickname match ambiguous: <nickname>`。
- 未做 OCR、模糊匹配、跨群联系人检索或 sidecar 协议变更。

## 验证结果

```powershell
python -m unittest tests.test_wechat_group_memory.WechatGroupMemoryServiceTest.test_preview_injects_unique_profile_by_nickname_when_only_bot_is_mentioned tests.test_wechat_group_memory.WechatGroupMemoryServiceTest.test_preview_skips_nickname_profile_when_match_is_ambiguous
python -m unittest tests.test_wechat_group_memory.WechatGroupMemoryServiceTest.test_preview_injects_unique_profile_by_nickname_when_at_list_is_empty
python -m unittest tests.test_wechat_group_memory
python -m unittest tests.test_wechat_group_context
python -m py_compile channel\wechat_group\wechat_group_memory.py tests\test_wechat_group_memory.py
python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web
```

以上命令均已通过。

## 剩余事项

- 真实微信群链路仍需手动验证：在目标群维护“粉嘟嘟.”画像后发送 `@小灯 粉嘟嘟. 是什么人`，确认本轮 prompt 预览或回复上下文包含 `matched_by="nickname"` 的群友画像。
