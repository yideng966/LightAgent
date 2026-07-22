# Git 历史与 README 清理计划

## 目标

- 清理仓库内明确的临时脚本、缓存目录和历史运行日志，不删除用户配置、依赖目录或运行数据。
- 删除根 README 顶部的“旧版中文文档”和“日本語”入口，并确保当前产品描述统一为 `LightAgent`。
- 保留 MIT 上游项目 `zhayujie/CowAgent` 的真实名称、根 `LICENSE` 和指定鸣谢链接。
- 以当前完整工作区为唯一代码快照，将 `master` 重建为一个由 GitHub 用户 `yideng966` 提交的根提交。
- 强制推送新的 `master`，使 GitHub 远端不再包含其他用户的提交记录，并确认本地与远端一致。

## 实施约束

- 重写前创建完整 Git bundle 备份，保存在仓库外的 `D:\JiangShuai\SourceCode`。
- 新提交使用 `yideng966 <172368954+yideng966@users.noreply.github.com>` 作为作者和提交者。
- 临时文件仅清理已审计的根目录缓存、测试日志、运行日志、临时调研脚本及递归 Python 缓存。
- `config.json`、用户数据目录、Node.js 依赖、迁移备份、stash 和 MIT 许可内容不得作为临时文件删除。
- README 中的 `CowAgent` 仅允许作为上游专有名称和真实 GitHub URL 保留，不作为当前产品描述使用。

## 执行步骤

- [x] 审计工作区、临时文件、README 与提交作者分布。
- [x] 停止当前 LightAgent 进程并创建 Git bundle 回退备份。
- [x] 清理明确临时文件和递归 Python 缓存。
- [x] 修改 README 并回写本计划。
- [x] 运行最小必要验证，确认待提交快照不包含密钥和临时文件。
- [x] 创建新的单根提交 `master`，作者与提交者均为 `yideng966`。
- [x] 使用 `--force-with-lease` 推送 GitHub，并核验远端只有一个提交和一个作者。
- [x] 如任务前服务处于运行状态，从新历史工作区重新启动并验证 Web 控制台。

## 回退

- force push 前的完整提交历史与 refs 由仓库外 bundle 保留。
- GitHub 历史可通过从 bundle 取回原 `master` 后再次强制推送恢复。
- 当前工作区快照在创建新根提交前不通过 reset、checkout 或 clean 改写。

## 执行结果

- 状态：已完成。
- 实际改动：清理根目录调研脚本、Playwright 临时文件、`tmp`、历史运行/测试日志、桌面构建产物、egg-info 与当前工作树 Python 缓存，累计清理约 176.6 MB；README 删除“旧版中文文档”和“日本語”入口，当前产品描述统一使用 `LightAgent`，仅保留 MIT 上游专名与鸣谢 URL；`master` 重建为单个 `yideng966` 根提交并覆盖远端旧历史。
- 回退备份：`D:\JiangShuai\SourceCode\LightAgent-before-history-rewrite-20260722.bundle`，SHA-256 为 `00A4566F2152AF2D6B7050D595AD4AA7B07E0FDEFF9EE75239485839E80256DF`。
- 验证结果：`python -m unittest discover -s tests` 通过，823 项测试 OK；索引共 914 个文件，不含本地配置、运行数据或临时文件；常见真实密钥格式扫描仅命中 2 个单元测试假 key；GitHub 无其他分支、tag、release 或 ruleset，最终本地与远端树、提交数和作者均一致。
- 剩余事项：无。
