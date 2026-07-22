# BaiLongmaPro 聊天历史迁移计划

## 背景

- 源库：`D:\JiangShuai\SourceCode\BaiLongmaPro\data\jarvis.db`
- 目标库：`C:\Users\clancy\cow\memory\long-term\index.db`
- 源库聊天记录在 `conversations` 表，目标库聊天记录在 `sessions` / `messages` 表。
- Web 控制台历史会话列表当前只展示 `channel_type = "web"` 的会话，因此本次迁移按“独立归档会话导入到 Web 历史列表”处理。

## 迁移假设

1. 本次迁移默认采用独立归档方式，不与当前活跃会话直接拼接。
2. 每个源会话按“来源渠道 + 外部对话对象”聚合为一个目标会话。
3. 目标会话使用稳定的 `session_...` 会话 ID，并写入 `channel_type = "web"`，以便直接在当前 Web 控制台中查看。
4. 保留原始消息时间戳，避免全部显示为迁移执行时间。
5. 若某个源会话只有旧项目的 `jarvis` 输出而没有对应 `user` 输入，为了兼容当前历史渲染逻辑，会插入一条明确标注为“迁移占位”的用户消息。

## 实施步骤

- [x] 新增迁移模块，负责读取源库、构建迁移计划、执行导入和生成摘要。
- [x] 新增脚本入口，支持 `--dry-run` 与正式写入模式，并在正式写入前对目标库做备份。
- [x] 先写单元测试覆盖会话聚合、时间戳保留、纯 assistant 会话占位、目标库写入结果。
- [x] 完成实现并运行最小必要验证。
- [x] 回写本计划中的实际改动、验证结果与剩余事项。

## 计划状态

- 2026-07-04：已完成源库/目标库 schema 核对，确认需要脚本化转换而非直接拷表。
- 2026-07-04：已新增 `agent/chat/history_migration.py`、`scripts/migrate_legacy_chat_history.py` 与 `tests/test_chat_history_migration.py`。
- 2026-07-04：已执行真实迁移，将源库 `41` 条 `conversations` 记录导入为 `5` 个 Web 归档会话、`43` 条目标消息；其中 `2` 条为纯 assistant 源会话的透明迁移占位消息。
- 2026-07-04：正式迁移前已创建目标库备份：`C:\Users\clancy\cow\memory\long-term\index.migration-backup-20260704090946.db`。

## 验证记录

- `python -m unittest tests.test_chat_history_migration -v`
- `python -m py_compile agent\chat\history_migration.py scripts\migrate_legacy_chat_history.py tests\test_chat_history_migration.py`
- `python scripts\migrate_legacy_chat_history.py --source-db 'D:\JiangShuai\SourceCode\BaiLongmaPro\data\jarvis.db' --target-db 'C:\Users\clancy\cow\memory\long-term\index.db'`
- `python scripts\migrate_legacy_chat_history.py --source-db 'D:\JiangShuai\SourceCode\BaiLongmaPro\data\jarvis.db' --target-db 'C:\Users\clancy\cow\memory\long-term\index.db' --apply`
- SQLite 核对：新增会话 `session_migrated_blmp_feishu_fb660fe884c1`、`session_migrated_blmp_wechat_official_2c9a034f73d8`、`session_migrated_blmp_wecom_8ec66265a7d9`、`session_migrated_blmp_tui_72728acebc8f`、`session_migrated_blmp_wechat_22aed63d2ec6`，目标消息数为 `43`。

## 剩余事项

- 代码已在隔离 worktree `D:\JiangShuai\SourceCode\CowAgent\.worktrees\chat-history-migration-20260704` 中完成，尚未合并回主工作区。
- 可选手动验证：打开 Web 控制台历史会话列表，确认能看到标题以“迁移 FEISHU / WECHAT_OFFICIAL / WECOM / TUI / WECHAT”开头的归档会话。
