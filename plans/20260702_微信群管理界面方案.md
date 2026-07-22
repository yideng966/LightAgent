# 群聊管理页 UI 开发计划

## 背景

当前 Web 控制台“个人微信群”通道卡片中混合了承接入、群选择、人设和最近上下文配置。用户希望在左侧管理目录新增“群聊”子菜单，并把群聊相关设置迁移到独立页面中。

## 目标

- 左侧管理目录新增“群聊”入口。
- 新增 Web 端群聊管理页，页面宽度参考知识库页，整体不出现页面级滚动条。
- 群聊管理页采用双栏紧凑布局：
  - 左侧为子菜单。
  - 右侧显示当前子菜单对应设置详情。
- 左侧子菜单固定为：
  - 基础设置
  - 群聊开关
  - 人设设定
- “基础设置”显示 4.2 最近上下文三个配置：
  - `wechat_group_recent_context_enabled`
  - `wechat_group_recent_context_limit`
  - `wechat_group_recent_context_minutes`
- “群聊开关”显示目标群选择，不展示 room ID，只展示群名，支持下拉列表与检索。
- “人设设定”只保留自定义人设，不再显示三个预设。
- “个人微信群”通道卡片只保留接入、扫码、连接和断开能力。

## 实施范围

### 后端

- 修改 `channel/web/web_channel.py`：
  - 在 `wechat_group.extra` 中返回最近上下文配置。
  - 允许 `/api/channels` 的 `save/wechat_group` 保存最近上下文三个配置。
  - 对数字配置做整数归一化，避免字符串直接写入配置。

### Web 前端

- 修改 `channel/web/chat.html`：
  - 管理目录中新增“群聊”入口。
  - 新增 `view-groups` 页面容器，采用固定高度双栏布局。
  - 为 `console.js` 引用增加版本参数，降低浏览器缓存旧脚本的概率。
- 修改 `channel/web/static/js/console.js`：
  - 新增 `groups` 视图注册、加载、渲染和保存逻辑。
  - 支持刷新群列表。
  - 群列表以下拉弹层展示，弹层内部可滚动；页面主体不滚动。
  - 只展示群名，不在 UI 中展示 room ID。
  - 人设设定只保留自定义文本框。
  - 个人微信群通道卡片不再展示群聊细项设置。

### 测试与验证

- 修改 `tests/test_wechat_group_web.py`：
  - 覆盖 `wechat_group.extra.recent_context` 返回。
  - 覆盖保存最近上下文三个配置。
- 运行：
  - `python -m unittest tests.test_wechat_group_web`
  - `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
  - `node --check .\channel\web\static\js\console.js`

## UI 结构

页面使用固定高度双栏：

- 外层：`flex-1 flex flex-col min-h-0 overflow-hidden`
- 内容区：`flex-1 min-h-0 border-t border-default`
- 内层宽度：参考知识库页，使用全宽双栏而不是窄表单卡片。
- 左栏：固定宽度约 `w-60`，显示三个子菜单和简短状态。
- 右栏：`flex-1 min-w-0`，显示当前表单区域。

右侧表单按子菜单拆分：

- 基础设置：
  - 最近上下文开关。
  - 上下文消息条数。
  - 上下文时间窗口。
- 群聊开关：
  - 刷新群列表。
  - 可检索多选下拉。
  - 已选择群以紧凑标签显示。
  - 群名兜底输入保留为高级兜底能力。
- 人设设定：
  - 自定义人设文本框。
  - 字数计数和边界提示。

## 风险与边界

- 不改微信群消息处理链路。
- 不新增后端 API，避免扩大接口面。
- 不移除 Web 控制台现有能力。
- 不删除后端人设预设能力，只在 Web 端新群聊页不展示预设。
- 页面级不滚动；若小窗口高度不足，优先压缩表单密度，群列表只在下拉弹层内部滚动。
