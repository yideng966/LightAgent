# 群聊 WebUI 中文化计划

## 背景

用户反馈群聊 WebUI 页面中有较多英文，看不懂。已先排查确认：问题主要集中在 Web 控制台 `console.js` 的群聊动态面板、中文文案里的技术英文、运行记录标签、自由回复状态标签和前端错误兜底。

## 实施范围

- 修改 `channel/web/static/js/console.js`：
  - 补齐群聊页中文 i18n 文案。
  - 将自由回复决策、后台任务状态、活跃档位、情绪指标、学习运行记录等硬编码英文改为中文展示。
  - 增加常见群聊接口错误的前端中文映射，避免直接展示 `room_id is required`、`save failed` 等英文。
- 更新 `CHANGES.md` 记录代码改动和验证结果。

## 不做范围

- 不修改桌面端 `desktop/`。
- 不修改后端接口返回结构。
- 不调整群聊页面布局和业务逻辑。

## 验证计划

- 运行 `node --check .\channel\web\static\js\console.js` 检查前端脚本语法。
- 运行 `python -m unittest tests.test_wechat_group_web` 做群聊 Web 接口相关回归。

## 当前状态

- [x] 修改群聊 WebUI 文案。
- [x] 更新变更记录。
- [x] 执行验证并回写结果。

## 实际改动

- `channel/web/static/js/console.js`
  - 将群聊页中文文案中的 `room ID`、`sender ID`、`worker`、`LLM`、`vision`、`TTL`、`valence / energy / sociability` 等技术英文改为中文或中文说明。
  - 将自由回复决策里的 `score / threshold / reasons / suppressions / preview`、后台任务统计里的 `queue / approved / rejected / dropped / expired / active`、活跃档位里的 `quiet / normal / active / crazy` 改为按当前语言展示。
  - 将群记忆学习运行记录中的 `messages / profiles / memories` 和运行状态改为按当前语言展示。
  - 增加群聊状态栏的常见英文错误映射，避免直接展示 `room_id is required`、`save failed`、`load failed` 等英文。

## 验证结果

- `node --check .\channel\web\static\js\console.js`：通过。
- `python -m unittest tests.test_wechat_group_web`：通过，`Ran 32 tests in 0.371s OK`。

## 剩余事项

- 未启动真实 Web 控制台做浏览器截图验证；本次为文案和前端脚本层修改，已完成语法与 Web 接口回归。
