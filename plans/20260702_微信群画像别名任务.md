# 微信群群友画像别名匹配计划

## 背景

用户在微信群中询问“大力是谁”时，当前 CowAgent 不能稳定命中目标群友画像。

## 当前结论

- `WechatGroupMemoryService._match_profiles_by_query_nickname()` 当前只使用画像 metadata 中的 `sender_nickname` 做文本子串匹配。
- 如果画像昵称是花体名、英文名、群昵称或旧昵称，而用户使用“大力”“力佬”等外号，当前逻辑会返回 `nickname match not found`，不会注入对应 `[mentioned_profile]`。
- BaiLongmaPro 的参考做法是把 `display_name`、`room_alias`、`contact_alias`、`contact_name`、`wechat_id`、`wxid` 和 `aliases` 聚合为身份候选名，并在“谁是/称呼/聊天记录”类问题中优先注入当前群证据。

## 最小方案

1. 在 CowAgent 群友画像中增加 `aliases` 字段，接受数组、逗号分隔或换行分隔文本。
2. 写入画像时把 `aliases` 保存到 metadata 的 `profile_fields`，并渲染到画像内容中。
3. 查询匹配时使用 `sender_nickname + aliases` 作为候选名；只在当前群内检索，保持现有跨群隔离。
4. 如果同一个别名命中多个不同 `sender_id`，不注入画像，并记录 ambiguous filtered reason，避免误配。
5. 同步 Web 控制台画像编辑表单和自动蒸馏候选 schema，让人工维护和自动提取都能产生别名。
6. 增加回归测试覆盖“大力是谁”通过别名命中画像，以及别名冲突时不注入。

## 预计改动文件

- `channel/wechat_group/wechat_group_memory.py`
- `channel/wechat_group/wechat_group_memory_distiller.py`
- `channel/web/web_channel.py`
- `channel/web/static/js/console.js`
- `tests/test_wechat_group_memory.py`
- `tests/test_wechat_group_memory_distiller.py`
- `CHANGES.md`

## 验证计划

```powershell
python -m unittest tests.test_wechat_group_memory tests.test_wechat_group_memory_distiller tests.test_wechat_group_web
```

如 Web 控制台 JS 改动较多，再补充静态检查或最小 UI 手动验证。

## 状态

- [x] 根因定位
- [x] BaiLongmaPro 参考实现确认
- [x] 等待用户确认实施
- [x] 编写失败测试
- [x] 实现最小代码改动
- [x] 运行相关验证

## 实施结果

- 群友画像已新增 `aliases` 字段，支持数组、逗号分隔或换行分隔文本。
- 运行时画像召回现在会使用 `sender_nickname + aliases` 匹配当前问题；别名命中时注入 `matched_by="alias"`。
- 同一个别名命中多个不同 `sender_id` 时不注入画像，并返回 `alias match ambiguous: <别名>`。
- Web 控制台画像表单已新增“别名”字段，并刷新 `console.js` 缓存版本。
- 自动蒸馏候选 schema 已支持 `aliases`，自动应用画像时会保留别名。

## 验证结果

```powershell
python -m unittest tests.test_wechat_group_memory tests.test_wechat_group_memory_distiller tests.test_wechat_group_web tests.test_wechat_group_memory_ui tests.test_wechat_group_message tests.test_wechat_group_channel
node --check .\channel\web\static\js\console.js
python -m py_compile channel\wechat_group\wechat_group_memory.py channel\wechat_group\wechat_group_memory_distiller.py channel\web\web_channel.py tests\test_wechat_group_memory.py tests\test_wechat_group_memory_distiller.py tests\test_wechat_group_web.py tests\test_wechat_group_memory_ui.py
```
