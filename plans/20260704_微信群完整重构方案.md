# 微信群群友画像与群记忆全量重构开发计划（2026-07-04）

## 1. 已确认的业务决策

本次改造按以下前提执行：

1. 群友画像不再做群隔离，同一个微信号（`sender_id`）只有一份全局画像。
2. 成员画像不需要候选审核，不保留“pending / approve / reject”的人工勾选流程。
3. 旧的按 `room_id + sender_id` 存储的成员画像、候选和 revision 数据全部废弃，不做迁移。
4. 参考 `MumuBot` 的架构思想进行全量重构；若影响群记忆，群记忆也同步全量重构。

## 2. 参考项目复盘结论

本次设计主要参考 `MumuBot` 的以下实现与边界：

- `internal/learning/learner.go`
  - 学习链路独立于长期记忆链路。
  - learner 只消费“已被上游处理完成的消息前缀”。
  - 成员画像按用户聚合证据，证据足够时直接调用 `updateMemberProfile` 更新。
- `internal/learning/AGENTS.md`
  - 学习系统负责黑话、风格卡片、成员画像，不直接承担长期记忆写入。
- `internal/memory/AGENTS.md`
  - 长期记忆、消息日志、成员画像、风格卡片等由独立的数据层统一持久化。
  - 成员画像保持全局 `user_id` 维度，不按群隔离。
- `internal/memory/models.go`
  - 成员画像模型是轻量字段：`nickname / name_records / speak_style / interests / common_words / activity / intimacy / msg_count`。
- `internal/tools/member.go`
  - 成员画像学习工具直接覆盖 `speak_style / interests / common_words`，别名只追加。

结合本项目需求后，结论如下：

- 要借鉴 `MumuBot` 的“学习链路和长期记忆链路分离”“全局成员画像”“按成员聚合证据样本”“轻量画像字段”。
- 不直接照搬其 QQ / MySQL / Milvus 形态；本项目继续使用当前 Python + SQLite 的本地落地方式。
- 群记忆保留“群维度隔离”，但从当前 `scoped memory chunk` 体系中拆出，进入独立的微信群知识存储层。

## 3. 目标架构

### 3.1 总体结构

本次重构后，微信群知识体系拆成 3 条独立链路：

1. **消息归档链路**
   - 继续负责原始消息、回复、媒体、证据消息查询。
   - 作为学习与群记忆蒸馏的唯一事实来源。

2. **学习链路**
   - 面向群文化学习与全局成员画像学习。
   - 输入是“可学习消息批次”。
   - 输出是：
     - 全局成员画像
     - 群黑话 / 群风格卡片（本期可先只重构画像和群记忆，为黑话/风格预留接口）

3. **长期知识链路**
   - 面向“群记忆”的提取、存储、检索与注入。
   - 群记忆仍按 `room_id` 隔离。
   - 成员画像不再属于长期群记忆的一部分，而是运行时单独注入。

### 3.2 运行时注入结构

当前 LLM user message 的微信群增强上下文改为：

```text
<wechat-group-persona>
...
</wechat-group-persona>

<recent-wechat-group-transcript>
...
</recent-wechat-group-transcript>

<wechat-group-knowledge>
[group_memory]
当前 room_id 的群长期记忆

[speaker_profile sender_id="..."]
当前发言人的全局成员画像

[mentioned_profile sender_id="..."]
本轮明确 @ 或文本命中的成员全局画像
</wechat-group-knowledge>
```

其中：

- `group_memory` 继续按 `room_id` 过滤。
- `speaker_profile` / `mentioned_profile` 改为全局 `sender_id` 画像，不再受 `room_id` 限制。
- 群内差异信息只保留在 `name_records` 之类的附属字段，不再生成独立群画像。

## 4. 数据模型重构

## 4.1 新的成员画像模型

新增全局成员画像模型，唯一键为 `sender_id`：

- `sender_id`
- `primary_nickname`
- `name_records_json`
- `speak_style`
- `interests_json`
- `common_words_json`
- `activity_score`
- `intimacy_score`
- `msg_count`
- `last_seen_at`
- `updated_at`

说明：

- `name_records_json` 参考 `MumuBot` 的 `MemberNameRecord` 设计，保留：
  - 群名片 / 群昵称来源
  - 学到的稳定别称
  - 来源群 `room_id`
  - 更新时间
- `speak_style / interests / common_words` 是全局字段，允许被新证据覆盖。
- 本期不保留“member profile revision 审核历史”。

## 4.2 新的群记忆模型

群记忆不再依赖当前 `agent.memory` scoped chunk 存储，改为独立表：

- `memory_id`
- `room_id`
- `content`
- `status`（建议保留 `active / archived`，不做成员画像式审核）
- `evidence_message_ids_json`
- `evidence_text`
- `source_kind`
- `created_at`
- `updated_at`

说明：

- 群记忆继续按群隔离。
- 与成员画像彻底分层。
- 若后续需要候选层，可单独对群记忆保留 candidate，但不与成员画像共用旧表。

## 4.3 学习状态模型

新增或重建学习水位：

- `room_id`
- `last_archived_message_id`
- `updated_at`

目标：

- 学习链路只消费连续、可确认已归档的消息前缀。
- 不重复学习同一批消息。
- 不因为一次学习失败错误推进水位。

## 5. 代码重构范围

### 5.1 拆除/废弃的旧设计

以下旧设计将被废弃或降级兼容：

- `WechatGroupMemoryService` 中按 `room_id + sender_id` 的成员画像存储
- `WechatGroupMemoryDistiller` 中成员画像 `candidate / approve / reject` 审核流程
- Web 端“当前群成员画像候选审核”逻辑
- 旧的成员画像 `revision` 表与展示入口
- 旧的“成员画像属于 scoped memory chunk”的实现方式

### 5.2 新增模块建议

建议新增以下模块：

- `channel/wechat_group/wechat_group_profile_store.py`
  - 全局成员画像表、名字记录表、学习水位表
- `channel/wechat_group/wechat_group_profile_service.py`
  - 全局成员画像 CRUD、搜索、别名/Nickname 命中
- `channel/wechat_group/wechat_group_group_memory_store.py`
  - 群记忆表与检索接口
- `channel/wechat_group/wechat_group_learner.py`
  - 学习批次消费、成员聚合、画像蒸馏执行
- `channel/wechat_group/wechat_group_context_service.py`
  - 统一组装 `<wechat-group-knowledge>` 注入块

### 5.3 修改模块建议

- `channel/wechat_group/wechat_group_archive.py`
  - 补充学习水位读取能力，必要时扩展可学习消息读取接口
- `channel/wechat_group/wechat_group_channel.py`
  - 改为使用新 `context_service`
  - 移除对旧成员画像 scoped memory 的依赖
- `channel/web/web_channel.py`
  - 改造成员画像 API：
    - 从“按群管理”改为“按全局成员管理”
    - 保留群记忆单独入口
- `channel/web/static/js/console.js`
  - 群友画像页面改为全局成员画像视图
  - 群页面只保留“从当前群归档学习画像”的触发和预览
- `config.py`
  - 清理旧的成员画像候选审核相关配置
  - 新增学习批次、样本条数、最小证据等配置
- `config-template.json`
  - 同步新配置

## 6. 行为设计

### 6.1 成员画像学习流程

参考 `MumuBot`，新成员画像学习流程如下：

1. 从归档中按 `room_id` 读取“未学习的新消息批次”。
2. 过滤空消息、异常消息、媒体消息。
3. 按 `sender_id` 聚合发言：
   - 统计消息数
   - 截取最多 `N` 条样本
4. 只对满足最小样本数的成员做蒸馏。
5. LLM 仅允许输出结构化成员画像更新：
   - `speak_style`
   - `interests`
   - `common_words`
   - `aliases`
6. 服务层直接更新全局成员画像：
   - `speak_style` 覆盖
   - `interests` 覆盖
   - `common_words` 覆盖
   - `aliases` 追加去重
7. 更新成员活跃度、最后发言时间、消息计数与学习水位。

### 6.2 群记忆蒸馏流程

群记忆重构后建议保持独立：

1. 从归档中按 `room_id` 取最近窗口消息。
2. LLM 只抽取“当前群长期稳定记忆”。
3. 输出结构化群记忆条目。
4. 写入群记忆表。
5. 运行时通过关键字/简单语义检索装配当前群记忆。

说明：

- 成员画像和群记忆分开跑。
- 成员画像学习不再共享群记忆 candidate 表。
- 群记忆是否保留审核开关可单独决定，但本期不再沿用旧的成员候选审核模型。

### 6.3 运行时检索规则

成员画像检索优先级：

1. 明确 `sender_id`
2. `at_list` 中的明确成员 ID
3. 名字记录中的稳定别称 / 群名片
4. 最后才做文本兜底匹配

群记忆检索优先级：

1. 当前 `room_id` 的显式查询命中
2. 最近活跃群记忆

## 7. 与当前实现的兼容策略

### 7.1 数据兼容

- 旧成员画像数据、候选、修订历史直接废弃。
- 新代码默认不再读取旧 scoped member profile 数据。
- 若旧表仍保留，仅视为历史垃圾数据，不参与新链路。

### 7.2 API 兼容

需要区分“可平滑兼容”和“必须改前端”：

- 后端内部服务接口：允许重命名和重构
- Web API：尽量保持基础路径稳定，但返回结构要切换到新模型
- 前端页面：允许重构布局和交互，因为画像维度从“当前群”改成了“全局成员”

## 8. 测试与验证计划

### 8.1 单元测试

重点新增或重写：

- `tests/test_wechat_group_profile_store.py`
- `tests/test_wechat_group_profile_service.py`
- `tests/test_wechat_group_learner.py`
- `tests/test_wechat_group_context.py`

保留并改写：

- `tests/test_wechat_group_memory.py`
- `tests/test_wechat_group_memory_distiller.py`
- `tests/test_wechat_group_web.py`

### 8.2 关键验证项

1. 同一个 `sender_id` 在多个群出现时，只维护一份画像。
2. 不同群里的群名片/别称记录能作为附属数据保留。
3. 成员画像不再进入审核候选。
4. 群记忆仍然按 `room_id` 强隔离。
5. 运行时注入可以同时拿到：
   - 当前群记忆
   - 当前发言人的全局画像
   - 被提及成员的全局画像
6. 学习水位不会跳过失败批次。

### 8.3 最小验证命令

```powershell
python -m unittest tests.test_wechat_group_profile_store
python -m unittest tests.test_wechat_group_profile_service
python -m unittest tests.test_wechat_group_learner
python -m unittest tests.test_wechat_group_context
python -m unittest tests.test_wechat_group_channel tests.test_wechat_group_web
```

若改动 Web 控制台入口：

```powershell
python -m unittest tests.test_wechat_group_memory_ui tests.test_wechat_group_web
```

## 9. 开发实施顺序

### 阶段 1：建新模型，切断旧成员画像依赖

- 建立全局成员画像存储与服务
- 新增学习水位
- 停止旧成员画像 scoped memory 写入

### 阶段 2：重写 learner 和运行时注入

- 新成员画像蒸馏器
- 新 context assembler
- `WechatGroupChannel` 切换到新注入链路

### 阶段 3：重写群记忆存储与检索

- 群记忆从 scoped memory chunk 中拆出
- 建立独立群记忆存储
- 统一放入 `<wechat-group-knowledge>`

### 阶段 4：重构 Web 管理入口

- 全局成员画像管理页
- 群记忆单独管理页
- 移除旧画像候选审核入口

### 阶段 5：清理旧实现与补全回归测试

- 清理废弃配置与接口
- 删除或降级旧成员画像相关测试
- 更新计划文档、CHANGES.md 与必要文档

## 10. 风险与控制

### 10.1 主要风险

- 全局画像可能丢失群内差异表达
- 旧接口重构会影响 Web 控制台
- 群记忆从 scoped memory 脱离后，检索质量可能阶段性下降

### 10.2 控制手段

- 用 `name_records` 保留群内命名差异
- 成员画像字段保持轻量，避免过度人格化
- 群记忆和成员画像分阶段切换，优先保证运行时注入可用
- 每个阶段都以测试回归为关口，不一次性大爆炸切换

## 11. 推荐执行结论

推荐按“全量重构，但分阶段落地”的方式执行：

- **成员画像**：完全按 `MumuBot` 的全局画像思路重做
- **群记忆**：同步从当前 scoped memory 实现中拆出，独立为长期群知识存储
- **运行时上下文**：统一由新的知识装配服务生成
- **旧画像数据**：全部废弃，不迁移

这条路线改动大，但结构会明显比当前实现更清晰，也更符合你已经确认的业务目标。
## 进度回写（2026-07-04）

- 已按本方案完成“全局画像 + 按群隔离群记忆 + learner 直接学习写入 + `<wechat-group-knowledge>` 运行时注入”的主链路切换。
- Web API、Web 控制台和配置项已同步切换到新模型；旧 `candidate / approve / reject / revision / distill` 入口已移除。
- 旧 scoped memory 实现与旧 distiller 实现已从代码主链路和测试集合中删除。
- 当前剩余工作只包括真实微信环境手动验收，以及按团队流程执行最终 Git 提交。
