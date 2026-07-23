# CHANGES

## 2026-07-23

### GitHub 标签自动发布 LightAgent 镜像

- 将 AMD64 与 ARM64 Docker 工作流的宽泛 `create` 事件替换为显式 `push.tags: ['v*']`，保留 `master` 分支触发，并增加 `workflow_dispatch` 手动重试入口。
- 将仓库运行条件更新为 `yideng966/LightAgent`，Docker Hub 与 GHCR 镜像统一为 `yideng966/lightagent`，移除 `zhayujie/chatgpt-on-wechat` 等旧发布目标。
- 将 GHCR 清理目标 `package-name` 更新为 `lightagent`；AMD64 继续发布 Docker Hub 与 GHCR，ARM64 继续使用 `-arm64` 标签后缀发布到 GHCR。
- 将 `docker/docker-compose.yml` 的服务名与容器名统一为 `lightagent`，默认镜像地址更新为 `yideng966/lightagent`，避免部署时继续使用旧项目标识。

关键文件：

- `.github/workflows/deploy-image.yml`
- `.github/workflows/deploy-image-arm.yml`
- `docker/docker-compose.yml`
- `plans/20260723_GitHub标签自动发布.md`

验证记录：

- PyYAML 解析与触发器断言通过：两个工作流均包含 `master`、`v*` 和 `workflow_dispatch`，且不再包含 `create`。
- Docker 工作流旧仓库、旧镜像和旧 package-name 残留扫描通过。
- `docker compose config --services` 与 `--images` 校验通过，分别输出 `lightagent` 和 `yideng966/lightagent`；Compose 关键字段断言与旧标识扫描通过。
- `git diff --check`：通过。

### GitHub 提交通知到指定微信群

- 新增 `/api/github/webhook`：按 GitHub `X-Hub-Signature-256` 对原始请求体执行 HMAC-SHA256 恒定时间验签，只处理 `ping` 与目标仓库/分支的 `push`，并限制 25 MB 请求体。
- 新增 GitHub delivery SQLite 去重记录；在配置的保留期内，相同 `X-GitHub-Delivery` 在任务排队中或已投递后不会重复创建群消息，数据库仅保存 delivery ID、任务 ID、仓库、分支和状态，不保存 Secret 或原始 payload。
- 复用 scheduler 固定消息投递链路创建确定性一次性任务，使用 `stable_room_id` 在发送前解析当前 runtime room；通知默认不 mention 群成员，群未登录或身份未恢复时按任务级有效期重试，原有 scheduler 仍保持 10 分钟默认延迟窗口。
- 在 Web 控制台「群聊 -> 基础设置」新增 GitHub 提交通知配置区，支持启用开关、仓库、分支、目标群单选下拉、commit 展开数、重试时长、去重保留期、只读 Webhook 地址和 Secret 输入；目标群只取已选择的稳定群，离线的已保存目标不会被页面清空。
- Webhook Secret 支持保存到本地配置，`LIGHTAGENT_GITHUB_WEBHOOK_SECRET` 仍具有最高优先级；配置 API 只返回是否已配置、来源和固定掩码，不返回真实 Secret，页面未填写新值时不会覆盖已有 Secret。
- 新增中文部署文档，说明 Web 控制台配置、公网 HTTPS 精确路径反向代理、GitHub Webhook 设置、安全边界和错误排查。

关键文件：

- `channel/web/github_commit_webhook.py`
- `channel/web/web_channel.py`
- `channel/web/static/js/console.js`
- `agent/tools/scheduler/integration.py`
- `agent/tools/scheduler/scheduler_service.py`
- `tests/test_github_commit_webhook.py`
- `tests/test_scheduler_wechat_group_delivery.py`
- `docs/zh/guide/github-commit-wechat.mdx`

验证记录：

- GitHub/scheduler 与个人微信群联合回归：通过，243 项 OK。
- `python -m unittest discover -s tests`：通过，854 项 OK。
- Python 编译、`node --check channel/web/static/js/console.js`、`config-template.json` / `docs/docs.json` JSON 语法、临时 Secret 扫描与 `git diff --check`：通过。
- Playwright 隔离验收通过：1440px 暗色与 375px 亮色无横向溢出或文本重叠，目标群下拉可切换，Secret 不回显，环境变量接管时输入框禁用；隔离实例只启用 Web 通道，测试配置、日志和截图均已清理。

### 微信群成员黑名单

- 新增结构化配置 `wechat_group_blacklist_members`，字段结构复用群管理员成员记录，按当前群 `stable_room_id + stable_member_id` 精确生效；旧 `wechat_group_blocked_stable_member_ids` 与 `wechat_group_blocked_sender_ids` 继续作为兼容 fallback。
- Web 控制台“群与管理员”页新增“群黑名单”面板，支持选择目标群、搜索已确认群成员、保存和删除黑名单成员；保存时写入结构化黑名单，不再扩展旧 flat 字段。
- 微信群通道在入口处对黑名单成员静默跳过，覆盖主动 @ bot、引用 bot、拍一拍、图片/视频直接触发和普通自由回复候选；自由回复评分继续返回 `blocked_sender` 抑制原因用于诊断。
- 补充回归测试覆盖黑名单归一化/作用域/fallback、direct reply 静默跳过、自由回复 blocked sender、Web extra/保存/UI 字段。

验证记录：
- `python -m unittest tests.test_wechat_group_permissions tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，225 项 OK。
- `node --check channel/web/static/js/console.js`：通过。
- `python -m json.tool config-template.json`：通过。

## 2026-07-22

### 项目品牌迁移为 LightAgent

- 将项目展示名统一为 `LightAgent`，并按使用场景同步更新 Python 项目、`lightagent` CLI、插件、环境变量、PID 文件、默认数据目录、Web 控制台、Electron 桌面端、构建脚本、工作流、测试和当前使用文档中的机器标识。
- GitHub 仓库已调整为公开、独立且非 fork 的 `yideng966/LightAgent`，默认分支和唯一业务分支均为 `master`；本地 `origin` 已更新为 `git@github.com:yideng966/LightAgent.git`。
- 本地主工作区已迁移到 `D:\JiangShuai\SourceCode\LightAgent`，旧项目后端与 Wechaty sidecar 已终止，Python editable 安装已重新绑定新路径；迁移前 Git bundle、当前 `master` 和已有 stash 均已保留并通过完整性校验。
- 将 `plugins/cow_cli/` 重命名为 `plugins/lightagent_cli/`，将桌面后端构建描述文件重命名为 `desktop/build/lightagent-backend.spec`，并移除旧 `cow` CLI 安装入口。
- 完整保留上游 MIT `LICENSE` 原文和版权声明；README 已注明本项目为 `zhayujie/CowAgent` 的 MIT 衍生项目，并增加指定鸣谢链接 `https://github.com/zhayujie/CowAgent.git`。
- 用户数据采用“复制、校验、保留旧目录”的方式迁移：`~/.cow -> ~/.lightagent` 共 3714 个文件、2,113,491,531 字节，`~/cow -> ~/lightagent` 共 147 个文件、47,256,135 字节，`%APPDATA%/CowAgent -> %APPDATA%/LightAgent` 共 47 个文件、8,545,371 字节；微信凭据文件同步迁移且哈希一致。
- 配置中的语言键和浏览器本地语言、主题键增加一次性兼容迁移，已有配置值、用户技能和运行数据保持不变；旧数据目录暂不删除，作为稳定运行确认前的回退副本。

验证记录：

- 品牌相关 Python 回归：45 项通过；个人微信群回归：213 项通过；Wechaty sidecar：49 项通过。
- `python -m unittest discover -s tests`：通过，823 项测试 OK。
- Electron `npm run build`、Python `compileall`、JSON 语法、PowerShell 脚本语法、`bash -n run.sh` 与 `git diff --check`：通过。
- 新旧工作区在排除 Git 元数据后均为 41,359 个文件、991,645,367 字节且镜像干跑无差异；恢复后的 Git 仅包含本地 `master`、`origin/master` 与原有 stash，`git fsck --full --no-dangling` 通过。
- 根目录 `LICENSE` SHA-256 保持为 `BB0C7223DC4FD273914FED10FDAA864987F03DCCEB216B503A236B2CDE4255D9`。

### 微信群表情包描述人工编辑与批量图片理解

- Web 控制台表情包卡片支持内联编辑本地描述，服务端按当前稳定群校验并使用旧描述条件更新；同一表情包再次自动收集时不再覆盖已保存的人工或 Vision 语义。
- 列表顶部新增当前群待理解、可处理、文件缺失和空文件统计；待理解范围限定为空值、通用占位、微信 XML、纯数字和长哈希，已停用素材不进入批处理统计。
- 新增后台图片理解任务：点击并确认后先在线备份表情包 SQLite，再以 2 路受限并发复用现有 `Vision`；GIF 继续转换为多帧联系图，逐条条件提交，失败项保留原值并支持续跑。
- Web UI 提供运行进度、成功/失败/跳过结果、按钮禁用态、内联错误、键盘保存/取消、明暗主题与窄屏布局；移动端改用下拉菜单切换群聊子页，统计加载失败时停止自动循环并提供显式重试。
- 人工保存即使未显式传入旧描述也会自动绑定当前值执行条件更新；新增主操作使用可读对比度配色，进度动画遵循减少动态效果偏好。
- 将原 `scripts/label_wechat_group_stickers.py` 标注实现提取到共用模块，保留原 CLI 参数，并新增 `pending` 类型和 `--room-id` 稳定群过滤。
- 新表情包实时收藏仍不自动调用 Vision；只有用户在 Web UI 确认后才执行批量图片理解。

关键文件：

- `channel/wechat_group/wechat_group_sticker_labeling.py`
- `channel/wechat_group/wechat_group_sticker_store.py`
- `channel/wechat_group/wechat_group_sticker_service.py`
- `channel/web/web_channel.py`
- `channel/web/static/js/console.js`
- `scripts/label_wechat_group_stickers.py`

验证记录：

- `python -m unittest tests.test_wechat_group_sticker_labeling tests.test_wechat_group_sticker_service tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，239 项测试 OK。
- `python -m compileall -q channel/wechat_group channel/web scripts/label_wechat_group_stickers.py`：通过。
- `node --check channel/web/static/js/console.js`：通过。
- Playwright 隔离验收通过：1440px 暗色与 375px 亮色下人工编辑、确认、50% 进度、完成刷新、移动端布局和统计失败重试均正常；未调用真实 Vision 或修改正式表情包数据库。

### 微信群表情包文字前摇修复

- 修复 `wechat_group_sticker_send` 成功后，Agent 最终文本被挂到图片回复 `text_content`，导致先发送“（文件名.gif）”再发送表情包的问题。
- `AgentBridge` 仅对当前个人微信群且带 `sticker_id` 或 `online_id` 的表情包文件抑制附加文本，直接发送表情包媒体。
- 普通图片与文件的显式图文回复保持原行为，并补充本地表情包、在线表情包和普通图片三类回归测试。

关键文件：

- `bridge/agent_bridge.py`
- `tests/test_wechat_group_agent_bridge_tools.py`

验证记录：

- `python -m unittest tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，218 项测试 OK。
- `python -m py_compile bridge/agent_bridge.py tests/test_wechat_group_agent_bridge_tools.py`：通过。

### 微信群静默判断泄漏修复

- 扩展微信群发送层已有的短文本静默说明识别，覆盖“不是在问我 + 不用插嘴”等句式，避免模型内部的不接话判断被当作普通回复发到群里。
- 同步扩展自由回复本地抑制口径；继续保留 24 字窄口径上限，避免误拦截正常长文本解释。
- 增加实际泄漏原句、旧静默句式和正常解释文本反例测试；命中静默说明时不发送、不归档助手回复，也不更新情绪回复计数。

关键文件：

- `channel/wechat_group/wechat_group_channel.py`
- `channel/wechat_group/wechat_group_free_reply.py`
- `tests/test_wechat_group_channel.py`
- `tests/test_wechat_group_free_reply.py`

验证记录：

- 聚焦静默发送与自由回复抑制测试：通过，5 项测试 OK。
- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，248 项测试 OK。
- `python -m py_compile channel/wechat_group/wechat_group_channel.py channel/wechat_group/wechat_group_free_reply.py tests/test_wechat_group_channel.py tests/test_wechat_group_free_reply.py`：通过。

### 微信群“闭嘴”暂停自由回复

- 新增 `wechat_group_free_reply_mute_minutes` 配置，默认 10 分钟，Web 控制台与服务端统一限制为 1–1440 分钟。
- 新增 `wechat_group_free_reply_mute_mentions_enabled` 开关，默认关闭以保持普通 @ 必回的原行为；开启后，当前群禁言有效期内的新 @ 消息也会静默忽略，引用、拍一拍和其他群不受影响。
- 任意群成员真实 @ 机器人并精确发送“闭嘴”时，通道静默消费命令，按当前稳定群暂停普通自由回复；命令识别先于 @ 禁言门禁，因此重复命令仍可续期。
- 自由回复本地评分与 worker 最终发送前均检查禁言状态，阻止命令前已排队候选延迟发言；状态随通道进程重启清空。
- Web 自由回复面板增加分钟输入和“禁言期间被 @ 也不回复”开关，提供可见标签、帮助文本、`aria-describedby`、键盘焦点环及明暗主题样式。

关键文件：

- `channel/wechat_group/wechat_group_free_reply.py`
- `channel/wechat_group/wechat_group_channel.py`
- `channel/web/web_channel.py`
- `channel/web/static/js/console.js`
- `config.py`
- `config-template.json`

验证记录：

- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，244 项测试 OK。
- `python -m py_compile channel/wechat_group/wechat_group_free_reply.py channel/wechat_group/wechat_group_channel.py channel/web/web_channel.py`：通过。
- `node --check channel/web/static/js/console.js`：通过。
- `python -m json.tool config-template.json`：通过。

## 2026-07-21

### Web 群管理员成员搜索修复

- 修复管理员成员搜索把稳定群 ID 同时作为运行时群 ID 传递，导致 sidecar 无法查询群成员的问题。
- Web API 兼容旧页面与浏览器缓存产生的重复群 ID 参数，并通过身份服务恢复当前运行时群 ID。
- 验证：`python -m unittest tests.test_wechat_group_web`、`node --check channel/web/static/js/console.js`。

## 2026-07-20

### 微信群群友画像按群唯一重构

- 将旧“全局画像 + 群内名称记录”重构为按 `stable_room_id + canonical stable_member_id` 唯一的群友画像；全局层只保留可验证的身份关系，画像正文、名称、证据、版本和运行记录均按群隔离。
- 统一 profiles、names、claims、revisions、runs 和 heuristic/evolution learning state 到 `wechat_group_profiles.db`，补充 member redirect、环检测、canonical 解析和完整回滚快照。
- 收紧自动画像门禁：缺少强 `wechat_id` 且未经确认的身份不创建最终画像；LLM 只接收批次 opaque token，服务端校验当前群、成员与 evidence 后才允许写入。
- 启发式学习和画像进化使用独立按群游标；新启用已有归档的群从当前高水位开始，不默认回放历史消息。
- Prompt 注入、真实 @ 成员解析、Agent 工具和 Web API 全部强制当前稳定群作用域；Web 文案改为“群友画像”，移除全部群聚合视图并支持从 stable member 创建空画像。
- 新增 `scripts/reset_wechat_group_profiles.py` 与回归测试，支持 SQLite 备份、新库校验、原子替换和旧 evolution 库退役；正式执行若未解析出目标稳定群会直接拒绝。
- 已对本机正式数据完成备份后全量重建：历史画像与旧进化数据不迁移，新库画像相关表为空，6 个群的 12 条学习基线均等于清理时归档高水位；archive、identity、knowledge 数据未改变。

关键文件：

- `channel/wechat_group/wechat_group_profile_store.py`
- `channel/wechat_group/wechat_group_profile_service.py`
- `channel/wechat_group/wechat_group_identity_store.py`
- `channel/wechat_group/wechat_group_identity_service.py`
- `channel/wechat_group/wechat_group_learner.py`
- `channel/wechat_group/wechat_group_profile_evolution_executor.py`
- `channel/wechat_group/wechat_group_profile_evolution_merger.py`
- `channel/web/web_channel.py`
- `channel/web/static/js/console.js`
- `scripts/reset_wechat_group_profiles.py`
- `plans/20260720_群友画像功能复盘与架构建议.md`

验证记录：

- `python -m unittest discover -s tests`：通过，797 项测试 OK。
- `python -m unittest tests.test_reset_wechat_group_profiles`：通过，4 项测试 OK。
- `python -m compileall -q channel/wechat_group channel/web scripts/reset_wechat_group_profiles.py scripts/migrate_wechat_group_identity.py`：通过。
- `node --check channel/web/static/js/console.js`：通过。
- 正式新库 `PRAGMA integrity_check`：`ok`；profiles/names/claims/revisions/runs 均为 0，learning state 为 12。
- 切换前后 archive、identity、knowledge 数据库 SHA-256 一致；`git diff --check` 通过。

## 2026-07-19

### 微信群表情包数字描述清理完成

- 修复新入库表情包传入描述本身为纯数字或长哈希时仍被直接保存的问题，统一回退为安全占位描述。
- 扩展历史语义标注脚本，支持按 `xml`、`opaque` 或 `all` 精确筛选，并支持 1–4 个并发 Vision 请求；外部调用可并发，SQLite 仍由主线程逐条条件更新。
- 对历史 190 条纯数字描述完成 Vision 语义标注和有限续跑，最终 `opaque` 候选为 0；用户要求保留的 8 条 XML 描述未处理。
- Web 表情包卡片继续直接展示数据库 `description`，页面刷新后可查看清洗后的语义。

验证记录：

- `python -m unittest tests.test_wechat_group_sticker_labeling tests.test_wechat_group_sticker_service`：通过，18 项测试 OK。
- `python scripts/label_wechat_group_stickers.py --description-type opaque`：候选 0。
- `python scripts/label_wechat_group_stickers.py --description-type xml`：候选 8，与用户要求保留数量一致。

## 2026-07-17

### 微信群表情包回复频率优化

- 新增 `wechat_group_sticker_reply_percent`（默认 20，范围 0–100），将轻松闲聊中主动使用表情包的目标频率注入自由回复、普通 @、引用等回复策略；0 表示仅响应明确的表情包请求。
- Web 控制台表情包设置增加“主动回复频率(%)”，并同步服务端读取、保存与范围归一化。
- 新收藏表情包遇到微信 `<msg><emoji>` 传输 XML 描述时，不再把 XML 写入素材描述，优先回退到安全文件名。
- 保持现有当前群隔离、先搜索后发送、发送冷却和每日上限不变。
- 新增 `scripts/label_wechat_group_stickers.py`，支持备份数据库、使用现有 Vision 为历史微信 XML 描述生成可检索中文语义、逐条提交和失败续跑；GIF 会先抽取最多四帧生成 PNG 联系图，避免兼容接口直接解析动画失败。
- 历史数据实际处理：143 条 XML 描述中，134 条已写入通过质量门禁的 Vision 语义，8 条按用户要求保留原描述不再处理，1 条 0 字节媒体标记为无效并禁用；其余正常描述未改动。

验证记录：

- `python -m unittest tests.test_wechat_group_sticker_service tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_context.WechatGroupReplyPolicyTest tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_humanization_config tests.test_wechat_group_web.WechatGroupWebTest.test_console_contains_wechat_group_sticker_panel`：通过，22 项测试 OK。
- `python -m unittest tests.test_wechat_group_web`：通过，82 项测试 OK。
- `python -m unittest tests.test_wechat_group_context`：通过，23 项测试 OK。
- Python 语法检查、`node --check channel/web/static/js/console.js` 与 `git diff --check`：通过。
- `python -m unittest tests.test_wechat_group_sticker_labeling tests.test_wechat_group_sticker_service`：通过，16 项测试 OK。

### 微信群真实 @ 降级日志

- 当 WeChat4U 原始真实 @ 发送失败或运行时对象不可用时，在 sidecar 标准错误流记录脱敏原因、目标数量和异常摘要，再保持原有可见文本 @ 降级行为。
- 日志不包含消息正文、群 ID、成员 ID 或昵称，避免诊断信息泄露聊天内容与身份数据。
- 更新 sidecar 回归测试，覆盖原始发送失败与运行时不可用两条降级路径。

验证记录：

- `npm test`（`channel/wechat_group/sidecar`）：通过，49 项测试 OK。

### 更新图片生成失败提示

- 将图片生成脚本执行失败或返回错误时的固定提示更新为“累了不想画了，你跪安吧。”。
- 个人微信群发送错误回复时移除通用装饰产生的 `[ERROR]` 前缀，保留错误类型与原有抑制逻辑。

验证记录：

- `python -m py_compile channel/channel.py`：通过。
- 文本检索确认两个对应失败分支均已更新，旧提示已无代码引用。
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_decorated_group_error_reply_does_not_include_error_prefix`：通过。

### 微信群三人复读直接回复

- 保持 `repeater_message` 的 3 个不同成员阈值不变。
- 复读命中后复用现有 `_send_reply()` 渠道管线直接发送原文，不再进入 `produce()` 及 Agent/LLM 生成链路。
- 保留自由回复群范围、复读文本冷却、免 mention、回复归档、文本发送处理和情绪状态记录。
- 修复当前成员的 stable/runtime ID 被统计为两个发送者的问题，确保两人不会误触发、三个不同成员才触发复读。
- 新增渠道回归测试，验证复读原文、回复类型、冷却记录及不调用 Agent。

验证记录：

- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_worker tests.test_wechat_group_channel tests.test_wechat_group_message tests.test_wechat_group_web`：通过，239 个测试 OK。
- stable/runtime 去重修复后运行 `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_worker tests.test_wechat_group_channel.WechatGroupChannelTest.test_approved_three_sender_repeater_sends_original_text_without_agent`：通过，42 个测试 OK。

### 修复自由回复评分规则保存后不回显

- 排查确认本地 `config.json` 未写入 `wechat_group_free_reply_rule_scores` / `wechat_group_free_reply_rule_enabled`：前端静态资源可热更新，但后端进程若未重启会忽略新配置键。
- 加固 Web 控制台规则采集：优先用 `getAttribute` 读取 data 属性，并从 rules 快照补齐默认分值/开关。
- 保存成功后若当前页有评分规则控件但 `applied` 未包含对应键，提示“请重启后端后再保存”。
- 后端 wechat_group 保存增加 applied keys 日志，便于确认是否真正落盘。

验证记录：

- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_renders_free_reply_rules_as_table_with_chinese_labels_and_scores tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_free_reply_config`：通过，2 个测试 OK。
- `node --check channel\web\static\js\console.js`：通过。

### 微信群自由回复评分规则可配置

- 加分规则支持在 Web 控制台「群聊 / 自由回复 / 评分规则」中直接修改分值；`banter_opportunity` 按安静/普通/活跃/高频四档分别配置。
- 抑制规则支持勾选是否启用；关闭后评估链路会跳过对应抑制项。
- 新增配置项 `wechat_group_free_reply_rule_scores`、`wechat_group_free_reply_rule_enabled`，并接入 `config.py`、`config-template.json`、保存归一化与本地评分逻辑。
- 评分规则表格压缩为三列（类型 / 规则 / 分值或启用），减少占位。
- 更新 `tests/test_wechat_group_free_reply.py`、`tests/test_wechat_group_web.py` 覆盖可改分、可开关与保存路径。

验证记录：

- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_free_reply_config tests.test_wechat_group_web.WechatGroupWebTest.test_console_renders_free_reply_rules_as_table_with_chinese_labels_and_scores`：通过，33 个测试 OK。
- `node --check channel\web\static\js\console.js`：通过。

### 微信群表情包配置可编辑

- 更新 `channel/web/static/js/console.js`：群聊「表情包」页将总开关、自动收集、注入上限、大小上限、每日发送上限、线上检索、发送冷却从只读摘要改为可编辑表单，并置于页面顶部设置区。
- 列表刷新重绘时通过 `configDraft` 保留未保存编辑，避免改完数值被列表加载冲掉；保存成功后清除草稿并回读服务端配置。
- 为上述配置项补充中英文提示文案；后端仍走既有 `/api/channels` 保存与归一化逻辑。
- 更新 `tests/test_wechat_group_web.py`：锁定表情包核心配置控件为可编辑表单，而不是只读摘要卡片。

验证记录：

- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_contains_wechat_group_sticker_panel tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_humanization_config`：通过，2 个测试 OK。
- `node --check channel\web\static\js\console.js`：通过。

## 2026-07-16

### 微信群历史图片引用修复

- 修复 `wechaty-puppet-wechat4u` 已识别原生引用消息、但 CowAgent 侧车重新解析原始载荷后得到空 `quote` 的问题：侧车现在按 `Content`、`OriginalContent`、`OriContent`、`MMActualContent` 收集 XML 候选，逐级解码实体并截取完整 `<msg>`，兼容 `refermsg` 的对象与单元素数组形态。
- 引用图片恢复 `message_id / type / sender_id / sender_name / content` 后，Python 多模态服务可继续按当前稳定群从归档读取真实 `media_path`，不再依赖模型构造临时路径。
- 扩充 Wechaty 展开引用文本的保守回退规则，使“`[图片]` + 看我当前配置”进入现有同群、同发送者或唯一近期图片匹配；跨发送者多图歧义拒绝绑定，真实媒体路径仍不会进入 prompt 或诊断字段。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs` 与 `tests/test_wechat_group_multimodal_context_service.py`，覆盖 `OriginalContent` 回退、图片引用字段、候选优先级、真实故障文本、Vision 服务端路径调用及路径不泄露。
- 真实微信群复测发现首轮修复仍使用了与 Wechaty 不同的 XML 解析器，且同发送者存在多张近期图片时错误选择了最新黑图；二次修复改为直接依赖并固定 `xml2js@0.4.23`，与 `wechaty-puppet-wechat4u` 保持相同解析行为，Sidecar 消息处理显式等待异步引用解析。
- 同发送者近期图片回退收紧为“候选唯一才允许绑定”；存在多张时返回 `ambiguous_same_sender_images` 并禁止调用 Vision，不再用时间顺序猜测用户引用目标。
- 多图歧义会向当前轮注入 `status: ambiguous_reference` 和“不得猜测图片内容”的安全提示，但不注入任何候选路径，避免 Agent 在 Vision 未执行时根据历史上下文继续臆测。
- 新增脱敏图片选择日志，记录 `quote_message_id / raw_app_type / reason / skipped_reason / matched_message_id`，不记录真实媒体路径，便于真实链路直接确认是否按 `svrid` 精确命中。
- 第三次真实复测确认安全降级生效，但 Sidecar 的原始载荷取得与引用解析异常仍被空 `catch` 静默吞掉；新增统一原始载荷入口，优先调用 `messageRawPayload()`，失败后仅对 Wechat4u 读取其一小时 `cacheMessageRawPayload`，避免因公开方法异常直接丢失 `refermsg.svrid`。
- Sidecar 新增 `quote_diagnostics` 脱敏状态，Python 消息适配器再按字段和值双重白名单过滤后写入归档；多模态选择日志增加原始载荷状态、来源和引用解析状态，诊断中不保留 XML、正文、错误消息或媒体路径。
- 移除引用解析对 `selfInfo.id` 的非必要门控：机器人 ID 只用于计算 `is_quote_self`，不再阻止普通成员图片引用解析。
- 重启后真实诊断确认当前 Wechat4u 对部分图片引用只上报 `MsgType=1 / AppMsgType=0` 的展开文本，不包含 `refermsg.svrid`；按用户选择切换为优先可用策略：同一发送者短窗口内有多张图片时选择最新一张并调用 Vision，原因标记为 `same_sender_latest_image`。不同发送者之间的多图歧义仍拒绝绑定。

验证记录：

- `npm test`（`channel/wechat_group/sidecar`）：第三轮修复后通过，49 个测试 OK。
- `python -m unittest tests.test_wechat_group_multimodal_context_service tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：第三轮修复后通过，212 个测试 OK。
- 同一组 212 个微信群回归测试在优先可用策略调整后再次通过；其中同发送者多图覆盖 `same_sender_latest_image` 并确认 Vision 接收最新图片路径，跨发送者多图仍不调用 Vision。
- `python -m py_compile channel\wechat_group\wechat_group_multimodal_context_service.py tests\test_wechat_group_multimodal_context_service.py`：通过。
- `node --check channel\wechat_group\sidecar\wechaty-sidecar-core.mjs`、`wechaty-sidecar-core.test.mjs` 与 `wechaty-sidecar.mjs`：通过。
- `npm ls xml2js`：CowAgent Sidecar 与 `wechaty-puppet-wechat4u` 均使用 `xml2js@0.4.23`。

### 刷新群列表后目标群勾选丢失修复

- 修复 Web 控制台「群与管理员」点击「刷新群列表」后，目标群下拉框勾选全部消失的问题。
- 根因：`refreshWechatGroupRooms()` 用接口返回的原始 `data.rooms`（Wechaty runtime id）覆盖了 `extra.rooms` 中已归一化的房间（`id = stable_room_id`），导致 checkbox 的 `data-groups-room-id` 与已保存的 `wgr_*` 选中列表对不上。
- 更新 `channel/web/static/js/console.js`：刷新时优先使用 `data.extra.rooms`；保留已有目标群选择快照；下拉勾选按 `stable_room_id / id / runtime_room_id` 匹配。
- 更新 `tests/test_wechat_group_web.py`，锁定刷新逻辑不再用 raw `data.rooms` 覆盖归一化列表。

验证记录：

- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_refresh_rooms_keeps_normalized_rooms_and_selection tests.test_wechat_group_web.WechatGroupWebTest.test_console_saves_wechat_group_free_reply_stable_room_ids`：通过。
- `node --check .\channel\web\static\js\console.js`：通过。

### Vision 强制非流式 JSON 响应

- 修复 `agent/tools/vision/vision.py` 调用 OpenAI 兼容 `/chat/completions` 时未显式设置 `stream: false` 的问题：部分 new-api / sub2api 网关在省略 `stream` 时默认返回 `text/event-stream`，导致 `resp.json()` 抛出 `JSONDecodeError: Expecting value`。
- 解析失败时改为抛出带 `Content-Type` 与 body 预览的 `VisionAPIError`，便于回退链路与日志定位，不再被归类为 unexpected error。
- 新增 `tests/test_vision_stream.py`，覆盖 payload 含 `stream: false` 以及 SSE/非法 JSON 错误信息。

验证记录：

- `python -m unittest tests.test_vision_stream -v`：通过，2 个测试 OK。

## 2026-07-14

### 自定义 Provider TTS 恢复

- 恢复 `voice/custom/custom_voice.py` 的 TTS 能力：通用 OpenAI-compatible 模型调用 `/audio/speech` 并保存 MP3，`mimo-v2.5-tts*` 调用 `/chat/completions` 并解析 base64 WAV；请求错误、HTTP 200 JSON 错误、空音频和无效 WAV 均安全失败，日志继续脱敏 Key/Base。
- 更新 `voice/factory.py` 与 `bridge/bridge.py`：按显式 `text_to_voice` 能力创建 `CustomVoice`，配置热刷新后可直接使用 `custom:<id>`，不依赖当前聊天 Provider。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：凭据完整的自定义 Provider 可用于 TTS 反显和保存；保存前校验 Provider、Key/Base 与模型；没有预置音色目录时显示自定义 voice 输入，不再把有效配置提示为无效 Provider。
- 更新 `tests/test_custom_voice.py`、`tests/test_voice_factory.py`、`tests/test_models_handler.py` 与 `tests/test_wechat_group_web.py`，覆盖两类 TTS 协议、错误响应防护、路由热刷新、配置持久化和 Web 输入状态。
- 更新 `README.md`、`AGENTS.md`、`plans/20260713_自定义Provider支持ASR.md` 与 `plans/20260714_自定义Provider支持TTS.md`，纠正此前误撤回 Custom TTS 的范围记录并固化语音路由同步检查要求。

验证记录：

- `python -m unittest tests.test_custom_voice tests.test_voice_factory tests.test_models_handler`：通过，40 个测试 OK。
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_models_console_surfaces_invalid_voice_provider_warning`：通过，1 个测试 OK。
- `python -m unittest tests.test_custom_provider tests.test_custom_voice tests.test_voice_factory tests.test_models_handler tests.test_models_console tests.test_chat_channel_voice tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，260 个测试 OK。
- `python -m unittest discover -s tests`：全量回归通过，772 个测试 OK。
- `node --check .\channel\web\static\js\console.js` 与 `python -m compileall -q voice bridge channel\web`：通过。
- `git diff --check`：通过，仅输出工作区现有 LF/CRLF 提示。

### Windows Agent 生图参数解析修复

- 修复 `skills/image-generation/SKILL.md` 使用类 Unix 单引号包裹内联 JSON、在 Windows `cmd.exe` 下导致 JSON 被拆分并于生图请求前报 `Invalid JSON` 的问题。
- 更新 `skills/image-generation/scripts/generate.py`：新增 `--json-file <path>` 参数入口，支持 UTF-8 与 UTF-8 BOM 请求文件；保留原有单参数内联 JSON 兼容，并为 Windows 参数被拆分的情况返回明确指引。
- 更新生图技能调用规范：统一优先使用 `write` 工具创建唯一临时 JSON 请求文件，再调用 `generate.py --json-file`，避免提示词中的引号、`&`、`%` 等内容被 Shell 改写。
- 更新 `channel/channel.py`：直接生图子进程显式设置 `PYTHONIOENCODING=utf-8`，父进程以 UTF-8 解码时使用替换容错，避免 Windows 本地代码页或第三方异常输出导致 stdout/stderr 读取线程抛出 `UnicodeDecodeError` 并退化为 `unknown error`。
- 更新 `tests/test_image_generation_custom_provider.py`，覆盖请求文件解析、Unicode 与 Shell 元字符、无效 JSON、Windows 拆参提示、旧入口兼容和技能文档调用契约。
- 更新 `tests/test_wechat_group_channel.py`，锁定直接生图子进程的 UTF-8 输出环境和解码容错参数。

验证记录：

- `python -m unittest tests.test_image_generation_custom_provider`：通过，15 个测试 OK。
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_image_create_script_payload_normalizes_string_false_proxy_enabled`：通过，1 个测试 OK。
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_image_create_script_runner_uses_json_argument_without_shell tests.test_wechat_group_channel.WechatGroupChannelTest.test_image_create_script_payload_preserves_empty_proxy_domains tests.test_wechat_group_channel.WechatGroupChannelTest.test_image_create_script_payload_normalizes_string_false_proxy_enabled`：通过，3 个测试 OK。
- `python -m unittest tests.test_image_generation_custom_provider tests.test_wechat_group_channel`：通过，124 个测试 OK。
- `python -m py_compile skills\image-generation\scripts\generate.py tests\test_image_generation_custom_provider.py`：通过。
- `python -m py_compile channel\channel.py tests\test_wechat_group_channel.py`：通过。
- 真实 `cmd.exe` 使用运行目录副本执行 `generate.py --json-file <smoke.json>`：成功解析请求文件并进入 `Missing required parameter: prompt` 业务校验，未再出现 `Invalid JSON`。
- 异编码烟雾验证：子进程向 stdout/stderr 原始写入 GBK 字节时，父进程可正常返回且不再触发 `_readerthread` 解码异常。
- 运行实例于 15:59:22 重启加载修复后，真实微信群生图链路连续处理 4 次请求；截至核查时未再出现 `_readerthread`、`UnicodeDecodeError` 或 `image generation failed: unknown error`，群内随后正常讨论生成结果。

## 2026-07-13

### 微信群语音交互策略

- 新增 `wechat_group_voice_interaction_mode` 配置，支持 `force_reply` 与 `free_reply`，缺失或非法值统一回退为默认的 `force_reply`；同步更新 `config.py`、`config-template.json` 和 Web 配置读写校验。
- 更新 `channel/chat_channel.py` 与 `channel/wechat_group/wechat_group_channel.py`：ASR 转写完成后通过可覆盖钩子继续处理；强制模式直接进入 Agent 回复链路，自由回复模式复用现有本地评分、群范围、冷却和 LLM 判定队列，判定通过后保留语音来源与 `desire_rtype`，不会重复执行 ASR。
- 更新 `channel/web/static/js/console.js`：在 Web 控制台“群聊”中新增“语音交互”菜单，使用可访问的单选控件选择“强制回复”或“依赖自由回复规则”，默认显示强制回复，并为菜单侧栏补充纵向滚动。
- 更新 `tests/test_chat_channel_voice.py`、`tests/test_wechat_group_channel.py` 与 `tests/test_wechat_group_web.py`，覆盖转写后钩子、两种语音策略、自由回复通过后的语音输出偏好、默认配置、非法值回退及 Web 保存字段。

验证记录：

- `python -m unittest tests.test_chat_channel_voice tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，203 个测试 OK。
- `python -m unittest discover -s tests`：通过，768 个测试 OK。
- `python -m py_compile channel\chat_channel.py channel\wechat_group\wechat_group_channel.py channel\web\web_channel.py`、`python -m json.tool config-template.json` 与 `node --check .\channel\web\static\js\console.js`：通过。

### 自定义 Provider 语音识别

- 新增 `voice/custom/custom_voice.py`，让 `custom:<id>` 复用 `custom_providers` 中的 Key/Base，通过 OpenAI-compatible `/audio/transcriptions` 完成 ASR。
- 更新 `models/custom_provider.py`、`voice/factory.py` 与 `bridge/bridge.py`：按显式 Provider ID 解析独立语音凭据，并仅在 `voice_to_text` 能力下创建自定义适配器，不依赖当前聊天 Provider；自定义 TTS 继续保持不支持。
- 更新 `channel/web/web_channel.py`：ASR 能力列表追加已配置的 `custom:<id>`，保存前校验 Provider、Key/Base 和显式 ASR 模型，保存后热刷新 Bridge 缓存；TTS 列表和保存逻辑保持不变。
- 更新 `README.md`、`tests/test_custom_provider.py`、`tests/test_custom_voice.py`、`tests/test_voice_factory.py`、`tests/test_models_handler.py` 与 `plans/20260713_自定义Provider支持ASR.md`，覆盖凭据隔离、HTTP 契约、错误脱敏和 Web 保存校验。
- 实例配置已将 `voice_to_text_model` 从无效的 `mimo-v2.5` 切换为真实验证成功的 `TeleAI/TeleSpeechASR`。

验证记录：
- 真实 ASR：`TeleAI/TeleSpeechASR` 返回 HTTP 200，本地合成语音识别为 `Hello, world`；重启后的 9901 `/api/voice/asr` 完整闭环同样成功。
- `python -m unittest tests.test_custom_provider tests.test_custom_voice tests.test_voice_factory tests.test_models_handler` 通过；Python 语法检查通过。
- `python -m unittest tests.test_audio_convert tests.test_chat_channel_voice tests.test_voice_factory tests.test_custom_voice tests.test_models_handler tests.test_models_console tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web` 通过，244 个测试 OK。
- `python -m unittest discover -s tests` 全量回归通过，762 个测试 OK。
- 2026-07-14 拆分提交阶段曾误撤回本批自定义 TTS 增量；后续确认该撤回并非用户真实意图，已在“自定义 Provider TTS 恢复”中重新实现并补齐验证。

### Agent 模型故障熔断与界面说明

- 更新 `bridge/agent_bridge.py` 与 `bridge/bridge.py`：保留当前请求首次临时故障立即 fallback 的行为，并按 `bot_type + model` 跨会话记录主模型连续故障；默认连续 3 次后熔断 300 秒，冷却结束只允许一个并发请求试探主模型，成功后自动恢复；Bridge 重置时清空运行时状态。
- 更新 `agent/protocol/agent_stream.py`：备用模型链全部耗尽时使用结构化标记终止 Agent 外层整链重试，避免重复请求主备模型并等待 30/45/60 秒。
- 更新 `config.py`、`config-template.json` 与 `channel/web/web_channel.py`：新增 `model_failover_failure_threshold`、`model_failover_cooldown_seconds` 默认配置，并向模型管理页返回实际生效参数。
- 更新 `channel/web/static/js/console.js`：在“模型管理 -> 主模型 -> 备用模型”区域展示当前请求兜底、连续临时故障熔断、冷却试探恢复和不改写主模型配置的规则，支持中英文、深色模式和窄屏换行。
- 更新 `tests/test_agent_model_fallback.py`、`tests/test_models_handler.py` 与 `tests/test_models_console.py`，新增 `plans/20260713_模型故障熔断与界面说明.md` 记录设计、实施和验证结果。

验证记录：
- RED：新增熔断测试在旧实现上出现 `_ModelFailoverState` 缺失、备用链耗尽未标记、Agent 实际调用 4 轮、API 参数缺失和 UI 文案缺失，符合预期。
- GREEN：`python -m unittest tests.test_agent_model_fallback` 通过，10 个测试 OK。
- `python -m unittest tests.test_agent_model_fallback tests.test_agent_stream_logging tests.test_agent_stream_scheduler_guard tests.test_agent_stream_retrieval_failure_recovery tests.test_agent_event_handler tests.test_agent_bridge_wechat_group_persistence tests.test_wechat_group_agent_bridge_tools tests.test_models_handler tests.test_models_console tests.test_qianfan_provider tests.test_wechat_group_channel` 通过，190 个测试 OK。
- `python -m py_compile bridge\agent_bridge.py bridge\bridge.py agent\protocol\agent_stream.py channel\web\web_channel.py`、`python -m json.tool config-template.json` 与 `node --check .\channel\web\static\js\console.js` 通过。
- 浏览器验证 `http://127.0.0.1:9902`：模型页正确显示 3 次/5 分钟规则；桌面与 375px 窄屏均无文字重叠或横向溢出，控制台 0 个错误。

## 2026-07-12

### 微信群拍一拍强制回复

- 更新 `channel/wechat_group/wechat_group_message.py`：识别 Wechaty 已上报的文本形态 `"发送者" 拍了拍我`，新增 `is_pat_self`、`pat_actor_name`、`pat_target_name` 与 `pat_suffix` 字段。
- 更新 `channel/wechat_group/wechat_group_channel.py`：将 `is_pat_self` 纳入 direct reply 判定，使用 `wechat_group_trigger_source = "pat_self"` 强制进入主回复链路，不再交给自由回复 judge 过滤；发送时不把拍一拍系统消息的群 ID 误当作成员 mention。
- 更新 `tests/test_wechat_group_message.py` 与 `tests/test_wechat_group_channel.py`：覆盖拍一拍解析和强制回复触发行为；新增 `plans/20260712_微信群拍一拍强制回复.md` 记录设计、边界和验证结果。

验证记录：
- RED：`python -m unittest tests.test_wechat_group_message.WechatGroupMessageTest.test_parse_pat_self_text_message_metadata tests.test_wechat_group_channel.WechatGroupChannelTest.test_pat_self_text_enters_forced_reply_context` 按预期失败，确认消息字段缺失且通道仍进入自由回复判定。
- GREEN：同一组定向测试通过，2 个测试 OK；补充 `test_send_pat_self_reply_does_not_mention_room_sender` 覆盖拍一拍回复不误 mention 群 ID。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web` 通过，191 个测试 OK。
- `python -m py_compile channel\wechat_group\wechat_group_message.py channel\wechat_group\wechat_group_channel.py tests\test_wechat_group_message.py tests\test_wechat_group_channel.py` 通过。

## 2026-07-12

### 微信群音频格式误判修复

- 修复 Wechaty 音频文件扩展名为 `.sil` 但真实内容为 MP3/MPEG 时被误送入 Silk 解码的问题；`voice/audio_convert.py` 新增文件头识别，`.sil/.silk/.slk` 只有在真实 Silk 或无法识别时才走 `pysilk`。
- 更新 `channel/chat_channel.py`：语音转换失败时记录脱敏的真实格式；误标 MP3/MPEG 会创建唯一临时别名交给 ASR，避免覆盖同目录已有媒体；微信群 sidecar 归档媒体源文件不再被通用语音临时清理删除。
- 更新 `tests/test_audio_convert.py`、`tests/test_chat_channel_voice.py` 与 `plans/20260712_微信群音频格式误判修复.md`，覆盖误标 `.sil`、ASR fallback 和归档媒体保留。

验证记录：
- RED：`python -m unittest tests.test_audio_convert.TestAudioConvert.test_mpeg_audio_with_silk_extension_uses_pydub_not_pysilk tests.test_chat_channel_voice.TestChatChannelVoice.test_mpeg_audio_with_silk_extension_falls_back_to_asr_alias tests.test_chat_channel_voice.TestChatChannelVoice.test_wechat_group_voice_keeps_archived_source_file` 按预期失败。
- GREEN：同一组定向测试通过，3 个测试 OK。
- 审查后 RED：`python -m unittest tests.test_chat_channel_voice.TestChatChannelVoice.test_asr_alias_does_not_overwrite_existing_audio_file` 按预期失败。
- 审查后 GREEN：`python -m unittest tests.test_chat_channel_voice.TestChatChannelVoice.test_asr_alias_does_not_overwrite_existing_audio_file tests.test_audio_convert.TestAudioConvert.test_mpeg_audio_with_silk_extension_uses_pydub_not_pysilk tests.test_chat_channel_voice.TestChatChannelVoice.test_mpeg_audio_with_silk_extension_falls_back_to_asr_alias tests.test_chat_channel_voice.TestChatChannelVoice.test_wechat_group_voice_keeps_archived_source_file` 通过，4 个测试 OK。
- `python -m unittest tests.test_audio_convert tests.test_chat_channel_voice tests.test_voice_factory tests.test_models_handler tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web` 通过，230 个测试 OK。
- `python -m py_compile voice\audio_convert.py channel\chat_channel.py tests\test_audio_convert.py tests\test_chat_channel_voice.py` 通过。
- `git diff --check -- voice/audio_convert.py channel/chat_channel.py tests/test_audio_convert.py tests/test_chat_channel_voice.py plans/20260712_微信群音频格式误判修复.md CHANGES.md` 通过，仅输出工作区 LF/CRLF 提示。

## 2026-07-12

### 微信群回复 Markdown 清洗

- 更新 `channel/wechat_group/wechat_group_reply_cleanup.py`：在既有微信群回复清洗链路中增加 Markdown 去格式化，去除标题、引用、列表、加粗/斜体包装、代码围栏、行内代码和 Markdown 链接展示符号，同时保留数学表达式、配置项、URL 与微信文字表情。
- 更新 `channel/wechat_group/wechat_group_reply_policy.py` 与 `channel/wechat_group/wechat_group_persona.py`：在微信群回复策略和三个内置人设中明确要求直接发送自然纯文本，不使用 Markdown 展示格式。
- 更新 `tests/test_wechat_group_humanization.py`、`tests/test_wechat_group_persona.py`、`tests/test_wechat_group_context.py` 与 `tests/test_wechat_group_channel.py`：覆盖清洗器、生成侧约束和发送出口归档行为；新增 `plans/20260712_微信群回复Markdown清洗修复计划.md` 并回写实施状态。

验证记录：
- RED：`python -m unittest tests.test_wechat_group_humanization.WechatGroupReplyCleanupTest` 按预期失败，证明 Markdown 标记未被清理。
- RED：`python -m unittest tests.test_wechat_group_persona tests.test_wechat_group_context` 按预期失败，证明生成侧缺少不使用 Markdown 的约束。
- GREEN：`python -m unittest tests.test_wechat_group_humanization.WechatGroupReplyCleanupTest` 通过，5 个测试 OK。
- `python -m unittest tests.test_wechat_group_persona tests.test_wechat_group_context` 通过，33 个测试 OK。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_web` 通过，84 个测试 OK。
- `python -m unittest tests.test_wechat_group_channel` 通过，104 个测试 OK。

## 2026-07-12

### 微信群回复对象意图识别

- 更新 `channel/wechat_group/wechat_group_reply_policy.py`：新增 `<wechat-group-addressee-policy>`，基于当前发言人、机器人 ID 与 `at_list` 提醒 LLM 区分请求机器人、请求其他群友和全群闲聊；同时 @ 其他群友时，不把“他/她/这个人”误解为发言人或机器人，不替被请求群友答应、拒绝或执行。
- 更新 `channel/wechat_group/wechat_group_humanized_context.py` 与 `channel/wechat_group/wechat_group_channel.py`：在人性化上下文和降级上下文中注入回复对象策略，保持现有真实 @ 发送策略不变。
- 更新 `channel/wechat_group/wechat_group_free_reply_judge.py`：自由回复 LLM judge 明确要求 A 对 B、请求群友或两人私聊场景默认 `should_reply=false`，除非文本明确请求机器人能力。
- 新增 `tests/test_wechat_group_addressee_policy.py`，覆盖回复对象策略块和自由回复 judge prompt；更新 `plans/20260712_微信群回复对象意图识别.md` 记录实施进度与验证结果。

验证记录：
- RED：`python -m unittest tests.test_wechat_group_addressee_policy` 按预期失败，缺少 `build_wechat_group_addressee_policy_block`。
- GREEN：`python -m unittest tests.test_wechat_group_addressee_policy` 通过，2 个测试 OK。
- `python -m unittest tests.test_wechat_group_free_reply_judge` 通过，6 个测试 OK。
- `python -m unittest tests.test_wechat_group_humanization` 通过，16 个测试 OK。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_humanization tests.test_wechat_group_addressee_policy tests.test_wechat_group_free_reply_judge` 通过，212 个测试 OK。
- `python -m py_compile channel\wechat_group\wechat_group_reply_policy.py channel\wechat_group\wechat_group_humanized_context.py channel\wechat_group\wechat_group_channel.py channel\wechat_group\wechat_group_free_reply_judge.py` 通过。
- `git diff --check -- channel/wechat_group/wechat_group_reply_policy.py channel/wechat_group/wechat_group_humanized_context.py channel/wechat_group/wechat_group_channel.py channel/wechat_group/wechat_group_free_reply_judge.py tests/test_wechat_group_addressee_policy.py plans/20260712_微信群回复对象意图识别.md` 通过，仅有工作区既有 LF/CRLF 提示。

## 2026-07-11

### 生图脚本 Python 3.9 兼容修复

- 在生图脚本中启用延迟注解，避免 Python 3.9 加载 `str | None` 等注解时直接失败，不改变 Python 3.10+ 行为。

验证记录：
- Python 3.9 下运行 `.venv/bin/python -m unittest tests.test_image_generation_custom_provider`：通过，5 个测试 OK。

### 生图代理域名配置

- 更新 `config.py` 与 `config-template.json`：新增 `tools.web_fetch.proxy` 以及 `skills.image-generation.proxy_enabled` / `proxy_domains` 配置，用于复用基础代理地址控制生图结果图片下载。
- 更新 `channel/channel.py` 与 `skills/image-generation/scripts/generate.py`：生图脚本 payload 透传代理配置；远程图片下载仅在启用开关、代理地址非空且 URL 域名命中配置列表时使用代理，生成接口请求本身保持原路径；补强字符串布尔值解析与 legacy `tool` / `skill` 配置合并读取。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：Web 控制台基础设置支持配置代理地址，图片与生图页支持配置生图结果图片代理开关和域名列表，并支持保存/回显。
- 更新 `tests/test_image_generation_custom_provider.py`、`tests/test_wechat_group_channel.py`、`tests/test_wechat_group_web.py`：覆盖脚本代理匹配、环境变量域名列表解析、自定义 provider 只代理结果图下载、legacy 配置合并、通道 payload 透传、空域名列表覆盖、字符串布尔值归一化、Web 配置保存/回显和前端字段存在。
- 更新 `plans/20260711_生图代理域名配置.md`：记录实际改动、完成状态与验证结果。

验证记录：
- `python -m unittest tests.test_image_generation_custom_provider.TestImageGenerationCustomProvider.test_custom_provider_generation_proxies_result_download_only tests.test_image_generation_custom_provider.TestImageGenerationCustomProvider.test_load_image_proxy_config_merges_mixed_legacy_namespaces tests.test_wechat_group_channel.WechatGroupChannelTest.test_image_create_script_payload_normalizes_string_false_proxy_enabled`：通过，3 个测试 OK。
- `python -m unittest tests.test_image_generation_custom_provider tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，192 个测试 OK。
- `node --check .\channel\web\static\js\console.js`：通过。
- `python -m py_compile channel\channel.py channel\web\web_channel.py skills\image-generation\scripts\generate.py config.py`：通过。
- `python -m json.tool config-template.json`：通过。
- `git diff --check`：通过，仅输出工作区 LF/CRLF 提示。
- `python -m unittest discover -s tests`：通过，730 个测试 OK。

### Agent 模型限流自动切换与微信群错误脱敏

- 更新 `bridge/agent_bridge.py`：`AgentLLMModel` 新增 `model_fallbacks` 候选轮询，主模型遇到 408/429/5xx、超时、rate limit、FreeUsageLimitError 等临时模型故障时自动尝试下一个配置候选；流式响应仅在首个 chunk 即临时错误时切换，避免已输出内容后混用多个模型。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：Web 控制台“模型管理 -> 主模型”支持配置 `model_fallbacks` 备用模型列表，保存主模型时可同步持久化备用候选。
- 更新 `channel/wechat_group/wechat_group_channel.py`：微信群发送层仅对 `AgentBridge` 包装出的临时模型故障类 `ReplyType.ERROR` 做脱敏，非强制回复静默不发到底层群聊；强制回复场景改发脱敏兜底文案 `别@我了哥，没Token了。`，不再外显供应商 429/FreeUsageLimitError 原文；普通工具、插件或业务错误即使包含 timeout 也仍按原错误回复。
- 更新 `config.py` 与 `config-template.json`：新增 `model_fallbacks` 默认空列表，支持手工配置备用聊天模型渠道，例如 `{"bot_type": "custom:backup", "model": "backup-model"}`；默认空配置保持原行为。
- 新增 `tests/test_agent_model_fallback.py` 与 `tests/test_models_console.py`，并更新 `tests/test_models_handler.py`、`tests/test_wechat_group_channel.py`：覆盖流式/非流式 fallback、仅填写模型名时按模型推断 Provider、非临时 400 不切换、Web API/UI 配置 `model_fallbacks`、微信群临时模型错误不外显、强制回复兜底和业务错误仍可见。
- 更新 `plans/20260711_模型渠道限流自动切换.md`：记录本次设计、TDD 步骤、实际改动和验证结果。

验证记录：
- RED：`python -m unittest tests.test_agent_model_fallback` 按预期失败，证明当前流式 429 与非流式 429 不会自动 fallback。
- GREEN：`python -m unittest tests.test_agent_model_fallback` 通过，4 个测试 OK。
- RED：`python -m unittest tests.test_wechat_group_channel` 中新增 2 个临时模型错误外显用例按预期失败，证明当前会把 `Agent error: ... Status: 429 ... FreeUsageLimitError` 发到群里。
- GREEN：`python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_send_business_error_reply_to_original_room_with_sender_mention tests.test_wechat_group_channel.WechatGroupChannelTest.test_send_suppresses_transient_agent_error_when_not_forced tests.test_wechat_group_channel.WechatGroupChannelTest.test_send_forced_transient_agent_error_uses_token_exhausted_hint` 通过，3 个测试 OK。
- RED：`python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_send_non_agent_timeout_error_is_not_suppressed` 按预期失败，证明仅按 timeout 关键字判断会误吞非模型业务错误。
- GREEN：`python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_send_non_agent_timeout_error_is_not_suppressed tests.test_wechat_group_channel.WechatGroupChannelTest.test_send_suppresses_transient_agent_error_when_not_forced tests.test_wechat_group_channel.WechatGroupChannelTest.test_send_forced_transient_agent_error_uses_token_exhausted_hint` 通过，3 个测试 OK。
- GREEN：`python -m unittest tests.test_wechat_group_channel` 通过，101 个测试 OK；输出中存在既有后台消费线程在测试退出阶段打印的 `MemoryError` 噪声，但 unittest 退出码为 0。
- RED：`python -m unittest tests.test_models_handler.TestModelsHandler.test_chat_capability_exposes_model_fallbacks_for_ui tests.test_models_handler.TestModelsHandler.test_set_chat_persists_model_fallbacks tests.test_models_console.TestModelsConsole.test_models_page_exposes_chat_fallback_controls` 按预期失败，证明 Web API 和模型页尚不能配置 `model_fallbacks`。
- GREEN：同一组 `model_fallbacks` Web 配置测试通过，3 个测试 OK。
- `python -m unittest tests.test_models_handler tests.test_models_console` 通过，24 个测试 OK。
- `node --check .\channel\web\static\js\console.js` 通过。
- `python -m py_compile bridge\agent_bridge.py channel\web\web_channel.py channel\wechat_group\wechat_group_channel.py` 通过；`python -m json.tool config-template.json` 通过。
- `python -m unittest tests.test_wechat_group_message` 通过，5 个测试 OK。
- `git diff --check -- bridge/agent_bridge.py channel/wechat_group/wechat_group_channel.py config.py config-template.json tests/test_agent_model_fallback.py tests/test_wechat_group_channel.py CHANGES.md plans/20260711_模型渠道限流自动切换.md` 通过，仅输出工作区既有 LF/CRLF 提示。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web` 通过，185 个测试 OK。
- `python -m unittest tests.test_agent_model_fallback tests.test_models_handler tests.test_models_console tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web` 通过，212 个测试 OK。

## 2026-07-10

### 微信群 Silk 语音转写与语音 Provider 防御修复

- 修复微信群 Silk 语音因缺少正确依赖而出现 `pysilk` 未定义、转换失败后仍把原始 Silk 交给 ASR，以及无效 `custom:*` ASR/TTS Provider 触发空 `RuntimeError` 并中断当前 Worker 的连续故障。
- 更新 `requirements-optional.txt`、`voice/audio_convert.py` 与 `voice/baidu/README.md`：声明 `pysilk-mod>=1.6.4`，当前环境已安装 `pysilk-mod 1.6.4`（导入名为 `pysilk`）；按 WAV、Silk、其他 `pydub` 格式分别检查依赖，真实 PCM→Silk→WAV 回环用例实际执行且未 skip。当前 `ffmpeg` 检查结果为 `NOT_FOUND`，不影响 Silk 分支，但其他 `pydub` 转码格式仍需系统级 `ffmpeg`。
- 更新 `channel/chat_channel.py`：Silk 转换失败时返回可操作错误并停止 ASR，其他可能被下游直接接受的音频格式保留原始文件兼容路径；清理临时文件且日志不输出完整媒体路径、语音内容或用户标识。
- 更新 `voice/factory.py` 与 `bridge/bridge.py`：集中声明运行时支持的 ASR/TTS Provider，以包含 Provider 的 `UnsupportedVoiceProviderError` 替代空异常；Bridge 仅捕获该配置异常并返回 `ReplyType.ERROR`，不吞掉未知编程错误，修正配置并刷新后可恢复创建 Voice Bot。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：Web/API 拒绝 `custom`、`custom:<id>` 和未知语音 Provider；切换 ASR Provider 且未显式选择模型时清除旧供应商模型；历史无效配置与语音工厂支持但不在 Web 白名单中的合法直配 Provider 分开提示，避免重新保存无效值。
- 新增或更新 `tests/test_audio_convert.py`、`tests/test_chat_channel_voice.py`、`tests/test_voice_factory.py`、`tests/test_models_handler.py` 与 `tests/test_wechat_group_web.py`，并更新根 README 与实施计划。自定义 OpenAI-compatible 聊天 Provider 不会自动获得 ASR/TTS 能力。

验证记录：
- 初始 RED：`python -m unittest tests.test_audio_convert tests.test_chat_channel_voice tests.test_models_handler tests.test_voice_factory tests.test_wechat_group_web.WechatGroupWebTest.test_models_console_surfaces_invalid_voice_provider_warning` 共运行 21 项，出现 12 failures、1 skip，覆盖缺失 Silk 依赖错误、原始 Silk 透传、无效 Provider 保存、旧模型残留、Factory/Bridge 错误及前端告警缺失；后续代码审查补强用例也先确认 RED 再实现 GREEN。
- `python -m unittest tests.test_audio_convert tests.test_chat_channel_voice tests.test_voice_factory tests.test_models_handler`：通过，37 个测试 OK。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，178 个测试 OK。
- `python -m unittest discover -s tests`：通过，692 个测试 OK。
- `node --check .\channel\web\static\js\console.js`：通过；`git diff --check`：通过，仅有工作区既有 LF/CRLF 提示。
- 自动化与代码审查已完成；本次未启动真实微信群、扫码、发送真实语音、发起真实 ASR/TTS 网络请求或修改真实 `config.json`。有效 ASR/TTS 凭据配置与真实微信群语音闭环仍待人工验收。

### 微信群图片 XML 误判 HEVC 修复

- 更新 `channel/wechat_group/wechat_group_channel.py`：直接图片和自由回复图片统一使用语义化默认问题进入 `_compose_context()`，不再把 Wechaty 图片 `message.text()` 中含 `hevc_mid_size` 的传输层 XML 写入当前 LLM 消息或 `wechat_group_user_content`；图片原始 XML、媒体归档和 Vision 多模态摘要链路保持不变。
- 修复 `wechat_group_image_understanding_comment_enabled = false` 时图片 XML 因非空而绕过纯图片评论开关的问题。
- 加固所有已确认的 XML 回灌边界：引用图片/贴纸只输出语义占位符；无媒体路径的 recent transcript 与焦点栈不再读取非文本原文；画像进化 LLM 对非文本消息只接收类型占位；贴纸收藏不再把 XML 作为描述，贴纸搜索/发送工具会屏蔽既有污染描述。
- 新增 `channel/wechat_group/wechat_group_transport.py` 共享检测器：结合媒体标签与微信协议字段识别图片/贴纸传输 XML，并兼容历史上被误标为 `message_type = text` 的归档；引用定位、recent、archive evidence、local summary、焦点和画像提取统一复用，不修改原始归档。
- 更新微信群通道、上下文、焦点、多模态、画像和贴纸工具相关测试：使用脱敏的真实图片/贴纸 XML fixture 覆盖直接图片、自由回复图片、纯图片评论关闭、引用归档与 fallback、媒体下载失败、画像提取及贴纸工具输出，并验证协议字段不会进入 prompt、工具结果或 Agent 持久化输入。
- 更新 `AGENTS.md` 与 `plans/20260710_微信群图片XML误判HEVC修复计划.md`，固化传输层 XML 与用户语义内容的边界并记录实施结果。
- 2026-07-11 经用户确认后执行受污染会话隔离：停服并备份会话数据库，将两个微信群会话的 `context_start_seq` 分别设置为 `134` 和 `126`；历史消息未删除，微信群归档未修改，随后重启 CowAgent。
- 2026-07-11 真实微信群核对：图片入站日志投影为 `text="[image]"`，后续 @ 图片追问的 Agent 输入为用户文本“这图是啥意思”并携带 `multimodal` 上下文，未出现图片 XML 或 HEVC 误判。

验证记录：
- 定向 TDD 红灯：3 个测试均按预期失败；两条路径将 XML 写入 `wechat_group_user_content`，关闭纯图片评论后仍调用 Vision。
- 定向 TDD 绿灯：`python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_image_message_uses_readable_default_question tests.test_wechat_group_channel.WechatGroupChannelTest.test_worker_approved_image_free_reply_injects_vision_summary tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_image_transport_xml_does_not_bypass_comment_disabled`：通过，3 个测试 OK。
- 审查补充 TDD 红灯：10 个引用、无媒体上下文、画像和贴纸工具用例均按预期失败，失败输出确认原始 XML 会经旁路进入模型或工具结果。
- 审查补充 TDD 绿灯：同一组 10 个测试通过。
- 历史兼容 TDD 红灯：6 个 `message_type = text` 但正文为真实形态 XML 的用例均按预期失败，覆盖引用、recent、focus、画像、archive evidence 与 local summary。
- 历史兼容 TDD 绿灯：同一组 6 个测试通过；共享检测器额外验证普通 `<img src=...>` HTML 和纯文本协议讨论不会被误判。
- `python -m unittest tests.test_agent_bridge_wechat_group_persistence`：通过，3 个测试 OK。
- `python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_multimodal_context_service tests.test_wechat_group_context tests.test_agent_bridge_wechat_group_persistence`：通过，131 个测试 OK。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，178 个测试 OK。
- `python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_focus_service tests.test_wechat_group_multimodal_context_service tests.test_wechat_group_profile_llm_extractor tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_sticker_service tests.test_agent_bridge_wechat_group_persistence`：通过，163 个测试 OK。
- `python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_focus_service tests.test_wechat_group_multimodal_context_service tests.test_wechat_group_profile_llm_extractor tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_sticker_service tests.test_agent_bridge_wechat_group_persistence tests.test_wechat_group_humanization`：通过，176 个测试 OK。
- 2026-07-11 继续复核：`python -m unittest tests.test_wechat_group_transport tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_focus_service tests.test_wechat_group_multimodal_context_service tests.test_wechat_group_profile_llm_extractor tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_humanization tests.test_wechat_group_learner tests.test_wechat_group_profile_service tests.test_wechat_group_style_service`：通过，201 个测试 OK；`git diff --check` 通过。
- 2026-07-11 会话隔离验证：两个已确认微信群会话的 `load_messages(max_turns=20)` 均不再返回 `HEVC` 或 `hevc_mid_size` 内容；历史污染记录仍保留在数据库中，可审计但不再进入 LLM 上下文。
- 2026-07-11 真实链路验证：08:10 至 08:12 的 `run.log` 中 `HEVC`、`hevc_mid_size`、`<?xml`、`<img` 命中数为 0；最新图片追问会话 `wechat_group:wgr_bec3418e4d214a039df11d7d9f4a35b6` 的 `load_messages(max_turns=20)` 返回 39 条上下文消息，未包含 `HEVC`、`hevc_mid_size` 或图片 XML。

### 微信群画像进化 LLM 临时不可用修复

- 更新 `channel/wechat_group/wechat_group_profile_llm_extractor.py`：新增画像抽取异常分类，识别 `{"error": true, "status_code": ...}` 模型错误 envelope，避免把 HTTP 503/429 等供应商临时故障误报为画像 JSON 解析失败。
- 更新 `channel/wechat_group/wechat_group_profile_evolution_executor.py` 与 `wechat_group_profile_evolution_trigger.py`：失败原因写入可读的供应商状态；临时故障复用现有 idle 窗口退避，不推进归档游标、不执行画像合并，减少自动触发重复 warning。
- 更新画像进化 extractor、executor、trigger 回归测试，并回写 `plans/20260710_微信群画像进化LLM临时不可用修复计划.md`。

验证记录：
- `python -m unittest tests.test_wechat_group_profile_llm_extractor tests.test_wechat_group_profile_evolution_executor tests.test_wechat_group_profile_evolution_trigger`：通过，13 个测试 OK。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，177 个测试 OK。

### 微信群稳定身份自动恢复与群名回显修复

- 更新 `channel/wechat_group/wechat_group_identity_store.py` 与 `wechat_group_identity_service.py`：保留 `stable account -> stable room -> stable member` 双层身份模型；账号按强微信号、runtime alias 或唯一 sidecar profile 自动恢复，同一 stable account 下唯一完全同名群自动恢复原 stable room，成员按 `wechat_id/weixin/wxid` 自动恢复原 stable member。
- 收紧群名恢复边界：inactive `suspected` alias 不得绕过唯一候选检查；同一当前登录态中已被另一个 runtime room 占用的同名群自动隔离，群列表尚未同步时也不会把两个同名群合并到同一 `wgr_...`；同名集合一旦出现多个 runtime，瞬时解析失败后的重试也不会重新开放群名恢复；会话判断与 room 解析使用同一原子锁，避免并发消息反序落库时误合并。
- 收紧成员权限继承边界：缺少强微信号或微信号候选歧义时，不再按昵称或旧管理员 active alias 复用旧成员，而是自动创建 confirmed 隔离 stable member；后续消息只复用同一歧义隔离 alias，避免 stable member 持续漂移。
- 加固自动解析状态机：room/member 写入前校验 confirmed 父级，进程级解析锁覆盖候选读取至 alias 激活；sidecar 与身份服务共享实际默认 profile 路径，并兼容唯一空路径旧 alias 的自动迁移。
- 更新 `channel/wechat_group/wechat_group_channel.py`：自动恢复后的 stable 群直接参与目标群筛选；新增线程安全的登录会话群名/runtime 集合，新登录转换时重置、重复 `logged_in` 状态不重置；群列表按不同 runtime ID 判断同名歧义，重复返回同一 room 不会阻断跨登录恢复；未选中群的入站消息新增 `reason=unselected_room` INFO 路由日志，仅记录 message ID、runtime/stable room ID 和群名，不记录消息正文或媒体路径。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：移除 Web“身份恢复”人工确认页面和确认交互，旧确认 API 停止写入并返回自动恢复提示；身份异常仅保留为只读诊断；保存目标群时把误提交的 runtime room ID 转换为 stable room ID。
- 修复“群与管理员”已保存群名回显：优先显示实时群名，实时列表缺失时使用持久化 `selected_room_names`，最后才回退“已保存群 N”；离线、缺失或 identity unresolved 的已保存群再次保存时继续保留，仅在明确取消或按 room ID 删除时移除。
- 更新身份、通道、Web 与画像回归测试；画像测试通过显式 suspected alias 保留“未确认历史别名不得扩展群画像范围”的安全边界。
- 新增并回写 `plans/20260710_微信群稳定身份自动恢复开发计划.md`，记录实施结果、验证命令和真实微信链路待验证项。

验证记录：
- `node --test channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`：通过，29 个测试 OK。
- `python -m unittest tests.test_wechat_group_identity_store tests.test_wechat_group_identity_service tests.test_wechat_group_stable_identity_integration`：通过，39 个测试 OK。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，175 个测试 OK。
- `python -m unittest tests.test_wechat_group_permissions tests.test_wechat_group_persona tests.test_wechat_group_profile_service tests.test_wechat_group_free_reply`：通过，63 个测试 OK。
- `node --check channel/web/static/js/console.js` 与相关 Python 文件 `py_compile`：通过。
- `python -m unittest discover -s tests`：通过，652 个测试 OK。

### 微信群贴纸下载异常降级修复

- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`：新增可测试的贴纸下载编排，FileBox 下载抛错或产生空文件时改用原始消息 XML 中的媒体 URL；两条路径均不可用时返回失败状态，不再向通道层泄露 puppet 的 XML 解析异常。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar.mjs`：贴纸下载传入已获取的 `rawPayload.Content` 并按下载结果返回有效或空 `file_path`；图片、语音、视频和文件继续沿用原异常处理逻辑。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`：覆盖 FileBox 抛出 `reading 'msg'` 后备用下载成功，以及 `[动画表情]` 占位内容无法下载时安静降级两个场景。
- 新增并回写 `plans/20260710_微信群贴纸下载异常修复计划.md`，记录实施范围、TDD 过程、验证结果和真实链路待验证事项。

验证记录：
- `node --test --test-name-pattern='downloadStickerMediaWithFallback' wechaty-sidecar-core.test.mjs`：新增测试先失败，原因为 `downloadStickerMediaWithFallback is not defined`；实现后 2 个测试通过。
- `channel/wechat_group/sidecar` 下执行 `npm test`：通过，30 个测试 OK。
- `node --check wechaty-sidecar.mjs` 与 `node --check wechaty-sidecar-core.mjs`：通过。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，163 个测试 OK。

### 微信群稳定身份显式配置二次修复

- 新增 `wechat_group_free_reply_stable_room_ids` 与 `wechat_group_blocked_stable_member_ids` 默认配置，避免继续用旧 runtime 字段承载 stable 语义。
- 更新自由回复和通道黑名单判断：自由回复范围优先读取 stable room 配置；成员黑名单优先读取 stable member 配置，同时保留旧 `wechat_group_free_reply_room_ids` 与 `wechat_group_blocked_sender_ids` legacy fallback。
- 更新 Web/API 与控制台保存链路：Web extra 返回自由回复 stable/legacy room 字段和黑名单 stable/legacy 字段；控制台保存自由回复群范围时写 stable 主配置，并保留旧 runtime 快照。
- 修复控制台 legacy 自由回复配置兼容：旧 runtime room 配置会映射到 stable 勾选态；用户在界面明确取消勾选时不再被旧字段回填。
- 更新 `scripts/migrate_wechat_group_identity.py`：迁移旧自由回复 room 配置到 `wechat_group_free_reply_stable_room_ids`，并把可解析的旧 blocked sender 转换到 `wechat_group_blocked_stable_member_ids`。
- 加固迁移脚本幂等性与安全报告：保留已有 stable 配置，未映射 room 和歧义 blocked sender 进入人工确认，SQLite `media_path` 缺失文件进入报告且不阻断迁移。
- 修复群列表身份链路：sidecar room 列表先解析 stable account/room；未解析 room 不再伪装 stable，待确认 room 不进入消息处理。
- 收紧名称配置边界：`wechat_group_names` 与 `wechat_group_free_reply_names` 只用于候选发现和显示，不再直接放行消息或自由回复。
- 更新 Web 与桌面群选择：只允许选择已确认 stable room；身份确认成功后同步刷新运行中 room 绑定状态。
- 补充归档媒体路径 metadata：新归档消息写入 `runtime_media_path`、`stable_media_path` 和 `media_path_storage`，当前未物理重排时明确标记为 `runtime_legacy`。
- 补齐 stable account -> room -> member 身份恢复顺序：Web 身份恢复新增账号确认入口，账号未确认时不能确认群；确认接口校验实体存在、所属 account/room 一致，并记录真实确认时间。
- 补齐在线成员 stable 映射和管理员确认闭环：成员列表返回 stable/runtime 双身份及确认状态；未确认成员不能写入管理员配置；迁移管理员标记为 `legacy_imported`，成员确认后自动更新并持久化管理员配置。
- 拒绝跨账号 legacy runtime 歧义解析：同一 runtime room/sender 命中多个 stable account 时返回未解析，在线成员优先使用当前运行中 room 的 stable 映射。
- 修复通道层 stable scope 遗漏：管理员硬门禁和 humanized 降级上下文改用 stable room/member；生图小时额度按 stable room 计数。
- 扩展 assistant reply 与 image usage 归档：新增 stable/runtime room/member 快照列和 stable 索引，重登后群名查询与生图额度连续。
- 修复 scheduler 会话稳定性：Agent/Skill 隔离 session 使用 stable receiver，send/tool delivery context 使用 stable `notify_session_id`，runtime receiver 仅用于投递。
- 修复 inactive candidate alias 重复解析绕过：未激活 account/room/member alias 始终保持 suspected，不能因目标 stable 实体已 confirmed 自动放行。
- 修复未确认 alias 的权限继承：本轮身份待确认时，通道硬门禁、Prompt 角色、Agent 工具过滤和人设跳过判断统一按普通成员处理。
- 修复历史画像按 stable 群过滤为空：画像列表、群内昵称和群内别名统一展开 active 或显式确认的历史 runtime room alias，并排除仅为 `suspected` 的同名候选。
- 更新 Web、通道与 Agent 画像链路：统一注入 identity-aware profile service；Web 画像筛选显式传 `stable_room_id`，画像编辑不再把 legacy sender ID 标记为 stable member。
- 扩展迁移脚本：修复误写入 stable 群配置的 runtime ID，扫描历史画像 room 来源，并支持在不切换 active 发送目标的情况下显式确认新建或已有 `suspected` 历史 alias。
- 完成本机历史画像关联修复：写入前创建配置、identity DB 和画像 DB 备份；修复 7 个配置项并确认 7 个历史 room alias，画像总量保持 102。
- 补充迁移运行边界：最终复核发现遗留旧版 `app.py`/sidecar 进程会以迁移前内存配置覆盖磁盘；已停止进程树、保存二次污染快照并重新 apply，计划明确后续迁移必须离线执行。
- 更新 `plans/20260709_微信群稳定身份无降级改造方案.md` 与 `plans/20260709_微信群稳定身份显式配置二次修复计划.md`：回写二次复查、实际改动、验证结果和媒体物理迁移剩余边界。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_record_inbound_message_keeps_runtime_media_path_metadata tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_returns_stable_room_selection_and_runtime_alias`：通过。
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_saves_wechat_group_free_reply_stable_room_ids tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_returns_stable_room_selection_and_runtime_alias`：通过。
- `node --check channel\web\static\js\console.js`：通过。
- `python -m py_compile channel\wechat_group\wechat_group_channel.py channel\web\web_channel.py tests\test_wechat_group_channel.py tests\test_wechat_group_web.py`：通过。
- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_stable_identity_integration`：通过，179 个测试 OK。
- `python -m unittest discover -s tests`：通过，580 个测试 OK。
- `Set-Location -LiteralPath .\desktop` 后执行 `npm run build`：通过；仅有既有字体运行时解析和 chunk 体积警告。
- `python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_humanization tests.test_wechat_group_identity_service tests.test_wechat_group_identity_store tests.test_wechat_group_stable_identity_integration tests.test_wechat_group_web tests.test_scheduler_wechat_group_delivery tests.test_scheduler_ui`：通过，210 个测试 OK。
- `python -m unittest discover -s tests`：通过，596 个测试 OK。
- `channel/wechat_group/sidecar` 下执行 `npm test`：通过，28 个测试 OK。
- `desktop` 下执行 `npm run build`：通过；仅有既有字体路径和 chunk 体积警告。
- 画像筛选与已有 suspected 历史 alias 两个新增用例均完成先失败、后通过的红绿验证。
- `python -m unittest tests.test_wechat_group_identity_service tests.test_wechat_group_profile_service tests.test_wechat_group_stable_identity_integration tests.test_wechat_group_web tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_channel`：通过，202 个测试 OK。
- `python -m unittest discover -s tests`：通过，611 个测试 OK。
- 本机迁移修复后 dry-run：新增 room 0、已确认 room 7、stable 配置待修复 0、历史画像候选 0、冲突 0、人工确认 0；当前 active room alias 与备份一致。
- 二次恢复后确认 7 个 stable 群配置均为 `wgr_*`，画像总量仍为 102，按群过滤已返回历史画像；`python app.py` 与 Wechaty sidecar 均已停止。

## 2026-07-09

### 微信群稳定身份无降级阶段改造

- 新增 `channel/wechat_group/wechat_group_identity_store.py` 与 `wechat_group_identity_service.py`：引入 stable account / stable room / stable member 与 runtime alias 的持久化和解析能力。
- 更新微信群入口、归档、上下文、人设、权限、Agent 工具绑定、学习、画像、画像进化、多模态、焦点、情绪、自由回复、风格、表情和 scheduler 投递链路：发送仍使用 runtime ID，长期配置/状态/记忆/画像/调度优先使用 stable ID，并保留 legacy runtime 兼容读。
- 更新 Web 与桌面配置链路：新增 `wechat_group_stable_room_ids` 默认配置；Web extra 返回 stable room、runtime alias 和绑定状态；Web/桌面保存目标群时写 stable room，同时保留 runtime 快照。
- 新增 Web 身份恢复能力：管理 API 支持 `stable_room_id` / `stable_member_id` 入参和 legacy 转换，新增身份候选查询、room/member/account 确认接口，控制台提供身份恢复入口，桌面二维码弹窗提示待确认绑定数量。
- 新增 `scripts/migrate_wechat_group_identity.py` 和 `tests/test_wechat_group_stable_identity_integration.py`：支持 dry-run/apply、旧配置迁移、identity alias 写入、带 stable 列 SQLite 表补写、scheduler stable 投递字段补写，以及跨账号同名群冲突报告。
- 更新 `AGENTS.md`：明确微信群稳定身份改造后长期数据和权限优先使用 stable 字段，旧 `room_id` / `sender_id` 仅作为 runtime legacy 快照。
- 更新 Qianfan / MiniMax 既有测试：适配当前文档结构、多语言 provider label 和 Windows UTF-8 源码读取，避免全量 `unittest discover` 被无关测试断言阻断。
- 更新 `plans/20260709_微信群稳定身份无降级改造方案.md`：回写 Task 1 至 Task 10 完成状态、实际改动、验证结果与剩余物理媒体路径迁移边界。

验证记录：
- `python -m unittest tests.test_wechat_group_identity_store tests.test_wechat_group_identity_service`：通过。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过。
- `python -m unittest tests.test_wechat_group_permissions tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_persona`：通过。
- `python -m unittest tests.test_wechat_group_humanization tests.test_wechat_group_multimodal_context_service`：通过。
- `python -m unittest tests.test_wechat_group_learner tests.test_wechat_group_profile_store tests.test_wechat_group_profile_service tests.test_wechat_group_memory_tools`：通过。
- `python -m unittest tests.test_wechat_group_profile_evolution_executor tests.test_wechat_group_profile_evolution_store tests.test_wechat_group_profile_evolution_merger tests.test_wechat_group_profile_evolution_trigger`：通过。
- `python -m unittest tests.test_wechat_group_focus_service tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_worker tests.test_wechat_group_free_reply_judge tests.test_wechat_group_emotion_service tests.test_wechat_group_style_service tests.test_wechat_group_sticker_service tests.test_wechat_group_sticker_online`：通过。
- `python -m unittest tests.test_scheduler_wechat_group_delivery tests.test_scheduler_ui tests.test_wechat_group_web`：通过。
- `python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_context`：通过。
- `python -m unittest tests.test_wechat_group_stable_identity_integration`：通过。
- `python -m unittest tests.test_wechat_group_identity_store tests.test_wechat_group_identity_service tests.test_wechat_group_stable_identity_integration`：通过。
- `python -m unittest tests.test_qianfan_provider tests.test_minimax_provider`：通过。
- `python -m unittest discover -s tests`：通过；本机先安装缺失的 `pytest`，用于 pytest 风格 bash 测试模块导入。
- `Set-Location -LiteralPath .\desktop` 后执行 `npm install`、`npm run build`：通过；构建输出仅包含字体运行时解析提示和 chunk 体积警告。
- `channel/wechat_group/sidecar` 目录执行 `npm test`：通过。

### 微信群引用消息 @ 机器人回复修复

- 修复 `channel/wechat_group/wechat_group_channel.py`：微信群文本 direct reply（明确 @ 机器人）也设置 `wechat_group_force_reply`，避免微信引用格式消息被通用群聊引用过滤拦截。
- 保持引用机器人自身的标记边界不变：只有 `is_quote_self = true` 时才写入 `wechat_group_quote_self_triggered`。
- 更新 `tests/test_wechat_group_channel.py`：新增“引用别人消息后 @ 机器人询问图片含义”应进入 direct reply 上下文的回归测试。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_reference_text_enters_direct_reply_context`：新增测试先失败，表现为 `produce()` 未被调用；修复后通过。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，127 个测试 OK。
- `python -m py_compile channel\wechat_group\wechat_group_channel.py tests\test_wechat_group_channel.py`：通过。

### 微信群画像自主进化自动学习

- 新增 `channel/wechat_group/wechat_group_profile_evolution_store.py`、`wechat_group_profile_llm_extractor.py`、`wechat_group_profile_evolution_merger.py`、`wechat_group_profile_evolution_executor.py`、`wechat_group_profile_evolution_trigger.py` 和 `wechat_group_profile_evolution_rollback.py`：复用归档、画像服务和当前 Agent 模型，实现按群自动触发、LLM 结构化提取、服务端自动合并、diff 记录与回滚入口。
- 更新 `channel/wechat_group/wechat_group_channel.py`：群消息归档成功后记录画像演进 signal，通道启动后启动后台扫描线程；扫描仍受 `wechat_group_profile_evolution_enabled` 开关控制，默认关闭。
- 更新 `channel/web/web_channel.py`、`channel/web/static/js/console.js`：新增 `/api/wechat-group/memories/profile-evolution/*` API 和群记忆页 UI，展示配置、状态、运行记录、详情和回滚按钮。
- 更新 `config.py` 与 `config-template.json`：新增 `wechat_group_profile_evolution_enabled`、`idle_minutes`、`min_messages`、`max_interval_minutes` 和 `batch_message_limit` 默认配置。
- 更新相关测试：覆盖存储、LLM 抽取、合并、执行器、触发器、归档 signal、Web API 与 UI 静态入口。

验证记录：
- `python -m unittest tests.test_wechat_group_profile_llm_extractor`：通过，4 个测试 OK。
- `python -m unittest tests.test_wechat_group_web`：通过，59 个测试 OK；输出中的 `room_id is required` 为既有负向用例的预期错误日志。
- `python -m unittest tests.test_wechat_group_memory_ui`：通过，5 个测试 OK。
- `python -m unittest tests.test_wechat_group_profile_llm_extractor tests.test_wechat_group_profile_evolution_store tests.test_wechat_group_profile_evolution_trigger tests.test_wechat_group_profile_evolution_executor tests.test_wechat_group_web tests.test_wechat_group_memory_ui tests.test_wechat_group_channel.WechatGroupChannelTest.test_record_inbound_message_notifies_profile_evolution_signal`：通过，76 个测试 OK。
- `node --check channel\web\static\js\console.js`：通过。
- `python -m unittest tests.test_wechat_group_profile_evolution_store tests.test_wechat_group_profile_evolution_merger tests.test_wechat_group_profile_llm_extractor tests.test_wechat_group_profile_evolution_executor tests.test_wechat_group_profile_evolution_trigger tests.test_wechat_group_profile_service tests.test_wechat_group_context tests.test_wechat_group_memory_tools tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_memory_ui`：通过，185 个测试 OK。
- `python -m py_compile channel\wechat_group\wechat_group_profile_evolution_store.py channel\wechat_group\wechat_group_profile_evolution_merger.py channel\wechat_group\wechat_group_profile_llm_extractor.py channel\wechat_group\wechat_group_profile_evolution_executor.py channel\wechat_group\wechat_group_profile_evolution_trigger.py channel\wechat_group\wechat_group_profile_evolution_rollback.py channel\web\web_channel.py channel\wechat_group\wechat_group_channel.py`：通过。

### 微信群拟人化回复尾问清洗

- 修复 `channel/wechat_group/wechat_group_reply_cleanup.py`：发送前清洗补充“你想了解具体哪方面”“要不要继续展开/对比”等咨询式尾问匹配，避免群聊回复以销售式追问收尾。
- 更新 `channel/wechat_group/wechat_group_reply_policy.py`：direct reply / quote / image / free reply 策略统一补充紧凑回复和禁止追问收尾约束，降低模型生成长篇尾问回复的概率。
- 更新 `tests/test_wechat_group_humanization.py` 与 `tests/test_wechat_group_context.py`：新增车评类尾问清洗和 direct reply 策略约束回归测试。

验证记录：
- `python -m unittest tests.test_wechat_group_humanization.WechatGroupReplyCleanupTest.test_cleanup_removes_consultative_followup_tail_question`：新增测试先失败，表现为“你想了解具体的哪方面...”未被移除；实现后通过。
- `python -m unittest tests.test_wechat_group_context.WechatGroupReplyPolicyTest.test_direct_reply_policy_requires_compact_answer_without_tail_question`：新增测试先失败，表现为 direct reply 策略缺少紧凑与禁止尾问约束；实现后通过。
- `python -m unittest tests.test_wechat_group_humanization tests.test_wechat_group_context tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，157 个测试 OK。
- `python -m py_compile channel\wechat_group\wechat_group_reply_cleanup.py channel\wechat_group\wechat_group_reply_policy.py tests\test_wechat_group_humanization.py tests\test_wechat_group_context.py`：通过。

### 微信群自由回复 AI 看法评分大小写适配

- 修复 `channel/wechat_group/wechat_group_free_reply.py`：`ai_opinion` 评分规则改为大小写不敏感匹配，`AI怎么看`、`ai怎么看`、`Ai怎么看`、`aI怎么看` 以及 `问问AI/ai/Ai/aI` 均可获得“询问 AI 看法”加分。
- 更新 `tests/test_wechat_group_free_reply.py`：新增混合大小写 AI 看法问题的回归测试，防止后续恢复为大小写敏感匹配。

验证记录：
- `python -m unittest tests.test_wechat_group_free_reply.WechatGroupFreeReplyDecisionTest.test_ai_opinion_matches_ai_case_insensitively`：新增测试先失败，表现为 `Ai/aI` 未触发且缺少 `ai_opinion`；实现后通过。
- `python -m unittest tests.test_wechat_group_free_reply`：通过，27 个测试 OK。
- `python -m py_compile channel\wechat_group\wechat_group_free_reply.py tests\test_wechat_group_free_reply.py`：通过。

### 微信群自由回复复读文本冷却

- 修复 `channel/wechat_group/wechat_group_free_reply.py`：新增 `repeater_text_cooldown` 抑制规则。当前群同一句复读已经被机器人接过后，30 分钟内再次命中 `repeater_message` 不再触发自由回复，避免机器人跟着群友反复复读同一句。
- 修复 `channel/wechat_group/wechat_group_channel.py`：自由回复 worker 通过后，仅当本地决策包含 `repeater_message` 时记录本次复读文本，不影响普通自由回复、图片自由回复和常规冷却逻辑。
- 更新 `tests/test_wechat_group_free_reply.py`：新增同句复读已被机器人接过后的抑制回归测试。

验证记录：
- `python -m unittest tests.test_wechat_group_free_reply`：通过，26 个测试 OK。
- `python -m unittest tests.test_wechat_group_free_reply_worker`：通过，9 个测试 OK。
- `python -m unittest tests.test_wechat_group_channel`：通过，68 个测试 OK。
- `python -m unittest tests.test_wechat_group_message`：通过，4 个测试 OK。
- `python -m unittest tests.test_wechat_group_web`：通过，54 个测试 OK。
- `python -m py_compile channel\wechat_group\wechat_group_free_reply.py channel\wechat_group\wechat_group_channel.py tests\test_wechat_group_free_reply.py`：通过。

## 2026-07-08
### 微信群“群与管理员”页启动后自动刷新群列表

- 更新 `channel/web/static/js/console.js`：`loadGroupsView()` 在检测到微信群通道已登录但当前群列表为空时，自动静默触发一次 `refreshWechatGroupRooms()`，复用现有“刷新群列表”按钮逻辑，避免系统启动后还需要手工刷新。
- 保持手动按钮行为不变：`refreshWechatGroupRooms()` 新增静默模式支持，仅供页面自动触发复用；手动点击仍然显示成功/失败提示。
- 更新 `tests/test_wechat_group_web.py`：新增回归测试，锁定群页加载时的自动刷新钩子与静默刷新调用。

验证记录：

- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_auto_refreshes_wechat_group_rooms_when_groups_view_loads`：新增测试先失败，补实现后通过。

### 微信群图片引用标记触发图片理解

- 修复 `channel/wechat_group/wechat_group_multimodal_context_service.py`：当文本包含微信引用样式 `[图片]`，且同时包含“哪个 / 什么 / 啥 / 怎么看 / 意思 / ？”等疑问或识别意图时，视为图片指代问题，继续复用既有最近图片选择与 Vision 摘要链路。
- 保持候选绑定边界不变：仍通过现有同发送者近图、唯一近图、引用图规则选择图片，不因为普通闲聊里出现 `[图片]` 就无条件调用 Vision。
- 更新 `tests/test_wechat_group_multimodal_context_service.py`：覆盖 `「紫菜：[图片]」...这是哪个？` 在自由回复链路中应绑定唯一近图并调用 Vision。

验证记录：
- `python -m unittest tests.test_wechat_group_multimodal_context_service.WechatGroupMultimodalContextServiceTest.test_free_reply_wechat_image_marker_question_binds_unique_recent_image`：新增测试先失败，表现为 `Vision.execute` 未被调用；实现后通过。
- `python -m unittest tests.test_wechat_group_multimodal_context_service`：通过，9 个测试 OK。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，125 个测试 OK。

### 微信群图片自由回复路径脱敏

- 修复 `channel/wechat_group/wechat_group_channel.py`：非 @ 图片进入自由回复候选时，只向本地评分、日志和 LLM judge 传递 `[image]` 占位符，不再拼接本地 `media_path`，避免 Windows 缓存路径被误判为 `sensitive_or_dangerous`。
- 更新 `tests/test_wechat_group_channel.py`：覆盖非 @ 图片自由回复候选不暴露媒体路径，以及 `C:\Users\...\wechat_group\media\...` 路径不会触发敏感抑制。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_non_at_image_message_queues_free_reply_when_image_switch_enabled tests.test_wechat_group_channel.WechatGroupChannelTest.test_non_at_image_free_reply_does_not_treat_windows_media_path_as_sensitive`：新增测试先失败，修复后通过。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_free_reply`：通过，150 个测试 OK。

### 微信群自然接梗与表情包回复

- 增强 `channel/wechat_group/wechat_group_free_reply.py`：新增明确表情包/梗图请求评分，按群活跃度提高玩梗、接梗、吐槽类消息的自由回复评分，并保留复读机高分触发。
- 增强 `channel/wechat_group/wechat_group_free_reply_judge.py` 与 `channel/wechat_group/wechat_group_reply_policy.py`：自由回复二次判定允许明显玩梗、吐槽、笑点和表情包请求；通过后的回复策略默认文字优先，明确适合时引导复用 `wechat_group_sticker_search` / `wechat_group_sticker_send` 发送一张表情包。
- 增强 `channel/wechat_group/wechat_group_free_reply_worker.py`：本地已确认的复读接梗候选可跳过 LLM 反刷屏误判，直接进入既有自由回复主链路。
- 修复 `channel/wechat_group/wechat_group_humanized_context.py`：当 focus 只返回当前消息且本轮需要历史上下文时，回退读取当前群 recent transcript，避免“总结刚才”等请求丢失最近群聊记录。
- 更新 `tests/test_wechat_group_free_reply.py`、`tests/test_wechat_group_free_reply_worker.py`、`tests/test_wechat_group_context.py`、`tests/test_wechat_group_humanization.py`：覆盖接梗评分、表情包请求、judge/policy prompt、复读本地批准和 recent transcript fallback。

验证记录：
- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_worker tests.test_wechat_group_context tests.test_wechat_group_humanization tests.test_wechat_group_sticker_online tests.test_wechat_group_sticker_service tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，200 个测试 OK。
- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_context tests.test_wechat_group_humanization`：通过，54 个测试 OK。
- `python -m unittest tests.test_wechat_group_sticker_online tests.test_wechat_group_sticker_service tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，137 个测试 OK。

### 微信群自由回复复读机 LLM 放行

- 更新 `channel/wechat_group/wechat_group_free_reply_worker.py`：当本地自由回复决策已经命中 `repeater_message`、已触发且无抑制原因时，worker 直接用本地决策放行，不再交给 LLM judge 按“重复消息/刷屏”拒绝。
- 更新 `tests/test_wechat_group_free_reply_worker.py`：覆盖复读机候选即使 LLM judge 会返回重复消息拒绝，也应绕过 judge 并进入回复提交。

验证记录：
- `python -m unittest tests.test_wechat_group_free_reply_worker.WechatGroupFreeReplyWorkerPoolTest.test_repeater_message_bypasses_llm_spam_rejection`：新增测试先失败，表现为 worker 仍调用 LLM judge 并记录 `free reply llm rejected`；实现后通过。
- `python -m unittest tests.test_wechat_group_free_reply_worker`：通过，9 个测试 OK。
- `python -m unittest tests.test_wechat_group_free_reply`：通过，25 个测试 OK。
- `python -m unittest tests.test_wechat_group_message`：通过，4 个测试 OK。
- `python -m unittest tests.test_wechat_group_channel`：通过，67 个测试 OK。
- `python -m unittest tests.test_wechat_group_web`：通过，53 个测试 OK。

### 微信群自由回复评分规则表格

- 更新 `channel/wechat_group/wechat_group_free_reply.py`：自由回复正向/抑制规则补充中文释义字段，负向规则补齐 `score: "-"`，供控制台和日志统一展示。
- 更新 `channel/web/static/js/console.js`：Web 控制台“群聊 -> 自由回复 -> 评分规则”由标签列表改为表格展示，包含类型、规则 ID、中文释义和评分。
- 更新 `channel/wechat_group/wechat_group_channel.py`：自由回复判定日志中的 `reasons` / `suppressions` 继续保留规则 ID，同时括号内显示中文注释。
- 更新 `tests/test_wechat_group_web.py`、`tests/test_wechat_group_free_reply.py`、`tests/test_wechat_group_channel.py`：覆盖规则表格结构、规则中文释义/评分元数据和日志中文注释。

验证记录：
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_renders_free_reply_rules_as_table_with_chinese_labels_and_scores tests.test_wechat_group_free_reply.WechatGroupFreeReplyDecisionTest.test_rules_snapshot_exposes_chinese_labels_and_scores tests.test_wechat_group_channel.WechatGroupChannelTest.test_non_at_message_logs_inbound_message_and_free_reply_decision`：新增测试先失败，表现为缺少规则表格、`label_zh` 和日志中文注释；实现后通过。
- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，145 个测试 OK。

### 微信群自由回复复读机评分

- 更新 `channel/wechat_group/wechat_group_free_reply.py`：自由回复本地评分新增 `repeater_message` 正向规则，当当前消息与最近群聊中同一句文本被 3 个及以上不同发送者复读时，评分增加 50 分。
- 复读判定只复用现有 `recent_messages` 输入，并按 `sender_id` 优先、昵称兜底去重；不改变低信息、安全、冷却、小时上限和连续上限等抑制规则。
- 更新 `tests/test_wechat_group_free_reply.py`：覆盖 3 个不同成员复读同一句话时可获得复读机加分，并能在 `crazy` 阈值下触发自由回复。

验证记录：
- `python -m unittest tests.test_wechat_group_free_reply.WechatGroupFreeReplyDecisionTest.test_repeater_message_adds_score_for_three_distinct_senders`：新增测试先失败，表现为缺少复读机加分导致未触发；实现后通过。
- `python -m unittest tests.test_wechat_group_free_reply`：通过，20 个测试 OK。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，123 个测试 OK。

### 微信群图片指代表达扩展

- 扩展微信群图片理解文本意图正则，支持“海佬发的啥”“某人发了什么”“谁刚发的什么”等按发送行为指代最近图片的句尾问法。
- 保持当前候选选择边界不变：只在已命中图片指代后复用现有同发送者最近图 / 唯一近图 / 引用图选择链路，不新增普通文本昵称解析，避免多图场景误绑。
- 更新 `tests/test_wechat_group_multimodal_context_service.py`，覆盖 `direct_reply` 文本“海佬发的啥”可绑定唯一近图并调用 Vision 生成 `<wechat-group-multimodal>`。

验证记录：
- `python -m unittest tests.test_wechat_group_multimodal_context_service`：新增测试先失败，表现为 `Vision.execute` 未被调用；完善正则后通过，8 个测试 OK。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_multimodal_context_service`：通过，131 个测试 OK。

### 微信群拟人化上下文优化

- 新增 `WechatGroupHumanizedContextBuilder`，按触发来源和意图统一装配微信群当轮上下文，包含 mention verification、reply policy、archive evidence、local summary、safe recent transcript、focus、memory、style、emotion、reference policy 和 multimodal 块。
- 新增归档搜索与安全 formatter，按 `room_id`、时间窗口和关键词检索证据，排除当前消息，并避免在 LLM prompt 中暴露 `message_id`、`media_path`、本机路径、XML 或 base64。
- 调整个人微信群 recent 默认窗口为 1440 分钟、100 条；standalone @ 不再无条件注入旧群聊，只有上下文依赖、引用、自由回复、多模态等场景按需注入。
- 新增 AgentBridge 微信群原文持久化与运行后内存清洗，默认只把用户原文写入会话历史，避免 `<wechat-group-*>` 块污染下一轮。
- 修复 `Context` 构造函数的可变默认 `kwargs`，避免调度任务上下文污染后续普通上下文；同时让 AgentBridge 调度裁剪分支在精简 agent 替身上安全 no-op。
- 新增发送前回复清洗，移除内部 prompt 标签、固定开场和尾问，并按清洗后的文本执行输入延迟、真实发送和回复归档。
- Web 控制台“群聊”新增“拟人化”分栏，迁移 recent 控件并新增拟人化、归档证据、本地摘要、引用/链接策略和发送前清洗配置；记忆自动保存不再覆盖 recent 配置。
- 更新 `AGENTS.md` 与 `plans/20260708_微信群拟人化上下文优化.md`，记录当前上下文链路、实际改动、验证结果和剩余手动验证事项。

验证记录：
- `python -m unittest tests.test_agent_bridge_wechat_group_persistence`
- `python -m unittest tests.test_wechat_group_humanization`
- `python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_message tests.test_wechat_group_persona tests.test_wechat_group_memory_ui`
- `python -m py_compile channel\wechat_group\wechat_group_humanized_context.py channel\wechat_group\wechat_group_archive_context.py channel\wechat_group\wechat_group_reply_policy.py channel\wechat_group\wechat_group_reference_policy.py channel\wechat_group\wechat_group_reply_cleanup.py bridge\agent_bridge.py channel\wechat_group\wechat_group_channel.py channel\web\web_channel.py`
- `python -m unittest tests.test_robustness_fixes.TestContextKwargsIsolation`
- `python -m unittest tests.test_scheduler_wechat_group_delivery tests.test_wechat_group_agent_bridge_tools.WechatGroupAgentBridgeToolsTest.test_wechat_group_turn_temporarily_attaches_scoped_memory_tools`
- `python -m unittest tests.test_scheduler_wechat_group_delivery tests.test_security_ssrf_browser_navigate tests.test_security_ssrf_path_traversal tests.test_security_ssrf_web_fetch tests.test_self_evolution_docs tests.test_web_search_providers tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_channel`
- `python -m unittest discover -s tests` 已执行但未通过；最终结果为 497 个测试、3 个 failure、5 个 error，失败项为既有全量环境/文档类问题：缺少 `pytest` 导致 `test_bash_streaming` / `test_invariant_bash` 导入失败，MiniMax 测试按系统默认编码读取 UTF-8 文件失败，Qianfan 文档文件缺失及文档/控制台断言不满足。
- 手动真实微信群扫码和群内消息验证尚未执行。

## 2026-07-07

### 自主进化功能链路确认

- 修复 GitHub issue #22：确认当前自主进化已覆盖普通 Agent 主链路与微信群群聊链路，并补充 README 中的触发、执行、通知和回滚说明。
- 更新 `README.md`：写清 `self_evolution_enabled` 总开关、`self_evolution_idle_minutes` / `self_evolution_min_turns` 的运行时 fallback 默认值，说明自主进化只作用于 Agent 模式主链路，并说明 `AgentBridge.agent_reply` / `agent.chat.service` 如何调用 `note_user_turn` 与 `mark_run_active`，以及 `agent.evolution.trigger` 如何触发 `agent.evolution.executor.run_evolution_for_session()`。
- 更新 `README.md`：说明自主进化 review agent 使用受限工具、工作空间写入边界、备份、`memory/evolution/YYYY-MM-DD.md` 记录、`remember_scheduled_output` 注入 `[EVOLUTION]` 和 `evolution_undo` 回滚。
- 更新 `README.md`：确认 `WechatGroupChannel -> ChatChannel -> Bridge.fetch_agent_reply -> AgentBridge.agent_reply` 复用自主进化链路；`wechat_group` 群聊会记录轮次但不设置主动推送 receiver，避免主动打扰群。
- 新增 `tests/test_self_evolution_docs.py`：静态锁定 README 中的自主进化链路说明、微信群复用说明，并用 AST 检查代码中群聊记录轮次但不主动通知的关键约束。
- 更新 `tests/test_evolution.py`：为测试脚本中的 UTF-8 临时文件读取补齐显式编码，避免 Windows 默认 GBK 环境下直接运行自主进化验证脚本失败。

验证记录：
- `python -m unittest tests.test_self_evolution_docs`：新增测试先失败，补充 README 后通过，3 个测试 OK。
- `python tests\test_evolution.py`：修复测试脚本编码读取后通过，13 个 stub 场景通过，undo 校验通过。
- `python -m py_compile bridge\agent_bridge.py agent\evolution\trigger.py agent\evolution\executor.py agent\chat\service.py tests\test_self_evolution_docs.py tests\test_evolution.py`：通过。

### 微信群表情包检索与发送优化

- 修复 GitHub issue #21：微信群表情包回复现在保留本地素材优先，同时支持线上表情包候选补足，并通过受控 `online_id` 发送线上候选。
- 新增 `channel/wechat_group/wechat_group_sticker_online.py`：封装线上表情包检索、关键词清洗、敏感词过滤、HTTPS URL 归一化、检索 endpoint allowlist、允许域名校验、GIF 开关和候选打散。
- 更新 `channel/wechat_group/wechat_group_sticker_service.py` 与 `channel/wechat_group/wechat_group_sticker_tools.py`：支持本地 + 线上混合检索、线上候选缓存、下载到受控缓存、发送冷却和每日上限；工具结果不向模型暴露原始图片 URL。
- 更新 `bridge/agent_bridge.py`：微信群表情包工具提示支持 `sticker_id` 或 `online_id`，并禁止暴露裸 URL；文件回复保留线上表情包来源元数据。
- 更新 `config.py`、`config-template.json`、`channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：补齐线上检索默认配置、Web 保存归一化、`/api/wechat-group/stickers/search-online` API、群聊表情包设置区和线上检索测试入口。
- 更新 `README.md`：补充“群聊 -> 表情包”的 Web 使用路径、线上候选安全边界和当前运行环境验证方式。
- 更新 `tests/test_wechat_group_sticker_online.py`、`tests/test_wechat_group_sticker_service.py`、`tests/test_wechat_group_agent_bridge_tools.py` 与 `tests/test_wechat_group_web.py`：覆盖线上检索安全过滤、混合检索、线上下载发送、URL 脱敏、配置保存和控制台入口。

验证记录：
- `python -m unittest tests.test_wechat_group_agent_bridge_tools`：新增桥接/工具测试先失败，修复后通过，6 个测试 OK。
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_lists_wechat_group_humanization_defaults tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_humanization_config tests.test_wechat_group_web.WechatGroupWebTest.test_wechat_group_stickers_online_search_api_hides_internal_url tests.test_wechat_group_web.WechatGroupWebTest.test_console_contains_wechat_group_sticker_panel`：新增 Web 测试先失败，修复后通过，4 个测试 OK。
- `python -m unittest tests.test_wechat_group_sticker_online.WechatGroupStickerOnlineTest.test_search_online_memes_rejects_private_or_unapproved_endpoint`：新增 endpoint SSRF 回归测试先失败，修复后通过。
- `python -m unittest tests.test_wechat_group_sticker_online tests.test_wechat_group_sticker_service tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_web tests.test_wechat_group_message tests.test_wechat_group_channel`：通过，140 个测试 OK。
- `python -m py_compile config.py bridge\agent_bridge.py channel\web\web_channel.py channel\wechat_group\wechat_group_sticker_online.py channel\wechat_group\wechat_group_sticker_service.py channel\wechat_group\wechat_group_sticker_tools.py tests\test_wechat_group_sticker_online.py tests\test_wechat_group_sticker_service.py tests\test_wechat_group_agent_bridge_tools.py tests\test_wechat_group_web.py`：通过。
- `node --check channel\web\static\js\console.js`：通过。
- Playwright 打开 `http://127.0.0.1:9899/chat` 后切换到“群聊 -> 表情包”：确认表情包面板、线上检索开关、Provider、Endpoint、允许域名、测试线上检索和保存表情包设置入口均渲染；截图保存为 `issue21-sticker-panel.png`。

### 微信群自由回复强触发关键词

- 修复 GitHub issue #9：新增 `wechat_group_free_reply_force_keywords` 配置，命中后可强制进入自由回复候选，不再因低信息或本地评分低于阈值被拦截。
- 更新 `channel/wechat_group/wechat_group_free_reply.py`：自由回复配置返回 `force_keywords`；本地判定命中关键词时记录 `force_keyword_match`，仅绕过 `low_information` 和 `below_threshold`，仍保留群范围、自发消息、blocked sender、静默说明、媒体 payload、敏感/危险内容、生图失败讨论、冷却、小时上限和连续上限等抑制。
- 更新 `config.py`、`config-template.json`、`channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：补齐默认配置、Web 保存规范化和控制台编辑入口，支持逗号、中文逗号、空白和换行分隔并去重。
- 更新 `tests/test_wechat_group_free_reply.py`、`tests/test_wechat_group_channel.py` 与 `tests/test_wechat_group_web.py`：覆盖配置规范化、强触发绕过范围、不可绕过抑制项、通道层图片上下文缺失拦截、Web 保存和控制台字段暴露。

验证记录：
- `python -m unittest tests.test_wechat_group_free_reply`：通过，19 个测试 OK。
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_free_reply_image_question_is_suppressed_without_image_context`：通过，1 个测试 OK。
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_free_reply_config tests.test_wechat_group_web.WechatGroupWebTest.test_console_exposes_free_reply_force_keywords_setting`：通过，2 个测试 OK。
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`：通过，117 个测试 OK。
- `python -m py_compile config.py channel\wechat_group\wechat_group_free_reply.py channel\web\web_channel.py tests\test_wechat_group_free_reply.py tests\test_wechat_group_channel.py tests\test_wechat_group_web.py`：通过。

### 微信群隐藏内部工具进度

- 修复 GitHub issue #5：微信群 Agent 回复不再把带工具调用的 assistant 中间过程消息发送到群里，避免“我先看看文档”“我正在查知识库”等内部进度刷屏。
- 更新 `bridge/agent_event_handler.py`：识别 `channel_type=wechat_group`，当 `message_end` 带 `tool_calls` 时只记录日志，不调用渠道 `_send`；无工具调用的最终回复仍按原链路发送。
- 更新 `channel/wechat_group/wechat_group_persona.py`：三套内置微信群 persona 均明确要求不要汇报查文档、检索知识库、写入记忆、检查配置、生图排队等内部工具过程，只输出最终结果、简短失败原因或补充信息请求。
- 新增 `tests/test_agent_event_handler.py` 并更新 `tests/test_wechat_group_persona.py`：覆盖微信群抑制中间过程、非微信群保留原行为和 persona 约束。

验证记录：
- `python -m unittest tests.test_agent_event_handler`（先确认新增测试在旧实现下失败，修复后通过）
- `python -m unittest tests.test_agent_event_handler tests.test_wechat_group_persona`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile bridge\agent_event_handler.py channel\wechat_group\wechat_group_persona.py tests\test_agent_event_handler.py tests\test_wechat_group_persona.py`

### 知识库来源可信规则

- 修复 GitHub issue #8：知识库整理规则现在明确要求基于真实可访问来源，避免把模型猜测的文档路径或失败链接写成资料来源。
- 更新 `agent/prompt/builder.py`：在知识系统 prompt 中新增来源可信规则，要求优先使用页面真实导航链接、只把成功读取的 URL 写入 Source，并排除 404/410、失败请求和猜测路径。
- 更新 `agent/prompt/workspace.py`：同步补充新工作空间初始化模板中的中英文知识库来源规则。
- 更新 `skills/knowledge-wiki/SKILL.md`：在知识写入技能中明确 Web 来源必须成功打开/抓取后才能作为 `> Source:`，找不到页面时应说明而不是保存不可靠内容。
- 新增 `tests/test_knowledge_source_reliability_rules.py`：静态锁定系统 prompt、workspace 模板和知识库技能中的来源可信规则。

验证记录：
- `python -m unittest tests.test_knowledge_source_reliability_rules`（先确认新增测试在旧规则下失败，修复后通过）
- `python -m unittest tests.test_prompt_scheduler_guidance tests.test_knowledge_web tests.test_knowledge_service`（当前 unittest 仅识别并运行 1 个测试，通过）
- `python -m py_compile agent\prompt\builder.py agent\prompt\workspace.py tests\test_knowledge_source_reliability_rules.py`
- `python -m pytest tests/test_knowledge_web.py tests/test_knowledge_service.py` 未运行：当前环境未安装 `pytest`

### Agent 检索工具连续失败可恢复

- 修复 GitHub issue #7：`web_fetch` / `web_search` 连续失败达到 8 次保护时，不再返回 `critical_error` 直接中断整个 Agent 任务。
- 更新 `agent/protocol/agent_stream.py`：为非破坏性检索工具增加可恢复连续失败分支，提示停止继续抓取或猜测链接，基于已成功获取内容总结，资料不足时向用户索要准确链接。
- 保留其他工具的原有 critical 连续失败保护，避免非检索工具无限循环。
- 新增 `tests/test_agent_stream_retrieval_failure_recovery.py`：覆盖 `web_fetch`、`web_search` 连续失败返回普通 error，以及 `bash` 等非检索工具仍返回 `critical_error`。

验证记录：
- `python -m unittest tests.test_agent_stream_retrieval_failure_recovery`（先确认新增测试在旧实现下失败，修复后通过）
- `python -m unittest tests.test_agent_stream_scheduler_guard tests.test_agent_stream_logging`
- `python -m py_compile agent\protocol\agent_stream.py tests\test_agent_stream_retrieval_failure_recovery.py`

### web_fetch 404/410 同站导航恢复

- 修复 GitHub issue #6：`web_fetch` 遇到网页 404/410 时仍返回失败状态，但会附带受限的同站父级路径和可访问导航候选，提示模型不要继续猜测更深 URL。
- 更新 `agent/tools/web_fetch/web_fetch.py`：新增 404/410 恢复提示构造、最多 2 层父级探测、最多 5 个候选输出与最多 5 次候选探测，父级和候选请求均继续走 `_safe_get()` 与 `validate_url_safe()`。
- 候选链接仅允许同 `scheme + netloc` 的 `http/https` URL；外站、非 HTTP 链接、内网地址、重复坏链和不可访问同站链接会被过滤。
- 更新 `tests/test_security_ssrf_web_fetch.py`：新增 404/410 导航恢复回归测试，覆盖父级提示、候选过滤、停止猜测提示、候选可访问性校验、重复坏链去重与探测次数上限。

验证记录：
- `python -m unittest tests.test_security_ssrf_web_fetch.TestWebFetchNotFoundRecovery`（先确认新增边界测试在旧实现下失败，修复后通过）
- `python -m unittest tests.test_security_ssrf_web_fetch`
- `python -m py_compile agent\tools\web_fetch\web_fetch.py tests\test_security_ssrf_web_fetch.py`

### 消息消费循环异常隔离

- 修复 GitHub issue #16：`ChatChannel.consume()` 现在同时隔离整轮消费循环异常与单个 session 异常，避免缺失 session、异常 session state 或分发异常导致后续消息不可见。
- 更新 `channel/chat_channel.py`：消费 session 快照后若 session 已被删除会记录 warning 并跳过；异常 session state 会被跳过；pending future 不再依赖 `assert` 作为运行时控制流；callback 注册失败时会释放已获取的 semaphore。
- 增强 image-create 异步链路日志：补充生图请求入队、分发和处理阶段的可检索日志，便于排查生图队列和 worker 行为。
- 更新 `tests/test_robustness_fixes.py`：新增消费循环回归测试，覆盖缺失 session、异常 session state、pending future 保留、callback 注册失败释放 semaphore，以及 image-create 关键日志。
- 新增并回写 `plans/20260707_处理全部开放issue.md`，记录全部 open issue 的执行顺序、边界、验证结果与状态。

验证记录：
- `python -m unittest tests.test_robustness_fixes.TestChatChannelConsumeRobustness`（先确认新增边界测试在旧实现下失败，修复后通过）
- `python -m unittest tests.test_robustness_fixes tests.test_wechat_group_channel tests.test_models_handler`

### 微信群画像群名同步补齐

- 修复 GitHub issue #17：微信群全局画像历史 name records 只有 `room_id`、缺少 `room_name` 时，房间列表同步后会把已知群名持久化补齐到底层记录，不再只依赖展示层兜底。
- 更新 `channel/wechat_group/wechat_group_profile_store.py`：新增缺失群名 room id 查询与批量回填方法，只更新 `room_name` 为空的记录，不覆盖已有群名。
- 更新 `channel/wechat_group/wechat_group_profile_service.py`：扩展 `repair_historical_profile_names(room_name_by_id=None)`，保留历史主昵称修复，同时补齐画像 name records 的群名，并返回 `room_names_repaired`。
- 更新 `channel/wechat_group/wechat_group_channel.py`：在 sidecar rooms 事件后基于同步到的房间列表触发画像群名修复；失败只记录 warning，不影响登录状态和群列表同步。
- 更新 `tests/test_wechat_group_profile_service.py` 与 `tests/test_wechat_group_channel.py`：新增归档补齐、同步 room map 优先、rooms 事件触发修复和修复异常不阻断连接状态的回归测试。
- 新增并回写 `plans/20260707_微信群画像群名持久化补齐.md`，记录 issue 确认、实施方案、实际改动和验证结果。

验证记录：
- `python -m unittest tests.test_wechat_group_profile_service.WechatGroupProfileServiceTest.test_repair_historical_profile_names_persists_missing_room_name_from_archive tests.test_wechat_group_profile_service.WechatGroupProfileServiceTest.test_repair_historical_profile_names_prefers_synced_room_map tests.test_wechat_group_channel.WechatGroupChannelTest.test_rooms_event_repairs_missing_profile_room_names tests.test_wechat_group_channel.WechatGroupChannelTest.test_rooms_event_keeps_connected_status_when_profile_repair_fails`（先确认失败，修复后通过）
- `python -m unittest tests.test_wechat_group_profile_service tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile channel\wechat_group\wechat_group_profile_store.py channel\wechat_group\wechat_group_profile_service.py channel\wechat_group\wechat_group_channel.py`

### 微信群图片理解统一优化

- 跟进 GitHub issue #14：在既有全局多模态上下文架构上收敛微信群图片理解逻辑，避免继续在通道层点状补丁。
- 更新 `channel/wechat_group/wechat_group_channel.py`：移除旧图片理解 builder、旧图片摘要缓存和已迁移的旧 multimodal formatter；通道层只保留回复门控和 `_compose_context()` 编排，不再直接调用 Vision。
- 更新 `channel/wechat_group/wechat_group_multimodal_context_service.py`：统一图片摘要缓存、失败/空结果文案和诊断字段；`summary_generated` 只在真实成功摘要时为 `true`，Vision 异常或非 success 结果不再把本机路径写入 prompt 或诊断信息。
- 更新 `tests/test_wechat_group_channel.py` 与 `tests/test_wechat_group_multimodal_context_service.py`：新增旧入口守护、图片摘要缓存归属、Vision 失败脱敏、默认图片问题文案可读性等回归测试。
- 新增并回写 `plans/20260707_微信群图片理解统一优化.md`：记录实施步骤、实际改动、验证结果、审查结论和未执行的真实微信群手动验证。

验证记录：
- `python -m unittest tests.test_wechat_group_multimodal_context_service tests.test_wechat_group_channel tests.test_wechat_group_context`
- `python -m unittest tests.test_wechat_group_multimodal_context_service tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_context tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile channel\wechat_group\wechat_group_channel.py channel\wechat_group\wechat_group_multimodal_context_service.py tests\test_wechat_group_channel.py tests\test_wechat_group_multimodal_context_service.py`

### 微信群焦点栈替代话题追踪

- 修复 GitHub issue #24：个人微信群 standalone @ 不再自动混入旧话题/旧焦点上下文，避免把“她不爱我了”和“让 gpt 来帮忙了”等独立请求拼成同一回复背景。
- 新增 `channel/wechat_group/wechat_group_focus_store.py` 与 `channel/wechat_group/wechat_group_focus_service.py`：实现按 `room_id` 隔离的焦点栈、焦点消息引用、上下文/standalone 判定和 `<wechat-group-focus>` prompt block。
- 更新 `channel/wechat_group/wechat_group_channel.py` 与 `wechat_group_context.py`：移除 `<wechat-group-topic>` 注入，改为 recent transcript 按焦点结果精确渲染；总结刚才、引用、图片理解等上下文依赖请求仍可读取当前群焦点消息。
- 删除 `channel/wechat_group/wechat_group_topic_store.py`、`channel/wechat_group/wechat_group_topic_service.py` 与 `tests/test_wechat_group_topic_service.py`；旧 `wechat_group_topics.db` 或旧 topic 表按需求废弃，不迁移、不保留历史数据。
- 更新 `config.py`、`config-template.json`、`channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：移除 `wechat_group_topic_*` 配置和 `/api/wechat-group/topics/*`，新增 `wechat_group_focus_*` 配置、`/api/wechat-group/focus/*` 和 Web 控制台“焦点栈”面板。
- 更新 `AGENTS.md` 与 `plans/20260707_微信群回复上下文话题隔离优化.md`：补充焦点栈维护约束、旧 topic 数据处置策略和实际执行结果。

验证记录：
- `python -m unittest tests.test_wechat_group_focus_service tests.test_wechat_group_context.WechatGroupRecentContextTest.test_recent_context_block_can_render_focus_rows`
- `python -m unittest tests.test_wechat_group_context tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_focus_service tests.test_wechat_group_context tests.test_wechat_group_channel tests.test_wechat_group_web`

### 微信群自由回复误触发生图修复

- 更新 `channel/chat_channel.py` 与 `config.py`：收窄默认 `image_create_prefix`，移除容易误伤普通文本的 `看`、`找` 单字前缀，避免“找到问题...”这类自由回复候选被误判为图片生成。
- 更新 `tests/test_wechat_group_channel.py`：新增自由回复强制处理路径下“找到问题...”保持文本回复的回归测试，并补齐相关测试消息归档字段。
- 更新 `AGENTS.md`：补充微信群自由回复进入主链路后，默认生图触发词必须保守的维护约束。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_wechat_group_free_reply_text_starting_with_find_does_not_create_image`（先确认旧实现失败，修复后通过）
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_wechat_group_free_reply_text_starting_with_find_does_not_create_image tests.test_wechat_group_channel.WechatGroupChannelTest.test_wechat_group_image_create_uses_builtin_prefix_when_config_missing`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile channel\chat_channel.py config.py tests\test_wechat_group_channel.py`

### 微信群静默说明误发送修复

- 更新 `channel/wechat_group/wechat_group_channel.py`：新增微信群短文本静默说明识别，在发送层拦截 `（没@我，不插嘴）` 这类内容，避免真实发送到群里或 mention 原发送者。
- 更新 `channel/wechat_group/wechat_group_free_reply.py`：新增 `bot_silent_notice` 自由回复抑制原因，避免同类静默说明进入自由回复 worker。
- 更新 `tests/test_wechat_group_channel.py` 与 `tests/test_wechat_group_free_reply.py`：新增静默说明不发送、长文本不误拦截、自由回复本地评分抑制的回归测试。
- 新增 `plans/20260707_微信群静默回复防护.md`：记录 issue #23 的确认、方案、执行结果和验证记录。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_send_silent_reply_notice_is_not_sent_to_group`（先确认旧实现失败，修复后通过）
- `python -m unittest tests.test_wechat_group_free_reply.WechatGroupFreeReplyDecisionTest.test_bot_silent_notice_is_suppressed`（先确认旧实现失败，修复后通过）
- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile channel\wechat_group\wechat_group_channel.py channel\wechat_group\wechat_group_free_reply.py tests\test_wechat_group_channel.py tests\test_wechat_group_free_reply.py`

### 微信群管理员门禁误拦截修复

- 更新 `channel/wechat_group/wechat_group_channel.py`：在注入微信群管理员策略、人设、最近上下文等 prompt 块前保留本轮用户原文；管理员门禁只扫描用户原文，避免策略块中的“写入知识库/永久记忆/定时任务”等权限说明反向触发普通群消息报错。
- 更新 `tests/test_wechat_group_channel.py`：新增非管理员普通 @ 问答场景，覆盖已注入管理员策略块时不应被通道门禁拒绝。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_non_admin_normal_message_with_admin_policy_context_is_not_rejected`（先确认旧实现失败，修复后通过）
- `python -m unittest tests.test_wechat_group_permissions tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile channel\wechat_group\wechat_group_channel.py tests\test_wechat_group_channel.py`

### 个人微信群登录状态修复

- 更新 `channel/wechat_group/wechat_group_client.py`：新增 sidecar 启动错误缓存和 `poll_error()`，用于暴露 `subprocess.Popen()` 失败或 sidecar 进程退出状态。
- 更新 `channel/wechat_group/wechat_group_channel.py`：新增 `last_error` 与 `get_login_status()`，区分 sidecar 进程启动成功和微信扫码登录成功；`qr/status/rooms/error` 事件按 `starting`、`qr_ready`、`logged_in`、`connected`、`error` 推进登录态。
- 更新 `channel/web/web_channel.py`：通道列表中 `wechat_group.active` 改为仅在 `logged_in` 或 `connected` 时为 `true`，同时返回 `configured`、`runtime_active`、`connected`、`message`；QR 轮询接口返回真实登录态、错误信息、二维码和群列表。
- 更新 `tests/test_wechat_group_channel.py` 与 `tests/test_wechat_group_web.py`：新增 sidecar 启动错误、扫码前未接入、登录后已接入、错误信息透出和登录后非致命错误不降级的回归测试。

验证记录：
- `python -m unittest tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

### 微信群连续普通消息自由回复防抖

- 更新 `channel/wechat_group/wechat_group_free_reply_worker.py`：新增按 `room_id` 隔离的短暂防抖 pending 队列；同一群短时间连续自由回复候选只保留最新任务进入 LLM judge，不同群候选互不影响。
- 更新 `channel/wechat_group/wechat_group_channel.py`：自由回复候选入队时不再提前写入 `last_triggered_at`；仅在 worker 判定通过并进入回复上下文后记录触发冷却，避免同一突发窗口内后续消息无法替换最新候选。
- 更新 `tests/test_wechat_group_free_reply_worker.py` 与 `tests/test_wechat_group_channel.py`：新增同群候选合并、跨群隔离、连续候选不被入队冷却提前拦截的回归测试。
- 更新 `AGENTS.md`：补充微信群自由回复 worker 的 room 级防抖、跨群隔离和冷却记录时机维护约束。
- 新增 `plans/20260707_微信群连续消息防抖.md`：记录 issue #19 的排查、改动和验证结果。

验证记录：
- `python -m unittest tests.test_wechat_group_free_reply_worker.WechatGroupFreeReplyWorkerPoolTest.test_debounce_coalesces_same_room_candidates_to_latest_task tests.test_wechat_group_free_reply_worker.WechatGroupFreeReplyWorkerPoolTest.test_debounce_keeps_different_rooms_isolated tests.test_wechat_group_channel.WechatGroupChannelTest.test_free_reply_burst_keeps_latest_candidate_before_cooldown`（修复前确认失败，修复后通过）
- `python -m unittest tests.test_wechat_group_free_reply_worker tests.test_wechat_group_free_reply tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

## 2026-07-06

### 微信群自由回复图片上下文缺失抑制

- 更新 `channel/wechat_group/wechat_group_channel.py`：自由回复入队前增加图片指代问题保护；当自由回复图片上下文未启用且近期群聊包含图片时，普通非 @ 的“这是真的吗 / 啥意思”等图片相关追问不再进入自由回复 worker，避免模型在看不到图的情况下猜测回复。
- 更新 `channel/wechat_group/wechat_group_free_reply.py`：补充 `image_context_unavailable` 抑制原因标签，便于日志和状态页诊断。
- 更新 `tests/test_wechat_group_channel.py`：新增回归测试覆盖自由回复图片上下文关闭时，图片相关普通群聊问题应被跳过。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_free_reply_image_question_is_suppressed_without_image_context`（先确认旧实现会提交自由回复 worker，修复后通过）
- `python -m unittest tests.test_wechat_group_free_reply`
- `python -m py_compile channel\wechat_group\wechat_group_channel.py channel\wechat_group\wechat_group_free_reply.py tests\test_wechat_group_channel.py`
- `python -m unittest tests.test_wechat_group_channel`

### 微信群管理员成员画像别名检索修复

- 更新 `channel/wechat_group/wechat_group_channel.py`：管理员成员检索仍以 sidecar 当前群成员为候选来源，但按 `sender_id` 合并已有画像的 `primary_nickname` 与 `aliases` 参与筛选；当 sidecar 返回的昵称是原始 ID 时，用画像昵称兜底展示。
- 更新 `tests/test_wechat_group_channel.py`：新增运行态成员昵称为原始 ID、画像昵称包含 `一灯` 时仍可检索命中的回归测试。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_channel_filters_room_members_by_profile_nickname_for_runtime_member`（先确认旧实现返回 0，修复后通过）
- 使用当前运行接口返回的真实群成员数据喂给新 `WechatGroupChannel.get_room_members(..., query="一灯", refresh=False)`，命中 sender_id `@ec16...`，展示名为 `一灯（无情的复读机）`

### 微信群画像工具当前群绑定修复

- 更新 `channel/wechat_group/wechat_group_memory_tools.py`：`wechat_group_profile_get` 工具绑定当前 `room_id`，搜索、精确读取和新增 `list_all` 列表模式均只返回当前微信群画像，不再把其他群画像混入 Agent 回复。
- 更新 `tests/test_wechat_group_memory_tools.py`：新增工具级回归测试，覆盖按 query 搜索和 `list_all=true` 列出当前群画像时必须排除跨群成员。

验证记录：
- `python -m unittest tests.test_wechat_group_memory_tools`（先确认旧实现跨群返回/不支持 list_all 失败，修复后通过）
- `python -m unittest tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_memory_tools`
- `python -m py_compile channel\wechat_group\wechat_group_memory_tools.py`

### 微信群管理员成员微信号检索修复

- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`：新增群成员 payload 构造与微信号解析 helper，支持从 Wechaty contact payload 的 `weixin`、`handle`、`address` 以及 wechat4u raw `Alias` 兜底解析 `wechat_id`。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar.mjs`：群成员列表在有搜索词且基础字段未命中时，按需读取 raw contact payload 补充微信号，避免空查询加载全群时对大量成员做重 raw 查询。
- 更新 `channel/wechat_group/wechat_group_client.py` 与 `channel/wechat_group/wechat_group_channel.py`：`list_room_members` 命令透传成员搜索词；有搜索词时适当延长等待，便于微信号 raw Alias 检索返回。
- 更新 `tests/test_wechat_group_channel.py` 与 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`：覆盖查询词透传、微信号 payload/raw Alias 解析和成员匹配逻辑。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_client_list_room_members_includes_request_id_and_query tests.test_wechat_group_channel.WechatGroupChannelTest.test_channel_refresh_room_members_sends_sidecar_command`（先确认旧实现缺少 query 参数失败，修复后通过）
- `node --test .\channel\wechat_group\sidecar\wechaty-sidecar-core.test.mjs`（先确认新增 helper 未导出失败，修复后通过）
- `node --check .\channel\wechat_group\sidecar\wechaty-sidecar.mjs`
- `node --check .\channel\wechat_group\sidecar\wechaty-sidecar-core.mjs`
- `python -m py_compile channel\wechat_group\protocol.py channel\wechat_group\wechat_group_client.py channel\wechat_group\wechat_group_channel.py channel\web\web_channel.py`

### 微信群画像称呼跨群串用修复

- 更新 `channel/wechat_group/wechat_group_context_service.py`：生成微信群画像上下文时把当前 `room_id` 传入画像解析链路。
- 更新 `channel/wechat_group/wechat_group_profile_service.py`：带 `room_id` 构造 prompt 画像时，`reply_name`、`primary_nickname` 与 `aliases` 不再回退使用其他群学到的 name record，避免 A 群昵称出现在 B 群回复中。
- 更新 `tests/test_wechat_group_profile_service.py`：新增跨群别名回归测试，覆盖同一 `sender_id` 在 A 群有别名、B 群只有原始 ID 时，B 群 prompt 不注入 A 群 `reply_name` 的场景。
- 更新 `AGENTS.md`：补充微信群画像称呼必须按当前 `room_id` 过滤的维护约束。

验证记录：
- `python -m unittest tests.test_wechat_group_profile_service`（先确认新增用例在旧实现下失败，修复后通过）
- `python -m py_compile channel\wechat_group\wechat_group_profile_service.py channel\wechat_group\wechat_group_context_service.py`
- `python -m unittest tests.test_wechat_group_profile_service tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web` 当前未全量通过；失败集中在工作区既有 `refresh_room_members` / `list_room_members` 相关未完成改动，非本次画像称呼修复引入。

### 微信群管理员成员列表切群刷新修复

- 更新 `channel/web/static/js/console.js`：群管理员面板切换目标群后立即重新请求 `/api/wechat-group/members`，不再停留在旧群成员结果；异步回包增加当前 `room_id` 与 request id 校验，避免旧请求晚返回覆盖新群列表。
- 更新 `tests/test_wechat_group_web.py`：新增控制台静态回归断言，锁定切群触发成员加载和旧请求回包保护。

验证记录：
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_reload_admin_members_when_admin_room_changes`（先确认旧实现失败，修复后通过）
- `python -m unittest tests.test_wechat_group_web`
- `node --check .\channel\web\static\js\console.js`

### 个人微信群管理员权限门禁

- 新增 `channel/wechat_group/wechat_group_permissions.py`：集中定义群管理员配置归一化、`room_id + sender_id` 精确判断、权限矩阵元数据、写入类意图识别、拒绝文案、Prompt 权限块和 Agent 工具过滤。
- 更新 `config.py` 与 `config-template.json`：新增 `wechat_group_admin_members` 与 `wechat_group_admin_required_permissions`，旧 `wechat_group_admin_sender_ids` 仅保留为兼容 fallback。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：Web 控制台“群聊开关”改为“群与管理员”，移除群名兜底输入，新增按群检索成员、保存/删除管理员和 10 项门禁能力权限矩阵。
- 更新 `channel/wechat_group/wechat_group_channel.py`、`channel/wechat_group/wechat_group_persona.py` 与 `bridge/agent_bridge.py`：非管理员写入类请求在通道层拒绝，普通请求注入管理员策略提示，Agent turn 内过滤 `write`、`edit`、`bash`、`scheduler` 等受控工具；persona 管理员判断迁移为 `room_id + sender_id`。
- 更新 `tests/test_wechat_group_permissions.py`、`tests/test_wechat_group_channel.py`、`tests/test_wechat_group_persona.py` 与 `tests/test_wechat_group_web.py`：覆盖管理员作用域、legacy fallback、权限矩阵、成员检索 API、通道拒绝/放行、persona 跳过和 AgentBridge 工具过滤接入。
- 更新 `AGENTS.md` 与 `plans/20260706_微信群管理员权限.md`：补充微信群管理员权限维护约束并回写实施记录。

验证记录：
- `python -m unittest tests.test_wechat_group_permissions`
- `python -m unittest tests.test_wechat_group_permissions tests.test_wechat_group_channel tests.test_wechat_group_persona`
- `python -m unittest tests.test_wechat_group_permissions tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_persona`
- `python -m py_compile channel\wechat_group\wechat_group_permissions.py channel\wechat_group\wechat_group_channel.py channel\wechat_group\wechat_group_persona.py bridge\agent_bridge.py channel\web\web_channel.py`
- `node --check .\channel\web\static\js\console.js`

### 微信群多模态上下文全局注入

- 新增 `channel/wechat_group/wechat_group_multimodal_context_service.py`：统一在 `_compose_context()` 阶段装配 `<wechat-group-multimodal>`，覆盖当前图片、引用图片、引用发送者近图、同发送者追问近图、群内唯一近图，以及引用/转发/视频元信息。
- 更新 `channel/wechat_group/wechat_group_channel.py`：自由回复通过后只传递 `wechat_group_trigger_source`，不再在 worker 通过点单独查最近图片；direct reply 和自由回复都走同一全局多模态上下文入口。
- 更新 `channel/wechat_group/wechat_group_context.py`：最近群聊 transcript 中的图片、文件、视频、语音等媒体消息只输出类型和 `message_id`，不再暴露本机媒体绝对路径。
- 更新 `config.py`、`config-template.json`、`channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：新增全局多模态上下文总开关、图片摘要注入开关、自由回复近图绑定开关，以及同发送者/唯一近图/引用发送者/最大扫描数窗口配置，并在 Web 控制台“群聊 -> 图片与生图”中可视化配置。
- 更新 `tests/test_wechat_group_multimodal_context_service.py`、`tests/test_wechat_group_channel.py`、`tests/test_wechat_group_context.py`、`tests/test_wechat_group_web.py`：覆盖图片候选优先级、自由回复和 direct reply 的全局注入、路径脱敏、Web 配置读写和控制台字段。
- 更新 `plans/20260706_微信群多模态上下文全局注入.md`：回写实施结果、实际改动、验证记录和未执行的手动验证。

验证记录：
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_lists_wechat_group_as_qr_channel tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_image_config tests.test_wechat_group_web.WechatGroupWebTest.test_console_contains_wechat_group_image_settings`（先确认缺失字段失败，修复后通过）
- `python -m unittest tests.test_wechat_group_multimodal_context_service tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_context tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `node --check .\channel\web\static\js\console.js`

### 微信群真实 @ 原始 ID 泄露修复
- 对照 BaiLongmaPro 的微信群发送链路后，修复 sidecar 出站 @ 文本清理：`buildManualMentionText()` 不再把 web 微信内部长 `@sender_id` 当作可见群昵称，也会在模型回复开头带超长 raw `@id` 时先剥离，再重建正确的可见 `@群昵称`。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`：新增 raw 微信内部 ID 判断、可见 mention 名称清理、长 raw mention 前缀清理，以及 `resolveContactDisplayName()`，入站成员显示名优先使用群内 alias / raw payload 可见昵称，避免最近发言上下文继续暴露内部 ID。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar.mjs`：入站消息组装复用 `resolveContactDisplayName()`，并复用一次 `messageRawPayload()` 结果给引用解析，减少重复读取。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`：覆盖长 raw `@sender_id` 清理、raw ID 不作为可见 mention 名称、群 alias 优先和 raw payload 昵称兜底。
验证记录：
- `npm test`（在 `channel/wechat_group/sidecar` 目录执行，先在旧实现下确认新增 raw ID 用例失败，修复后通过）
- `node --check wechaty-sidecar.mjs`
- `node --check wechaty-sidecar-core.mjs`

### 微信群全局画像别名称呼提示词约束

- 更新 `channel/wechat_group/wechat_group_profile_service.py`：群成员画像 prompt 内容新增 `reply_name` 字段，优先使用全局画像别名，别名为空时回退到 `primary_nickname`。
- 更新 `channel/wechat_group/wechat_group_context_service.py`：当生成前上下文注入群成员画像时，同步注入 `[naming_policy]`，提示 LLM 在回复中提到该成员时优先使用 `reply_name`，避免使用 `sender_id` 作为称呼。
- 更新 `tests/test_wechat_group_context.py`：新增回归测试，覆盖全局画像中 `徐徐图之 -> 图总` 这类别名应进入生成前提示词约束。
验证记录：
- `python -m unittest tests.test_wechat_group_context.WechatGroupRecentContextTest.test_context_service_adds_reply_name_policy_for_member_aliases`（先在旧实现下确认失败，修复后通过）
- `python -m unittest tests.test_wechat_group_context tests.test_wechat_group_profile_service`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_context tests.test_wechat_group_profile_service`
- `python -m py_compile channel\wechat_group\wechat_group_profile_service.py channel\wechat_group\wechat_group_context_service.py`

### 微信群表情包预览空文件修复

- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs` 与 `wechaty-sidecar.mjs`：表情消息优先保存为 `.gif`；当 Wechaty `toFileBox()` 写出 0 字节文件时，从表情 XML 的 `cdnurl` 等地址补下载真实图片内容，避免 Web 预览拿到空文件。
- 更新 `channel/wechat_group/wechat_group_sticker_service.py`：收集表情包时拒绝 0 字节文件，防止下载失败的空资产进入表情包列表。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs` 与 `tests/test_wechat_group_sticker_service.py`：覆盖表情 CDN 地址提取、fallback 下载、`.gif` 扩展名和空文件跳过。

验证记录：
- `python -m unittest tests.test_wechat_group_sticker_service.WechatGroupStickerServiceTest.test_collect_from_message_skips_empty_sticker_file`（先在旧实现下确认失败，修复后通过）
- `npm test -- wechaty-sidecar-core.test.mjs`（在 `channel/wechat_group/sidecar` 目录执行，先在旧实现下确认失败，修复后通过）
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_sticker_service`

### 微信群全局画像命名记录计数修复

- 更新 `channel/web/static/js/console.js`：全局画像左侧画像列表的“命名记录”改为统计 `name_records.length`，与右侧详情保持一致，不再误用“出现过的群”数量。
- 更新 `tests/test_wechat_group_memory_ui.py`：新增前端静态回归断言，锁定画像列表必须使用实际命名记录数量。

验证记录：
- `python -m unittest tests.test_wechat_group_memory_ui.WechatGroupMemoryUiTest.test_global_profiles_list_counts_actual_name_records`（先在旧实现下确认失败，修复后通过）
- `python -m unittest tests.test_wechat_group_memory_ui`
- `node --check .\channel\web\static\js\console.js`

### 微信群话题参与者群昵称显示修复

- 更新 `channel/wechat_group/wechat_group_topic_service.py`：刷新活动话题时，参与者优先写入归档消息中的 `sender_nickname`，昵称为空或疑似原始 ID 时才回退 `sender_id`。
- 更新 `channel/web/web_channel.py`：`/api/wechat-group/topics/active` 与 `/api/wechat-group/topics/archive` 返回前按当前群成员归档把旧话题中的 `sender_id` 映射为群昵称，修复当前活动话题和历史活动话题参与者显示原始 ID 的问题。
- 更新 `tests/test_wechat_group_topic_service.py` 与 `tests/test_wechat_group_web.py`：新增昵称展示回归测试，并同步旧断言到群昵称展示语义。

验证记录：
- `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicServiceTest.test_build_prompt_block_from_archive_uses_sender_nicknames_as_participants`（先在旧实现下确认失败，再修复后通过）
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_wechat_group_topics_archive_api_uses_service`（先在旧实现下确认失败，再修复后通过）
- `python -m unittest tests.test_wechat_group_topic_service`
- `python -m unittest tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_context`

### 微信群情绪状态展示格式修复

- 更新 `channel/web/static/js/console.js`：在“群聊 -> 情绪与主动性”当前情绪卡片中，对情绪正负值、活跃度、社交倾向统一按两位小数展示，避免 `0.010000000000000002` 这类浮点误差直接暴露给用户。
- 更新 `channel/web/static/js/console.js`：新增 `withdrawn / engaged / guarded / steady` 解释状态的本地化映射，中文界面展示为“收敛 / 积极 / 谨慎 / 平稳”。
- 更新 `tests/test_wechat_group_web.py`：新增控制台资源回归断言，锁定情绪数值格式化与解释状态本地化入口。

验证记录：
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_formats_wechat_group_emotion_state_for_display`（先在旧实现下确认失败，修复后通过）
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_contains_wechat_group_emotion_panel tests.test_wechat_group_web.WechatGroupWebTest.test_console_formats_wechat_group_emotion_state_for_display tests.test_wechat_group_web.WechatGroupWebTest.test_wechat_group_emotion_state_api_uses_service_and_running_status`
- `node --check .\channel\web\static\js\console.js`
- `python -m unittest tests.test_wechat_group_web` 未全量通过：`test_wechat_group_topics_archive_api_uses_service` 当前期望归档参与者展示群昵称，但接口实际返回 `wxid_alice / wxid_bob`；该失败来自工作区已有话题归档相关改动，非本次情绪展示改动引入。

### 微信群学习运行时间格式修复

- 更新 `channel/web/static/js/console.js`：为「群聊 -> 永久记忆 -> 学习运行 -> 运行记录」新增运行时间格式化，将秒级/毫秒级时间戳展示为 `yyyy-MM-dd HH:mm:ss`。
- 更新 `channel/web/chat.html`：刷新 `console.js` 缓存版本，避免浏览器继续使用旧脚本。
- 更新 `tests/test_wechat_group_memory_ui.py`：新增回归断言，锁定运行记录 `started_at` 不能直接显示原始时间戳。

验证记录：
- `python -m unittest tests.test_wechat_group_memory_ui.WechatGroupMemoryUiTest.test_learning_runs_format_started_at_as_full_datetime`（先在旧实现下确认失败，再修复后通过）
- `python -m unittest tests.test_wechat_group_memory_ui`
- `node --check .\channel\web\static\js\console.js`

### 微信群 @ 人优先使用群昵称

- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`：当 `room.alias(contact)` 首次未取到群昵称时，先执行一次 `room.sync()` 刷新群成员数据，再重试 alias，避免在 wechat4u 可见 @ 文本里过早退回到联系人实际昵称。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`：新增回归测试，覆盖“首次 alias 为空、刷新后拿到群昵称”的发送场景，锁定群昵称优先级。

验证记录：
- `node --test .\channel\wechat_group\sidecar\wechaty-sidecar-core.test.mjs`
- `node --check .\channel\wechat_group\sidecar\wechaty-sidecar-core.mjs`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

### 微信群群昵称补同步节流

- 更新 `channel/wechat_group/protocol.py`、`channel/wechat_group/wechat_group_client.py` 与 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`：新增 `wechat_group_alias_sync_cooldown_minutes` 配置，默认 `1` 分钟，按 `room_id` 节流群昵称补同步；只有 `room.alias(contact)` 为空时才考虑刷新，命中冷却窗口则直接回退当前可用名称，不重复触发 `room.sync()`。
- 更新 `config.py` 与 `config-template.json`：持久化该配置，并将数值归一化到 `1..1440` 分钟。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：在「群聊 -> 基础设置」新增“群昵称补同步冷却分钟数”可配置项，保存后当前运行态通过发送命令实时下发到 sidecar，无需重启通道。
- 更新 `tests/test_wechat_group_channel.py`、`tests/test_wechat_group_web.py` 与 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`：补充命令透传、Web 保存/UI 展示和按群节流回归测试。
- 更新 `plans/20260706_微信群群昵称补同步节流.md`：回写本次实施结果、验证记录和剩余注意事项。

验证记录：
- `node --test .\channel\wechat_group\sidecar\wechaty-sidecar-core.test.mjs`
- `node --check .\channel\wechat_group\sidecar\wechaty-sidecar-core.mjs`
- `node --check .\channel\web\static\js\console.js`
- `python -m unittest tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

### 微信群正文显式 @ 别名自动学习

- 更新 `channel/wechat_group/wechat_group_learner.py`：新增正文显式 mention 别名学习，只在“一个非机器人目标成员 + 一个非机器人显式 mention 文本”时，将称呼学习到被提及成员画像，避免多目标误学。
- 更新 `channel/wechat_group/wechat_group_profile_service.py`：新增 `merge_learned_aliases()`，仅合并学习别名并更新最近出现时间，不覆盖既有 `speak_style`、`interests`、`common_words` 等画像字段。
- 更新 `channel/wechat_group/wechat_group_channel.py`：归档入站消息 metadata 时补充 `self_id`，供学习器识别并排除机器人 mention。
- 更新 `tests/test_wechat_group_learner.py`、`tests/test_wechat_group_profile_service.py`：补充“单目标显式 @ 学别名”“多目标不学习”“学习别名不覆盖既有字段”回归测试。

验证记录：
- `python -m unittest tests.test_wechat_group_profile_service tests.test_wechat_group_learner`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_profile_service tests.test_wechat_group_learner`
- `python -m py_compile channel\wechat_group\wechat_group_profile_service.py channel\wechat_group\wechat_group_learner.py channel\wechat_group\wechat_group_channel.py`

## 2026-07-05

### 微信群图片后省略追问识图修复

- 更新 `channel/wechat_group/wechat_group_channel.py`：扩展文本识图触发判断，使用户在 @ 机器人时发送“啥意思”“什么意思”这类紧跟图片的省略追问，也会进入最近群图片识别链路。
- 更新 `tests/test_wechat_group_channel.py`：新增回归测试覆盖群里最近有图片后，用户 @ 机器人问“啥意思”时会调用视觉工具并注入 `<wechat-group-image>` 上下文。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_text_ambiguous_image_question_uses_recent_group_image`（先在旧实现下确认失败，再修复后通过）
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

### 微信群全局画像群名展示修复

- 更新 `channel/wechat_group/wechat_group_archive.py`：新增按 `room_id` 查询最近非空群名的归档读取能力，覆盖消息归档和助手回复归档。
- 更新 `channel/wechat_group/wechat_group_profile_service.py` 与 `channel/web/web_channel.py`：全局画像的“出现过的群”缺少 `room_name` 时，依次从画像记录、已保存群名、运行态房间列表和归档中补齐群名。
- 更新 `channel/web/static/js/console.js`：群记忆/全局画像房间列表使用 `selected_room_names` 兜底；画像详情没有群名时显示“未命名群”，群 ID 保留在下一行用于诊断。
- 更新 `tests/test_wechat_group_profile_service.py`、`tests/test_wechat_group_web.py` 与 `tests/test_wechat_group_memory_ui.py`：增加群名补齐和前端兜底回归测试。

验证记录：
- `python -m unittest tests.test_wechat_group_profile_service tests.test_wechat_group_web tests.test_wechat_group_memory_ui`
- `python -m py_compile channel\wechat_group\wechat_group_archive.py channel\wechat_group\wechat_group_profile_service.py channel\web\web_channel.py`
- `node --check .\channel\web\static\js\console.js`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

### 微信群自由回复参数布局压缩

- 更新 `channel/web/static/js/console.js`：将自由回复「活跃档位」下的 7 个数字参数合并到同一个紧凑字段组，避免桌面端拆成两行占用过多高度。
- 更新 `channel/web/static/css/console.css`：新增自由回复紧凑网格样式，桌面宽度使用 7 列一行，平板和小屏继续响应式换行。
- 更新 `tests/test_wechat_group_web.py`：新增前端资源结构回归断言，锁定自由回复数字参数使用同一个 compact grid。

验证记录：
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_compacts_free_reply_number_fields_in_one_desktop_row`（先在旧布局下确认失败，再恢复实现后通过）
- `node --check .\channel\web\static\js\console.js`
- `python -m unittest tests.test_wechat_group_web`

### 微信群自由回复图片理解开关

- 更新 `config.py` 与 `config-template.json`：新增 `wechat_group_free_reply_image_understanding_enabled`，默认关闭，避免升级后自动增加视觉模型调用。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：在「群聊 / 图片与生图」面板新增「启用自由回复图片理解」开关，并接入 Web 配置读取、保存和布尔归一化。
- 更新 `channel/wechat_group/wechat_group_channel.py` 与 `channel/wechat_group/wechat_group_free_reply.py`：非 @ 图片仅在新开关开启时进入自由回复候选；先通过自由回复门控和大模型判定，批准后再复用现有图片理解生成 `<wechat-group-image>` 上下文。
- 更新 `tests/test_wechat_group_channel.py` 与 `tests/test_wechat_group_web.py`：覆盖默认关闭旧行为、开启后先排队不提前识图、批准后注入视觉摘要，以及 Web 配置/UI 字段。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_non_at_image_message_is_archived_without_reply_context tests.test_wechat_group_channel.WechatGroupChannelTest.test_non_at_image_message_queues_free_reply_when_image_switch_enabled tests.test_wechat_group_channel.WechatGroupChannelTest.test_worker_approved_image_free_reply_injects_vision_summary tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_lists_wechat_group_as_qr_channel tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_image_config tests.test_wechat_group_web.WechatGroupWebTest.test_console_contains_wechat_group_image_settings`
- `python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_free_reply`
- `node --check .\channel\web\static\js\console.js`

### 微信群画像常用词噪声修复

- 更新 `channel/wechat_group/wechat_group_learner.py`：为群友画像自动学习的 `common_words` 增加噪声过滤，排除 `amp`、`size`、`biztype`、短十六进制片段等 HTML/XML/微信消息元数据残留，同时保留 `api`、`nas`、`docker` 等有效技术词。
- 更新 `channel/web/static/js/console.js`：将全局画像编辑页中误标为“专业背景 / Expertise”的字段改为“常用词 / Common words”，继续沿用既有 `common_words` 接口字段，避免误导为独立专业背景。
- 更新 `tests/test_wechat_group_learner.py` 与 `tests/test_wechat_group_web.py`：新增回归测试覆盖噪声词过滤和前端字段文案契约。

验证记录：

- `python -m unittest tests.test_wechat_group_learner.WechatGroupLearnerTest.test_learner_filters_markup_noise_from_common_words`
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_console_labels_profile_common_words_as_common_words`
- `python -m unittest tests.test_wechat_group_learner tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_profile_service tests.test_wechat_group_profile_store`
- `node --check .\channel\web\static\js\console.js`

### 微信群表情包普通图片误收集修复

- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`：补齐 Wechaty `Emoticon=5` 到 `sticker` 的类型映射，并支持字符串类型 `Emoticon` / `Sticker` 识别，避免表情消息被退化为普通文本或图片类型。
- 更新 `channel/wechat_group/wechat_group_message.py` 与 `channel/wechat_group/wechat_group_channel.py`：保留 `sticker` 媒体消息进入渠道上下文的能力，但自动表情包收集只接收 `message_type="sticker"`，不再把普通图片自动加入表情包资产。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs` 与 `tests/test_wechat_group_channel.py`：新增回归测试覆盖 sidecar 表情类型识别、普通图片跳过收集和表情消息正常收集。

验证记录：

- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_sticker_collection_skips_normal_images tests.test_wechat_group_channel.WechatGroupChannelTest.test_sticker_collection_accepts_sticker_messages`
- `node --test .\wechaty-sidecar-core.test.mjs`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_sticker_service`
- `node --check .\wechaty-sidecar-core.mjs`

### 群聊 WebUI 中文化

- 更新 `channel/web/static/js/console.js`：补齐群聊页中文文案，将自由回复决策、后台任务状态、活跃档位、情绪指标、群记忆学习运行记录等动态展示里的英文改为中文展示。
- 增加群聊状态栏常见英文错误映射，避免直接展示 `room_id is required`、`save failed`、`load failed` 等接口或前端兜底英文。
- 新增并回写 `plans/20260705_微信群网页界面中文化.md`：记录本次排查范围、实际改动、验证结果和剩余事项。

验证记录：

- `node --check .\channel\web\static\js\console.js`
- `python -m unittest tests.test_wechat_group_web`

## 2026-07-04

### 微信群拟人化增强 Phase 0 配置骨架
- 更新 `config.py` 与 `config-template.json`：新增 `topic/style/emotion/sticker` 四组微信群拟人化配置默认值，为后续话题、风格、情绪和表情包能力预留统一配置入口。
- 更新 `channel/web/web_channel.py`：扩展 `/api/channels` 的 `wechat_group.extra` 返回结构，新增四组拟人化面板配置；同时补充对应保存逻辑与类型归一化，确保旧配置缺项时可回退默认值。
- 更新 `tests/test_wechat_group_web.py`：新增 `test_channels_api_lists_wechat_group_humanization_defaults` 与 `test_channels_save_wechat_group_humanization_config`，覆盖默认读取、旧配置缺项回退、新配置保存与归一化行为。

验证记录：
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_lists_wechat_group_humanization_defaults`
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_humanization_config`
- `python -m unittest tests.test_wechat_group_web`

### 微信群拟人化增强 Phase 1 话题存储底座
- 新增 `channel/wechat_group/wechat_group_topic_store.py`：引入 `wechat_group_topic_threads`、`wechat_group_topic_message_refs`、`wechat_group_topic_summary_history` 三张 SQLite 表，并提供活动话题写入、消息归属映射和摘要历史读取的首版接口。
- 新增 `channel/wechat_group/wechat_group_topic_service.py`：提供活动话题读取、`<wechat-group-topic>` prompt block 组装和按 query 搜索话题的首版服务层。
- 更新 `channel/wechat_group/wechat_group_channel.py`：把 `<wechat-group-topic>` 注入接入群消息主链路，位置位于 recent transcript 之后、knowledge 之前；同时在运行时根据 archive 最近消息规则型刷新活动话题。
- 新增 `tests/test_wechat_group_topic_service.py`：覆盖话题线程按群持久化、消息 ID / row_id 归属查询按 `room_id` 隔离、摘要历史按时间倒序返回，以及 topic service 的 prompt 组装与搜索行为。
- 更新 `tests/test_wechat_group_context.py`：新增 topic 注入顺序回归测试，确保 prompt 块顺序稳定。

验证记录：
- `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicStoreTest.test_upsert_topic_thread_persists_active_threads_by_room`
- `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicStoreTest.test_map_message_to_thread_scopes_lookup_to_room`
- `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicStoreTest.test_append_summary_history_lists_latest_snapshots`
- `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicServiceTest.test_build_prompt_block_renders_latest_active_topics`
- `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicServiceTest.test_search_topics_matches_title_and_gist`
- `python -m unittest tests.test_wechat_group_topic_service.WechatGroupTopicServiceTest.test_build_prompt_block_from_archive_refreshes_active_topic`
- `python -m unittest tests.test_wechat_group_context.WechatGroupRecentContextTest.test_channel_injects_topic_after_recent_context_before_memory`
- `python -m unittest tests.test_wechat_group_context tests.test_wechat_group_topic_service`
- `python -m unittest tests.test_wechat_group_topic_service`

### 微信群拟人化增强 Phase 3 情绪状态与主动性调度首版
- 新增 `channel/wechat_group/wechat_group_emotion_store.py`：落库 `wechat_group_emotion_states` 情绪状态表，按 `room_id` 持久化 `valence / energy / sociability / last_decay_at / last_reply_at / reply_count_1h / updated_at`。
- 新增 `channel/wechat_group/wechat_group_emotion_service.py`：实现默认值初始化、消息观察、回复后的 energy 衰减、定时回归平稳区间、时段规则拦截和 `interpreted_state` 文本解释。
- 更新 `channel/wechat_group/wechat_group_channel.py`：在文本消息进入主链路前观察群情绪，在自由回复本地决策后叠加 emotion/time-rule 修正，把 `<wechat-group-emotion>` 注入到 `knowledge` 之后、用户问题之前，并在文本回复发送前模拟 typing delay、发送后记录情绪回复。
- 更新 `channel/web/web_channel.py`：新增 `/api/wechat-group/emotion/state`、`/api/wechat-group/emotion/config`、`/api/wechat-group/emotion/reset`，支持读取当前群情绪状态、重置状态以及保存时段/typing 相关配置。
- 更新 `channel/web/static/js/console.js`：在 groups 管理页新增“情绪与主动性”子页，支持按群查看实时情绪、最近自由回复决策，以及保存时段规则和 typing delay 配置。
- 更新 `tests/test_wechat_group_context.py`、`tests/test_wechat_group_channel.py`，新增 `tests/test_wechat_group_emotion_service.py`：覆盖默认情绪初始化、消息观察、时段规则拦截、自由回复压制、prompt 注入顺序和 typing delay 行为。
- 更新 `tests/test_wechat_group_web.py`：覆盖情绪状态读取、情绪重置、情绪配置保存和群页面板入口。

验证记录：
- `python -m unittest tests.test_wechat_group_emotion_service tests.test_wechat_group_context tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_web tests.test_wechat_group_topic_service tests.test_wechat_group_emotion_service tests.test_wechat_group_context tests.test_wechat_group_channel`
- `node --check .\\channel\\web\\static\\js\\console.js`

### 微信群拟人化增强 Phase 2 风格卡片
- 新增 `channel/wechat_group/wechat_group_style_store.py` 与 `channel/wechat_group/wechat_group_style_service.py`：实现风格卡片候选持久化、规则型候选学习、审核通过/拒绝和 `<wechat-group-style>` prompt 注入。
- 更新 `channel/wechat_group/wechat_group_channel.py`：在微信群上下文中接入风格卡片块，异常时跳过对应块，不影响主链路。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：新增风格卡片候选、已启用卡片和审核操作 API/UI。
- 新增 `tests/test_wechat_group_style_service.py`，扩展 `tests/test_wechat_group_context.py` 与 `tests/test_wechat_group_web.py`：覆盖候选学习、审核启用、注入顺序和 Web 面板入口。

验证记录：
- `python -m unittest tests.test_wechat_group_style_service tests.test_wechat_group_context tests.test_wechat_group_web`
- `node --check .\\channel\\web\\static\\js\\console.js`

### 微信群拟人化增强 Phase 4 表情包资产层
- 新增 `channel/wechat_group/wechat_group_sticker_store.py`、`wechat_group_sticker_service.py` 与 `wechat_group_sticker_tools.py`：实现表情包资产存储、文件哈希去重、按群搜索、停用、每日发送限制和发送结果装配。
- 更新 `channel/wechat_group/wechat_group_channel.py`：归档图片消息后收集表情包候选，发送回复后记录表情包使用。
- 更新 `bridge/agent_bridge.py`：为微信群 turn 临时挂载 `wechat_group_sticker_search` 与 `wechat_group_sticker_send` scoped tools，保持按当前群隔离。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：新增表情包列表、搜索、预览和停用管理 API/UI。
- 新增 `tests/test_wechat_group_sticker_service.py`，扩展 `tests/test_wechat_group_agent_bridge_tools.py` 与 `tests/test_wechat_group_web.py`：覆盖收集去重、发送限制、停用搜索和 Agent 工具挂载。

验证记录：
- `python -m unittest tests.test_wechat_group_sticker_service tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_web`
- `node --check .\\channel\\web\\static\\js\\console.js`

### 微信群拟人化增强 Phase 5 多模态上下文补齐
- 更新 `config.py` 与 `config-template.json`：新增 `wechat_group_video_understanding_enabled`、`wechat_group_forward_preview_enabled`、`wechat_group_quote_context_enabled` 三个保守配置项。
- 更新 `channel/wechat_group/wechat_group_message.py`、`channel/wechat_group/sidecar/wechaty-sidecar-core.mjs` 与 `wechaty-sidecar.mjs`：补齐 `raw_app_type`、`forward`、引用和合并消息预览元数据上报。
- 更新 `channel/wechat_group/wechat_group_channel.py`：新增 `<wechat-group-multimodal>` 块，支持引用消息、合并转发预览和视频消息上下文；视频理解默认关闭，直接 @ / 引用机器人时才进入文本上下文路径。
- 更新 `channel/wechat_group/wechat_group_archive.py`：`get_recent_messages()` 返回解析后的 `metadata` 与 `at_list`，供后续多模态上下文使用。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：在 `/api/channels` 和“图片与生图”面板中接入视频上下文、转发预览、引用上下文三个开关。
- 扩展 `tests/test_wechat_group_message.py`、`tests/test_wechat_group_channel.py`、`tests/test_wechat_group_context.py` 与 `tests/test_wechat_group_web.py`：覆盖 forward 元数据解析、多模态块注入、视频直达文本上下文、归档 metadata 返回和 Web 配置保存。

验证记录：
- `python -m unittest tests.test_wechat_group_message.WechatGroupMessageTest.test_parse_forward_preview_metadata tests.test_wechat_group_channel.WechatGroupChannelTest.test_compose_context_injects_multimodal_quote_and_forward_block tests.test_wechat_group_channel.WechatGroupChannelTest.test_handle_text_video_message_builds_text_context_when_video_understanding_enabled tests.test_wechat_group_web.WechatGroupWebTest.test_channels_api_lists_wechat_group_as_qr_channel tests.test_wechat_group_web.WechatGroupWebTest.test_channels_save_wechat_group_image_config`
- `python -m unittest tests.test_wechat_group_context.WechatGroupRecentContextTest.test_archive_recent_messages_include_parsed_metadata`
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_text_image_request_prefers_quoted_image`
- `node --check .\\channel\\wechat_group\\sidecar\\wechaty-sidecar-core.mjs`
- `node --check .\\channel\\wechat_group\\sidecar\\wechaty-sidecar.mjs`
- `node --check .\\channel\\web\\static\\js\\console.js`

### 微信群拟人化增强 Phase 6 Web 管理 UI 与阶段回归
- 更新 `channel/web/web_channel.py`：补齐 `/api/wechat-group/topics/*`、`/api/wechat-group/styles/*`、`/api/wechat-group/emotion/*`、`/api/wechat-group/stickers/*` 运维接口。
- 更新 `channel/web/static/js/console.js`：在 groups 视图中完成话题追踪、风格卡片、情绪与主动性、表情包、图片与多模态配置等子页，补齐加载、空状态、错误状态和写操作反馈。
- 更新 `plans/20260704_微信群拟人化升级方案.md`：回写 Phase 2、Phase 4、Phase 5、Phase 6 实际进度、验证命令和剩余 Phase 7 收尾项。

验证记录：
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_sticker_service`
- `node --check .\\channel\\web\\static\\js\\console.js`

### 微信群拟人化增强 Phase 7 收尾回归
- 更新 `plans/20260704_微信群拟人化升级方案.md`：标记 Phase 7 完成，补充 sidecar 真实扫码链路手动验证说明。
- 更新 `CHANGES.md`：记录本轮拟人化增强 Phase 2/4/5/6/7 的代码交付与验证结果。

验证记录：
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_topic_service tests.test_wechat_group_style_service tests.test_wechat_group_emotion_service tests.test_wechat_group_sticker_service tests.test_wechat_group_memory_ui`
- `node --check .\\channel\\wechat_group\\sidecar\\wechaty-sidecar-core.mjs`
- `node --check .\\channel\\wechat_group\\sidecar\\wechaty-sidecar.mjs`
- `node --check .\\channel\\web\\static\\js\\console.js`

### 修复微信群全局画像列表昵称回退为原始 sender id
- 修复 `channel/wechat_group/wechat_group_profile_service.py`：当画像主昵称被学习成原始 sender id（如 `@...` / `wxid_...`）时，列表展示会优先使用当前群最近可用昵称；写入与返回阶段同时清洗无效昵称、别名和房间摘要，避免前端继续显示原始 id。
- 修复 `channel/wechat_group/wechat_group_learner.py`：学习画像时不再盲目采用最后一条样本消息的 `sender_nickname`，改为倒序选择最近一个可用真实昵称，降低被异常 `@...` 标识覆盖的概率。
- 修复 `channel/wechat_group/wechat_group_archive.py`：群成员列表聚合时，若最新记录是原始 sender id、历史消息中存在真实昵称，会回退到可用昵称，供画像列表按群过滤时直接显示。
- 新增/扩展 `tests/test_wechat_group_profile_service.py` 与 `tests/test_wechat_group_learner.py`，覆盖“已有真实昵称不被原始 sender id 覆盖”“按群过滤时优先显示群内真实昵称”“learner 优先学习真实昵称”。

验证记录：
- `python -m unittest tests.test_wechat_group_profile_service.WechatGroupProfileServiceTest.test_merge_learned_profile_keeps_existing_real_nickname_when_new_value_is_raw_sender_id tests.test_wechat_group_profile_service.WechatGroupProfileServiceTest.test_list_profiles_prefers_room_member_nickname_over_raw_sender_id -v`
- `python -m unittest tests.test_wechat_group_learner.WechatGroupLearnerTest.test_learner_prefers_real_nickname_over_raw_sender_id -v`
- `python -m unittest tests.test_wechat_group_profile_service tests.test_wechat_group_learner tests.test_wechat_group_web -v`

### 迁移 BaiLongmaPro 聊天历史到 CowAgent 会话库
- 新增 `agent/chat/history_migration.py`，支持读取 BaiLongmaPro `conversations` 表并转换为 CowAgent `sessions` / `messages` 结构。
- 新增 `scripts/migrate_legacy_chat_history.py`，支持默认 dry-run、`--apply` 正式写入和写入前 SQLite 备份。
- 新增 `tests/test_chat_history_migration.py`，覆盖来源渠道与外部对象聚合、Web 归档会话写入、原始时间戳保留、纯 assistant 源会话占位、重复导入阻断和脚本独立运行。
- 新增 `plans/20260704_聊天历史迁移.md`，记录迁移范围、实际导入结果、验证命令和剩余手动验证项。
- 已执行真实迁移：`D:\JiangShuai\SourceCode\BaiLongmaPro\data\jarvis.db` 中 `41` 条旧聊天记录导入到 `C:\Users\clancy\cow\memory\long-term\index.db`，生成 `5` 个 Web 归档会话和 `43` 条目标消息。
- 正式写入前已创建备份：`C:\Users\clancy\cow\memory\long-term\index.migration-backup-20260704090946.db`。

验证记录：
- `python -m unittest tests.test_chat_history_migration -v`
- `python -m py_compile agent\chat\history_migration.py scripts\migrate_legacy_chat_history.py tests\test_chat_history_migration.py`
- `python scripts\migrate_legacy_chat_history.py --source-db 'D:\JiangShuai\SourceCode\BaiLongmaPro\data\jarvis.db' --target-db 'C:\Users\clancy\cow\memory\long-term\index.db'`
- `python scripts\migrate_legacy_chat_history.py --source-db 'D:\JiangShuai\SourceCode\BaiLongmaPro\data\jarvis.db' --target-db 'C:\Users\clancy\cow\memory\long-term\index.db' --apply`
- SQLite 核对新增迁移会话 `5` 个、目标消息 `43` 条。

## 2026-07-03

### 修复缺失生图前缀配置时不触发生图
- 修复 `config.json` 未显式包含 `image_create_prefix` 时，微信群 `@小灯 画个兔子` 被当作普通文本送入 Agent、没有进入 `ContextType.IMAGE_CREATE` 的问题。
- 更新 `channel/chat_channel.py`：缺失 `image_create_prefix` 时恢复内置生图触发词 `画`、`看`、`找`；若用户显式配置为空列表，仍保持关闭前缀触发的语义。
- 修复 `skills/image-generation/scripts/generate.py` 在独立子进程中没有加载主配置，导致已配置的 `custom:a838bee2` 被误判为 `unknown custom provider id` 的问题；脚本现在会从数据目录 `config.json` 回读 `custom_providers`。
- 修复 NewAPI 图像模型返回 `b64_json: null` 且同时返回 `url` 时，脚本错误解码空值导致生图失败的问题；现在会跳过空 `b64_json` 并下载 `url` 图片。
- 本地运行配置已将图像生成模型从文本模型 `agnes-2.0-flash` 调整为 NewAPI 图像模型 `agnes-image-2.1-flash`。
- 更新 `channel/channel.py`：图像生成脚本失败时，技术错误只写入日志，群内回复使用固定兜底文案，避免把内部 provider id / 异常细节直接推送到微信群。
- 更新 `channel/wechat_group/wechat_group_free_reply.py`：普通群聊里讨论“图片生成失败 / 绘图密钥 / 画不了”等失败话题时不再触发自由回复，避免拟人回复继续放大错误。
- 扩展 `tests/test_wechat_group_channel.py`：覆盖缺失配置时微信群 @ 生图请求应转成 `ContextType.IMAGE_CREATE`。
- 扩展 `tests/test_image_generation_custom_provider.py`：覆盖子进程空内存配置时从 `config.json` 解析自定义图像生成厂商。
- 扩展 `tests/test_wechat_group_free_reply.py`：覆盖生图失败讨论不触发微信群自由回复。
验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_wechat_group_image_create_uses_builtin_prefix_when_config_missing`
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_image_create_script_failure_returns_safe_user_message tests.test_image_generation_custom_provider.TestImageGenerationCustomProvider.test_build_providers_loads_custom_provider_from_config_file_when_conf_is_empty`
- `python -m py_compile channel\channel.py skills\image-generation\scripts\generate.py tests\test_wechat_group_channel.py tests\test_image_generation_custom_provider.py`
- `python -m unittest tests.test_image_generation_custom_provider.TestImageGenerationCustomProvider.test_custom_provider_generation_uses_url_when_b64_json_is_null tests.test_wechat_group_free_reply.WechatGroupFreeReplyDecisionTest.test_image_generation_failure_discussion_is_suppressed`
- `python -m unittest tests.test_image_generation_custom_provider tests.test_wechat_group_free_reply tests.test_wechat_group_channel tests.test_models_handler`
- `python -B -c "from pathlib import Path; paths=['skills/image-generation/scripts/generate.py','channel/wechat_group/wechat_group_free_reply.py','channel/channel.py','channel/chat_channel.py','tests/test_image_generation_custom_provider.py','tests/test_wechat_group_free_reply.py','tests/test_wechat_group_channel.py']; [compile(Path(p).read_text(encoding='utf-8'), p, 'exec') for p in paths]; print('syntax ok')"`
- 真实脚本验证：`custom:a838bee2` + `agnes-image-2.1-flash` 成功生成本地图片。

### Agent 模式生图请求直连图像生成脚本
- 修复微信群 `@小灯 画个兔子` 在 Agent 模式下没有真正生图的问题：`ContextType.IMAGE_CREATE` 现在会直接调用 `skills/image-generation/scripts/generate.py`，不再依赖 LLM 自行决定是否读取技能并拼接 `bash` 命令。
- 图像生成脚本调用改为 Python `subprocess.run([...])` 参数列表传入 JSON，避免 Windows shell 引号处理导致 `Invalid JSON`。
- 继续只在 `agent=true` 时启用该确定性分支；非 Agent 模式保留原有 Bot 生图路径。
- 扩展 `tests/test_wechat_group_channel.py`，覆盖 Agent 模式生图绕过通用 Agent 文本回复、脚本参数使用 JSON 且不走 shell。
验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_image_create_in_agent_mode_uses_deterministic_script_runner tests.test_wechat_group_channel.WechatGroupChannelTest.test_image_create_script_runner_uses_json_argument_without_shell tests.test_wechat_group_channel.WechatGroupChannelTest.test_image_create_success_records_hourly_usage`
- `python -B -c "from pathlib import Path; paths=['channel/channel.py','tests/test_wechat_group_channel.py']; [compile(Path(p).read_text(encoding='utf-8'), p, 'exec') for p in paths]; print('syntax ok')"`
- `python -m unittest tests.test_wechat_group_channel tests.test_models_handler tests.test_image_generation_custom_provider`

### 图像生成支持自定义厂商
- 更新 `channel/web/web_channel.py`：图像生成能力下拉框展开 `custom:<id>` 自定义厂商，保存时校验自定义厂商存在、`api_key`、`api_base` 与模型名，并移除已完成路由后的 `router_pending` 状态。
- 更新 `skills/image-generation/scripts/generate.py`：显式选择 `custom:<id>` 时，从 `custom_providers` 读取凭据和默认模型，并复用 OpenAI-compatible `/images/generations` / `/images/edits` 接口。
- 更新 `skills/image-generation/SKILL.md`：将 `SKILL_IMAGE_GENERATION_PROVIDER` 纳入技能可用性判断，避免只配置自定义图像生成厂商时技能被隐藏。
- 扩展 `tests/test_models_handler.py` 并新增 `tests/test_image_generation_custom_provider.py`，覆盖图像生成自定义厂商下拉、保存校验、默认模型回填、运行时请求 URL/Header/Payload 和错误路径。
验证记录：
- `python -m unittest tests.test_models_handler tests.test_image_generation_custom_provider`
- `python -m unittest tests.test_custom_provider tests.test_custom_provider_handlers tests.test_models_handler tests.test_image_generation_custom_provider`
- `python -m py_compile channel\web\web_channel.py skills\image-generation\scripts\generate.py tests\test_models_handler.py tests\test_image_generation_custom_provider.py`
- `git diff --check`

### 微信群图片理解与生图限流
- 新增 `plans/20260703_微信群图片多模态方案.md`，记录微信群图片理解、生图限流和 Web 配置方案，并在开发完成后回写实际改动、验证结果和剩余事项。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`、`wechaty-sidecar.mjs` 与 sidecar 测试：识别图片消息、规整媒体文件名、下载媒体到外部目录，并向 Python 上报 `message_type` 与 `file_path`。
- 修复真实 wechat4u 链路中文本消息 `MessageType.Text = 7` 被误判为文件的问题，避免普通文本消息触发 `toFileBox()` 并报 `text message no file`。
- 修复“回复引用图片并 @ 机器人识别这张图”的实际群聊链路：直接触发的文本识图请求会优先使用引用消息指向的图片；引用 ID 查不到时按引用发送者匹配当前群最近图片，最后才回退到当前群 10 分钟内最近图片。
- 更新 `channel/wechat_group/wechat_group_channel.py` 与 `wechat_group_archive.py`：直接触发的图片消息复用既有 `Vision` 工具生成视觉摘要并注入 `<wechat-group-image>` 上下文，增加摘要缓存；微信群生图请求按群统计最近 1 小时成功受理次数并超额拒绝。
- 更新 `config.py`、`config-template.json`、`channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：新增图片理解开关、纯图片评论开关、视觉摘要缓存分钟数、生图每小时上限，并在 Web 控制台“群聊 -> 图片与生图”中配置。
- 扩展 `tests/test_wechat_group_channel.py`、`tests/test_wechat_group_web.py` 和 sidecar Node 测试，覆盖图片理解上下文注入、非 @ 图片跳过回复、摘要缓存、生图限流记录、配置保存和媒体路径安全。
验证记录：
- `python -m unittest tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_context`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `npm test`（在 `channel/wechat_group/sidecar` 目录）
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_text_image_request_uses_recent_group_image`
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_text_image_request_prefers_quoted_image`
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_at_text_image_request_uses_quoted_sender_when_quote_id_missing`
- 未执行真实微信群手动验证；仍需扫码登录后在目标群验证 @ 图片评论、生图返回和超额拒绝。

### 微信群引用机器人消息触发
- 新增 `plans/20260703_微信群引用自身触发.md`，记录引用机器人消息按被 @ 处理的实现方案、风险与验证结果。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs` 与 `wechaty-sidecar.mjs`：通过 wechat4u raw `appmsg type=57` 解析 `refermsg.fromusr`，当引用发送者等于当前机器人 ID 时上报 `is_quote_self` 和引用摘要。
- 更新 `channel/wechat_group/wechat_group_message.py`、`channel/wechat_group/wechat_group_channel.py` 与 `channel/chat_channel.py`：保存引用元数据，并将引用机器人消息纳入微信群直接回复链路，同时保留普通引用消息跳过逻辑。
- 扩展 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`、`tests/test_wechat_group_message.py` 和 `tests/test_wechat_group_channel.py`，覆盖引用机器人、引用他人、引用文本过滤绕过和自由回复绕过场景。
验证记录：
- `node --test .\wechaty-sidecar-core.test.mjs`
- `node --check .\wechaty-sidecar.mjs`
- `node --check .\wechaty-sidecar-core.mjs`
- `python -m py_compile channel\chat_channel.py channel\wechat_group\wechat_group_message.py channel\wechat_group\wechat_group_channel.py`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- 未执行真实微信群手动验证；仍需扫码登录后在目标群引用机器人消息确认真实链路。

## 2026-07-03

### 同步上游 master 更新
- 新增 `upstream = git@github.com:zhayujie/CowAgent.git` 远端并合并 `upstream/master` 的 6 个提交。
- 吸收上游 Claude 默认模型更新：新增 `claude-sonnet-5` 常量，更新 Claude 推荐模型、视觉工具默认候选、Web 控制台模型列表及多语言模型文档。
- 吸收桌面端更新：新增 macOS 签名/公证相关 `desktop/electron-builder.js`、`desktop/build/entitlements.mac.plist`、静态资源类型声明和桌面端品牌 logo；保留本 fork 的微信群、记忆、搜索与日志改动。
- 新增 `plans/20260703_上游同步.md` 记录本次同步分析、执行步骤与验证结果。
验证记录：
- `npm run build`（在 `desktop/` 目录）
- `python -m unittest tests.test_models_handler tests.test_web_search_providers tests.test_chat_gpt_logging`
- `python -m unittest tests.test_security_ssrf_web_fetch`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile common\const.py channel\web\web_channel.py agent\tools\vision\vision.py models\claudeapi\claude_api_bot.py models\chatgpt\chat_gpt_bot.py`
- `git diff --check`
- 全量 `python -m unittest discover -s tests` 未通过：291 个测试中失败 5、错误 5；失败项为合并前已存在的测试环境/历史断言问题，包括缺少 `pytest`、Windows 默认 GBK 读取 UTF-8 文件、Qianfan 文档断言、Web console cache buster 旧断言，以及测试导入顺序导致的 `requests` stub 污染。

### ChatGPT query 日志摘要精简
- 更新 `models/chatgpt/chat_gpt_bot.py`：将 `[CHATGPT] query=` 从完整打印用户输入改为单行摘要；对微信群自由回复 LLM 判定 prompt 仅记录 `room`、`sender`、`text`、本地得分、阈值、原因、字符数和行数，避免整段判定器说明刷屏。
- 新增 `tests/test_chat_gpt_logging.py`：覆盖自由回复判定 prompt 不泄露完整说明文本，并保留普通短 query 原样打印。
验证记录：
- `python -B -m unittest tests.test_chat_gpt_logging tests.test_wechat_group_free_reply_judge`
- `python -B -c "from pathlib import Path; paths=['models/chatgpt/chat_gpt_bot.py','tests/test_chat_gpt_logging.py']; [compile(Path(p).read_text(encoding='utf-8'), p, 'exec') for p in paths]; print('syntax ok')"`
- `git diff --check`

### 联网搜索支持 Serper 与 Jina
- 更新 `agent/tools/web_search/web_search.py`：新增 `serper` 与 `jina` 搜索 Provider，分别读取 `tools.web_search.serper_api_key` / `SERPER_API_KEY` 与 `tools.web_search.jina_api_key` / `JINA_API_KEY`，并按统一结果格式返回标题、链接和摘要。
- 更新 `channel/web/web_channel.py` 与 `channel/web/static/js/console.js`：在「模型管理 -> 联网搜索 -> 添加厂商」中加入 Serper、Jina；Bocha/Serper/Jina 复用搜索专用 API Key 弹窗，并在弹窗中展示对应申请链接。
- 更新 `config.py`、`config-template.json` 与 `docs/*/tools/web-search.mdx`：补充 `tools.web_search` 默认结构、Serper/Jina 配置键、申请入口和自动路由顺序说明。
- 新增 `tests/test_web_search_providers.py` 并扩展 `tests/test_models_handler.py`：覆盖 Serper/Jina Provider 识别、专用凭证保存、Serper 请求归一化和 Jina 文本结果解析。

验证记录：
- `python -m unittest tests.test_models_handler tests.test_web_search_providers`
- `node --check D:\JiangShuai\SourceCode\CowAgent\channel\web\static\js\console.js`
- `python -m py_compile agent\tools\web_search\web_search.py channel\web\web_channel.py config.py tests\test_models_handler.py tests\test_web_search_providers.py`
- `python -m json.tool config-template.json`

### 微信群自由回复评分与发送链路修复
- 参考 `BaiLongmaPro/src/social/wechat-ambient-reply.js` 的接话评分思路，扩展 `channel/wechat_group/wechat_group_free_reply.py`：普通群问题支持“哪里/啥意思/能不能/看看”等口语问法，结合当前群近期消息补充 `unanswered_question` 加分；低信息闲聊和梗类文本按更接近群聊语境的规则判断。
- 修复 XML / 表情 / 图片原始 payload 因包含 `?` 被误判为群问题的问题，新增 `media_payload` 抑制，避免非文本内容误入自由回复 LLM 复核。
- 更新 `channel/wechat_group/wechat_group_channel.py` 与 `channel/chat_channel.py`：自由回复本地评分时读取当前群最近消息；LLM 复核通过后用 `wechat_group_force_reply` 绕过通用群聊非 @ 过滤，确保进入最终 LLM 回复与微信群发送链路，同时仍保留自由回复不 mention 发送者的行为。
- 更新 `channel/web/static/js/console.js`：切换自由回复活跃档位时同步刷新阈值、间隔和上限输入框，避免把 normal 档参数误保存到 active/crazy 等档位。
- 扩展 `tests/test_wechat_group_free_reply.py`、`tests/test_wechat_group_channel.py`、`tests/test_wechat_group_web.py`：覆盖口语问法 active 档触发、XML payload 抑制、worker 通过后进入最终回复队列，以及 Web 档位切换同步逻辑。

验证记录：
- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_judge tests.test_wechat_group_free_reply_worker tests.test_wechat_group_channel tests.test_wechat_group_web`
- `node --check D:\JiangShuai\SourceCode\CowAgent\channel\web\static\js\console.js`
- `python -m py_compile channel\chat_channel.py channel\wechat_group\wechat_group_free_reply.py channel\wechat_group\wechat_group_channel.py tests\test_wechat_group_free_reply.py tests\test_wechat_group_channel.py tests\test_wechat_group_web.py`

### Agent turn start 日志摘要优化
- 更新 `agent/protocol/agent_stream.py`：Agent 入口日志改为 `[Agent] turn start` 结构化摘要，只展示模型、thinking 状态、真实用户问题预览和微信群增强块规模。
- 微信群增强上下文只记录块类型和统计信息，例如 `wechat_context=persona, recent_transcript, memory`、`recent_transcript_messages`、`recent_transcript_window`、`memory_chars`，不再打印最近群聊逐条内容、人设正文或群记忆正文。
- 扩展 `tests/test_agent_stream_logging.py`：覆盖微信群人设、最近群聊 transcript 和群记忆均不会泄露到入口日志，同时保留用户真实问题预览。

验证记录：
- `python -m unittest tests.test_agent_stream_logging`
- `python -m py_compile agent\protocol\agent_stream.py tests\test_agent_stream_logging.py`

### 微信群与 Agent 请求日志可读性优化
- 更新 `channel/wechat_group/wechat_group_channel.py`：收到微信群消息时记录群名、发送人、消息类型、是否 @ 和截断文本；未 @ 文本进入自由回复判定后记录入队/跳过、得分、阈值、档位、命中原因和抑制原因。
- 更新 `channel/wechat_group/wechat_group_free_reply_worker.py`：自由回复 LLM 复核通过或拒绝时记录置信度、错误码/原因和消息预览，便于定位“为什么接话或沉默”。
- 更新 `agent/protocol/agent_stream.py`：将 LLM 请求摘要压缩为单行，保留 system 来源、历史角色/字数和工具名称，去掉工具 schema 展开，降低日志噪声。
- 扩展 `tests/test_agent_stream_logging.py`、`tests/test_wechat_group_channel.py`、`tests/test_wechat_group_free_reply_worker.py`：覆盖新的 Agent 请求摘要、微信群入站消息日志、自由回复本地判定日志和 LLM 复核拒绝日志。

验证记录：
- `python -m unittest tests.test_agent_stream_logging tests.test_wechat_group_free_reply_worker`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile agent\protocol\agent_stream.py channel\wechat_group\wechat_group_channel.py channel\wechat_group\wechat_group_free_reply_worker.py tests\test_agent_stream_logging.py tests\test_wechat_group_channel.py tests\test_wechat_group_free_reply_worker.py`

### 微信群回复真实 @ 提问人
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`：在 wechat4u runtime internals 可用时，优先通过 `webwxsendmsg` 的 `MsgSource.atuserlist` 发送带协议元数据的群聊 @；失败或 internals 不可用时继续降级为可见 `@昵称` 文本，保留原有兼容行为。
- 更新 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs`：`MsgSource.atuserlist` 允许写入真实群成员 `wxid_...`，不再只接受 `@...` Web 微信 ID，避免实际发言人 ID 被过滤后降级为普通文本。
- 扩展 `channel/wechat_group/sidecar/wechaty-sidecar-core.test.mjs`：覆盖 `sendText` 在 wechat4u runtime 可用时不再只调用 `room.say('@昵称 文本')`，而是写入 `MsgSource.atuserlist`；同时覆盖 `wxid_...` 成员 ID 的真实 @ 元数据。

验证记录：
- `node --test .\wechaty-sidecar-core.test.mjs`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

### web_fetch 代理配置透传
- 更新 `agent/tools/web_fetch/web_fetch.py`：`web_fetch` 请求优先读取 `tools.web_fetch.proxy`，未配置时复用全局 `proxy`，并将代理透传给 `requests.get`；未配置代理时保留 `requests` 默认环境变量代理行为。
- 扩展 `tests/test_security_ssrf_web_fetch.py`：覆盖工具专用代理和全局代理都会传入请求，同时保留 SSRF 跳转校验路径。

验证记录：
- `python -m unittest tests.test_security_ssrf_web_fetch.TestWebFetchProxy`
- `python -m unittest tests.test_security_ssrf_web_fetch`

### 微信群群友画像向量检索
- 更新 `agent/memory/manager.py`：修复混合检索合并结果时丢失 `id`、`scope_type`、`scope_id`、`channel_type`、`subject_id`、metadata 和来源消息的问题，保证向量命中后的作用域信息可继续用于安全过滤。
- 更新 `agent/memory/scope.py` 与 `agent/memory/storage.py`：新增当前微信群所有群友画像的作用域检索能力，允许按 `room_id` 强过滤后跨 `subject_id` 做语义召回，不放宽跨群边界。
- 更新 `channel/wechat_group/wechat_group_memory.py`：群友画像在无明确 @ 且昵称/别名不命中时，按当前群画像执行向量/关键词混合检索并注入 `matched_by="semantic"`；若昵称/别名存在歧义则保持不注入，避免误选成员。
- 更新 `channel/wechat_group/wechat_group_memory_tools.py`：`wechat_group_profile_get` 增加 `query`、`max_results`、`min_score` 参数，支持 Agent 在当前群内按自然语言搜索群友画像，仍不暴露 `room_id`。
- 扩展 `tests/test_wechat_group_memory.py` 与 `tests/test_wechat_group_memory_tools.py`：覆盖群友画像向量召回、跨群隔离、当前发言人/机器人排除和工具语义搜索。

验证记录：
- `python -m unittest tests.test_wechat_group_memory.WechatGroupMemoryServiceTest.test_preview_uses_vector_search_for_related_member_profile tests.test_wechat_group_memory_tools.WechatGroupMemoryToolsTest.test_profile_get_tool_can_vector_search_current_room_profiles`
- `python -m unittest tests.test_wechat_group_memory tests.test_wechat_group_memory_tools tests.test_wechat_group_channel`
- `python -m unittest tests.test_memory_scope tests.test_wechat_group_context tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_web`
- `python -m py_compile agent\memory\scope.py agent\memory\storage.py agent\memory\manager.py channel\wechat_group\wechat_group_memory.py channel\wechat_group\wechat_group_memory_tools.py channel\wechat_group\wechat_group_channel.py tests\test_wechat_group_memory.py tests\test_wechat_group_memory_tools.py`

### 浏览器工具缺失 Playwright 依赖提示
- 更新 `agent/tools/browser/browser_service.py`：在启动 Playwright 前显式检查依赖是否可用，缺少 `playwright` 时返回明确安装提示，避免报 `sync_playwright` 未定义。
- 新增 `tests/test_browser_service_dependency.py`：覆盖缺少 Playwright 时浏览器服务应给出可执行安装指引。

验证记录：
- `python -m unittest tests.test_browser_service_dependency`
- `python -m unittest tests.test_security_ssrf_browser_navigate`

### 微信群记忆复用向量供应商
- 更新 `channel/wechat_group/wechat_group_memory.py`：新增微信群记忆服务创建函数，创建 `MemoryManager` 时复用全局 `create_default_embedding_provider()`，避免已配置向量供应商时仍降级为关键词检索。
- 更新 `channel/wechat_group/wechat_group_channel.py` 与 `channel/web/web_channel.py`：微信群运行时上下文注入和 Web 群记忆管理入口统一使用上述服务创建函数，不再直接裸创建 `MemoryManager()`。
- 扩展 `tests/test_wechat_group_channel.py` 与 `tests/test_wechat_group_web.py`：覆盖两条懒加载入口会把配置解析出的 embedding provider 传入 `MemoryManager`。

验证记录：
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_memory_service_uses_configured_embedding_provider tests.test_wechat_group_web.WechatGroupWebTest.test_wechat_group_memory_service_uses_configured_embedding_provider`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_memory`
- `python -m py_compile channel\wechat_group\wechat_group_memory.py channel\wechat_group\wechat_group_channel.py channel\web\web_channel.py tests\test_wechat_group_channel.py tests\test_wechat_group_web.py`

### 微信群定时任务投递复用运行通道
- 更新 `agent/tools/scheduler/integration.py`：调度器投递到 `wechat_group` 时优先复用 `ChannelManager` 中已启动的微信群通道实例，避免新建未 `startup()` 的通道导致 `wechat group sidecar is not started`；其它渠道仍保持原有创建通道逻辑。
- 新增 `tests/test_scheduler_wechat_group_delivery.py`：覆盖 Agent 定时任务结果发送到微信群时必须使用运行中的微信群 sidecar 通道。

验证记录：
- `python -m unittest tests.test_scheduler_wechat_group_delivery`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_scheduler_wechat_group_delivery`
- `python -m unittest tests.test_agent_stream_scheduler_guard tests.test_prompt_scheduler_guidance tests.test_scheduler_ui`

### 微信群自由回复
- 新增 `channel/wechat_group/wechat_group_free_reply.py`、`wechat_group_free_reply_judge.py`、`wechat_group_free_reply_worker.py`：支持自由回复配置归一化、按群范围启用、本地规则评分与强抑制、每群冷却/上限状态、独立 worker 池、TTL 丢弃和轻量 LLM JSON 二次判定。
- 更新 `channel/wechat_group/wechat_group_channel.py`：未 @ 普通文本先进入自由回复本地判定，命中后只入 worker 队列；@ 机器人原必回链路不进入自由回复；worker 判定通过后复用原 `_compose_context()` / `produce()` 回复链路，并默认不真实 mention 发言人。
- 更新 `config.py`、`config-template.json`、`channel/web/web_channel.py`、`channel/web/static/js/console.js` 与 `channel/web/chat.html`：新增自由回复默认配置、Web API 读写与边界归一化、群聊页自由回复配置面板、worker/最近判定展示和脚本缓存版本。
- 新增 `tests/test_wechat_group_free_reply.py`、`tests/test_wechat_group_free_reply_judge.py`、`tests/test_wechat_group_free_reply_worker.py`，并扩展 `tests/test_wechat_group_channel.py`、`tests/test_wechat_group_web.py`：覆盖默认关闭、评分命中/抑制、冷却/上限、JSON 判定、worker 回调/丢弃、通道分流、不 mention 和 Web 配置读写。

验证记录：
- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_judge tests.test_wechat_group_free_reply_worker`
- `python -m unittest tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_web`
- `node --check .\channel\web\static\js\console.js`
- `python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_judge tests.test_wechat_group_free_reply_worker tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile channel\wechat_group\wechat_group_free_reply.py channel\wechat_group\wechat_group_free_reply_judge.py channel\wechat_group\wechat_group_free_reply_worker.py channel\wechat_group\wechat_group_channel.py channel\web\web_channel.py tests\test_wechat_group_free_reply.py tests\test_wechat_group_free_reply_judge.py tests\test_wechat_group_free_reply_worker.py tests\test_wechat_group_channel.py tests\test_wechat_group_web.py`

### 微信群当前群记忆工具
- 新增 `channel/wechat_group/wechat_group_memory_tools.py`：提供 `wechat_group_memory_search` 与 `wechat_group_profile_get` 两个只绑定当前微信群的 Agent 工具，工具参数不暴露 `room_id`，避免模型或用户跨群指定作用域。
- 更新 `channel/wechat_group/wechat_group_channel.py`：在微信群上下文中写入 `wechat_group_room_id`、`wechat_group_sender_id`、`wechat_group_bot_sender_id`，供 AgentBridge 安全创建当前 turn 的 scoped 工具。
- 更新 `bridge/agent_bridge.py`：微信群 turn 临时挂载当前群记忆/画像工具，并追加 scoped memory 使用提示；运行结束后恢复原工具列表和 `extra_system_suffix`，避免污染后续 turn。
- 更新 `agent/prompt/builder.py`：在工具摘要中展示微信群 scoped memory 工具。
- 新增 `tests/test_wechat_group_memory_tools.py`、`tests/test_wechat_group_agent_bridge_tools.py`，并扩展 `tests/test_wechat_group_context.py`：覆盖当前群记忆检索、群友画像读取、工具 schema 不暴露 room、AgentBridge 临时挂载与恢复、真实通道元数据注入。

验证记录：
- `python -m unittest tests.test_wechat_group_memory_tools tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_context tests.test_wechat_group_memory`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_memory_tools tests.test_wechat_group_agent_bridge_tools tests.test_wechat_group_context tests.test_wechat_group_memory`
- `python -m py_compile channel\wechat_group\wechat_group_memory_tools.py channel\wechat_group\wechat_group_channel.py bridge\agent_bridge.py agent\prompt\builder.py tests\test_wechat_group_memory_tools.py tests\test_wechat_group_agent_bridge_tools.py tests\test_wechat_group_context.py`
- `git diff --check`

### 微信群群友画像别名匹配
- 更新 `channel/wechat_group/wechat_group_memory.py`：群友画像新增 `aliases` 字段，写入 metadata 和画像正文；运行时画像召回从只匹配 `sender_nickname` 扩展为匹配 `sender_nickname + aliases`，命中别名时注入 `matched_by="alias"`，同别名命中多个 `sender_id` 时跳过注入并返回歧义诊断，保持当前群作用域隔离。
- 更新 `channel/wechat_group/wechat_group_memory_distiller.py`：自动蒸馏候选 schema 支持 `aliases`，自动应用群友画像时保留别名。
- 更新 `channel/web/web_channel.py`、`channel/web/static/js/console.js` 与 `channel/web/chat.html`：Web 控制台群友画像表单增加“别名”字段，保存画像时透传到服务层，画像列表展示已维护别名，并刷新控制台脚本缓存版本。
- 更新 `tests/test_wechat_group_memory.py`、`tests/test_wechat_group_memory_distiller.py`、`tests/test_wechat_group_web.py`、`tests/test_wechat_group_memory_ui.py`：覆盖“大力是谁”通过别名命中群友画像、别名歧义不注入、蒸馏保存别名、Web API 与 UI 入口。

验证记录：
- `python -m unittest tests.test_wechat_group_memory tests.test_wechat_group_memory_distiller tests.test_wechat_group_web tests.test_wechat_group_memory_ui tests.test_wechat_group_message tests.test_wechat_group_channel`
- `node --check .\channel\web\static\js\console.js`
- `python -m py_compile channel\wechat_group\wechat_group_memory.py channel\wechat_group\wechat_group_memory_distiller.py channel\web\web_channel.py tests\test_wechat_group_memory.py tests\test_wechat_group_memory_distiller.py tests\test_wechat_group_web.py tests\test_wechat_group_memory_ui.py`

## 2026-07-02

### 微信群运行时群友画像昵称兜底
- 更新 `channel/wechat_group/wechat_group_memory.py`：在真实 `at_list` 过滤后没有群友 ID 时，按当前群 active 群友画像的 `sender_nickname` 做唯一精确兜底；唯一命中时注入 `matched_by="nickname"`，同名歧义时不注入并返回诊断原因。参考 BaiLongmaPro 后修正 `at_list` 为空的真实链路，避免 `message.mentionList()` 未返回成员时跳过昵称画像召回。
- 更新 `tests/test_wechat_group_memory.py`：覆盖“只 @ 机器人但正文包含群友昵称”可注入画像、`at_list` 为空但正文包含群友昵称仍可注入画像，以及同昵称多画像时跳过注入。
- 新增 `plans/20260702_微信群运行时成员画像查询.md`：记录本次运行时昵称兜底方案、BaiLongmaPro 对照结论、边界、验证结果和剩余真实链路手动验证项。

验证记录：
- `python -m unittest tests.test_wechat_group_memory.WechatGroupMemoryServiceTest.test_preview_injects_unique_profile_by_nickname_when_only_bot_is_mentioned tests.test_wechat_group_memory.WechatGroupMemoryServiceTest.test_preview_skips_nickname_profile_when_match_is_ambiguous`
- `python -m unittest tests.test_wechat_group_memory.WechatGroupMemoryServiceTest.test_preview_injects_unique_profile_by_nickname_when_at_list_is_empty`
- `python -m unittest tests.test_wechat_group_memory`
- `python -m unittest tests.test_wechat_group_context`
- `python -m py_compile channel\wechat_group\wechat_group_memory.py tests\test_wechat_group_memory.py`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

### 微信群群友画像手动录入支持成员检索
- 更新 `channel/wechat_group/wechat_group_archive.py`：新增按当前 `room_id` 检索归档群成员能力，聚合 `sender_id`、昵称、最近发言时间和消息数，并支持按 `sender_id`、昵称及元数据中的微信 ID 字段过滤。
- 更新 `channel/web/web_channel.py`：新增 `/api/wechat-group/memories/members` 查询分支，供 Web 控制台在当前群内检索群友并避免跨群返回成员。
- 更新 `channel/web/static/js/console.js` 与 `channel/web/chat.html`：在群友画像手动表单上方增加“检索群友”输入、结果列表和一键回填 `sender_id` / 昵称；同步更新脚本缓存版本。
- 修复检索结果点击回填：结果项改用 `data-sender-id` / `data-sender-nickname` 保存值，并由点击元素读取，避免内联 `onclick` 参数转义导致不回填。
- 更新 `tests/test_wechat_group_context.py`、`tests/test_wechat_group_web.py`、`tests/test_wechat_group_memory_ui.py`：覆盖归档成员检索、Web API 和 UI 入口。

验证记录：
- `python -m unittest tests.test_wechat_group_context.WechatGroupRecentContextTest.test_archive_lists_members_by_room_and_query`
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_wechat_group_memory_members_api_uses_archive`
- `python -m unittest tests.test_wechat_group_memory_ui.WechatGroupMemoryUiTest.test_groups_page_exposes_memory_management_section`
- `python -m unittest tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_memory_ui`
- `node --check .\channel\web\static\js\console.js`
- `python -m py_compile channel\wechat_group\wechat_group_archive.py channel\web\web_channel.py tests\test_wechat_group_context.py tests\test_wechat_group_web.py tests\test_wechat_group_memory_ui.py`
- `python -m unittest tests.test_wechat_group_web`
- `python -m py_compile channel\web\web_channel.py`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_memory_ui`
- `python -m unittest tests.test_wechat_group_memory_ui.WechatGroupMemoryUiTest.test_groups_page_exposes_memory_management_section`
- `python -m unittest tests.test_wechat_group_memory_ui`
- `python -m unittest tests.test_wechat_group_context tests.test_wechat_group_web tests.test_wechat_group_memory_ui`
- `python -m py_compile tests\test_wechat_group_memory_ui.py`

## 2026-07-02

### Web 定时任务目标群展示
- 更新 `channel/web/static/js/console.js`：定时任务卡片展示目标群名，使用已有 `action.receiver_name`，不暴露 room ID。
- 更新 `channel/web/chat.html`：刷新 `console.js` 缓存版本，避免浏览器继续使用旧脚本。
- 新增 `tests/test_scheduler_ui.py`，并更新 `tests/test_wechat_group_memory_ui.py` 的脚本版本断言。
验证记录：
- `python -m unittest tests.test_scheduler_ui`
- `python -m unittest tests.test_wechat_group_memory_ui.WechatGroupMemoryUiTest.test_groups_page_cache_buster_changes_for_memory_ui`
- `python -m unittest tests.test_wechat_group_memory_ui`
- `python -m unittest tests.test_scheduler_ui tests.test_wechat_group_memory_ui`
- `node --check .\channel\web\static\js\console.js`

### 定时任务假确认拦截与微信群调度意图标记

- 更新 `agent/protocol/agent_stream.py`：识别定时/提醒/周期任务请求，记录本轮是否成功执行 `scheduler.create`；当模型未成功创建任务却回复“已设置/定好了/会准时”等确认语义时，替换为未创建成功提示，并同步修正会话历史中的最后一条 assistant 文本。
- 更新 `agent/protocol/agent.py`、`bridge/agent_bridge.py`、`agent/chat/service.py`：将当前 `Context` 透传给 `AgentStreamExecutor`，供执行层读取 `intent_requires_scheduler` 等上下文标记。
- 更新 `channel/wechat_group/wechat_group_channel.py`：微信群消息去除 @ 后若匹配定时/提醒/每日播报等调度意图，则设置 `intent_requires_scheduler=True`，避免人设和群聊上下文稀释原始任务。
- 更新 `agent/prompt/builder.py`：当 `scheduler` 工具可用时，在工具调用提示中明确要求定时任务必须调用 `scheduler`，不能只口头确认。
- 新增 `tests/test_agent_stream_scheduler_guard.py`、`tests/test_prompt_scheduler_guidance.py`，并扩展 `tests/test_wechat_group_channel.py`，覆盖假确认拦截、真实 `scheduler.create` 后允许确认、澄清回复不拦截、微信群调度意图标记和 prompt 规则。

验证记录：
- `python -m unittest tests.test_agent_stream_scheduler_guard`
- `python -m unittest tests.test_wechat_group_channel.WechatGroupChannelTest.test_wechat_group_scheduler_request_sets_scheduler_intent`
- `python -m unittest tests.test_prompt_scheduler_guidance`
- `python -m unittest tests.test_agent_stream_scheduler_guard tests.test_prompt_scheduler_guidance tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile agent\protocol\agent_stream.py agent\protocol\agent.py agent\chat\service.py bridge\agent_bridge.py channel\wechat_group\wechat_group_channel.py agent\prompt\builder.py tests\test_agent_stream_scheduler_guard.py tests\test_prompt_scheduler_guidance.py tests\test_wechat_group_channel.py`

## 2026-07-02

### Agent 流式工具调用解析错误降级

- 更新 `agent/protocol/agent_stream.py`：当上游 OpenAI-compatible 流式接口在带 tools 请求下返回 `Value looks like object, but can't find closing '}' symbol` / `bad_response_status_code` 这类 400 解析错误时，仅重试一次不带 tools 的请求，避免整轮 Agent 直接失败。
- 更新 `channel/wechat_group/wechat_group_channel.py`：微信群通道将 `ReplyType.INFO` / `ReplyType.ERROR` 按文本消息发送，并沿用真实 `mention_ids` @ 触发用户，避免 Agent 错误回复落入 `unsupported reply type: ERROR`。
- 更新 `tests/test_agent_stream_logging.py` 与 `tests/test_wechat_group_channel.py`：补充上游 object 解析错误无工具降级、微信群错误回复发送的回归测试。

验证记录：
- `python -m unittest tests.test_agent_stream_logging tests.test_wechat_group_channel`
- `python -m py_compile agent\protocol\agent_stream.py channel\wechat_group\wechat_group_channel.py tests\test_agent_stream_logging.py tests\test_wechat_group_channel.py`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`

### 个人微信群 4.3.7 聊天记录自动蒸馏

- 修复自动生成结果展示：`distill/run` 返回 `disabled` / `failed` 时 Web API 不再包装成成功；前端在没有自动写入和候选时显示 distiller 返回的原因，避免“自动生成已完成但没有任何记忆”的假阳性。
- 补充空候选诊断：当 LLM 返回 `group_memories: []` 且 `member_profiles: []` 时，运行结果会显示 `LLM returned no memory candidates`，便于区分“失败”和“模型认为没有稳定记忆可提取”。
- 修复 `channel/wechat_group/wechat_group_memory_distiller.py` 默认 LLM 调用路径：不再访问不存在的 `AgentBridge.llm_model`，改为直接通过 `AgentLLMModel(Bridge()).call()` 调用当前模型适配层，避免 Web 控制台点击“从最近聊天生成记忆”时报 `'AgentBridge' object has no attribute 'llm_model'`。
- 新增 `channel/wechat_group/wechat_group_memory_distiller.py`：实现从当前群归档消息手动蒸馏群记忆与群友画像，支持严格 JSON 解析、证据消息校验、画像 `sender_id` 可证明校验、置信度分流、高置信度自动写入、低置信度候选、批准和驳回。
- 更新 `channel/wechat_group/wechat_group_archive.py`：新增蒸馏消息读取、运行记录表和候选表，运行与候选查询均按 `room_id` 强过滤。
- 更新 `channel/wechat_group/wechat_group_memory.py`：群记忆/画像写入增加来源标记；自动画像更新只合并非空字段，避免清空旧画像。
- 更新 `channel/web/web_channel.py`、`config.py`、`config-template.json`：新增自动蒸馏配置返回/保存和 `/api/wechat-group/memories/distill/*` 手动运行、运行列表、候选列表、批准、驳回、来源消息查询接口。
- 更新 `channel/web/static/js/console.js` 与 `channel/web/chat.html`：在 Web 控制台“群聊 -> 永久记忆”当前群详情中新增“自动生成”标签页，提供配置保存、手动运行、运行记录和候选审核入口，并更新脚本缓存版本。
- 新增 `tests/test_wechat_group_memory_distiller.py`，扩展 `tests/test_wechat_group_web.py`：覆盖置信度分流、跨群证据拒绝、非法成员拒绝、自动写入、候选审核和 Web API。
- 更新 `plans/20260701_微信群机器人迁移方案.md`：回写 4.3.7 首个手动触发切片的完成进度、验证结果和剩余第二切片事项。

验证记录：

- `python -m unittest tests.test_wechat_group_memory_distiller tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_memory_distiller.DefaultLlmClientTest`
- `python -m unittest tests.test_wechat_group_web.WechatGroupWebTest.test_wechat_group_distill_run_api_reports_disabled_status`
- `python -m unittest tests.test_wechat_group_memory_distiller.WechatGroupMemoryDistillerTest.test_empty_llm_candidates_return_diagnostic_reason`
- `node --check .\channel\web\static\js\console.js`
- `python -m unittest tests.test_wechat_group_memory_ui tests.test_wechat_group_web tests.test_wechat_group_memory_distiller`
- `python -m py_compile channel\wechat_group\wechat_group_archive.py channel\wechat_group\wechat_group_memory.py channel\wechat_group\wechat_group_memory_distiller.py channel\web\web_channel.py tests\test_wechat_group_memory_distiller.py tests\test_wechat_group_web.py tests\test_wechat_group_memory_ui.py`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_context tests.test_wechat_group_memory tests.test_wechat_group_web tests.test_wechat_group_memory_ui tests.test_wechat_group_memory_distiller`

### 微信群人设日志脱敏

- 更新 `agent/protocol/agent_stream.py`：调用 LLM 前的用户消息日志会将 `<wechat-group-persona>...</wechat-group-persona>` 内容替换为 `微信群聊人设提示词`，避免日志打印完整微信群人设提示词；真实传给模型的上下文不变。
- 更新 `tests/test_agent_stream_logging.py`：覆盖微信群人设块只打印标签、不泄露原始人设内容，同时保留用户真实问题日志。

验证记录：
- `python -m unittest tests.test_agent_stream_logging`

### OpenAI 兼容 Agent 消息格式修复

- 更新 `models/openai_compatible_bot.py`：修复 Agent 内部 Claude text blocks 转 OpenAI 兼容消息时，普通 `user` 消息仍保留数组 `content` 的问题，避免严格网关报 `cannot unmarshal array into ... content of type string`。
- 新增 `tests/test_openai_compatible_messages.py`：覆盖普通 `user` text blocks 必须转换为字符串 `content` 的回归场景。

验证记录：
- `python -m unittest tests.test_openai_compatible_messages`
- `python -m unittest tests.test_openai_compatible_messages tests.test_custom_provider`
- `python -m py_compile models\openai_compatible_bot.py tests\test_openai_compatible_messages.py`

### 个人微信群 4.3 群记忆完整闭环

- 更新 `channel/web/static/js/console.js` 与 `channel/web/chat.html`：在 Web 控制台“群聊”页新增“永久记忆”子菜单，支持按已选 `room_id` 管理群记忆、群友画像和注入预览；包含当前群搜索、摘要数量、停用、画像 revision 只读查看和脚本缓存版本更新。
- 更新 `agent/memory/storage.py` 与 `channel/wechat_group/wechat_group_memory.py`：补齐 scoped chunk 软停用、群记忆摘要、按群摘要列表、群记忆停用和群友画像停用能力。
- 更新 `channel/web/web_channel.py`：补齐 `/api/wechat-group/memories/summary`、`groups` 和 `disable` 后端分支，形成列表、搜索、新增、更新、停用、版本查看和预览的 API 闭环。
- 更新 `tests/test_wechat_group_memory.py`、`tests/test_wechat_group_web.py`、`tests/test_wechat_group_memory_ui.py`：覆盖停用隔离、按群摘要、summary/disable Web API、Web 控制台永久记忆入口、搜索、停用和 revision 入口。
- 更新 `plans/20260701_微信群机器人迁移方案.md`：回写 4.3.2/4.3.3/4.3.6 最新完成进度、实际改动、验证结果与剩余手动验证事项。

验证记录：

- `python -m unittest tests.test_wechat_group_memory`
- `python -m unittest tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_memory_ui`
- `node --check .\channel\web\static\js\console.js`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_context tests.test_wechat_group_memory tests.test_memory_scope tests.test_wechat_group_memory_ui`
- `python -m py_compile agent\memory\scope.py agent\memory\storage.py agent\memory\manager.py channel\wechat_group\wechat_group_memory.py channel\wechat_group\wechat_group_channel.py channel\web\web_channel.py tests\test_memory_scope.py tests\test_wechat_group_memory.py tests\test_wechat_group_context.py tests\test_wechat_group_web.py tests\test_wechat_group_memory_ui.py`

### 个人微信群 4.3 群记忆后端基础

- 新增 `agent/memory/scope.py`：定义 `MemoryScope`，统一表达 shared/user/session 与微信群 `room_id`、`room_id + sender_id` 作用域。
- 更新 `agent/memory/storage.py` 与 `agent/memory/manager.py`：为长期记忆索引兼容新增 `scope_type`、`scope_id`、`channel_type`、`subject_id`、`status`、`source_message_ids` 字段，支持按 `MemoryScope` 强过滤检索和写入；旧 `scope` / `user_id` 路径保持兼容。
- 新增 `channel/wechat_group/wechat_group_memory.py`：提供 `WechatGroupMemoryService`，支持群永久记忆、群友画像 active profile、画像 revision 审计和 `<wechat-group-memory>` 预览装配。
- 更新 `channel/wechat_group/wechat_group_channel.py`：在最近群聊上下文之后、用户真实问题之前注入 `<wechat-group-memory>`，配置关闭、无命中或异常时不注入空块。
- 更新 `channel/web/web_channel.py`：新增 `/api/wechat-group/memories/(.*)` 后端 handler，完成 group、profiles、profiles/revisions 与 preview 的最小 API 闭环。
- 更新 `plans/20260701_微信群机器人迁移方案.md`：回写 4.3.1 和 4.3.2 已完成进度、实际改动、验证结果与剩余事项。

验证记录：

- `python -m unittest tests.test_memory_scope`
- `python -m unittest tests.test_wechat_group_memory`
- `python -m unittest tests.test_wechat_group_context`
- `python -m unittest tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_context tests.test_wechat_group_memory tests.test_memory_scope`
- `python -m py_compile agent\memory\scope.py agent\memory\storage.py agent\memory\manager.py channel\wechat_group\wechat_group_memory.py channel\wechat_group\wechat_group_channel.py channel\web\web_channel.py tests\test_memory_scope.py tests\test_wechat_group_memory.py tests\test_wechat_group_context.py tests\test_wechat_group_web.py`
- 未完成：`python -m pytest tests/test_knowledge_service.py` 因当前环境未安装 `pytest`，无法验证该 pytest 风格测试文件。

### 个人微信群 4.3 开发计划与 UI 设计细化

- 更新 `plans/20260701_微信群机器人迁移方案.md`：在 4.3 群永久记忆与群友画像章节新增待确认细化方案，覆盖通用作用域记忆升级、`WechatGroupMemoryService` 适配层、上下文注入链路、后端 Web API、配置边界和不做项。
- 细化 4.3 UI 设计：明确“永久记忆”入口放在群聊管理页子菜单，采用按群分组的信息架构，并拆分群记忆、群友画像、诊断预览三个面板；补充加载、错误、空状态、长 ID 展示、loading/disabled 和可访问性约束。
- 补充 4.3 待确认点：包括 Web 控制台与桌面端交付范围、群友画像表单形态、API 路径命名和画像 revision 存储方式。

验证记录：

- 文档变更，已静态检查计划文件包含 `4.3.1` 至 `4.3.5` 小节、建议 API 形态、UI 设计细化和待确认点。

### New API 自定义渠道计划修正

- 更新 `plans/20260702_新接口能力路由方案.md`：将方案从“新增独立 `newapi` provider”修正为“把 QuantumNous/new-api 作为现有 `custom:<id>` 自定义 OpenAI-compatible 渠道使用”。
- 明确不新增 `newapi_api_key` / `newapi_api_base`，改为增强现有自定义渠道覆盖图像理解、图像生成、语音识别、语音合成和向量五类能力。

验证记录：

- 已核对 QuantumNous/new-api 项目定位为统一 AI 模型网关，支持 OpenAI-compatible 及 Chat/Image/Audio/Embeddings 等接口。
- 文档变更，已静态检查计划文件包含 `custom:<id>` 路由、五类能力任务、配置示例、风险回退和验证命令。

### 个人微信群 4.3 记忆上下文链路文档

- 更新 `AGENTS.md`：将个人微信群 LLM 请求上下文链路扩展为 4.3 目标结构，明确 `<wechat-group-memory>` 应注入当前群记忆、当前发言人群友画像和本轮被 @ 群友画像，并补充 `room_id` / `sender_id` 隔离规则。
- 更新 `plans/20260701_微信群机器人迁移方案.md`：在 4.3 群永久记忆与群友画像章节列出下一步开发任务，覆盖 `WechatGroupMemoryService` 装配入口、通道注入位置、被 @ 群友画像召回和测试要求。

验证记录：

- 文档变更，已检查 `AGENTS.md` 与 4.3 开发计划中的上下文注入顺序和隔离规则一致。

### AGENTS UI 默认修改目标规则

- 更新 `AGENTS.md`：补充 UI 修改默认目标规则，明确用户要求修改 UI、页面、布局、交互或样式但未指定端时，只修改 Web 控制台相关文件，不默认联动修改桌面端；仅在用户明确指定桌面端、Electron 或 `desktop/` 时才修改桌面端 UI。

验证记录：

- 文档变更，已检查 `AGENTS.md` 包含 UI 默认修改 Web 控制台规则。

### AGENTS 开发计划回写规则

- 更新 `AGENTS.md`：在“修改原则”中补充跟进开发计划文档开发时的收尾要求，明确开发完成后必须回写对应计划文档，更新已完成进度、实际改动、验证结果与剩余事项。

验证记录：

- 文档变更，已检查 `AGENTS.md` 包含开发计划回写规则，`CHANGES.md` 已记录本次修改。

### 桌面端群聊页宽度调整

- 更新 `desktop/src/renderer/src/pages/GroupsPage.tsx`：移除右侧详情面板的 `max-w-4xl` / `max-w-5xl` 宽度限制，使群聊页主内容区与知识库页一样覆盖可用窗口宽度。
- 调整群聊页内部布局：基础设置改为更适合宽屏的三列比例；群聊开关页扩大已选群列表和群名兜底编辑区；人设设定编辑器改为随右侧空间撑开并保留内部滚动。
- 更新 `channel/web/chat.html` 与 `channel/web/static/js/console.js`：同步 Web 控制台群聊页宽度，外层对齐知识库页 `max-w-[1600px]`，并扩大动态渲染的群聊开关、人设编辑内部空间。

验证记录：

- 静态布局断言：确认 `GroupsPage.tsx` 不再包含 `max-w-4xl` / `max-w-5xl` 详情宽度限制，并包含新的宽屏群聊布局。
- 静态布局断言：确认 Web 控制台 `view-groups` 外层已对齐知识库页 `max-w-[1600px]`，且动态群聊详情面板不再包含窄宽度限制。
- `node --check .\channel\web\static\js\console.js`
- `Set-Location -LiteralPath .\desktop`
- `npm run build`

### Agent LLM 请求上下文日志

- 更新 `agent/protocol/agent_stream.py`：在每次调用 LLM 前只打印请求上下文来源与概要，包括 system prompt 字符数、加载来源文件、顶层章节、messages 角色/块类型/字符统计和 tools 名称/schema 概况，避免完整打印 system prompt、历史消息正文和 tool schema。
- 更新 `tests/test_agent_stream_logging.py`：覆盖日志包含来源与概要信息，同时不泄露完整上下文正文、历史消息正文和长用户消息尾部内容。

验证记录：

- `python -m unittest tests.test_agent_stream_logging`
- `python -m py_compile agent/protocol/agent_stream.py tests/test_agent_stream_logging.py`

### 桌面端群聊页与 4.3 计划补充

- 新增 `desktop/src/renderer/src/pages/GroupsPage.tsx`：提供桌面端独立“群聊”管理页，支持“基础设置 / 群聊开关 / 人设设定”三段式左侧子菜单、4.2 最近上下文配置、群名检索多选和自定义人设保存。
- 更新 `desktop/src/renderer/src/App.tsx` 与 `desktop/src/renderer/src/layout/NavRail.tsx`：新增 `/groups` 路由和左侧“群聊”菜单入口。
- 更新 `desktop/src/renderer/src/pages/ChannelsPage.tsx`：个人微信群通道卡片不再展示群聊细项设置，仅保留接入、扫码、连接和断开入口。
- 更新 `desktop/src/renderer/src/types.ts` 与 `desktop/src/renderer/src/i18n.ts`：补充微信群最近上下文配置类型和群聊管理页中英文文案。
- 更新 `AGENTS.md`：补充个人微信群通道请求 LLM 前的实际上下文链路，明确其是在原 `ChatChannel` / Agent 主链路基础上叠加 `<wechat-group-persona>` 与 `<recent-wechat-group-transcript>`。
- 更新 `plans/20260701_微信群机器人迁移方案.md`：细化 4.3 群永久记忆与群友画像的首轮边界、上下文注入格式、服务接口、UI 运维范围和测试要求。
- 继续补充 4.3 记忆方案：明确微信群群记忆与群友画像进入 CowAgent 通用作用域记忆体系，通过 `scope_type`、`scope_id`、`channel_type`、`subject_id` 兼容扩展保持旧记忆行为不变。
- 细化 4.3 UI 展示要求：永久记忆页必须按群分类展示记忆内容；选中某个群后再区分群记忆与按成员展示的群友画像，并补充对应测试要求。
- 根据通用作用域记忆方案修订 4.3 任务五、任务六与相邻章节：明确群友画像采用单份 active profile + revision 审计模型，提示词装配必须通过 `WechatGroupMemoryService` / `MemoryScope` 获取已过滤结果，UI 分类数据必须来自统一记忆 API 的 scope 聚合结果，并补充作用域记忆验证命令。

验证记录：

- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `Set-Location -LiteralPath .\desktop`
- `npm run build`
- 文档变更，已检查 4.3 方案与当前微信群 4.2 上下文注入边界一致。

### 群聊管理页与 4.2 配置 UI

- 更新 `channel/web/chat.html` 与 `channel/web/static/js/console.js`：在 Web 控制台管理目录新增“群聊”入口和独立群聊管理页，支持“基础设置 / 群聊开关 / 人设设定”三段式左侧子菜单。
- Web 群聊页新增 4.2 最近上下文三个配置项、群名检索下拉多选、自定义人设设置；个人微信群通道卡片不再展示群聊细项设置。
- 为 Web 控制台 `console.js` 引用增加版本参数，避免浏览器缓存旧脚本导致重启后看不到新 UI。
- 修复 Web 群聊页状态提示误引用不存在的 `TRANSLATIONS` 对象导致的运行时异常，并补齐移除最后一个已选群后的空状态提示。
- 新增 `plans/20260702_微信群管理界面方案.md`：记录群聊管理页双栏紧凑布局、三个左侧子菜单和 4.2 配置迁移范围。
- 更新 `channel/web/web_channel.py`：`wechat_group.extra` 返回 `recent_context`，并支持保存 `wechat_group_recent_context_enabled`、`wechat_group_recent_context_limit`、`wechat_group_recent_context_minutes`。
- 更新 `tests/test_wechat_group_web.py`：覆盖最近上下文配置返回与保存。

验证记录：

- `python -m unittest tests.test_wechat_group_web`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `node --check .\channel\web\static\js\console.js`

### 4.2 当前群最近上下文

- 新增 `channel/wechat_group/wechat_group_archive.py`：使用微信群专用 SQLite 数据库记录 `wechat_group_messages` 与 `wechat_group_assistant_replies`，入站消息按 `room_id` 隔离，避免污染 CowAgent 全局长期记忆。
- 新增 `channel/wechat_group/wechat_group_context.py`：生成 `<recent-wechat-group-transcript>` 最近群聊上下文块，包含时间、消息类型、发送人昵称和简洁文本摘要。
- 更新 `channel/wechat_group/wechat_group_channel.py`：在微信群消息进入 CowAgent 回复链路前按配置注入当前群最近上下文，并在发送回复后记录助手出站内容。
- 更新 `channel/wechat_group/wechat_group_message.py`：保留 `message_type`、原始文本和媒体路径字段，供归档与后续多模态阶段复用。
- 新增 `tests/test_wechat_group_context.py`：覆盖按 `room_id` 查询隔离、上下文块格式和通道注入/归档闭环。
- 更新 `plans/20260701_微信群机器人迁移方案.md`：标记 4.2 最小闭环完成并记录当前实现边界。
- 补充 4.2 架构论证：明确专用 SQLite 表是微信群通道短期归档/最近上下文，不等同于 CowAgent 长期记忆；4.3 再通过 `WechatGroupMemoryService` 在 `room_id` / `sender_id` 隔离前提下复用 CowAgent 记忆能力组件。
- 消除微信群 4.2 回归测试中的环境 warning：`ChatChannel` 改用 `thread.daemon = True`，并把 `voice.audio_convert.any_to_wav` 改为语音分支懒加载，避免文本测试导入链路触发 pydub 的 ffmpeg 探测 warning。

验证记录：

- `python -m unittest tests.test_wechat_group_context`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_persona tests.test_wechat_group_context`
- 文档论证变更，已检查 4.2 与 4.3 边界描述一致。
- `python -W error -c "from channel.wechat_group.wechat_group_channel import WechatGroupChannel; print('imported')"`
- `python -W error::DeprecationWarning -m unittest tests.test_wechat_group_context`

## 2026-07-01

### 微信群迁移计划

- 更新 `plans/20260701_微信群机器人迁移方案.md`：在 4.1 微信群通道闭环中补充“人设设定与生效规则”，参考 BaiLongmaPro 的 `personaPrompt` / `personaPresetId` 方案，明确内置预设、自定义人设、保存生效、prompt 注入和管理员优先级边界。
- 同步补充文件级任务、建议配置项、UI 范围、测试覆盖、手动验证和首轮交付边界，确保人设功能进入开发计划但不进入本次实际实现。

验证记录：

- 文档变更，已检查计划中包含人设配置、提示词注入、UI、测试与交付边界。

### 4.1 微信群通道闭环

- 新增 `wechat_group` 渠道常量、工厂注册、默认配置与配置模板，支持通过 `channel_type` 启动个人微信群通道。
- 新增 `channel/wechat_group/` Python 通道层和 Node.js Wechaty sidecar，完成扫码登录、状态/二维码事件、群消息标准化、群列表刷新、文本/图片/文件/音频发送命令。
- 在 Web 控制台与桌面端通道管理中加入“个人微信群”接入入口，支持从“通道管理 -> 接入通道 -> 个人微信群”展示二维码并轮询登录状态。
- 为 `wechat_group` 增加二维码状态接口 `/api/wechat_group/qrlogin`，用于通道管理界面展示二维码和连接状态。
- 修复微信群回复真实 @ 问题：`wechat_group` 回复不再使用公共群聊装饰层拼接普通文本 `@昵称`，改为只把发送者 ID 传给 Wechaty 原生 mention。
- 修复 Wechaty `room.say` 调用参数：使用 `room.say(text, ...mentions)`，避免把 mention 数组作为单个参数导致 sidecar 报错。
- 修复 sidecar 按发送人 ID 解析真实 @ 目标的问题：不再把 `sender_id` 当作 `room.member(name)` 的名称查询，改为通过 `Contact.find({ id })` 获取联系人并用 `room.has(contact)` 确认其仍在当前群内，再传给 `Room.say(text, contact)`。
- 参考 BaiLongMaPro 的微信群 @ 实现后继续修复 sidecar 发送路径：优先从当前 `room.memberAll()` 按真实 `sender_id/contact.id` 精确命中成员，避免群成员不在联系人缓存时解析不到 @ 目标。
- 针对默认 `wechaty-puppet-wechat4u` 链路改为稳定可见 @ 文本兜底：按真实群昵称发送 `@昵称\u2005正文`，并清理模型可能自己拼出的开头 @；保留 `MsgSource/atuserlist` 实验函数测试，但生产默认不依赖该方案。
- 明确边界：Web 微信 / `wechaty-puppet-wechat4u` 不能稳定触发微信系统级「有人@我」提醒，本次保证的是回复发回同一群且文本中可见 @ 到真实发送人的群昵称；非 wechat4u puppet 仍优先尝试 Wechaty Contact mention，失败时降级为可见 @ 文本。
- 补齐 4.1 人设闭环：新增 `channel/wechat_group/wechat_group_persona.py`，直接复用 BaiLongmaPro 的三组初始化人设文本，并在 CowAgent 中映射为 `owner-digital-twin`、`tech-duty`、`social-fun` 三个预设。
- 新增微信群人设配置项 `wechat_group_persona_preset_id`、`wechat_group_persona_prompt`，支持 6000 字符限制、换行归一化、内置预设识别与 `custom` 标记。
- 在微信群文本上下文进入 CowAgent 回复链路前注入独立 `<wechat-group-persona>` 块；已验证管理员的配置/诊断类请求会跳过普通人设注入，避免人设覆盖管理员意图。
- 补齐目标群选择闭环：支持 `wechat_group_room_ids` 精确选择和 `wechat_group_names` 群名兜底过滤，二维码状态接口返回当前群列表，`refresh` 会触发 sidecar 刷新群列表。
- 扩展 `/api/channels` 的 `wechat_group.extra`，向 Web 控制台和桌面端暴露群列表、当前选中群、人设预设与当前生效人设，并支持保存目标群和人设配置。
- 在 Web 控制台与桌面端通道卡片中增加个人微信群最小运维面板：刷新群列表、选择目标群、填写群名兜底、切换预设人设、自定义人设并保存生效。
- 新增 `tests/test_wechat_group_message.py`、`tests/test_wechat_group_channel.py`、`tests/test_wechat_group_web.py`，覆盖消息解析、通道发送、二维码 API 与真实 @ 回归场景。
- 新增 `tests/test_wechat_group_persona.py`，覆盖人设预设、归一化、preset ID 解析、prompt 注入和管理员配置请求跳过人设。
- 新增 `channel/wechat_group/sidecar/wechaty-sidecar-core.mjs` 与 `wechaty-sidecar-core.test.mjs`，覆盖 sidecar 发送命令到 Wechaty Contact mention 的转换逻辑。

验证记录：

- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_persona`
- `node --test .\channel\wechat_group\sidecar\wechaty-sidecar-core.test.mjs`
- `node --check .\channel\web\static\js\console.js`
- `node --check .\channel\wechat_group\sidecar\wechaty-sidecar.mjs`
- `node --check .\channel\wechat_group\sidecar\wechaty-sidecar-core.mjs`
- `desktop` 目录下执行 `npm run build`

### 协作规则

- 新增本文件作为项目变更记录入口。
- 更新 `AGENTS.md`：明确以后每次代码、配置或文档修改都必须同步记录到根目录 `CHANGES.md`。
- 完善 `AGENTS.md` 中个人微信群通道说明，补充 sidecar 职责、通道管理扫码入口、真实 @ 规则、JSON Lines 协议同步要求、运行数据目录约束和最小验证命令。
## 2026-07-04

### 微信群全局画像与群记忆全量重构收尾

- 新增 `channel/wechat_group/wechat_group_profile_store.py`、`channel/wechat_group/wechat_group_profile_service.py`、`channel/wechat_group/wechat_group_knowledge_store.py`、`channel/wechat_group/wechat_group_knowledge_service.py`、`channel/wechat_group/wechat_group_learner.py`、`channel/wechat_group/wechat_group_context_service.py`，完成全局画像、群记忆、learner 与 `<wechat-group-knowledge>` 运行时注入主链路。
- 更新 `channel/wechat_group/wechat_group_archive.py`、`channel/wechat_group/wechat_group_channel.py`、`channel/wechat_group/wechat_group_memory_tools.py`、`bridge/agent_bridge.py`、`channel/web/web_channel.py`、`channel/web/static/js/console.js`、`channel/web/chat.html`，切换到新 Web API、新 UI 和 learner 运行记录模型。
- 更新 `config.py` 与 `config-template.json`：删除旧 `wechat_group_memory_auto_* / candidate / distill` 配置，改用 `wechat_group_knowledge_enabled`、`wechat_group_profile_enabled`、`wechat_group_profile_context_limit`、`wechat_group_group_memory_context_limit`、`wechat_group_learning_*` 新配置键。
- 删除 `channel/wechat_group/wechat_group_memory.py`、`channel/wechat_group/wechat_group_memory_distiller.py`、`tests/test_wechat_group_memory.py`、`tests/test_wechat_group_memory_distiller.py`，并将兼容性 embedding provider 获取改为直接使用 `agent.memory.create_default_embedding_provider`。
- 更新测试：`tests/test_wechat_group_profile_store.py`、`tests/test_wechat_group_profile_service.py`、`tests/test_wechat_group_knowledge_store.py`、`tests/test_wechat_group_knowledge_service.py`、`tests/test_wechat_group_learner.py`、`tests/test_wechat_group_context.py`、`tests/test_wechat_group_channel.py`、`tests/test_wechat_group_memory_tools.py`、`tests/test_wechat_group_agent_bridge_tools.py`、`tests/test_wechat_group_memory_ui.py`、`tests/test_wechat_group_web.py`。
- 追加 Web 群聊页“全局画像”独立浏览入口：从“永久记忆”中拆出单独导航，支持按群过滤、左侧画像列表、右侧详情摘要与手动修正表单。
- 追加 `profiles` 接口的 `room_id` 透传与服务层聚合：`WechatGroupProfileService.list_profiles()` 现可按群过滤，并返回 `room_summaries`、`last_seen_at` 供前端展示画像出现范围。
- 收口“永久记忆”页：移除右侧重复的群友画像编辑区，只保留群记忆、注入预览与 learner 运行；改为提示用户跳转到“全局画像”页面管理画像。

验证记录：

- `python -m unittest tests.test_wechat_group_profile_store tests.test_wechat_group_profile_service tests.test_wechat_group_knowledge_store tests.test_wechat_group_knowledge_service tests.test_wechat_group_learner -v`
- `python -m unittest tests.test_wechat_group_context tests.test_wechat_group_channel tests.test_wechat_group_memory_tools tests.test_wechat_group_agent_bridge_tools -v`
- `python -m unittest tests.test_wechat_group_memory_ui tests.test_wechat_group_web tests.test_wechat_group_message -v`
- `python -m unittest tests.test_wechat_group_profile_service tests.test_wechat_group_web tests.test_wechat_group_memory_ui -v`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web tests.test_wechat_group_memory_ui -v`
- `node --check channel/web/static/js/console.js`

未完成：

- 未执行真实微信扫码、入群、真实 @ mention 与跨群隔离的手动链路验证。
