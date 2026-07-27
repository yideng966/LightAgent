# 项目品牌重命名为 LightAgent 计划

## 目标

- 将 GitHub 公共仓库 `yideng966/wechatAgent` 重命名为 `yideng966/LightAgent`。
- 将当前项目的产品展示名统一为 `LightAgent`。
- 将机器可读标识按使用场景统一为 `lightagent`、`light-agent`、`light_agent` 和 `LIGHTAGENT_*`。
- 将本地仓库目录从 `CowAgent` 移动为 `LightAgent`。
- 将现有本机数据从旧目录完整复制到 LightAgent 新目录，并保留旧目录作为回退。
- 保留上游 MIT 许可文本和版权归属，并在 README 中明确鸣谢上游项目。

## 命名范围

- Python 项目名、CLI 命令、进程提示、PID 文件和默认工作目录。
- Web 控制台、Electron 桌面端、安装包标识、后端可执行文件和构建产物。
- Agent/MCP User-Agent、协议来源字段、技能元数据命名空间和微信群侧车包名。
- 当前 README、协作规则、安装脚本、工作流、测试和非历史性使用文档。
- 相关文件与目录名称，例如 `cowagent-backend.spec` 和 `plugins/cow_cli/`。

## MIT 与兼容边界

- 根目录 `LICENSE` 保持原文，不替换 `Copyright (c) 2022 zhayujie`。
- README 增加 `鸣谢项目：https://github.com/zhayujie/CowAgent.git`，并明确本项目为其 MIT 许可衍生项目。
- 上游仓库、第三方仓库、已部署域名、Cloudflare bucket/database 等真实外部标识不得机械替换为未经确认的新地址。
- `plans/`、`CHANGES.md` 和版本发布记录中的旧名称属于历史事实，不做全量改写；本计划与本次新增记录使用新名称。
- 本次按用户要求执行品牌切换，不保留旧 `cow` CLI、旧环境变量或旧数据目录作为默认入口。
- 数据迁移允许在迁移逻辑和迁移记录中出现旧目录名；这属于兼容来源标识，不作为新产品名称继续使用。

## 实施步骤

- [x] 重命名 GitHub 仓库，确认公开、非 fork、默认分支为 `master`，并更新本地 `origin`。
- [x] 更新 Python 包名、CLI 命令、插件目录与插件标识。
- [x] 更新默认数据目录、环境变量、PID 文件、临时文件前缀和来源标识。
- [x] 复制并校验 `~/.cow -> ~/.lightagent`、`~/cow -> ~/lightagent` 和 Electron 用户数据目录，旧目录暂不删除。
- [x] 更新 Electron 包名、`appId`、产品名、后端构建文件和构建产物路径。
- [x] 更新 Web、桌面、安装脚本、工作流、测试与当前使用文档中的产品名称。
- [x] 保持 `LICENSE` 原文，并在 README 增加 MIT 衍生说明和指定鸣谢链接。
- [x] 更新 `CHANGES.md`，记录实际修改和验证结果。
- [x] 运行最小必要回归、桌面构建、侧车测试与旧名称扫描。
- [x] 移动本地目录到 `D:\JiangShuai\SourceCode\LightAgent` 并完成最终核验。

## 回退

- Git 引用备份：`D:\JiangShuai\SourceCode\CowAgent-before-wechatAgent-20260722.bundle`。
- GitHub 仓库重命名后可通过仓库设置或 `gh repo rename` 改回。
- 本地目录移动前保留完整 Git 工作区和用户未提交内容，不暂存、不覆盖、不清理用户文件。
- 本机旧数据目录在新目录完成文件清单与字节数校验后仍保留，确认新版本稳定运行前不做删除。

## 执行结果

- 状态：已完成。
- 实际改动：GitHub 仓库已调整为公开、非 fork 的 `yideng966/LightAgent`；产品名、机器标识、CLI、插件、默认目录、Web、Electron、构建脚本、工作流、测试与当前文档已切换为 LightAgent；README 已补充 MIT 衍生说明和上游鸣谢；本地主工作区已迁移到 `D:\JiangShuai\SourceCode\LightAgent`，旧后端与 Wechaty sidecar 已终止，editable 安装已重新绑定新路径。
- 数据迁移：`~/.cow -> ~/.lightagent` 共 3714 个文件、2,113,491,531 字节，`~/cow -> ~/lightagent` 共 147 个文件、47,256,135 字节，`%APPDATA%/CowAgent -> %APPDATA%/LightAgent` 共 47 个文件、8,545,371 字节；微信凭据文件哈希一致，旧目录均保留。
- 验证结果：品牌回归 45 项、微信群回归 213 项、sidecar 49 项、全量 Python 823 项均通过；Electron 构建、Python 编译、JSON、PowerShell、Bash 和 `git diff --check` 均通过；GitHub 已核验为 `PUBLIC`、`isFork=false`、默认分支 `master`；新旧工作区排除 Git 元数据后均为 41,359 个文件、991,645,367 字节且镜像干跑无差异；Git bundle、`master`、stash 与对象库完整性校验通过。
- 剩余事项：旧 `D:\JiangShuai\SourceCode\CowAgent` 根目录由当前 Codex 会话持有 Windows 工作目录句柄，清空内容后需在会话释放句柄时删除；该空目录不再包含源码或用户数据。
