/* =====================================================================
   LightAgent Console - Main Application Script
   ===================================================================== */

// =====================================================================
// Version — fetched from backend (single source: /VERSION file)
// =====================================================================
let APP_VERSION = '';

// =====================================================================
// i18n
// =====================================================================
const I18N = {
    zh: {
        console: '控制台',
        nav_chat: '对话', nav_manage: '管理', nav_monitor: '监控',
        menu_chat: '对话', menu_config: '配置', menu_models: '模型', menu_skills: '技能',
        menu_memory: '记忆', menu_knowledge: '知识', menu_channels: '通道', menu_groups: '群聊', menu_tasks: '定时',
        menu_logs: '日志',
        models_title: '模型管理',
        models_desc: '统一管理对话、图像、语音、向量、搜索能力',
        models_section_vendors: '厂商凭据',
        models_section_vendors_desc: '一处配置，多个模型能力共享',
        models_section_capabilities: '模型能力',
        models_add_vendor: '添加厂商',
        models_provider: '厂商',
        models_model: '模型',
        models_voice: '音色',
        models_configured: '已配置',
        models_not_configured: '未配置',
        models_pick_to_configure: '选择以配置',
        models_clear_credential: '清除凭据',
        models_base_default_hint: '留空将使用官方默认地址',
        models_base_default: '默认',
        models_custom_vendor_label: '自定义',
        models_custom_name: '名称',
        models_custom_delete: '删除',
        models_custom_delete_confirm_title: '删除自定义厂商',
        models_custom_delete_confirm_msg: '确定删除该自定义厂商吗？此操作无法撤销。',
        models_custom_name_required: '请填写名称',
        models_custom_base_required: '请填写 API Base',
        models_custom_edit_title: '编辑自定义厂商',
        models_custom_add_title: '添加自定义厂商',
        models_capability_chat: '主模型',
        models_capability_chat_desc: '用于基础对话和 Agent 推理',
        models_chat_fallbacks: '备用模型',
        models_chat_fallbacks_desc: '主模型临时不可用时按顺序尝试',
        models_chat_fallback_add: '添加备用',
        models_chat_fallback_infer_provider: '按模型名推断',
        models_chat_fallback_remove: '移除备用模型',
        models_chat_failover_title: '自动切换规则',
        models_chat_failover_scope: '配置备用模型后自动生效，不会改写主模型配置。',
        models_chat_failover_immediate: '当前请求：主模型遇到临时故障时，立即按顺序尝试备用模型。',
        models_chat_failover_circuit: '连续故障：主模型连续出现{threshold}次临时故障后熔断，后续请求在{cooldown}内跳过主模型。',
        models_chat_failover_recovery: '自动恢复：冷却结束后仅放行一个请求试探主模型；成功恢复，失败则重新熔断。',
        models_chat_failover_minutes: '{value}分钟',
        models_chat_failover_seconds: '{value}秒',
        models_capability_vision: '图像理解',
        models_capability_vision_desc: '识别图片内容，用于图像识别工具',
        models_capability_image: '图像生成',
        models_capability_image_desc: '生成图片，用于图像生成技能',
        models_auto_using: '当前优先使用',
        models_capability_asr: '语音识别',
        models_capability_asr_desc: '语音转文字',
        models_capability_tts: '语音合成',
        models_capability_tts_desc: '文字转语音',
        models_invalid_voice_provider: '检测到无效的语音 Provider，请重新选择：',
        models_legacy_voice_provider: '当前语音 Provider 仅支持配置文件直配，请重新选择 Web 支持的 Provider：',
        models_voice_provider_required: '请先选择 Web 支持的语音 Provider',
        models_capability_embedding: '向量',
        models_capability_embedding_desc: '用于记忆与知识的向量化检索',
        models_capability_search: '联网搜索',
        models_capability_search_desc: '实时网页检索能力，用于搜索工具',
        models_strategy_auto: '自动',
        models_search_strategy_label: '策略',
        models_search_strategy_fixed: '指定',
        models_search_strategy_auto_hint: '从已配置厂商中自动选择',
        models_search_strategy_fixed_hint: '指定使用搜索厂商',
        models_pending_config: '待配置',
        models_search_available_label: '可用搜索厂商：',
        models_search_none_configured: '暂未启用任何搜索厂商，点击添加',
        models_search_add_provider: '添加厂商',
        models_search_add_desc: '选择一个搜索厂商进行配置',
        models_search_bocha_title: '配置博查 API Key',
        models_search_bocha_desc: '前往博查开放平台创建 API Key',
        models_search_serper_title: '配置 Serper API Key',
        models_search_serper_desc: '前往 Serper 控制台创建 API Key',
        models_search_jina_title: '配置 Jina API Key',
        models_search_jina_desc: '前往 Jina 控制台创建 API Key',
        models_search_apply_link: '申请 API Key',
        models_search_edit_hint: '点击修改配置',
        models_unavailable: '不可用',
        models_set_via_env: '通过环境变量启用',
        models_dim_label: '维度',
        models_save_success: '已保存',
        models_save_failed: '保存失败',
        models_cleared: '已清除',
        models_clear_failed: '清除失败',
        models_embedding_change_title: '更改向量模型',
        models_embedding_change_msg: '切换向量模型后，已有索引将失效，需要重建。是否继续？',
        models_embedding_saved_title: '向量模型已更新',
        models_embedding_saved_msg: '请在聊天框输入 /memory rebuild-index 重建索引。',
        models_embedding_saved_ok: '去执行',
        models_pick_provider: '待选择',
        models_clear_confirm_title: '清除厂商凭据',
        models_clear_confirm_msg: '确认清除该厂商的 API Key 与 Base URL 吗？相关能力将不再可用。',
        cancel: '取消',
        save: '保存',
        ok: '确定',
        knowledge_title: '知识库', knowledge_desc: '浏览和探索你的知识库',
        knowledge_tab_docs: '文档', knowledge_tab_graph: '图谱',
        knowledge_loading: '加载知识库中...', knowledge_loading_desc: '知识页面将显示在这里',
        knowledge_select_hint: '选择一个文档查看', knowledge_empty_hint: '暂无知识页面',
        knowledge_empty_guide: '在对话中发送文档、链接或主题给 Agent，它会自动整理到你的知识库中。',
        knowledge_go_chat: '开始对话',
        knowledge_new: '新建',
        knowledge_new_category: '新建分类',
        knowledge_new_document: '新建文档',
        knowledge_import_documents: '导入文档',
        welcome_subtitle: '我可以帮你解答问题、管理计算机、创造和执行技能，并通过<br>长期记忆和知识库不断成长',
        example_sys_title: '系统管理', example_sys_text: '查看工作空间里有哪些文件',
        example_task_title: '定时任务', example_task_text: '1分钟后提醒我检查服务器',
        example_code_title: '编程助手', example_code_text: '搜索AI资讯并生成可视化网页报告',
        example_knowledge_title: '知识库', example_knowledge_text: '查看知识库当前文档情况',
        example_skill_title: '技能系统', example_skill_text: '查看所有支持的工具和技能',
        example_web_title: '指令中心', example_web_text: '查看全部命令',
        slash_help: '显示命令帮助',
        slash_status: '查看运行状态',
        slash_context: '查看对话上下文',
        slash_context_clear: '清除对话上下文',
        slash_skill_list: '查看已安装技能',
        slash_skill_list_remote: '浏览技能广场',
        slash_skill_search: '搜索技能',
        slash_skill_install: '安装技能 (名称或 GitHub URL)',
        slash_skill_uninstall: '卸载技能',
        slash_skill_info: '查看技能详情',
        slash_skill_enable: '启用技能',
        slash_skill_disable: '禁用技能',
        slash_memory_dream: '手动触发记忆蒸馏 (可指定天数, 默认3)',
        slash_knowledge: '查看知识库统计',
        slash_knowledge_list: '查看知识库文件树',
        slash_knowledge_on: '开启知识库',
        slash_knowledge_off: '关闭知识库',
        slash_config: '查看当前配置',
        slash_cancel: '中止当前正在运行的 Agent 任务',
        slash_logs: '查看最近日志',
        slash_version: '查看版本',
        input_placeholder: '输入消息，或输入 / 使用指令',
        config_title: '配置管理', config_desc: '管理模型和 Agent 配置',
        config_model: '模型配置', config_agent: 'Agent 配置',
        config_language: '语言', config_language_hint: '界面展示、命令文案、系统提示词等使用的语言（与右上角切换同步）',
        config_model_advanced: '高级配置',
        config_channel: '通道配置',
        config_agent_enabled: 'Agent 模式',
        config_max_tokens: '最大上下文 Token', config_max_tokens_hint: '对话中 Agent 能输入的最大 Token 长度，超过后会智能压缩处理',
        config_max_turns: '最大记忆轮次', config_max_turns_hint: '一问一答为一轮，超过后会智能压缩处理',
        config_max_steps: '最大执行步数', config_max_steps_hint: '单次对话中 Agent 最多调用工具的次数',
        config_enable_thinking: '深度思考', config_enable_thinking_hint: '是否启用深度思考模式',
        config_self_evolution: '自主进化', config_self_evolution_hint: '会话空闲后自动复盘，沉淀记忆、优化技能、处理未完成事项',
        evolution_badge: '自主学习',
        config_channel_type: '通道类型',
        config_provider: '模型厂商', config_model_name: '模型',
        config_custom_model_hint: '输入自定义模型名称',
        config_save: '保存', config_saved: '已保存',
        config_save_error: '保存失败',
        config_custom_option: '自定义',
        config_custom_tip: '接口需遵循 OpenAI API 协议',
        config_security: '安全设置', config_password: '访问密码',
        config_password_hint: '留空则不启用密码保护',
        config_password_changed: '密码已更新，请重新登录',
        config_password_cleared: '密码已清除',
        skills_title: '技能管理', skills_desc: '查看、启用或禁用 Agent 工具和技能', skills_hub_btn: '探索技能广场',
        skills_loading: '加载技能中...', skills_loading_desc: '技能加载后将显示在此处',
        tools_section_title: '内置工具', tools_loading: '加载工具中...',
        skills_section_title: '技能', skill_enable: '启用', skill_disable: '禁用',
        skill_toggle_error: '操作失败，请稍后再试',
        memory_title: '记忆管理', memory_desc: '查看 Agent 记忆文件和内容',
        memory_tab_files: '记忆文件', memory_tab_dreams: '自主进化',
        memory_loading: '加载记忆文件中...', memory_loading_desc: '记忆文件将显示在此处',
        memory_back: '返回列表',
        memory_col_name: '文件名', memory_col_type: '类型', memory_col_size: '大小', memory_col_updated: '更新时间',
        channels_title: '通道管理', channels_desc: '管理已接入的消息通道',
        channels_add: '接入通道', channels_disconnect: '断开',
        channels_save: '保存配置', channels_saved: '已保存', channels_save_error: '保存失败',
        channels_restarted: '已保存并重启',
        channels_connect_btn: '接入', channels_cancel: '取消',
        channels_select_placeholder: '选择要接入的通道...',
        channels_empty: '暂未接入任何通道', channels_empty_desc: '点击右上角「接入通道」按钮开始配置',
        channels_disconnect_confirm: '确认断开该通道？配置将保留但通道会停止运行。',
        channels_connected: '已接入', channels_connecting: '接入中...',
        weixin_scan_title: '微信扫码登录', weixin_scan_desc: '请使用微信扫描下方二维码',
        weixin_scan_loading: '正在获取二维码...', weixin_scan_waiting: '等待扫码...',
        weixin_scan_scanned: '已扫码，请在手机上确认', weixin_scan_expired: '二维码已过期，正在刷新...',
        weixin_scan_success: '登录成功，正在启动通道...', weixin_scan_fail: '获取二维码失败',
        weixin_qr_tip: '二维码约2分钟后过期',
        wechat_group_scan_title: '个人微信群扫码登录', wechat_group_scan_desc: '请使用微信扫描下方二维码登录微信群通道',
        wechat_group_scan_loading: '正在启动微信群通道...', wechat_group_scan_success: '微信群通道已连接',
        wechat_group_scan_fail: '启动微信群通道失败', wechat_group_qr_tip: '扫码后将在群聊中响应 @ 消息',
        wechat_group_rooms_title: '目标群',
        wechat_group_rooms_hint: '按稳定群 ID 精确限制；群名用于重登后自动恢复。',
        wechat_group_rooms_refresh: '刷新群列表',
        wechat_group_rooms_empty: '登录后刷新群列表。',
        wechat_group_room_names_label: '群名候选发现',
        wechat_group_room_names_placeholder: '每行一个群名',
        wechat_group_rooms_refreshed: '群列表已刷新',
        wechat_group_rooms_refresh_failed: '刷新群列表失败',
        wechat_group_persona_title: '人设设定',
        wechat_group_persona_hint: '点击预设只填入文本，保存后才生效。',
        wechat_group_persona_active: '当前生效',
        wechat_group_persona_custom: '自定义',
        wechat_group_persona_dirty: '有未保存修改',
        wechat_group_persona_clean: '已生效',
        wechat_group_persona_prompt_label: '人设提示词',
        wechat_group_persona_prompt_placeholder: '输入微信群回复的身份、语气、风格和边界',
        wechat_group_persona_boundary: '人设不能绕过安全守卫、群限制和管理员权限。',
        wechat_group_settings_save: '保存并生效',
        wechat_group_settings_saved: '已保存并生效',
        groups_title: '群聊',
        groups_desc: '管理微信群目标群、拟人化上下文和人设',
        groups_loading: '加载群聊设置中...',
        groups_load_failed: '加载群聊设置失败',
        groups_nav_basic: '基础设置',
        groups_nav_basic_hint: '基础运行设置',
        groups_nav_identity: '身份恢复',
        groups_nav_identity_hint: '绑定确认',
        groups_nav_humanization: '拟人化',
        groups_nav_humanization_hint: '上下文与语气',
        groups_nav_rooms: '群与管理员',
        groups_nav_rooms_hint: '目标群与管理员',
        groups_nav_free_reply: '自由回复',
        groups_nav_free_reply_hint: '普通群聊接话',
        groups_nav_voice_interaction: '语音交互',
        groups_nav_voice_interaction_hint: '语音消息触发策略',
        groups_nav_focus: '焦点栈',
        groups_nav_focus_hint: '活动焦点与归档',
        groups_nav_style: '风格卡片',
        groups_nav_style_hint: '候选、审核与启用',
        groups_nav_emotion: '情绪与主动性',
        groups_nav_emotion_hint: '情绪状态与节奏',
        groups_nav_sticker: '表情包',
        groups_nav_sticker_hint: '资产与停用管理',
        groups_nav_persona: '人设设定',
        groups_nav_persona_hint: '自定义回复风格',
        groups_nav_memory: '永久记忆',
        groups_nav_memory_hint: '群记忆与画像',
        groups_nav_profiles: '群友画像',
        groups_nav_profiles_hint: '按群浏览与修正画像',
        groups_nav_image: '图片与生图',
        groups_nav_image_hint: '图片理解和额度',
        groups_identity_title: '身份恢复',
        groups_identity_desc: '确认重登后的群和成员绑定，未确认项不会自动继承敏感权限。',
        groups_identity_pending_rooms: '待确认群绑定',
        groups_identity_pending_account: '待确认登录账号',
        groups_identity_confirm_account_first: '请先确认登录账号绑定。',
        groups_identity_member_pending: '成员身份待确认',
        groups_identity_candidates: '候选绑定',
        groups_identity_no_pending: '暂无待确认群绑定。',
        groups_identity_no_candidates: '暂无候选绑定。',
        groups_identity_refresh: '刷新候选',
        groups_identity_confirm: '确认绑定',
        groups_identity_confirmed: '身份绑定已确认',
        groups_basic_title: '基础设置',
        groups_basic_desc: '控制当前群基础运行设置。',
        groups_voice_interaction_title: '语音交互',
        groups_voice_interaction_desc: '设置群语音识别成功后的回复触发方式。',
        groups_voice_interaction_force_reply: '强制回复',
        groups_voice_interaction_force_reply_hint: '语音识别成功后直接进入回复链路。',
        groups_voice_interaction_free_reply: '依赖自由回复规则',
        groups_voice_interaction_free_reply_hint: '转写文本通过自由回复规则和判定后才回复。',
        groups_humanization_title: '拟人化上下文',
        groups_humanization_desc: '控制群聊回复策略、证据检索、摘要、链接策略和发送前清洗。',
        groups_humanization_enabled: '启用拟人化上下文',
        groups_humanization_enabled_hint: '按触发来源和意图组织当前轮微信群上下文。',
        groups_humanization_persist_raw_user_only: '历史只保存用户原文',
        groups_humanization_persist_raw_user_only_hint: '增强提示词只进入当前轮请求，不写入后续对话历史。',
        groups_humanization_reply_policy_enabled: '启用回复策略',
        groups_humanization_reply_policy_enabled_hint: '区分直接 @、引用、自由回复和图片消息。',
        groups_humanization_recent_enabled: '启用最近上下文',
        groups_humanization_recent_enabled_hint: '仅在上下文依赖、自由回复、引用和多模态等场景按需注入 recent transcript。',
        groups_humanization_recent_limit: '最近上下文条数',
        groups_humanization_recent_minutes: '最近上下文分钟窗口',
        groups_humanization_archive_evidence_enabled: '启用归档证据',
        groups_humanization_archive_evidence_limit: '归档证据条数',
        groups_humanization_archive_evidence_days: '归档检索天数',
        groups_humanization_archive_evidence_recent_limit: '近聊兜底条数',
        groups_humanization_local_summary_enabled: '启用本地摘要',
        groups_humanization_local_summary_limit: '摘要候选条数',
        groups_humanization_local_summary_hours: '摘要小时窗口',
        groups_humanization_reference_policy_enabled: '启用引用/图片策略',
        groups_humanization_link_policy_enabled: '启用链接策略',
        groups_humanization_response_cleanup_enabled: '启用发送前清洗',
        groups_humanization_response_cleanup_max_chars: '清洗后最大字符数',
        groups_recent_enabled: '启用最近上下文',
        groups_recent_enabled_hint: '回复前注入当前群最近聊天流水。',
        groups_recent_limit: '消息条数',
        groups_recent_limit_hint: '最多读取多少条最近消息。',
        groups_recent_minutes: '时间窗口（分钟）',
        groups_recent_minutes_hint: '只读取该时间范围内的消息。',
        groups_alias_sync_cooldown_minutes: '群昵称补同步冷却时间（分钟）',
        groups_alias_sync_cooldown_minutes_hint: '群昵称缺失时，当前群最多多久补同步一次成员信息。',
        groups_basic_proxy: '代理地址',
        groups_basic_proxy_hint: '供需要代理的能力复用，例如 http://127.0.0.1:7890；留空则直连。',
        groups_github_notify_title: 'GitHub 提交通知',
        groups_github_notify_desc: '接收指定仓库的 push Webhook，并将 commit 聚合发送到一个已选择的微信群。',
        groups_github_notify_enabled: '启用提交通知',
        groups_github_notify_enabled_hint: '仅处理验签通过且命中仓库、分支和目标群的 push 事件。',
        groups_github_repository: '仓库全名',
        groups_github_repository_hint: '填写 owner/repository，例如 yideng966/LightAgent。',
        groups_github_branches: '通知分支',
        groups_github_branches_hint: '使用逗号或换行分隔；留空表示允许所有分支。',
        groups_github_target_room: '目标群',
        groups_github_target_room_hint: '只显示已在“群与管理员”中选择的稳定群。',
        groups_github_target_room_placeholder: '选择接收通知的群',
        groups_github_target_room_empty: '请先在“群与管理员”中选择目标群',
        groups_github_target_room_saved: '已保存',
        groups_github_max_commits: '单条最大 commit 数',
        groups_github_max_commits_hint: '一次 push 最多展开 1-20 条 commit。',
        groups_github_retry_hours: '最长重试时间（小时）',
        groups_github_retry_hours_hint: '群离线或身份未恢复时持续重试，范围 1-720 小时。',
        groups_github_retention_days: '去重保留天数',
        groups_github_retention_days_hint: '相同 GitHub delivery 的去重记录保留 1-365 天。',
        groups_github_webhook_url: 'Webhook 地址',
        groups_github_webhook_url_hint: '在 GitHub Webhook 的 Payload URL 中填写此 HTTPS 地址。',
        groups_github_secret: 'Webhook Secret',
        groups_github_secret_hint: '输入后保存；已配置时留空不会覆盖原 Secret。',
        groups_github_secret_placeholder: '输入与 GitHub 一致的高强度 Secret',
        groups_github_secret_from_environment: '由 LIGHTAGENT_GITHUB_WEBHOOK_SECRET 环境变量接管。',
        groups_github_secret_from_config: '已在本地配置中保存，真实值不会回显。',
        groups_github_secret_not_configured: '尚未配置 Secret，启用前必须填写。',
        groups_github_secret_show: '显示 Secret',
        groups_github_secret_hide: '隐藏 Secret',
        groups_rooms_title: '群与管理员',
        groups_rooms_desc: '选择机器人允许响应的微信群，并为每个群配置可触发持久化/写入类能力的管理员。',
        groups_rooms_select_label: '目标群',
        groups_rooms_select_placeholder: '选择微信群',
        groups_rooms_selected_count: '已选择 {count} 个群',
        groups_rooms_search_placeholder: '搜索群名...',
        groups_rooms_no_match: '没有匹配的群',
        groups_rooms_none_selected: '尚未选择目标群',
        groups_rooms_remove: '移除群',
        groups_admin_title: '群管理员',
        groups_admin_desc: '管理员按群生效，同一个 sender_id 在其他群不会自动获得权限。',
        groups_admin_room_label: '选择群',
        groups_admin_member_label: '搜索成员',
        groups_admin_member_search_placeholder: '按昵称、微信号或 sender ID 搜索',
        groups_admin_member_search: '搜索成员',
        groups_admin_add_selected: '保存管理员',
        groups_admin_selected_title: '已配置管理员',
        groups_admin_no_room: '请先选择一个目标群',
        groups_admin_no_members: '没有匹配成员。请确认微信已登录，并先刷新群列表。',
        groups_admin_no_selected: '尚未选择成员',
        groups_admin_no_admins: '尚未配置管理员',
        groups_admin_remove: '删除管理员',
        groups_admin_permissions_title: '管理员门禁能力',
        groups_admin_permissions_desc: '勾选后，普通成员不能触发对应持久化或写入类能力。',
        groups_admin_permission_enabled: '已启用门禁',
        groups_admin_permission_disabled: '未启用门禁',
        groups_admin_permission_details: '详情',
        groups_admin_permission_blocked_behavior: '限制行为',
        groups_admin_permission_allowed_behavior: '仍允许',
        groups_admin_permission_examples: '示例话术',
        groups_admin_permission_guard_layers: '门禁层级',
        groups_admin_permission_affected_objects: '影响对象',
        groups_blacklist_title: '群黑名单',
        groups_blacklist_desc: '黑名单按群生效。命中成员主动 @ bot、引用 bot 或进入自由回复判定时，机器人会静默跳过。',
        groups_blacklist_room_label: '选择群',
        groups_blacklist_member_label: '搜索成员',
        groups_blacklist_member_search_placeholder: '按昵称、微信号或 sender ID 搜索',
        groups_blacklist_member_search: '搜索成员',
        groups_blacklist_add_selected: '保存黑名单',
        groups_blacklist_selected_title: '已配置黑名单',
        groups_blacklist_no_room: '请先选择一个目标群',
        groups_blacklist_no_members: '没有匹配成员。请确认微信已登录，并先刷新群列表。',
        groups_blacklist_no_selected: '尚未选择成员',
        groups_blacklist_no_items: '尚未配置黑名单',
        groups_blacklist_remove: '删除黑名单',
        groups_rooms_fallback_hint: '群名兜底只在群 ID 不可用时使用，每行一个群名。',
        groups_room_unnamed: '未命名群',
        groups_room_saved: '已保存群 {n}',
        wechat_group_free_reply_title: '自由回复',
        wechat_group_free_reply_hint: '“闭嘴”命令暂停当前群自由回复；可选择禁言期间是否同时忽略 @ 消息。',
        wechat_group_free_reply_enabled: '启用自由回复',
        wechat_group_free_reply_mute_minutes: '“闭嘴”禁言时长（分钟）',
        wechat_group_free_reply_mute_minutes_hint: '群成员精确 @ 机器人发送“闭嘴”后，当前群暂停普通自由回复；范围 1–1440 分钟。',
        wechat_group_free_reply_mute_mentions: '禁言期间被 @ 也不回复',
        wechat_group_free_reply_mute_mentions_hint: '开启后，禁言有效期内的新 @ 消息也会静默忽略；引用和拍一拍仍正常。',
        wechat_group_free_reply_groups: '自由回复群',
        wechat_group_free_reply_names_label: '自由回复群名候选',
        wechat_group_free_reply_force_keywords: '强触发关键词',
        wechat_group_free_reply_force_keywords_hint: '命中后只绕过低信息和评分阈值，不绕过群范围、安全、冷却和上限。',
        wechat_group_free_reply_level: '活跃档位',
        wechat_group_free_reply_threshold: '接话阈值',
        wechat_group_free_reply_interval: '最小间隔（秒）',
        wechat_group_free_reply_hourly: '每小时上限',
        wechat_group_free_reply_consecutive: '连续发言上限',
        wechat_group_free_reply_ttl: '排队有效期（秒）',
        wechat_group_free_reply_worker_title: '后台任务池',
        wechat_group_free_reply_worker_max_workers: '后台任务并发数',
        wechat_group_free_reply_worker_queue_size: '队列长度上限',
        wechat_group_free_reply_llm_title: '大模型二次判定',
        wechat_group_free_reply_llm_enabled: '启用大模型二次判定',
        wechat_group_free_reply_llm_timeout: '判定超时（秒）',
        wechat_group_free_reply_llm_confidence: '最低置信度',
        wechat_group_free_reply_rules: '评分规则',
        wechat_group_free_reply_last_decision: '最近判定',
        wechat_group_free_reply_no_decision: '还没有自由回复判定。开启后，普通群消息会先经过本地评分和大模型二次判定。',
        wechat_group_free_reply_worker_status: '后台任务状态',
        wechat_group_free_reply_running: '运行中',
        wechat_group_free_reply_stopped: '未运行',
        wechat_group_free_reply_room_access: '需先属于目标群范围',
        wechat_group_free_reply_rule_type: '类型',
        wechat_group_free_reply_rule_id: '规则 ID',
        wechat_group_free_reply_rule_description: '规则',
        wechat_group_free_reply_rule_score: '分值/启用',
        wechat_group_free_reply_rule_score_hint: '加分项可改分值；抑制项可勾选是否启用',
        wechat_group_free_reply_rules_not_persisted: '评分规则未写入配置。请重启后端进程后再保存一次。',
        wechat_group_free_reply_rule_enabled: '启用',
        wechat_group_free_reply_rule_positive: '加分',
        wechat_group_free_reply_rule_negative: '抑制',
        wechat_group_free_reply_level_quiet: '安静',
        wechat_group_free_reply_level_normal: '普通',
        wechat_group_free_reply_level_active: '活跃',
        wechat_group_free_reply_level_crazy: '高频',
        wechat_group_free_reply_decision_score: '评分',
        wechat_group_free_reply_decision_threshold: '阈值',
        wechat_group_free_reply_decision_reasons: '触发原因',
        wechat_group_free_reply_decision_suppressions: '抑制原因',
        wechat_group_free_reply_decision_preview: '内容预览',
        wechat_group_free_reply_worker_queue: '队列',
        wechat_group_free_reply_worker_approved: '已通过',
        wechat_group_free_reply_worker_rejected: '已拒绝',
        wechat_group_free_reply_worker_dropped: '已丢弃',
        wechat_group_free_reply_worker_expired: '已过期',
        wechat_group_free_reply_worker_active: '运行任务',
        groups_image_title: '图片与生图',
        groups_image_desc: '控制微信群图片理解，以及每个群每小时可受理的生图次数。',
        groups_focus_title: '焦点栈',
        groups_focus_desc: '查看当前群运行时焦点栈，并搜索新的焦点归档。',
        groups_focus_room: '目标群',
        groups_focus_room_hint: '焦点栈按群 ID 隔离，切换群可查看不同群的上下文焦点。',
        groups_focus_empty: '请先在“群聊开关”里选择至少一个目标群。',
        groups_focus_loading: '正在读取当前群焦点栈...',
        groups_focus_refresh: '刷新焦点',
        groups_focus_refresh_done: '当前群焦点栈已刷新',
        groups_focus_search_placeholder: '搜索历史焦点标题或摘要...',
        groups_focus_active_title: '当前焦点栈',
        groups_focus_archive_title: '焦点归档',
        groups_focus_no_active: '当前群还没有活动焦点。',
        groups_focus_no_archive: '没有匹配的焦点归档。',
        groups_focus_enabled: '总开关',
        groups_focus_recent_message_limit: '最近消息窗口',
        groups_focus_context_message_limit: '上下文消息数',
        groups_focus_stack_depth: '栈深度',
        groups_focus_stale_rounds: '过期轮次',
        groups_focus_min_keywords: '最少关键词',
        groups_focus_archive_recall_limit: '归档召回上限',
        groups_focus_frame_title: '标题',
        groups_focus_frame_summary: '摘要',
        groups_focus_frame_keywords: '关键词',
        groups_focus_frame_participants: '参与者',
        groups_focus_frame_conclusions: '结论',
        groups_focus_frame_message_count: '消息数',
        groups_focus_frame_updated_at: '更新时间',
        groups_style_title: '风格卡片',
        groups_style_desc: '审核群聊里沉淀出来的表达风格，只把启用卡片注入到回复上下文。',
        groups_style_room: '目标群',
        groups_style_room_hint: '风格卡片按群 ID 隔离，切换群可查看当前候选和启用卡片。',
        groups_style_empty: '请先在“群聊开关”里选择至少一个目标群。',
        groups_style_loading: '正在读取当前群的风格卡片...',
        groups_style_refresh: '刷新候选',
        groups_style_active_title: '已启用卡片',
        groups_style_candidates_title: '待审核候选',
        groups_style_no_active: '当前群还没有启用中的风格卡片。',
        groups_style_no_candidates: '当前没有待审核候选，可先让群内继续讨论后再刷新。',
        groups_style_enabled: '总开关',
        groups_style_learning_enabled: '学习开关',
        groups_style_auto_apply_enabled: '自动启用',
        groups_style_context_limit: '注入上限',
        groups_style_candidate_min_evidence: '最少证据',
        groups_style_learning_batch_limit: '学习批量',
        groups_style_on: '开启',
        groups_style_off: '关闭',
        groups_style_intent: '意图',
        groups_style_tone: '语气',
        groups_style_trigger_rule: '适用场景',
        groups_style_avoid_rule: '避免事项',
        groups_style_example: '示例',
        groups_style_evidence_count: '证据数',
        groups_style_approve: '通过',
        groups_style_reject: '拒绝',
        groups_style_disable: '停用',
        groups_style_review_saved: '风格卡片已更新',
        groups_emotion_title: '情绪与主动性',
        groups_emotion_desc: '查看当前群情绪状态，调整时段规则与打字节奏。',
        groups_emotion_room: '目标群',
        groups_emotion_room_hint: '情绪状态按群 ID 隔离，切换群可查看实时状态。',
        groups_emotion_empty: '请先在“群聊开关”里选择至少一个目标群。',
        groups_emotion_loading: '正在读取当前群情绪状态...',
        groups_emotion_state: '当前情绪',
        groups_emotion_interpreted_state: '解释状态',
        groups_emotion_reply_count: '近 1 小时回复数',
        groups_emotion_last_reply: '最近回复时间',
        groups_emotion_last_decision: '最近自由回复决策',
        groups_emotion_enabled: '启用情绪模型',
        groups_emotion_enabled_hint: '关闭后不再根据群状态调节主动性。',
        groups_emotion_decay_minutes: '衰减周期（分钟）',
        groups_emotion_decay_minutes_hint: '多久向默认情绪回归一次。',
        groups_emotion_default_valence: '默认情绪正负值',
        groups_emotion_default_energy: '默认活跃度',
        groups_emotion_default_sociability: '默认社交倾向',
        groups_emotion_time_rules_enabled: '启用时段规则',
        groups_emotion_time_rules_enabled_hint: '未命中的时间段会抑制自由回复。',
        groups_emotion_time_rules: '时段规则 JSON',
        groups_emotion_time_rules_hint: '示例：[{"days":["mon","tue"],"start":"09:00","end":"18:00"}]',
        groups_emotion_typing_delay_enabled: '启用打字延迟',
        groups_emotion_typing_delay_enabled_hint: '文本回复前按字符数模拟自然等待。',
        groups_emotion_typing_chars_per_second: '打字速度（字/秒）',
        groups_emotion_typing_chars_per_second_hint: '值越小，发送前等待越久。',
        groups_emotion_refresh: '刷新状态',
        groups_emotion_reset: '重置当前群状态',
        groups_emotion_reset_confirm: '确定将当前群情绪状态恢复到默认值吗？',
        groups_emotion_reset_done: '当前群情绪状态已重置',
        groups_emotion_save: '保存情绪配置',
        groups_emotion_saved: '情绪配置已保存',
        groups_emotion_metric_valence: '情绪正负值',
        groups_emotion_metric_energy: '活跃度',
        groups_emotion_metric_sociability: '社交倾向',
        groups_emotion_state_withdrawn: '收敛',
        groups_emotion_state_engaged: '积极',
        groups_emotion_state_guarded: '谨慎',
        groups_emotion_state_steady: '平稳',
        groups_emotion_time_rules_invalid: '时段规则 JSON 格式不正确',
        groups_sticker_title: '表情包',
        groups_sticker_desc: '管理当前群沉淀的表情包资产，支持编辑描述并用图片理解补全待处理项。',
        groups_sticker_room: '目标群',
        groups_sticker_room_hint: '表情包资产按群 ID 隔离，停用后不会再被当前群检索到。',
        groups_sticker_empty: '请先在“群聊开关”里选择至少一个目标群。',
        groups_sticker_loading: '正在读取当前群表情包...',
        groups_sticker_refresh: '刷新列表',
        groups_sticker_search_placeholder: '搜索描述、文件名...',
        groups_sticker_list_title: '表情包列表',
        groups_sticker_no_items: '当前筛选条件下没有表情包。',
        groups_sticker_status: '状态',
        groups_sticker_status_all: '全部',
        groups_sticker_status_active: '启用中',
        groups_sticker_status_disabled: '已停用',
        groups_sticker_enabled: '总开关',
        groups_sticker_enabled_hint: '关闭后当前通道不再检索、注入或发送表情包。',
        groups_sticker_auto_collect_enabled: '自动收集',
        groups_sticker_auto_collect_enabled_hint: '群内表情消息自动沉淀为可检索资产。',
        groups_sticker_context_limit: '注入上限',
        groups_sticker_context_limit_hint: '单次检索/上下文中最多返回的表情包数量。',
        groups_sticker_reply_percent: '主动回复频率(%)',
        groups_sticker_reply_percent_hint: '轻松闲聊中主动使用表情包的目标比例；0 表示仅在明确要求时发送。',
        groups_sticker_max_size_mb: '大小上限(MB)',
        groups_sticker_max_size_mb_hint: '收集与发送时允许的单张表情包最大体积。',
        groups_sticker_daily_send_limit: '每日发送上限',
        groups_sticker_daily_send_limit_hint: '每个群每天最多发送的表情包次数。',
        groups_sticker_online_search_enabled: '线上检索',
        groups_sticker_online_search_enabled_hint: '本地素材不足时允许补充线上候选。',
        groups_sticker_online_allow_gif: '允许 GIF',
        groups_sticker_online_allow_gif_hint: '线上候选是否允许返回动态 GIF。',
        groups_sticker_online_provider: '线上源',
        groups_sticker_online_search_count: '线上候选数',
        groups_sticker_online_search_count_hint: '单次线上检索返回的候选数量上限。',
        groups_sticker_cooldown_seconds: '发送冷却(秒)',
        groups_sticker_cooldown_seconds_hint: '同一群连续发送表情包的最短间隔。',
        groups_sticker_settings_title: '表情包设置',
        groups_sticker_settings_hint: '修改后点击保存才会生效；列表刷新不会丢弃未保存的编辑。',
        groups_sticker_storage_dir: '存储目录',
        groups_sticker_online_endpoint: '线上接口',
        groups_sticker_online_allowed_domains: '允许域名',
        groups_sticker_online_allowed_domains_placeholder: '每行一个域名，例如 biaoqing.gtimg.com',
        groups_sticker_save: '保存表情包设置',
        groups_sticker_saved: '表情包设置已保存',
        groups_sticker_online_test: '测试线上检索',
        groups_sticker_online_test_placeholder: '输入情绪或关键词...',
        groups_sticker_online_test_done: '线上检索完成',
        groups_sticker_description: '描述',
        groups_sticker_file_name: '文件名',
        groups_sticker_source_message_id: '来源消息',
        groups_sticker_use_count: '使用次数',
        groups_sticker_updated_at: '更新时间',
        groups_sticker_disable: '停用',
        groups_sticker_disable_confirm: '确定停用这个表情包吗？停用后当前群不会再使用它。',
        groups_sticker_disabled_done: '表情包已停用',
        groups_sticker_preview_alt: '表情包预览',
        groups_sticker_description_status_loading: '正在统计待理解描述...',
        groups_sticker_description_status_failed: '待理解统计加载失败',
        groups_sticker_description_status_retry: '重试统计',
        groups_sticker_description_pending_summary: '待理解 {pending} 条，其中 {processable} 条可处理',
        groups_sticker_description_file_issues: '另有 {missing} 条文件缺失、{empty} 条文件为空',
        groups_sticker_describe_pending: '图片理解补全描述',
        groups_sticker_describe_confirm: '将使用已配置的图片理解处理当前群 {count} 个表情包，并在开始前备份数据库。是否继续？',
        groups_sticker_describe_starting: '正在启动...',
        groups_sticker_describe_running: '图片理解处理中 {processed}/{total}',
        groups_sticker_describe_busy: '其他群正在处理',
        groups_sticker_describe_started: '表情包描述批处理已启动',
        groups_sticker_describe_result: '已更新 {updated} 条，失败 {failed} 条，跳过 {skipped} 条',
        groups_sticker_describe_completed: '图片理解处理完成',
        groups_sticker_describe_partial_failed: '处理完成，部分项目仍需重试',
        groups_sticker_describe_failed: '批量图片理解失败，请检查模型配置后重试',
        groups_sticker_description_edit: '编辑描述',
        groups_sticker_description_edit_label: '表情包描述',
        groups_sticker_description_edit_hint: '1–200 个字符；Enter 保存，Esc 取消。',
        groups_sticker_description_save: '保存',
        groups_sticker_description_cancel: '取消',
        groups_sticker_description_saved: '表情包描述已保存',
        groups_sticker_description_invalid: '描述必须为 1–200 个字符',
        groups_sticker_description_semantic_required: '请填写有实际含义的描述，不能使用占位、XML、纯数字或长哈希',
        groups_sticker_description_changed: '描述已被其他操作更新，请刷新后重试',
        groups_sticker_description_not_found: '当前群中找不到该表情包',
        groups_sticker_description_no_processable: '当前群没有可处理的待理解描述',
        groups_sticker_description_job_running: '已有表情包描述任务正在运行',
        groups_image_understanding_enabled: '启用图片理解',
        groups_image_understanding_enabled_hint: '仅在图片直接 @ 或引用机器人时调用既有视觉工具。',
        groups_image_comment_enabled: '允许纯图片评论',
        groups_image_comment_enabled_hint: '用户只发图片也可基于视觉摘要生成简短回复。',
        groups_image_free_reply_understanding_enabled: '启用自由回复图片理解',
        groups_image_free_reply_understanding_enabled_hint: '普通群图片先经过自由回复判定，通过后才调用视觉工具生成回复。',
        groups_image_prompt: '图片理解提示词',
        groups_image_prompt_hint: '发送给既有图片理解工具的问题。',
        groups_image_cache_minutes: '摘要缓存分钟数',
        groups_image_cache_minutes_hint: '同一图片摘要的缓存时间，范围 1-120。',
        groups_multimodal_context_enabled: '启用全局多模态上下文',
        groups_multimodal_context_enabled_hint: '在统一上下文注入层装配引用、转发、视频和图片摘要。',
        groups_multimodal_image_context_enabled: '启用图片理解上下文注入',
        groups_multimodal_image_context_enabled_hint: '命中图片候选后，把视觉摘要注入当前回复上下文。',
        groups_multimodal_free_reply_image_context_enabled: '允许自由回复绑定最近图片',
        groups_multimodal_free_reply_image_context_enabled_hint: '普通非 @ 文本通过自由回复判定后，可按严格规则绑定近图；默认关闭。',
        groups_multimodal_same_sender_window_seconds: '同发送者追问窗口（秒）',
        groups_multimodal_same_sender_window_seconds_hint: '同一发送者发图后追问“这是真的吗”等短句的匹配窗口，范围 5-600。',
        groups_multimodal_unique_image_window_seconds: '群内唯一近图窗口（秒）',
        groups_multimodal_unique_image_window_seconds_hint: '短窗口内全群只有一张图且文本明确指代时才绑定，范围 5-600。',
        groups_multimodal_quote_sender_window_minutes: '引用发送者查找窗口（分钟）',
        groups_multimodal_quote_sender_window_minutes_hint: '引用消息 ID 未命中图片时，倒序查找该发送者近图，范围 1-120。',
        groups_multimodal_max_recent_messages: '最多检查最近消息数',
        groups_multimodal_max_recent_messages_hint: '多模态候选选择最多扫描多少条归档消息，范围 1-100。',
        groups_image_create_hourly_limit: '生图每小时上限',
        groups_image_create_hourly_limit_hint: '每个微信群每小时成功受理的生图次数；0 表示关闭微信群生图。',
        groups_image_generation_proxy_enabled: '指定域名图片下载走代理',
        groups_image_generation_proxy_enabled_hint: '生图接口仍直连；只有命中下方域名的结果图片下载会使用基础配置里的代理地址。',
        groups_image_generation_proxy_domains: '代理域名',
        groups_image_generation_proxy_domains_hint: '每行一个域名，支持 *.grok.com；代理地址在“基础设置”里配置。',
        groups_image_generation_proxy_domains_placeholder: 'assets.grok.com\n*.grok.com',
        groups_video_understanding_enabled: '启用视频上下文',
        groups_video_understanding_enabled_hint: '视频消息直接 @ 或引用机器人时，作为文本上下文进入主链路；默认关闭。',
        groups_forward_preview_enabled: '启用转发预览',
        groups_forward_preview_enabled_hint: '对合并聊天记录等转发消息注入短摘要字段，不注入大段原文。',
        groups_quote_context_enabled: '启用引用上下文',
        groups_quote_context_enabled_hint: '优先按消息 ID 命中被引用内容，减少把最近消息误判为引用对象。',
        groups_persona_title: '人设设定',
        groups_persona_desc: '只保留一份自定义人设，保存后对微信群回复生效。',
        groups_memory_title: '永久记忆',
        groups_memory_desc: '按群维护群记忆、群友画像和本轮注入预览。',
        groups_profiles_title: '群友画像',
        groups_profiles_desc: '每个群独立维护画像；同一群友在当前群最多一份。',
        groups_profiles_room_filter: '所属群',
        groups_profiles_room_all: '全部群',
        groups_profiles_search_placeholder: '搜索发送者 ID、昵称或别名',
        groups_profiles_search: '搜索画像',
        groups_profiles_result_count: '共 {count} 条',
        groups_profiles_no_data: '当前群暂无画像，可从群成员创建',
        groups_profiles_create_member: '选择群成员',
        groups_profiles_create: '新建画像',
        groups_profiles_no_members: '暂无可创建画像的群成员',
        groups_profiles_list_title: '画像列表',
        groups_profiles_detail_title: '画像详情',
        groups_profiles_detail_empty: '从左侧选择一位群友查看详情。',
        groups_profiles_summary_title: '只读摘要',
        groups_profiles_content_title: '画像正文',
        groups_profiles_rooms_title: '当前群',
        groups_profiles_last_seen: '最近出现',
        groups_profiles_name_records: '命名记录 {count}',
        groups_profiles_edit_title: '手动修正',
        groups_profiles_save: '保存修正',
        groups_profiles_room_empty: '未记录群来源',
        groups_profiles_metric_messages: '消息数',
        groups_profiles_metric_activity: '活跃度',
        groups_profiles_metric_intimacy: '熟悉度',
        groups_memory_no_room: '请先在“群聊开关”中选择至少一个群 ID。',
        groups_memory_group_title: '群记忆',
        groups_memory_group_hint: '保存当前群长期稳定信息，例如群规、偏好、长期项目和约定。',
        groups_memory_content_label: '群记忆正文',
        groups_memory_content_placeholder: '输入只属于当前群的长期记忆',
        groups_memory_summary_label: '来源摘要',
        groups_memory_save: '保存群记忆',
        groups_memory_saved: '群记忆已保存',
        groups_memory_empty: '当前群暂无群记忆',
        groups_memory_search_placeholder: '搜索当前群记忆',
        groups_memory_search: '搜索',
        groups_memory_disable: '停用',
        groups_memory_disabled: '已停用',
        groups_memory_count_label: '群记忆 {count}',
        groups_memory_profile_count_label: '画像 {count}',
        groups_memory_profiles_title: '群友画像',
        groups_memory_profiles_hint: '每个群独立维护群友画像，并以稳定群和稳定成员作为唯一键。',
        groups_memory_profiles_moved_hint: '群友画像已迁移到“群友画像”，这里仅保留群记忆、注入预览和学习运行。',
        groups_memory_member_lookup_label: '检索群友',
        groups_memory_member_lookup_placeholder: '输入微信 ID、发送者 ID 或昵称',
        groups_memory_member_lookup_hint: '从当前群已归档聊天记录中检索；没有结果时仍可手动填写发送者 ID。',
        groups_memory_member_lookup_empty: '未找到匹配群友',
        groups_memory_member_lookup_searching: '检索中...',
        groups_memory_member_lookup_select: '选择',
        groups_memory_sender_id: '发送者 ID',
        groups_memory_sender_name: '昵称',
        groups_memory_aliases: '别名',
        groups_memory_role: '身份/角色',
        groups_memory_preferences: '长期偏好',
        groups_memory_common_words: '常用词',
        groups_memory_interaction: '互动风格',
        groups_memory_boundaries: '已知边界',
        groups_memory_evidence: '更新依据',
        groups_memory_profile_save: '保存画像',
        groups_memory_profile_saved: '画像已保存',
        groups_memory_profiles_empty: '当前群暂无群友画像',
        groups_memory_revisions_title: '历史版本',
        groups_memory_revisions_empty: '点击画像后查看历史版本',
        groups_memory_preview_title: '注入预览',
        groups_memory_preview_hint: '只读查看本轮将注入的微信群知识上下文，不会调用模型或写入记忆。',
        groups_memory_preview_query: '模拟问题',
        groups_memory_preview_mentions: '被 @ 的发送者 ID',
        groups_memory_preview_run: '生成预览',
        groups_memory_preview_empty: '暂无可注入记忆',
        groups_memory_tab_manual: '记忆维护',
        groups_memory_tab_auto: '学习运行',
        groups_memory_auto_title: '从聊天记录学习',
        groups_memory_auto_hint: '从当前群的新归档文本消息中分别学习群记忆和群友画像。',
        groups_memory_knowledge_enabled: '启用群记忆',
        groups_memory_profile_enabled: '启用群友画像',
        groups_memory_learning_enabled: '启用学习',
        groups_memory_profile_context_limit: '画像注入条数',
        groups_memory_group_context_limit: '群记忆注入条数',
        groups_memory_learning_batch_limit: '每批学习消息数',
        groups_memory_learning_profile_min_messages: '画像最少消息数',
        groups_memory_learning_profile_sample_limit: '画像取样条数',
        groups_memory_learning_group_memory_min_messages: '群记忆最少消息数',
        groups_memory_learning_group_memory_window_minutes: '群记忆时间窗口（分钟）',
        groups_memory_auto_enabled: '启用自动蒸馏',
        groups_memory_auto_apply_threshold: '自动写入阈值',
        groups_memory_candidate_threshold: '候选阈值',
        groups_memory_window_minutes: '窗口分钟数',
        groups_memory_message_limit: '最大消息数',
        groups_memory_auto_apply_group: '允许自动写群记忆',
        groups_memory_auto_apply_member: '允许自动写群友画像',
        groups_memory_auto_save: '保存配置',
        groups_memory_auto_saved: '自动生成配置已保存',
        groups_memory_auto_run: '从最近聊天生成记忆',
        groups_memory_auto_runs: '运行记录',
        groups_memory_auto_candidates: '候选审核',
        groups_memory_auto_no_runs: '当前群暂无运行记录',
        groups_memory_auto_no_candidates: '当前群暂无候选',
        groups_memory_auto_approve: '批准写入',
        groups_memory_auto_reject: '驳回',
        groups_memory_auto_rejected: '候选已驳回',
        groups_memory_auto_approved: '候选已写入',
        groups_memory_auto_ran: '自动生成已完成',
        groups_memory_auto_status_pending: '待审核',
        groups_memory_auto_status_auto_applied: '已自动写入',
        groups_memory_auto_status_approved: '已批准',
        groups_memory_auto_status_rejected: '已驳回',
        groups_memory_auto_status_failed: '失败',
        groups_memory_run_messages: '消息数',
        groups_memory_run_profiles: '画像数',
        groups_memory_run_memories: '群记忆数',
        groups_error_summary_load_failed: '群聊汇总加载失败',
        groups_error_memory_load_failed: '群记忆加载失败',
        groups_error_runs_load_failed: '运行记录加载失败',
        groups_error_save_failed: '保存失败',
        groups_error_disable_failed: '停用失败',
        groups_error_preview_failed: '预览生成失败',
        groups_error_learning_failed: '学习运行失败',
        groups_error_approve_failed: '批准失败',
        groups_error_reject_failed: '驳回失败',
        groups_error_room_required: '请选择目标群',
        groups_error_sender_required: '请填写发送者 ID',
        groups_error_unknown_action: '未知操作',
        wecom_scan_btn: '扫码创建企微机器人', wecom_scan_desc: '使用企业微信扫码，一键创建智能机器人',
        wecom_scan_success: '创建成功，正在启动通道...',
        wecom_scan_fail: '创建失败',
        wecom_mode_scan: '扫码接入', wecom_mode_manual: '手动填写',
        feishu_scan_btn: '一键创建飞书应用',
        feishu_scan_desc: '使用飞书 App 扫码，自动创建应用并预置全部权限与事件订阅',
        feishu_scan_replace_desc: '使用飞书 App 扫码创建新机器人，将覆盖当前的 App ID / Secret',
        feishu_scan_loading: '正在向飞书申请二维码...',
        feishu_scan_waiting: '等待扫码...',
        feishu_scan_tip: '二维码 10 分钟内有效，仅供一次扫描',
        feishu_scan_open_link: '或点击此处在浏览器中打开',
        feishu_scan_success: '应用创建成功，正在启动通道...',
        feishu_scan_expired: '二维码已过期，请重试',
        feishu_scan_denied: '已取消授权',
        feishu_scan_fail: '创建失败',
        feishu_scan_retry: '重试',
        feishu_mode_scan: '扫码创建', feishu_mode_manual: '手动填写',
        tasks_title: '定时任务', tasks_desc: '查看和管理定时任务',
        tasks_coming: '即将推出', tasks_coming_desc: '定时任务管理功能即将在此提供',
        task_add_btn: '新增任务',
        task_edit_title: '编辑定时任务',
        task_add_title: '新增定时任务',
        task_name: '任务名称',
        task_enabled: '启用任务',
        task_schedule_type: '调度类型',
        task_schedule_cron: 'Cron 表达式',
        task_schedule_interval: '固定间隔',
        task_schedule_once: '一次性任务',
        task_cron_expression: 'Cron 表达式',
        task_cron_hint: '格式: 分 时 日 月 周，例如 "0 9 * * *" 表示每天 9:00',
        task_interval_seconds: '间隔秒数',
        task_interval_hint: '最小 60 秒，例如 3600 表示每小时执行一次',
        task_once_time: '执行时间',
        task_action_type: '动作类型',
        task_action_send_message: '发送消息',
        task_action_agent_task: 'AI 任务',
        task_channel_type: '通道类型',
        task_channel_hint: '选择定时消息发送的通道',
        task_message_content: '消息内容',
        task_task_description: '任务描述',
        task_delete_btn: '删除任务',
        task_delete_confirm_title: '删除定时任务',
        task_delete_confirm_msg: '确定删除该定时任务吗？此操作无法撤销。',
        logs_title: '日志', logs_desc: '实时日志输出 (run.log)',
        logs_live: '实时', logs_coming_msg: '日志流即将在此提供。将连接 run.log 实现类似 tail -f 的实时输出。',
        new_chat: '新对话',
        session_history: '历史会话',
        today: '今天', yesterday: '昨天', earlier: '更早',
        delete_session_confirm: '确认删除该会话？所有消息将被清除。',
        delete_session_title: '删除会话',
        rename_session: '重命名',
        delete_message_confirm: '确认删除这条消息？',
        delete_message_title: '删除消息',
        edit_disabled_reply_active: '正在生成回复，暂时无法编辑。',
        delete_disabled_reply_active: '正在生成回复，暂时无法删除。',
        untitled_session: '新对话',
        context_cleared: '— 以上内容已从上下文中移除 —',
        tip_new_chat: '新建对话',
        tip_clear_context: '清除上下文',
        tip_attach: '添加附件',
        attach_menu_file: '上传文件',
        mic_idle_title: '点击录音 / 再按一次结束',
        mic_recording_title: '录音中，再次点击结束',
        mic_busy_title: '识别中…',
        mic_permission_denied: '无法访问麦克风，请检查浏览器权限',
        mic_too_short: '录音太短，请重试',
        mic_error: '语音识别失败',
        speak_msg: '朗读这段回复',
        voice_reply_mode_label: '语音回复策略',
        voice_reply_off: '关闭',
        voice_reply_if_voice: '仅语音问/语音答',
        voice_reply_always: '总是语音回复',
        attach_menu_folder: '上传文件夹',
        confirm_yes: '确认',
        confirm_cancel: '取消',
        error_send: '发送失败，请稍后再试。', error_timeout: '请求超时，请再试一次。',
        thinking_in_progress: '思考中...', thinking_done: '已深度思考', thinking_duration: '耗时',
        edit_message: '编辑消息',
        regenerate_response: '重新生成',
        edit_save: '保存并发送',
        edit_cancel: '取消',
    },
    en: {
        console: 'Console',
        nav_chat: 'Chat', nav_manage: 'Management', nav_monitor: 'Monitor',
        menu_chat: 'Chat', menu_config: 'Config', menu_models: 'Models', menu_skills: 'Skills',
        menu_memory: 'Memory', menu_knowledge: 'Knowledge', menu_channels: 'Channels', menu_groups: 'Groups', menu_tasks: 'Tasks',
        menu_logs: 'Logs',
        models_title: 'Models',
        models_desc: 'Manage chat, image, voice, embedding and search capabilities in one place',
        models_section_vendors: 'Provider Credentials',
        models_section_vendors_desc: 'Configured once, shared by multiple model capabilities',
        models_section_capabilities: 'Capabilities',
        models_add_vendor: 'Add Provider',
        models_provider: 'Provider',
        models_model: 'Model',
        models_voice: 'Voice',
        models_configured: 'configured',
        models_not_configured: 'not configured',
        models_pick_to_configure: 'pick to configure',
        models_clear_credential: 'Clear credentials',
        models_base_default_hint: 'Leave blank to use the official default base URL',
        models_base_default: 'Default',
        models_custom_vendor_label: 'Custom',
        models_custom_name: 'Name',
        models_custom_delete: 'Delete',
        models_custom_delete_confirm_title: 'Delete custom provider',
        models_custom_delete_confirm_msg: 'Delete this custom provider? This cannot be undone.',
        models_custom_name_required: 'Name is required',
        models_custom_base_required: 'API Base is required',
        models_custom_edit_title: 'Edit custom provider',
        models_custom_add_title: 'Add custom provider',
        models_capability_chat: 'Main Model',
        models_capability_chat_desc: 'Used for basic chat and agent reasoning',
        models_chat_fallbacks: 'Fallback Models',
        models_chat_fallbacks_desc: 'Tried in order when the main model is temporarily unavailable',
        models_chat_fallback_add: 'Add fallback',
        models_chat_fallback_infer_provider: 'Infer from model name',
        models_chat_fallback_remove: 'Remove fallback model',
        models_chat_failover_title: 'Automatic failover',
        models_chat_failover_scope: 'Takes effect after fallbacks are configured and never rewrites the main model setting.',
        models_chat_failover_immediate: 'Current request: a temporary main-model failure immediately tries fallbacks in order.',
        models_chat_failover_circuit: 'Repeated failures: after {threshold} consecutive temporary failures, requests skip the main model for {cooldown}.',
        models_chat_failover_recovery: 'Automatic recovery: after cooldown, one request probes the main model; success restores it, while failure reopens the circuit.',
        models_chat_failover_minutes: '{value} minutes',
        models_chat_failover_seconds: '{value} seconds',
        models_capability_vision: 'Image Understanding',
        models_capability_vision_desc: 'Recognizes image content, used by image recognition tools',
        models_capability_image: 'Image Generation',
        models_capability_image_desc: 'Generates images, used by image generation skills',
        models_auto_using: 'Preferred',
        models_capability_asr: 'Speech Recognition',
        models_capability_asr_desc: 'Voice to text',
        models_capability_tts: 'Speech Synthesis',
        models_capability_tts_desc: 'Text to voice',
        models_invalid_voice_provider: 'Invalid voice provider detected. Please choose another:',
        models_legacy_voice_provider: 'The current voice provider is config-file only. Choose a Web-supported provider:',
        models_voice_provider_required: 'Choose a Web-supported voice provider first',
        models_capability_embedding: 'Embedding',
        models_capability_embedding_desc: 'Used for vectorized retrieval of memory and knowledge',
        models_capability_search: 'Web Search',
        models_capability_search_desc: 'Real-time web retrieval, used by search tools',
        models_strategy_auto: 'auto',
        models_search_strategy_label: 'Strategy',
        models_search_strategy_fixed: 'Pinned',
        models_search_strategy_auto_hint: 'Auto-pick from configured providers',
        models_search_strategy_fixed_hint: 'Always use a specific provider',
        models_pending_config: 'Pending setup',
        models_search_available_label: 'Available:',
        models_search_none_configured: 'No search provider enabled yet — click add.',
        models_search_add_provider: 'Add provider',
        models_search_add_desc: 'Pick a search provider to configure',
        models_search_bocha_title: 'Configure Bocha API Key',
        models_search_bocha_desc: 'Create a key at the Bocha open platform.',
        models_search_serper_title: 'Configure Serper API Key',
        models_search_serper_desc: 'Create a key from the Serper dashboard.',
        models_search_jina_title: 'Configure Jina API Key',
        models_search_jina_desc: 'Create a key from the Jina dashboard.',
        models_search_apply_link: 'Get API Key',
        models_search_edit_hint: 'Click to edit',
        models_unavailable: 'unavailable',
        models_set_via_env: 'enable via environment variable',
        models_dim_label: 'dim',
        models_save_success: 'Saved',
        models_save_failed: 'Save failed',
        models_cleared: 'Cleared',
        models_clear_failed: 'Clear failed',
        models_embedding_change_title: 'Change embedding model',
        models_embedding_change_msg: 'Switching the embedding model invalidates the existing index — a rebuild will be needed. Continue?',
        models_embedding_saved_title: 'Embedding model updated',
        models_embedding_saved_msg: 'Send /memory rebuild-index in the chat to rebuild the index.',
        models_embedding_saved_ok: 'Go',
        models_pick_provider: 'Pick a provider',
        models_clear_confirm_title: 'Clear provider credentials',
        models_clear_confirm_msg: 'Remove this provider\'s API Key and Base URL? Capabilities relying on it will stop working.',
        cancel: 'Cancel',
        save: 'Save',
        ok: 'OK',
        knowledge_title: 'Knowledge', knowledge_desc: 'Browse and explore your knowledge base',
        knowledge_tab_docs: 'Documents', knowledge_tab_graph: 'Graph',
        knowledge_loading: 'Loading knowledge base...', knowledge_loading_desc: 'Knowledge pages will be displayed here',
        knowledge_select_hint: 'Select a document to view', knowledge_empty_hint: 'No knowledge pages yet',
        knowledge_empty_guide: 'Send documents, links or topics to the agent in chat, and it will automatically organize them into your knowledge base.',
        knowledge_go_chat: 'Start a conversation',
        knowledge_new: 'New',
        knowledge_new_category: 'New category',
        knowledge_new_document: 'New document',
        knowledge_import_documents: 'Import documents',
        welcome_subtitle: 'I can help you answer questions, manage your computer, create and execute skills, and keep growing through <br> long-term memory and a personal knowledge base.',
        example_sys_title: 'System', example_sys_text: 'Show me the files in the workspace',
        example_task_title: 'Scheduler', example_task_text: 'Remind me to check the server in 5 minutes',
        example_code_title: 'Coding', example_code_text: 'Search today\'s AI news and generate a visual report webpage',
        example_knowledge_title: 'Knowledge', example_knowledge_text: 'Show me the current knowledge base',
        example_skill_title: 'Skills', example_skill_text: 'Show current tools and skills',
        example_web_title: 'Commands', example_web_text: 'Show all commands',
        slash_help: 'Show this help',
        slash_status: 'Show running status',
        slash_context: 'Show conversation context',
        slash_context_clear: 'Clear conversation context',
        slash_skill_list: 'List installed skills',
        slash_skill_list_remote: 'Browse Skill Hub',
        slash_skill_search: 'Search skills',
        slash_skill_install: 'Install a skill (name or GitHub URL)',
        slash_skill_uninstall: 'Uninstall a skill',
        slash_skill_info: 'Show skill details',
        slash_skill_enable: 'Enable a skill',
        slash_skill_disable: 'Disable a skill',
        slash_memory_dream: 'Trigger memory distillation (optional days, default 3)',
        slash_knowledge: 'Show knowledge base stats',
        slash_knowledge_list: 'Show knowledge base file tree',
        slash_knowledge_on: 'Enable knowledge base',
        slash_knowledge_off: 'Disable knowledge base',
        slash_config: 'Show current config',
        slash_cancel: 'Abort the running Agent task',
        slash_logs: 'Show recent logs',
        slash_version: 'Show version',
        input_placeholder: 'Type a message, or press / for commands',
        config_title: 'Configuration', config_desc: 'Manage model and agent settings',
        config_model: 'Model Configuration', config_agent: 'Agent Configuration',
        config_language: 'Language', config_language_hint: 'Language for the UI, command text, system prompts and more (synced with the top-right switch)',
        config_model_advanced: 'Advanced',
        config_channel: 'Channel Configuration',
        config_agent_enabled: 'Agent Mode',
        config_max_tokens: 'Max Context Tokens', config_max_tokens_hint: 'Max tokens the Agent can input per conversation, auto-compressed when exceeded',
        config_max_turns: 'Max Memory Turns', config_max_turns_hint: 'One Q&A pair = one turn, auto-compressed when exceeded',
        config_max_steps: 'Max Steps', config_max_steps_hint: 'Max tool calls the Agent can make in a single conversation',
        config_enable_thinking: 'Deep Thinking', config_enable_thinking_hint: 'Enable deep thinking mode',
        config_self_evolution: 'Self-Evolution', config_self_evolution_hint: 'Auto-review idle conversations to consolidate memory, improve skills, and follow up on unfinished tasks',
        evolution_badge: 'Self-learned',
        config_channel_type: 'Channel Type',
        config_provider: 'Provider', config_model_name: 'Model',
        config_custom_model_hint: 'Enter custom model name',
        config_save: 'Save', config_saved: 'Saved',
        config_save_error: 'Save failed',
        config_custom_option: 'Custom',
        config_custom_tip: 'API must follow OpenAI protocol.',
        config_security: 'Security', config_password: 'Password',
        config_password_hint: 'Leave empty to disable password protection',
        config_password_changed: 'Password updated, please re-login',
        config_password_cleared: 'Password cleared',
        skills_title: 'Skills', skills_desc: 'View, enable, or disable agent tools and skills', skills_hub_btn: 'Skill Hub',
        skills_loading: 'Loading skills...', skills_loading_desc: 'Skills will be displayed here after loading',
        tools_section_title: 'Built-in Tools', tools_loading: 'Loading tools...',
        skills_section_title: 'Skills', skill_enable: 'Enable', skill_disable: 'Disable',
        skill_toggle_error: 'Operation failed, please try again',
        memory_title: 'Memory', memory_desc: 'View agent memory files and contents',
        memory_tab_files: 'Memory Files', memory_tab_dreams: 'Self-Evolution',
        memory_loading: 'Loading memory files...', memory_loading_desc: 'Memory files will be displayed here',
        memory_back: 'Back to list',
        memory_col_name: 'Filename', memory_col_type: 'Type', memory_col_size: 'Size', memory_col_updated: 'Updated',
        channels_title: 'Channels', channels_desc: 'Manage connected messaging channels',
        channels_add: 'Connect', channels_disconnect: 'Disconnect',
        channels_save: 'Save', channels_saved: 'Saved', channels_save_error: 'Save failed',
        channels_restarted: 'Saved & Restarted',
        channels_connect_btn: 'Connect', channels_cancel: 'Cancel',
        channels_select_placeholder: 'Select a channel to connect...',
        channels_empty: 'No channels connected', channels_empty_desc: 'Click the "Connect" button above to get started',
        channels_disconnect_confirm: 'Disconnect this channel? Config will be preserved but the channel will stop.',
        channels_connected: 'Connected', channels_connecting: 'Connecting...',
        weixin_scan_title: 'WeChat QR Login', weixin_scan_desc: 'Scan the QR code below with WeChat',
        weixin_scan_loading: 'Loading QR code...', weixin_scan_waiting: 'Waiting for scan...',
        weixin_scan_scanned: 'Scanned, please confirm on your phone', weixin_scan_expired: 'QR code expired, refreshing...',
        weixin_scan_success: 'Login successful, starting channel...', weixin_scan_fail: 'Failed to load QR code',
        weixin_qr_tip: 'QR code expires in ~2 minutes',
        wechat_group_scan_title: 'WeChat Groups QR Login', wechat_group_scan_desc: 'Scan the QR code below with WeChat to connect the group channel',
        wechat_group_scan_loading: 'Starting WeChat group channel...', wechat_group_scan_success: 'WeChat group channel connected',
        wechat_group_scan_fail: 'Failed to start WeChat group channel', wechat_group_qr_tip: 'Replies to @ messages in groups after login',
        wechat_group_rooms_title: 'Target groups',
        wechat_group_rooms_hint: 'Use stable room IDs; group names support automatic recovery after re-login.',
        wechat_group_rooms_refresh: 'Refresh groups',
        wechat_group_rooms_empty: 'Refresh after login.',
        wechat_group_room_names_label: 'Candidate group names',
        wechat_group_room_names_placeholder: 'One group name per line',
        wechat_group_rooms_refreshed: 'Group list refreshed',
        wechat_group_rooms_refresh_failed: 'Failed to refresh groups',
        wechat_group_persona_title: 'Persona',
        wechat_group_persona_hint: 'Selecting a preset only fills the editor; save to apply it.',
        wechat_group_persona_active: 'Active',
        wechat_group_persona_custom: 'Custom',
        wechat_group_persona_dirty: 'Unsaved changes',
        wechat_group_persona_clean: 'Applied',
        wechat_group_persona_prompt_label: 'Persona prompt',
        wechat_group_persona_prompt_placeholder: 'Describe identity, tone, style, and boundaries for group replies',
        wechat_group_persona_boundary: 'Persona cannot bypass guards, group limits, or admin permissions.',
        wechat_group_settings_save: 'Save and apply',
        wechat_group_settings_saved: 'Saved and applied',
        groups_title: 'Groups',
        groups_desc: 'Manage WeChat group targets, humanized context, and persona',
        groups_loading: 'Loading group settings...',
        groups_load_failed: 'Failed to load group settings',
        groups_nav_basic: 'Basic',
        groups_nav_basic_hint: 'Basic runtime',
        groups_nav_identity: 'Identity recovery',
        groups_nav_identity_hint: 'Binding confirmation',
        groups_nav_humanization: 'Humanization',
        groups_nav_humanization_hint: 'Context and tone',
        groups_nav_rooms: 'Groups & admins',
        groups_nav_rooms_hint: 'Target groups and admins',
        groups_nav_free_reply: 'Free reply',
        groups_nav_free_reply_hint: 'Ambient group replies',
        groups_nav_voice_interaction: 'Voice interaction',
        groups_nav_voice_interaction_hint: 'Voice trigger policy',
        groups_nav_focus: 'Focus stack',
        groups_nav_focus_hint: 'Active focus and archive',
        groups_nav_style: 'Style cards',
        groups_nav_style_hint: 'Review and activate',
        groups_nav_emotion: 'Emotion',
        groups_nav_emotion_hint: 'State and pacing',
        groups_nav_sticker: 'Stickers',
        groups_nav_sticker_hint: 'Assets and disable',
        groups_nav_persona: 'Persona',
        groups_nav_persona_hint: 'Custom reply style',
        groups_nav_memory: 'Long-term memory',
        groups_nav_memory_hint: 'Group memory and profiles',
        groups_nav_profiles: 'Member profiles',
        groups_nav_profiles_hint: 'Browse room-scoped profiles',
        groups_nav_image: 'Images',
        groups_nav_image_hint: 'Vision and quota',
        groups_identity_title: 'Identity recovery',
        groups_identity_desc: 'Confirm group and member bindings after re-login. Unconfirmed items do not inherit sensitive permissions.',
        groups_identity_pending_rooms: 'Pending group bindings',
        groups_identity_pending_account: 'Pending login account',
        groups_identity_confirm_account_first: 'Confirm the login account binding first.',
        groups_identity_member_pending: 'Member identity pending',
        groups_identity_candidates: 'Binding candidates',
        groups_identity_no_pending: 'No pending group bindings.',
        groups_identity_no_candidates: 'No binding candidates.',
        groups_identity_refresh: 'Refresh candidates',
        groups_identity_confirm: 'Confirm binding',
        groups_identity_confirmed: 'Identity binding confirmed',
        groups_basic_title: 'Basic settings',
        groups_basic_desc: 'Controls basic runtime settings for the current group.',
        groups_voice_interaction_title: 'Voice interaction',
        groups_voice_interaction_desc: 'Choose how transcribed group voice messages trigger replies.',
        groups_voice_interaction_force_reply: 'Always reply',
        groups_voice_interaction_force_reply_hint: 'Enter the reply flow immediately after transcription succeeds.',
        groups_voice_interaction_free_reply: 'Use free reply rules',
        groups_voice_interaction_free_reply_hint: 'Reply only after the transcript passes free reply rules and judging.',
        groups_humanization_title: 'Humanized context',
        groups_humanization_desc: 'Controls reply policy, evidence search, summaries, link policy, and outgoing cleanup.',
        groups_humanization_enabled: 'Enable humanized context',
        groups_humanization_enabled_hint: 'Build current-turn WeChat group context by trigger source and intent.',
        groups_humanization_persist_raw_user_only: 'Persist raw user text only',
        groups_humanization_persist_raw_user_only_hint: 'Use enhanced prompts only for the current request, not future chat history.',
        groups_humanization_reply_policy_enabled: 'Enable reply policy',
        groups_humanization_reply_policy_enabled_hint: 'Distinguish direct @, quote, ambient reply, and image messages.',
        groups_humanization_recent_enabled: 'Enable recent context',
        groups_humanization_recent_enabled_hint: 'Inject recent transcript only when the request depends on context, quote, free reply, or multimodal state.',
        groups_humanization_recent_limit: 'Recent context limit',
        groups_humanization_recent_minutes: 'Recent context minutes',
        groups_humanization_archive_evidence_enabled: 'Enable archive evidence',
        groups_humanization_archive_evidence_limit: 'Archive evidence limit',
        groups_humanization_archive_evidence_days: 'Archive search days',
        groups_humanization_archive_evidence_recent_limit: 'Recent fallback limit',
        groups_humanization_local_summary_enabled: 'Enable local summary',
        groups_humanization_local_summary_limit: 'Summary candidate limit',
        groups_humanization_local_summary_hours: 'Summary hours',
        groups_humanization_reference_policy_enabled: 'Enable quote/image policy',
        groups_humanization_link_policy_enabled: 'Enable link policy',
        groups_humanization_response_cleanup_enabled: 'Enable outgoing cleanup',
        groups_humanization_response_cleanup_max_chars: 'Cleaned max chars',
        groups_recent_enabled: 'Enable recent context',
        groups_recent_enabled_hint: 'Inject recent messages from the current group before replying.',
        groups_recent_limit: 'Message limit',
        groups_recent_limit_hint: 'Maximum recent messages to read.',
        groups_recent_minutes: 'Time window (minutes)',
        groups_recent_minutes_hint: 'Only read messages within this time window.',
        groups_alias_sync_cooldown_minutes: 'Alias refresh cooldown (minutes)',
        groups_alias_sync_cooldown_minutes_hint: 'When a room alias is missing, limit how often member info is resynced per group.',
        groups_basic_proxy: 'Proxy URL',
        groups_basic_proxy_hint: 'Shared by features that opt into proxying, e.g. http://127.0.0.1:7890. Leave empty for direct access.',
        groups_github_notify_title: 'GitHub commit notifications',
        groups_github_notify_desc: 'Receive push webhooks from one repository and send aggregated commits to a selected WeChat group.',
        groups_github_notify_enabled: 'Enable commit notifications',
        groups_github_notify_enabled_hint: 'Only signed push events matching the repository, branch, and target group are processed.',
        groups_github_repository: 'Repository full name',
        groups_github_repository_hint: 'Use owner/repository, for example yideng966/LightAgent.',
        groups_github_branches: 'Notification branches',
        groups_github_branches_hint: 'Separate branches with commas or new lines. Leave empty to allow all branches.',
        groups_github_target_room: 'Target group',
        groups_github_target_room_hint: 'Only stable groups selected under Groups & admins are available.',
        groups_github_target_room_placeholder: 'Select a notification group',
        groups_github_target_room_empty: 'Select a target under Groups & admins first',
        groups_github_target_room_saved: 'saved',
        groups_github_max_commits: 'Maximum commits per message',
        groups_github_max_commits_hint: 'Expand between 1 and 20 commits from each push.',
        groups_github_retry_hours: 'Maximum retry time (hours)',
        groups_github_retry_hours_hint: 'Retry while the group is offline or identity is unresolved, from 1 to 720 hours.',
        groups_github_retention_days: 'Deduplication retention (days)',
        groups_github_retention_days_hint: 'Retain each GitHub delivery record for 1 to 365 days.',
        groups_github_webhook_url: 'Webhook URL',
        groups_github_webhook_url_hint: 'Use this HTTPS address as the GitHub webhook Payload URL.',
        groups_github_secret: 'Webhook secret',
        groups_github_secret_hint: 'Enter a new value to save it. Leaving it blank keeps the configured secret.',
        groups_github_secret_placeholder: 'Enter the same strong secret used by GitHub',
        groups_github_secret_from_environment: 'Managed by the LIGHTAGENT_GITHUB_WEBHOOK_SECRET environment variable.',
        groups_github_secret_from_config: 'Saved in local configuration. The actual value is never returned.',
        groups_github_secret_not_configured: 'No secret is configured. Enter one before enabling notifications.',
        groups_github_secret_show: 'Show secret',
        groups_github_secret_hide: 'Hide secret',
        groups_rooms_title: 'Groups & admins',
        groups_rooms_desc: 'Choose WeChat groups the bot may answer in and configure admins for persistent/write actions.',
        groups_rooms_select_label: 'Target groups',
        groups_rooms_select_placeholder: 'Select WeChat groups',
        groups_rooms_selected_count: '{count} group(s) selected',
        groups_rooms_search_placeholder: 'Search group names...',
        groups_rooms_no_match: 'No matching groups',
        groups_rooms_none_selected: 'No target groups selected',
        groups_rooms_remove: 'Remove group',
        groups_admin_title: 'Group admins',
        groups_admin_desc: 'Admins are scoped by group. The same sender ID is not an admin in other groups automatically.',
        groups_admin_room_label: 'Group',
        groups_admin_member_label: 'Search member',
        groups_admin_member_search_placeholder: 'Search by nickname, WeChat ID, or sender ID',
        groups_admin_member_search: 'Search members',
        groups_admin_add_selected: 'Save admins',
        groups_admin_selected_title: 'Configured admins',
        groups_admin_no_room: 'Select a target group first',
        groups_admin_no_members: 'No matching members. Make sure WeChat is logged in and refresh groups first.',
        groups_admin_no_selected: 'No member selected',
        groups_admin_no_admins: 'No admins configured',
        groups_admin_remove: 'Remove admin',
        groups_admin_permissions_title: 'Admin-gated permissions',
        groups_admin_permissions_desc: 'When checked, ordinary members cannot trigger the corresponding persistent or write action.',
        groups_admin_permission_enabled: 'Gate enabled',
        groups_admin_permission_disabled: 'Gate disabled',
        groups_admin_permission_details: 'Details',
        groups_admin_permission_blocked_behavior: 'Blocked behavior',
        groups_admin_permission_allowed_behavior: 'Still allowed',
        groups_admin_permission_examples: 'Example phrases',
        groups_admin_permission_guard_layers: 'Guard layers',
        groups_admin_permission_affected_objects: 'Affected objects',
        groups_blacklist_title: 'Group blacklist',
        groups_blacklist_desc: 'The blacklist is scoped by group. Matching members are silently skipped for @bot, quote replies, and free-reply decisions.',
        groups_blacklist_room_label: 'Group',
        groups_blacklist_member_label: 'Search member',
        groups_blacklist_member_search_placeholder: 'Search by nickname, WeChat ID, or sender ID',
        groups_blacklist_member_search: 'Search members',
        groups_blacklist_add_selected: 'Save blacklist',
        groups_blacklist_selected_title: 'Configured blacklist',
        groups_blacklist_no_room: 'Select a target group first',
        groups_blacklist_no_members: 'No matching members. Make sure WeChat is logged in and refresh groups first.',
        groups_blacklist_no_selected: 'No member selected',
        groups_blacklist_no_items: 'No blacklist members configured',
        groups_blacklist_remove: 'Remove blacklist member',
        groups_rooms_fallback_hint: 'Fallback names are used only when room IDs are unavailable. One group name per line.',
        groups_room_unnamed: 'Unnamed group',
        groups_room_saved: 'Saved group {n}',
        wechat_group_free_reply_title: 'Free reply',
        wechat_group_free_reply_hint: '“闭嘴” pauses free replies in the current group; you can optionally ignore @ mentions during the mute.',
        wechat_group_free_reply_enabled: 'Enable free reply',
        wechat_group_free_reply_mute_minutes: '“闭嘴” mute duration (minutes)',
        wechat_group_free_reply_mute_minutes_hint: 'When a member sends exactly “闭嘴” while mentioning the bot, ordinary free replies pause in the current group. Range: 1–1440 minutes.',
        wechat_group_free_reply_mute_mentions: 'Ignore @ mentions while muted',
        wechat_group_free_reply_mute_mentions_hint: 'When enabled, new @ mentions are silently ignored during the mute. Quotes and pat events still work.',
        wechat_group_free_reply_groups: 'Free reply groups',
        wechat_group_free_reply_names_label: 'Candidate free reply group names',
        wechat_group_free_reply_force_keywords: 'Force trigger keywords',
        wechat_group_free_reply_force_keywords_hint: 'When matched, bypasses only low-information and score-threshold checks; scope, safety, cooldown and limits still apply.',
        wechat_group_free_reply_level: 'Activity level',
        wechat_group_free_reply_threshold: 'Reply threshold',
        wechat_group_free_reply_interval: 'Minimum interval (seconds)',
        wechat_group_free_reply_hourly: 'Hourly limit',
        wechat_group_free_reply_consecutive: 'Consecutive limit',
        wechat_group_free_reply_ttl: 'Queue TTL (seconds)',
        wechat_group_free_reply_worker_title: 'Worker pool',
        wechat_group_free_reply_worker_max_workers: 'Worker concurrency',
        wechat_group_free_reply_worker_queue_size: 'Queue size limit',
        wechat_group_free_reply_llm_title: 'LLM decision',
        wechat_group_free_reply_llm_enabled: 'Enable LLM decision',
        wechat_group_free_reply_llm_timeout: 'Decision timeout (seconds)',
        wechat_group_free_reply_llm_confidence: 'Minimum confidence',
        wechat_group_free_reply_rules: 'Scoring rules',
        wechat_group_free_reply_last_decision: 'Latest decision',
        wechat_group_free_reply_no_decision: 'No free reply decision yet. After enabling, ordinary group messages go through local scoring and LLM decision.',
        wechat_group_free_reply_worker_status: 'Worker status',
        wechat_group_free_reply_running: 'Running',
        wechat_group_free_reply_stopped: 'Stopped',
        wechat_group_free_reply_room_access: 'Must also be in target group scope',
        wechat_group_free_reply_rule_type: 'Type',
        wechat_group_free_reply_rule_id: 'Rule ID',
        wechat_group_free_reply_rule_description: 'Rule',
        wechat_group_free_reply_rule_score: 'Score / On',
        wechat_group_free_reply_rule_score_hint: 'Positive rules use editable scores; suppressions can be toggled on/off.',
        wechat_group_free_reply_rules_not_persisted: 'Scoring rules were not persisted. Restart the backend process and save again.',
        wechat_group_free_reply_rule_enabled: 'Enabled',
        wechat_group_free_reply_rule_positive: 'Positive',
        wechat_group_free_reply_rule_negative: 'Suppression',
        wechat_group_free_reply_level_quiet: 'Quiet',
        wechat_group_free_reply_level_normal: 'Normal',
        wechat_group_free_reply_level_active: 'Active',
        wechat_group_free_reply_level_crazy: 'High frequency',
        wechat_group_free_reply_decision_score: 'Score',
        wechat_group_free_reply_decision_threshold: 'Threshold',
        wechat_group_free_reply_decision_reasons: 'Reasons',
        wechat_group_free_reply_decision_suppressions: 'Suppressions',
        wechat_group_free_reply_decision_preview: 'Preview',
        wechat_group_free_reply_worker_queue: 'Queue',
        wechat_group_free_reply_worker_approved: 'Approved',
        wechat_group_free_reply_worker_rejected: 'Rejected',
        wechat_group_free_reply_worker_dropped: 'Dropped',
        wechat_group_free_reply_worker_expired: 'Expired',
        wechat_group_free_reply_worker_active: 'Active workers',
        groups_image_title: 'Images',
        groups_image_desc: 'Control WeChat group image understanding and per-group hourly image generation quota.',
        groups_focus_title: 'Focus stack',
        groups_focus_desc: 'Inspect active room focus frames and search new focus archive.',
        groups_focus_room: 'Target room',
        groups_focus_room_hint: 'Focus stacks are isolated by room_id. Switch rooms to inspect different context focus.',
        groups_focus_empty: 'Select at least one target room in "Group switches" first.',
        groups_focus_loading: 'Loading focus stack for the current room...',
        groups_focus_refresh: 'Refresh focus',
        groups_focus_refresh_done: 'Current room focus stack refreshed',
        groups_focus_search_placeholder: 'Search archived focus frames...',
        groups_focus_active_title: 'Active focus stack',
        groups_focus_archive_title: 'Focus archive',
        groups_focus_no_active: 'No active focus for this room yet.',
        groups_focus_no_archive: 'No archived focus matched the current query.',
        groups_focus_enabled: 'Feature',
        groups_focus_recent_message_limit: 'Recent window',
        groups_focus_context_message_limit: 'Context messages',
        groups_focus_stack_depth: 'Stack depth',
        groups_focus_stale_rounds: 'Stale rounds',
        groups_focus_min_keywords: 'Minimum keywords',
        groups_focus_archive_recall_limit: 'Archive recall',
        groups_focus_frame_title: 'Title',
        groups_focus_frame_summary: 'Summary',
        groups_focus_frame_keywords: 'Keywords',
        groups_focus_frame_participants: 'Participants',
        groups_focus_frame_conclusions: 'Conclusions',
        groups_focus_frame_message_count: 'Messages',
        groups_focus_frame_updated_at: 'Updated',
        groups_style_title: 'Style cards',
        groups_style_desc: 'Review group-specific speaking patterns and inject only approved cards into the reply context.',
        groups_style_room: 'Target room',
        groups_style_room_hint: 'Style cards are isolated by room_id. Switch rooms to inspect candidates and active cards.',
        groups_style_empty: 'Select at least one target room in "Group switches" first.',
        groups_style_loading: 'Loading style cards for the current room...',
        groups_style_refresh: 'Refresh candidates',
        groups_style_active_title: 'Active cards',
        groups_style_candidates_title: 'Pending candidates',
        groups_style_no_active: 'No active style cards in this room yet.',
        groups_style_no_candidates: 'No pending candidates right now. Let the group chat continue and refresh later.',
        groups_style_enabled: 'Feature',
        groups_style_learning_enabled: 'Learning',
        groups_style_auto_apply_enabled: 'Auto apply',
        groups_style_context_limit: 'Context limit',
        groups_style_candidate_min_evidence: 'Min evidence',
        groups_style_learning_batch_limit: 'Batch size',
        groups_style_on: 'On',
        groups_style_off: 'Off',
        groups_style_intent: 'Intent',
        groups_style_tone: 'Tone',
        groups_style_trigger_rule: 'Use when',
        groups_style_avoid_rule: 'Avoid',
        groups_style_example: 'Example',
        groups_style_evidence_count: 'Evidence',
        groups_style_approve: 'Approve',
        groups_style_reject: 'Reject',
        groups_style_disable: 'Disable',
        groups_style_review_saved: 'Style card updated',
        groups_emotion_title: 'Emotion and pacing',
        groups_emotion_desc: 'Inspect the current room emotion state and tune time rules plus typing delay.',
        groups_emotion_room: 'Target room',
        groups_emotion_room_hint: 'Emotion state is isolated by room_id; switch rooms to inspect runtime state.',
        groups_emotion_empty: 'Select at least one target room in "Group switches" first.',
        groups_emotion_loading: 'Loading current room emotion state...',
        groups_emotion_state: 'Current emotion',
        groups_emotion_interpreted_state: 'Interpreted state',
        groups_emotion_reply_count: 'Replies in last hour',
        groups_emotion_last_reply: 'Last reply at',
        groups_emotion_last_decision: 'Latest free-reply decision',
        groups_emotion_enabled: 'Enable emotion model',
        groups_emotion_enabled_hint: 'Disable runtime emotion-based proactivity tuning.',
        groups_emotion_decay_minutes: 'Decay window (minutes)',
        groups_emotion_decay_minutes_hint: 'How often the room state drifts back to defaults.',
        groups_emotion_default_valence: 'Default valence',
        groups_emotion_default_energy: 'Default energy',
        groups_emotion_default_sociability: 'Default sociability',
        groups_emotion_time_rules_enabled: 'Enable time rules',
        groups_emotion_time_rules_enabled_hint: 'Free replies are suppressed outside matched windows.',
        groups_emotion_time_rules: 'Time-rule JSON',
        groups_emotion_time_rules_hint: 'Example: [{"days":["mon","tue"],"start":"09:00","end":"18:00"}]',
        groups_emotion_typing_delay_enabled: 'Enable typing delay',
        groups_emotion_typing_delay_enabled_hint: 'Wait before text replies based on message length.',
        groups_emotion_typing_chars_per_second: 'Typing speed (chars/s)',
        groups_emotion_typing_chars_per_second_hint: 'Lower values create longer delays.',
        groups_emotion_refresh: 'Refresh state',
        groups_emotion_reset: 'Reset current room state',
        groups_emotion_reset_confirm: 'Reset the current room emotion state back to defaults?',
        groups_emotion_reset_done: 'Current room emotion state reset',
        groups_emotion_save: 'Save emotion settings',
        groups_emotion_saved: 'Emotion settings saved',
        groups_emotion_metric_valence: 'Valence',
        groups_emotion_metric_energy: 'Energy',
        groups_emotion_metric_sociability: 'Sociability',
        groups_emotion_state_withdrawn: 'Withdrawn',
        groups_emotion_state_engaged: 'Engaged',
        groups_emotion_state_guarded: 'Guarded',
        groups_emotion_state_steady: 'Steady',
        groups_emotion_time_rules_invalid: 'Time-rule JSON is invalid',
        groups_sticker_title: 'Stickers',
        groups_sticker_desc: 'Manage collected room stickers, edit descriptions, and fill pending descriptions with vision.',
        groups_sticker_room: 'Target room',
        groups_sticker_room_hint: 'Sticker assets are isolated by room_id. Disabled stickers will no longer be returned to this room.',
        groups_sticker_empty: 'Select at least one target room in "Group switches" first.',
        groups_sticker_loading: 'Loading stickers for the current room...',
        groups_sticker_refresh: 'Refresh list',
        groups_sticker_search_placeholder: 'Search descriptions or file names...',
        groups_sticker_list_title: 'Sticker list',
        groups_sticker_no_items: 'No stickers matched the current filters.',
        groups_sticker_status: 'Status',
        groups_sticker_status_all: 'All',
        groups_sticker_status_active: 'Active',
        groups_sticker_status_disabled: 'Disabled',
        groups_sticker_enabled: 'Feature',
        groups_sticker_enabled_hint: 'When off, this channel will not search, inject, or send stickers.',
        groups_sticker_auto_collect_enabled: 'Auto collect',
        groups_sticker_auto_collect_enabled_hint: 'Automatically collect group sticker messages into searchable assets.',
        groups_sticker_context_limit: 'Context limit',
        groups_sticker_context_limit_hint: 'Max stickers returned in a single search or context injection.',
        groups_sticker_reply_percent: 'Proactive reply rate (%)',
        groups_sticker_reply_percent_hint: 'Target sticker rate in casual chat; 0 sends stickers only on explicit requests.',
        groups_sticker_max_size_mb: 'Max size (MB)',
        groups_sticker_max_size_mb_hint: 'Maximum sticker file size allowed for collect and send.',
        groups_sticker_daily_send_limit: 'Daily send limit',
        groups_sticker_daily_send_limit_hint: 'Max sticker sends per room per day.',
        groups_sticker_online_search_enabled: 'Online search',
        groups_sticker_online_search_enabled_hint: 'Allow online candidates when local stickers are missing or unsuitable.',
        groups_sticker_online_allow_gif: 'Allow GIF',
        groups_sticker_online_allow_gif_hint: 'Whether online candidates may include animated GIFs.',
        groups_sticker_online_provider: 'Online provider',
        groups_sticker_online_search_count: 'Online candidates',
        groups_sticker_online_search_count_hint: 'Max online candidates returned per search.',
        groups_sticker_cooldown_seconds: 'Send cooldown (s)',
        groups_sticker_cooldown_seconds_hint: 'Minimum interval between sticker sends in the same room.',
        groups_sticker_settings_title: 'Sticker settings',
        groups_sticker_settings_hint: 'Click save to apply changes. List refresh keeps unsaved edits.',
        groups_sticker_storage_dir: 'Storage dir',
        groups_sticker_online_endpoint: 'Online endpoint',
        groups_sticker_online_allowed_domains: 'Allowed domains',
        groups_sticker_online_allowed_domains_placeholder: 'One domain per line, e.g. biaoqing.gtimg.com',
        groups_sticker_save: 'Save sticker settings',
        groups_sticker_saved: 'Sticker settings saved',
        groups_sticker_online_test: 'Test online search',
        groups_sticker_online_test_placeholder: 'Enter a mood or keyword...',
        groups_sticker_online_test_done: 'Online search complete',
        groups_sticker_description: 'Description',
        groups_sticker_file_name: 'File name',
        groups_sticker_source_message_id: 'Source message',
        groups_sticker_use_count: 'Use count',
        groups_sticker_updated_at: 'Updated',
        groups_sticker_disable: 'Disable',
        groups_sticker_disable_confirm: 'Disable this sticker for the current room?',
        groups_sticker_disabled_done: 'Sticker disabled',
        groups_sticker_preview_alt: 'Sticker preview',
        groups_sticker_description_status_loading: 'Counting pending descriptions...',
        groups_sticker_description_status_failed: 'Failed to load pending-description counts',
        groups_sticker_description_status_retry: 'Retry counts',
        groups_sticker_description_pending_summary: '{pending} pending, {processable} processable',
        groups_sticker_description_file_issues: '{missing} files missing and {empty} files empty',
        groups_sticker_describe_pending: 'Fill descriptions with vision',
        groups_sticker_describe_confirm: 'Use the configured vision model for {count} stickers in this room? The database will be backed up first.',
        groups_sticker_describe_starting: 'Starting...',
        groups_sticker_describe_running: 'Processing {processed}/{total}',
        groups_sticker_describe_busy: 'Another room is processing',
        groups_sticker_describe_started: 'Sticker description job started',
        groups_sticker_describe_result: '{updated} updated, {failed} failed, {skipped} skipped',
        groups_sticker_describe_completed: 'Vision processing completed',
        groups_sticker_describe_partial_failed: 'Completed with items still requiring retry',
        groups_sticker_describe_failed: 'Batch vision failed. Check the model configuration and retry.',
        groups_sticker_description_edit: 'Edit description',
        groups_sticker_description_edit_label: 'Sticker description',
        groups_sticker_description_edit_hint: '1–200 characters. Enter saves; Esc cancels.',
        groups_sticker_description_save: 'Save',
        groups_sticker_description_cancel: 'Cancel',
        groups_sticker_description_saved: 'Sticker description saved',
        groups_sticker_description_invalid: 'Description must contain 1–200 characters',
        groups_sticker_description_semantic_required: 'Use a meaningful description instead of a placeholder, XML, numeric ID, or long hash',
        groups_sticker_description_changed: 'The description changed elsewhere. Refresh and try again.',
        groups_sticker_description_not_found: 'This sticker was not found in the current room',
        groups_sticker_description_no_processable: 'No pending descriptions can be processed in this room',
        groups_sticker_description_job_running: 'A sticker description job is already running',
        groups_image_understanding_enabled: 'Enable image understanding',
        groups_image_understanding_enabled_hint: 'Calls the existing vision tool only when an image directly mentions or quotes the bot.',
        groups_image_comment_enabled: 'Allow image-only comments',
        groups_image_comment_enabled_hint: 'Let the bot produce a short reply from the vision summary when the user sends only an image.',
        groups_image_free_reply_understanding_enabled: 'Enable image understanding for free replies',
        groups_image_free_reply_understanding_enabled_hint: 'Ambient group images are judged by free-reply rules before the vision tool is called.',
        groups_image_prompt: 'Image understanding prompt',
        groups_image_prompt_hint: 'Question sent to the existing vision tool.',
        groups_image_cache_minutes: 'Summary cache minutes',
        groups_image_cache_minutes_hint: 'Cache time for the same image summary, from 1 to 120.',
        groups_multimodal_context_enabled: 'Enable global multimodal context',
        groups_multimodal_context_enabled_hint: 'Assemble quote, forward, video and image summaries in the unified context layer.',
        groups_multimodal_image_context_enabled: 'Enable image context injection',
        groups_multimodal_image_context_enabled_hint: 'Inject a vision summary into the current reply context when an image candidate is matched.',
        groups_multimodal_free_reply_image_context_enabled: 'Allow free replies to bind recent images',
        groups_multimodal_free_reply_image_context_enabled_hint: 'After ambient text passes free-reply judging, it may bind a recent image under strict rules. Disabled by default.',
        groups_multimodal_same_sender_window_seconds: 'Same-sender follow-up window (sec)',
        groups_multimodal_same_sender_window_seconds_hint: 'Window for short follow-ups like "is this real" after the same sender posts an image, from 5 to 600.',
        groups_multimodal_unique_image_window_seconds: 'Unique recent image window (sec)',
        groups_multimodal_unique_image_window_seconds_hint: 'Bind only when the short window has one group image and the text clearly refers to it, from 5 to 600.',
        groups_multimodal_quote_sender_window_minutes: 'Quoted sender lookup window (min)',
        groups_multimodal_quote_sender_window_minutes_hint: 'If quoted message ID does not resolve to an image, search that sender recent images, from 1 to 120.',
        groups_multimodal_max_recent_messages: 'Max recent messages to inspect',
        groups_multimodal_max_recent_messages_hint: 'Maximum archived messages scanned for multimodal candidate selection, from 1 to 100.',
        groups_image_create_hourly_limit: 'Hourly image generation limit',
        groups_image_create_hourly_limit_hint: 'Successful image generation requests per WeChat group per hour; 0 disables group image generation.',
        groups_image_generation_proxy_enabled: 'Proxy selected image result domains',
        groups_image_generation_proxy_enabled_hint: 'The generation API remains direct. Only matching result-image downloads use the proxy from Basic settings.',
        groups_image_generation_proxy_domains: 'Proxy domains',
        groups_image_generation_proxy_domains_hint: 'One domain per line. Wildcards like *.grok.com are supported. Configure the proxy URL in Basic settings.',
        groups_image_generation_proxy_domains_placeholder: 'assets.grok.com\n*.grok.com',
        groups_video_understanding_enabled: 'Enable video context',
        groups_video_understanding_enabled_hint: 'When a video directly mentions or quotes the bot, send it through the text context path. Disabled by default.',
        groups_forward_preview_enabled: 'Enable forward preview',
        groups_forward_preview_enabled_hint: 'Inject concise metadata for merged chat forwards instead of large raw content.',
        groups_quote_context_enabled: 'Enable quote context',
        groups_quote_context_enabled_hint: 'Resolve quoted content by message ID first, reducing accidental matches against recent messages.',
        groups_persona_title: 'Persona',
        groups_persona_desc: 'Only one custom persona is kept. It applies to WeChat group replies after saving.',
        groups_memory_title: 'Long-term memory',
        groups_memory_desc: 'Maintain room memory, room-scoped member profiles, and prompt injection previews.',
        groups_profiles_title: 'Member profiles',
        groups_profiles_desc: 'Profiles are isolated by room; each member has at most one profile in the current room.',
        groups_profiles_room_filter: 'Room',
        groups_profiles_room_all: 'All rooms',
        groups_profiles_search_placeholder: 'Search sender ID, nickname, or alias',
        groups_profiles_search: 'Search profiles',
        groups_profiles_result_count: '{count} profiles',
        groups_profiles_no_data: 'No profiles in this room; create one from a room member',
        groups_profiles_create_member: 'Select member',
        groups_profiles_create: 'New profile',
        groups_profiles_no_members: 'No room members available for a new profile',
        groups_profiles_list_title: 'Profile list',
        groups_profiles_detail_title: 'Profile details',
        groups_profiles_detail_empty: 'Select a member from the left to inspect details.',
        groups_profiles_summary_title: 'Read-only summary',
        groups_profiles_content_title: 'Profile content',
        groups_profiles_rooms_title: 'Current room',
        groups_profiles_last_seen: 'Last seen',
        groups_profiles_name_records: 'Name records {count}',
        groups_profiles_edit_title: 'Manual correction',
        groups_profiles_save: 'Save correction',
        groups_profiles_room_empty: 'No room source recorded',
        groups_profiles_metric_messages: 'Messages',
        groups_profiles_metric_activity: 'Activity',
        groups_profiles_metric_intimacy: 'Familiarity',
        groups_memory_no_room: 'Select at least one room ID in Group switches first.',
        groups_memory_group_title: 'Group memory',
        groups_memory_group_hint: 'Save stable long-term facts for the current group, such as rules, preferences, projects, and agreements.',
        groups_memory_content_label: 'Memory content',
        groups_memory_content_placeholder: 'Enter long-term memory for this group only',
        groups_memory_summary_label: 'Source summary',
        groups_memory_save: 'Save group memory',
        groups_memory_saved: 'Group memory saved',
        groups_memory_empty: 'No group memory for this group',
        groups_memory_search_placeholder: 'Search current group memory',
        groups_memory_search: 'Search',
        groups_memory_disable: 'Disable',
        groups_memory_disabled: 'Disabled',
        groups_memory_count_label: 'Memory {count}',
        groups_memory_profile_count_label: 'Profiles {count}',
        groups_memory_profiles_title: 'Member profiles',
        groups_memory_profiles_hint: 'Each room keeps independent profiles keyed by stable room and stable member.',
        groups_memory_profiles_moved_hint: 'Member profiles moved to Member profiles. This page now keeps room memories, injection preview, and learning runs.',
        groups_memory_member_lookup_label: 'Find member',
        groups_memory_member_lookup_placeholder: 'Search by WeChat ID, sender ID, or nickname',
        groups_memory_member_lookup_hint: 'Searches archived messages in the current group. You can still enter sender ID manually.',
        groups_memory_member_lookup_empty: 'No matching members',
        groups_memory_member_lookup_searching: 'Searching...',
        groups_memory_member_lookup_select: 'Select',
        groups_memory_sender_id: 'sender ID',
        groups_memory_sender_name: 'Nickname',
        groups_memory_aliases: 'Aliases',
        groups_memory_role: 'Role',
        groups_memory_preferences: 'Preferences',
        groups_memory_common_words: 'Common words',
        groups_memory_interaction: 'Interaction style',
        groups_memory_boundaries: 'Known boundaries',
        groups_memory_evidence: 'Evidence',
        groups_memory_profile_save: 'Save profile',
        groups_memory_profile_saved: 'Profile saved',
        groups_memory_profiles_empty: 'No member profiles for this group',
        groups_memory_revisions_title: 'Revisions',
        groups_memory_revisions_empty: 'Select a profile to view revisions',
        groups_memory_preview_title: 'Injection preview',
        groups_memory_preview_hint: 'Read-only preview of <wechat-group-memory>; it does not call models or write memory.',
        groups_memory_preview_query: 'Simulated query',
        groups_memory_preview_mentions: 'Mentioned sender IDs',
        groups_memory_preview_run: 'Preview',
        groups_memory_preview_empty: 'No memory would be injected',
        groups_memory_tab_manual: 'Memory',
        groups_memory_tab_auto: 'Learning',
        groups_memory_auto_title: 'Learn from chat history',
        groups_memory_auto_hint: 'Learn room memories and room-scoped profiles independently from new archived messages.',
        groups_memory_knowledge_enabled: 'Enable group memory',
        groups_memory_profile_enabled: 'Enable member profiles',
        groups_memory_learning_enabled: 'Enable learning',
        groups_memory_profile_context_limit: 'Profile context limit',
        groups_memory_group_context_limit: 'Group memory context limit',
        groups_memory_learning_batch_limit: 'Learning batch size',
        groups_memory_learning_profile_min_messages: 'Profile min messages',
        groups_memory_learning_profile_sample_limit: 'Profile sample size',
        groups_memory_learning_group_memory_min_messages: 'Group memory min messages',
        groups_memory_learning_group_memory_window_minutes: 'Group memory window minutes',
        groups_memory_auto_enabled: 'Enable auto distillation',
        groups_memory_auto_apply_threshold: 'Auto-apply threshold',
        groups_memory_candidate_threshold: 'Candidate threshold',
        groups_memory_window_minutes: 'Window minutes',
        groups_memory_message_limit: 'Max messages',
        groups_memory_auto_apply_group: 'Auto-write group memories',
        groups_memory_auto_apply_member: 'Auto-write member profiles',
        groups_memory_auto_save: 'Save config',
        groups_memory_auto_saved: 'Auto-generation config saved',
        groups_memory_auto_run: 'Generate from recent chat',
        groups_memory_auto_runs: 'Runs',
        groups_memory_auto_candidates: 'Learning records',
        groups_memory_auto_no_runs: 'No runs for this room',
        groups_memory_auto_no_candidates: 'No candidates for this room',
        groups_memory_auto_approve: 'Approve',
        groups_memory_auto_reject: 'Reject',
        groups_memory_auto_rejected: 'Candidate rejected',
        groups_memory_auto_approved: 'Candidate applied',
        groups_memory_auto_ran: 'Auto-generation finished',
        groups_memory_auto_status_pending: 'Pending',
        groups_memory_auto_status_auto_applied: 'Auto-applied',
        groups_memory_auto_status_approved: 'Approved',
        groups_memory_auto_status_rejected: 'Rejected',
        groups_memory_auto_status_failed: 'Failed',
        groups_memory_run_messages: 'Messages',
        groups_memory_run_profiles: 'Profiles',
        groups_memory_run_memories: 'Memories',
        groups_error_summary_load_failed: 'Summary load failed',
        groups_error_memory_load_failed: 'Memory load failed',
        groups_error_runs_load_failed: 'Runs load failed',
        groups_error_save_failed: 'Save failed',
        groups_error_disable_failed: 'Disable failed',
        groups_error_preview_failed: 'Preview failed',
        groups_error_learning_failed: 'Learning failed',
        groups_error_approve_failed: 'Approve failed',
        groups_error_reject_failed: 'Reject failed',
        groups_error_room_required: 'Select a target room',
        groups_error_sender_required: 'Sender ID is required',
        groups_error_unknown_action: 'Unknown action',
        wecom_scan_btn: 'Scan to Create WeCom Bot', wecom_scan_desc: 'Scan with WeCom to create a bot instantly',
        wecom_scan_success: 'Bot created, starting channel...',
        wecom_scan_fail: 'Bot creation failed',
        wecom_mode_scan: 'Scan QR', wecom_mode_manual: 'Manual',
        feishu_scan_btn: 'One-click Create Feishu App',
        feishu_scan_desc: 'Scan with Feishu App to create an app with all required permissions pre-configured',
        feishu_scan_replace_desc: 'Scan with Feishu App to create a new bot — will overwrite the current App ID / Secret',
        feishu_scan_loading: 'Requesting QR code from Feishu...',
        feishu_scan_waiting: 'Waiting for scan...',
        feishu_scan_tip: 'QR code expires in 10 minutes, single use only',
        feishu_scan_open_link: 'Or click here to open in browser',
        feishu_scan_success: 'App created, starting channel...',
        feishu_scan_expired: 'QR code expired, please retry',
        feishu_scan_denied: 'Authorization cancelled',
        feishu_scan_fail: 'App creation failed',
        feishu_scan_retry: 'Retry',
        feishu_mode_scan: 'Scan QR', feishu_mode_manual: 'Manual',
        tasks_title: 'Scheduled Tasks', tasks_desc: 'View and manage scheduled tasks',
        tasks_coming: 'Coming Soon', tasks_coming_desc: 'Scheduled task management will be available here',
        task_add_btn: 'Add Task',
        task_edit_title: 'Edit Task',
        task_add_title: 'Add Task',
        task_name: 'Task Name',
        task_enabled: 'Enable Task',
        task_schedule_type: 'Schedule Type',
        task_schedule_cron: 'Cron Expression',
        task_schedule_interval: 'Fixed Interval',
        task_schedule_once: 'One-time Task',
        task_cron_expression: 'Cron Expression',
        task_cron_hint: 'Format: minute hour day month weekday, e.g. "0 9 * * *" means daily at 9:00',
        task_interval_seconds: 'Interval (seconds)',
        task_interval_hint: 'Minimum 60 seconds, e.g. 3600 means once per hour',
        task_once_time: 'Execution Time',
        task_action_type: 'Action Type',
        task_action_send_message: 'Send Message',
        task_action_agent_task: 'AI Task',
        task_channel_type: 'Channel Type',
        task_channel_hint: 'Select the channel to send scheduled messages',
        task_message_content: 'Message Content',
        task_task_description: 'Task Description',
        task_delete_btn: 'Delete Task',
        task_delete_confirm_title: 'Delete Task',
        task_delete_confirm_msg: 'Delete this scheduled task? This action cannot be undone.',
        logs_title: 'Logs', logs_desc: 'Real-time log output (run.log)',
        logs_live: 'Live', logs_coming_msg: 'Log streaming will be available here. Connects to run.log for real-time output similar to tail -f.',
        new_chat: 'New Chat',
        session_history: 'History',
        today: 'Today', yesterday: 'Yesterday', earlier: 'Earlier',
        delete_session_confirm: 'Delete this session? All messages will be removed.',
        delete_session_title: 'Delete Session',
        rename_session: 'Rename',
        delete_message_confirm: 'Delete this message?',
        delete_message_title: 'Delete Message',
        edit_disabled_reply_active: 'Reply is being generated; editing is temporarily unavailable.',
        delete_disabled_reply_active: 'Reply is being generated; deletion is temporarily unavailable.',
        untitled_session: 'New Chat',
        context_cleared: '— Context above has been cleared —',
        tip_new_chat: 'New Chat',
        tip_clear_context: 'Clear Context',
        tip_attach: 'Add Attachment',
        attach_menu_file: 'Upload File',
        mic_idle_title: 'Click to record, click again to stop',
        mic_recording_title: 'Recording, click to stop',
        mic_busy_title: 'Transcribing…',
        mic_permission_denied: 'Cannot access microphone — check browser permissions',
        mic_too_short: 'Recording too short, please retry',
        mic_error: 'Speech recognition failed',
        speak_msg: 'Read this reply aloud',
        voice_reply_mode_label: 'Voice reply policy',
        voice_reply_off: 'Off',
        voice_reply_if_voice: 'Voice only if voice input',
        voice_reply_always: 'Always reply with voice',
        attach_menu_folder: 'Upload Folder',
        confirm_yes: 'Confirm',
        confirm_cancel: 'Cancel',
        error_send: 'Failed to send. Please try again.', error_timeout: 'Request timeout. Please try again.',
        thinking_in_progress: 'Thinking...', thinking_done: 'Thought', thinking_duration: 'Duration',
        edit_message: 'Edit message',
        regenerate_response: 'Regenerate',
        edit_save: 'Save and send',
        edit_cancel: 'Cancel',
    }
};

// Resolve language by priority: user choice (localStorage) -> backend-detected
// (lightagent_lang) -> browser language -> 'zh'. Shares __lightAgentResolveLang__ defined in
// chat.html; falls back to a local resolver if loaded standalone.
let currentLang = (typeof window.__lightAgentResolveLang__ === 'function')
    ? window.__lightAgentResolveLang__()
    : (function () {
        const norm = (raw) => {
            if (!raw) return '';
            const v = String(raw).trim().toLowerCase();
            if (v === 'auto') return '';
            if (v.indexOf('zh') === 0) return 'zh';
            if (v.indexOf('en') === 0) return 'en';
            return '';
        };
        return norm(localStorage.getItem('lightagent_lang'))
            || norm(window.__LIGHTAGENT_DEFAULT_LANG__)
            || norm(navigator.language)
            || 'zh';
    })();

function t(key) {
    return (I18N[currentLang] && I18N[currentLang][key]) || (I18N.en[key]) || key;
}

// Resolve a localized label that may be either a plain string or
// a {zh, en} object returned by the backend.
function localizedLabel(label) {
    if (label && typeof label === 'object') {
        return label[currentLang] || label.en || label.zh || '';
    }
    return label || '';
}

function applyI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
        el.innerHTML = t(el.dataset.i18nHtml);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        el.placeholder = t(el.dataset['i18nPlaceholder']);
    });
    document.querySelectorAll('[data-tip-key]').forEach(el => {
        el.setAttribute('data-tooltip', t(el.dataset.tipKey));
    });
    installCfgTipPortal();
    const langLabel = document.getElementById('lang-label');
    if (langLabel) langLabel.textContent = currentLang === 'zh' ? '中文' : 'EN';
    // Point the docs link to the locale-specific documentation site.
    const docsLink = document.getElementById('docs-link');
    if (docsLink) docsLink.href = 'https://github.com/yideng966/LightAgent/tree/master/docs';
}

// Single entry point for switching language. Updates the in-memory language,
// persists the user choice locally, re-renders the UI, and binds the choice to
// the backend `lightagent_lang` config so logs / agent replies / CLI follow suit.
function setLanguage(lang) {
    const next = (lang === 'en') ? 'en' : 'zh';
    if (next === currentLang) {
        // Still persist + sync in case storage/backend drifted from the UI.
        syncLanguageToBackend(next);
        return;
    }
    currentLang = next;
    localStorage.setItem('lightagent_lang', currentLang);
    applyI18n();
    _applyInputTooltips();
    // Re-render views whose DOM is built in JS (data-i18n alone does not
    // cover strings interpolated via t() into innerHTML).
    try { rerenderDynamicViews(); } catch (e) {}
    // Keep the language switch button and config selector visually in sync.
    try { updateLangControls(); } catch (e) {}
    syncLanguageToBackend(currentLang);
}

// Persist the language to the backend `lightagent_lang` config (best-effort; the UI
// has already switched locally, so a network failure is non-blocking).
function syncLanguageToBackend(lang) {
    try {
        fetch('/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ updates: { lightagent_lang: lang } })
        }).catch(() => {});
    } catch (e) {}
}

// Reflect the current language on both the top-right toggle and the config
// selector (if present), so the two entry points stay synchronized.
function updateLangControls() {
    const langLabel = document.getElementById('lang-label');
    if (langLabel) langLabel.textContent = currentLang === 'zh' ? '中文' : 'EN';
    // The config language picker is the custom .cfg-dropdown component. Only
    // sync it once it has been initialized (i.e. the config panel was opened).
    const sel = document.getElementById('cfg-lang-select');
    if (sel && sel._ddValue !== undefined && sel._ddValue !== currentLang) {
        sel._ddValue = currentLang;
        const textEl = sel.querySelector('.cfg-dropdown-text');
        if (textEl) textEl.textContent = currentLang === 'zh' ? '中文' : 'English';
        sel.querySelectorAll('.cfg-dropdown-item').forEach(i => {
            i.classList.toggle('active', i.dataset.value === currentLang);
        });
    }
}

function toggleLanguage() {
    setLanguage(currentLang === 'zh' ? 'en' : 'zh');
}

// Refresh JS-rendered views after a language switch. Each branch uses the
// lightweight in-memory re-render path (no extra network round-trips).
function rerenderDynamicViews() {
    if (currentView === 'models' && typeof renderModelsView === 'function'
            && modelsState && (modelsState.providers || modelsState.capabilities)) {
        renderModelsView();
    }
    // Reload task list after language switch
    if (currentView === 'tasks') {
        tasksLoaded = false;
        loadTasksView();
    }
    if (currentView === 'groups') {
        renderGroupsView();
    }
}

// Floating tooltip portal for [data-tip-key] elements. Tooltip nodes are
// appended to <body> so they aren't clipped by overflow:hidden ancestors
// (e.g. the config panel's scroll container).
let _cfgTipPortalEl = null;
let _cfgTipPortalInstalled = false;
function installCfgTipPortal() {
    if (_cfgTipPortalInstalled) return;
    _cfgTipPortalInstalled = true;

    const showTip = (target) => {
        const text = target.getAttribute('data-tooltip');
        if (!text) return;
        if (!_cfgTipPortalEl) {
            _cfgTipPortalEl = document.createElement('div');
            _cfgTipPortalEl.className = 'cfg-tip-floating';
            document.body.appendChild(_cfgTipPortalEl);
        }
        _cfgTipPortalEl.textContent = text;
        const rect = target.getBoundingClientRect();
        // Render once to measure, then position above the target, centered.
        _cfgTipPortalEl.style.left = '0px';
        _cfgTipPortalEl.style.top = '0px';
        _cfgTipPortalEl.classList.add('show');
        const tipRect = _cfgTipPortalEl.getBoundingClientRect();
        let left = rect.left + rect.width / 2 - tipRect.width / 2;
        // Clamp horizontally to the viewport with an 8px gutter.
        left = Math.max(8, Math.min(left, window.innerWidth - tipRect.width - 8));
        const top = rect.top - tipRect.height - 6;
        _cfgTipPortalEl.style.left = left + 'px';
        _cfgTipPortalEl.style.top = top + 'px';
    };
    const hideTip = () => {
        if (_cfgTipPortalEl) _cfgTipPortalEl.classList.remove('show');
    };

    document.addEventListener('mouseover', (e) => {
        const target = e.target.closest('[data-tip-key]');
        if (target) showTip(target);
    });
    document.addEventListener('mouseout', (e) => {
        const target = e.target.closest('[data-tip-key]');
        if (target) hideTip();
    });
    // Hide on scroll/resize so the tooltip doesn't drift away from its anchor.
    window.addEventListener('scroll', hideTip, true);
    window.addEventListener('resize', hideTip);
}

// =====================================================================
// Theme
// =====================================================================
let currentTheme = localStorage.getItem('lightagent_theme') || 'dark';

function applyTheme() {
    const root = document.documentElement;
    if (currentTheme === 'dark') {
        root.classList.add('dark');
        document.getElementById('theme-icon').className = 'fas fa-sun';
        document.getElementById('hljs-light').disabled = true;
        document.getElementById('hljs-dark').disabled = false;
    } else {
        root.classList.remove('dark');
        document.getElementById('theme-icon').className = 'fas fa-moon';
        document.getElementById('hljs-light').disabled = false;
        document.getElementById('hljs-dark').disabled = true;
    }
}

function toggleTheme() {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('lightagent_theme', currentTheme);
    applyTheme();
}

// =====================================================================
// Sidebar & Navigation
// =====================================================================
const VIEW_META = {
    chat:     { group: 'nav_chat',    page: 'menu_chat' },
    config:   { group: 'nav_manage',  page: 'menu_config' },
    models:   { group: 'nav_manage',  page: 'menu_models' },
    skills:   { group: 'nav_manage',  page: 'menu_skills' },
    memory:   { group: 'nav_manage',  page: 'menu_memory' },
    knowledge:{ group: 'nav_manage',  page: 'menu_knowledge' },
    channels: { group: 'nav_manage',  page: 'menu_channels' },
    groups:   { group: 'nav_manage',  page: 'menu_groups' },
    tasks:    { group: 'nav_manage',  page: 'menu_tasks' },
    logs:     { group: 'nav_monitor', page: 'menu_logs' },
};

let currentView = 'chat';

function navigateTo(viewId) {
    if (!VIEW_META[viewId]) return;
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const target = document.getElementById('view-' + viewId);
    if (target) target.classList.add('active');
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.classList.toggle('active', item.dataset.view === viewId);
    });
    const meta = VIEW_META[viewId];
    document.getElementById('breadcrumb-group').textContent = t(meta.group);
    document.getElementById('breadcrumb-group').dataset.i18n = meta.group;
    document.getElementById('breadcrumb-page').textContent = t(meta.page);
    document.getElementById('breadcrumb-page').dataset.i18n = meta.page;
    currentView = viewId;
    if (window.innerWidth < 1024) closeSidebar();
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const isOpen = !sidebar.classList.contains('-translate-x-full');
    if (isOpen) {
        closeSidebar();
    } else {
        sidebar.classList.remove('-translate-x-full');
        overlay.classList.remove('hidden');
    }
}

function closeSidebar() {
    document.getElementById('sidebar').classList.add('-translate-x-full');
    document.getElementById('sidebar-overlay').classList.add('hidden');
}

document.querySelectorAll('.menu-group > button').forEach(btn => {
    btn.addEventListener('click', () => {
        btn.parentElement.classList.toggle('open');
    });
});

document.querySelectorAll('.sidebar-item').forEach(item => {
    item.addEventListener('click', () => navigateTo(item.dataset.view));
});

window.addEventListener('resize', () => {
    if (window.innerWidth >= 1024) {
        document.getElementById('sidebar').classList.remove('-translate-x-full');
        document.getElementById('sidebar-overlay').classList.add('hidden');
    } else {
        if (!document.getElementById('sidebar').classList.contains('-translate-x-full')) {
            closeSidebar();
        }
    }
});

// =====================================================================
// Markdown Renderer
// =====================================================================
const FALLBACK_HLJS = {
    getLanguage() { return false; },
    highlight(str) { return { value: escapeHtml(str) }; },
    highlightAuto(str) { return { value: escapeHtml(str) }; },
    highlightElement() {},
};

function getHljs() {
    return window.hljs || FALLBACK_HLJS;
}

function createMd() {
    const hljsLib = getHljs();
    const mdFactory = window.markdownit;
    if (typeof mdFactory !== 'function') {
        return {
            render(text) {
                return `<p>${escapeHtml(text || '')}</p>`;
            }
        };
    }
    const md = mdFactory({
        html: false, breaks: true, linkify: true, typographer: true,
        highlight: function(str, lang) {
            if (lang && hljsLib.getLanguage(lang)) {
                try { return hljsLib.highlight(str, { language: lang }).value; } catch (_) {}
            }
            return hljsLib.highlightAuto(str).value;
        }
    });
    const defaultLinkOpen = md.renderer.rules.link_open || function(tokens, idx, options, env, self) {
        return self.renderToken(tokens, idx, options);
    };
    md.renderer.rules.link_open = function(tokens, idx, options, env, self) {
        tokens[idx].attrPush(['target', '_blank']);
        tokens[idx].attrPush(['rel', 'noopener noreferrer']);
        return defaultLinkOpen(tokens, idx, options, env, self);
    };
    return md;
}

const md = createMd();

const VIDEO_EXT_RE = /\.(?:mp4|webm|mov|avi|mkv)$/i;  // tested against URL without query string
const IMAGE_EXT_RE = /\.(?:jpg|jpeg|png|gif|webp|bmp|svg)$/i;  // tested against URL without query string

function _toWebUrl(url) {
    if (/^\/[A-Za-z]/.test(url) && !url.startsWith('/api/')) {
        return '/api/file?path=' + encodeURIComponent(url);
    }
    if (/^file:\/\/\//i.test(url)) {
        return '/api/file?path=' + encodeURIComponent(url.replace(/^file:\/\/\//i, '/'));
    }
    return url;
}

function _buildVideoHtml(url) {
    const webUrl = _toWebUrl(url);
    const fileName = url.split('/').pop().split('?')[0];
    return `<div style="margin:10px 0;">` +
        `<video controls preload="metadata" ` +
        `style="max-width:100%;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.15);display:block;">` +
        `<source src="${webUrl}"></video>` +
        `<a href="${webUrl}" target="_blank" ` +
        `style="display:inline-flex;align-items:center;gap:4px;margin-top:4px;font-size:12px;color:#8b8fa8;text-decoration:none;">` +
        `<i class="fas fa-download"></i> ${escapeHtml(fileName)}</a></div>`;
}

function _openImageLightbox(src) {
    let overlay = document.getElementById('lightagent-lightbox');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'lightagent-lightbox';
        overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.85);display:flex;align-items:center;justify-content:center;cursor:zoom-out;opacity:0;transition:opacity .2s';
        overlay.onclick = () => { overlay.style.opacity = '0'; setTimeout(() => overlay.style.display = 'none', 200); };
        const img = document.createElement('img');
        img.id = 'lightagent-lightbox-img';
        img.style.cssText = 'max-width:92vw;max-height:92vh;border-radius:8px;box-shadow:0 4px 24px rgba(0,0,0,0.5);object-fit:contain;';
        img.onclick = (e) => e.stopPropagation();
        overlay.appendChild(img);
        document.body.appendChild(overlay);
    }
    overlay.querySelector('#lightagent-lightbox-img').src = src;
    overlay.style.display = 'flex';
    requestAnimationFrame(() => overlay.style.opacity = '1');
}

function _buildImageHtml(url) {
    const webUrl = _toWebUrl(url);
    const safeUrl = webUrl.replace(/"/g, '&quot;');
    return `<div style="margin:10px 0;">` +
        `<img src="${safeUrl}" alt="image" loading="lazy" ` +
        `onclick="_openImageLightbox(this.src)" ` +
        `style="max-width:520px;width:100%;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.15);display:block;cursor:zoom-in;">` +
        `</div>`;
}

function injectVideoPlayers(html) {
    // Step 1: replace markdown-it anchor tags whose href points to a video file.
    const step1 = html.replace(
        /<a\s+href="(https?:\/\/[^"]+)"[^>]*>[^<]*<\/a>/gi,
        (match, url) => VIDEO_EXT_RE.test(url.split('?')[0]) ? _buildVideoHtml(url) : match
    );
    // Step 2: replace any remaining bare video URLs in text nodes (not inside HTML tags).
    // Split on HTML tags to avoid touching src/href attributes already in markup.
    return step1.split(/(<[^>]+>)/).map((chunk, idx) => {
        // Even indices are text nodes; odd indices are HTML tags — leave them untouched.
        if (idx % 2 !== 0) return chunk;
        return chunk.replace(/https?:\/\/\S+/gi, (url) => {
            const bare = url.replace(/[),.\s]+$/, '');  // strip trailing punctuation
            return VIDEO_EXT_RE.test(bare.split('?')[0]) ? _buildVideoHtml(bare) : url;
        });
    }).join('');
}

// Convert image URLs into inline <img> previews. Mirrors injectVideoPlayers but for images.
// Handles three cases produced by markdown-it:
//   1. <a href="...image.jpg">...</a>  (bare URL or autolink that linkify turned into an anchor)
//   2. <img src="...">                  (markdown image syntax) — leave as-is, but normalize style
//   3. raw URL still present in a text node                    — only as a safety net
function injectImagePreviews(html) {
    // Step 1: anchor whose href points to an image file -> replace with <img> preview.
    const step1 = html.replace(
        /<a\s+href="(https?:\/\/[^"]+)"[^>]*>[^<]*<\/a>/gi,
        (match, url) => IMAGE_EXT_RE.test(url.split('?')[0]) ? _buildImageHtml(url) : match
    );
    // Step 2: bare image URLs left in text nodes (rare — markdown-it's linkify usually catches them).
    return step1.split(/(<[^>]+>)/).map((chunk, idx) => {
        if (idx % 2 !== 0) return chunk;
        return chunk.replace(/https?:\/\/\S+/gi, (url) => {
            const bare = url.replace(/[),.\s]+$/, '');
            return IMAGE_EXT_RE.test(bare.split('?')[0]) ? _buildImageHtml(bare) : url;
        });
    }).join('');
}

function _rewriteLocalImgSrc(html) {
    return html.replace(/<img\s([^>]*?)src="([^"]+)"([^>]*?)>/gi, (match, pre, src, post) => {
        const webSrc = _toWebUrl(src);
        const safeSrc = webSrc.replace(/"/g, '&quot;');
        const hasClick = /onclick/i.test(pre + post);
        const clickAttr = hasClick ? '' : ` onclick="_openImageLightbox(this.src)" style="cursor:zoom-in;"`;
        return `<img ${pre}src="${safeSrc}"${post}${clickAttr}>`;
    });
}

function renderMarkdown(text) {
    try {
        let html = md.render(text);
        html = _rewriteLocalImgSrc(html);
        // Order matters: video first (more specific), then image.
        html = injectImagePreviews(injectVideoPlayers(html));
        // Note: Code block headers are added via DOM manipulation after insertion
        // See addCodeBlockHeadersToElement()
        return html;
    }
    catch (e) { return text.replace(/\n/g, '<br>'); }
}

function _addCodeBlockHeaders(container) {
    // Add header with language label and copy button to each <pre> block using DOM manipulation
    const preBlocks = container.querySelectorAll('pre');
    preBlocks.forEach(pre => {
        if (pre.parentElement && pre.parentElement.classList.contains('code-block-wrapper')) return;
        
        const codeEl = pre.querySelector('code');
        if (!codeEl) return;
        
        const langClass = Array.from(codeEl.classList).find(c => c.startsWith('language-'));
        const language = langClass ? langClass.replace('language-', '') : '';
        // Hide label for unknown/empty languages (e.g. language-undefined)
        const showLang = language && language !== 'undefined' && language !== 'code';
        const langLabel = showLang ? language.charAt(0).toUpperCase() + language.slice(1) : '';
        
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';
        
        const header = document.createElement('div');
        header.className = 'code-block-header';
        header.innerHTML = `
            <span class="code-block-lang">${langLabel}</span>
            <button class="code-copy-btn" title="Copy code">
                <i class="fas fa-copy"></i>
            </button>
        `;
        
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(header);
        wrapper.appendChild(pre);
    });
}

// =====================================================================
// Chat Module
// =====================================================================
let isPolling = false;
let pollGeneration = 0;   // incremented on each restart to cancel stale poll loops
let loadingContainers = {};
let activeStreams = {};   // request_id -> EventSource
let sessionActiveRequest = {};   // session_id -> request_id (in-flight stream per session)

function isCurrentSessionConversationActive() {
    return !!sessionActiveRequest[sessionId];
}

function updateEditButtonsState() {
    const active = isCurrentSessionConversationActive();
    document.querySelectorAll('.edit-msg-btn, .delete-msg-btn').forEach(btn => {
        btn.disabled = active;
        if (btn.classList.contains('edit-msg-btn')) {
            btn.title = active
                ? t('edit_disabled_reply_active')
                : t('edit_message');
        } else {
            btn.title = active
                ? t('delete_disabled_reply_active')
                : t('delete_message_title');
        }
    });
}
let streamBuffers = {};   // request_id -> { items: [event...], timestamp } for re-attach replay
let isComposing = false;
let appConfig = { use_agent: false, title: 'LightAgent', subtitle: '', providers: {}, api_bases: {} };

const SESSION_ID_KEY = 'lightagent_session_id';

function generateSessionId() {
    return 'session_' + ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
    );
}

// Restore session_id from localStorage so conversation history survives page refresh.
// A new id is only generated when the user explicitly starts a new chat.
function loadOrCreateSessionId() {
    const stored = localStorage.getItem(SESSION_ID_KEY);
    if (stored) return stored;
    const fresh = generateSessionId();
    localStorage.setItem(SESSION_ID_KEY, fresh);
    return fresh;
}

let sessionId = loadOrCreateSessionId();

// ---- Conversation history state ----
let historyPage = 0;       // last page fetched (0 = nothing fetched yet)
let historyHasMore = false;
let historyLoading = false;

fetch('/config').then(r => r.json()).then(data => {
    if (data.status === 'success') {
        appConfig = data;
        const title = data.title || 'LightAgent';
        document.getElementById('welcome-title').textContent = title;
        initConfigView(data);
    }
    loadHistory(1);
}).catch(() => { loadHistory(1); });

// Start polling immediately so scheduler/push messages are received at any time
startPolling();

const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const messagesDiv = document.getElementById('chat-messages');
const fileInput = document.getElementById('file-input');
const folderInput = document.getElementById('folder-input');
const attachBtn = document.getElementById('attach-btn');
const attachMenu = document.getElementById('attach-menu');
const attachFolderOption = document.getElementById('attach-folder-option');
const supportsDirectoryUpload = !!folderInput && 'webkitdirectory' in folderInput;

if (!supportsDirectoryUpload && attachFolderOption) {
    attachFolderOption.classList.add('hidden');
}

// ---------------- Mic button: in-page voice input via the configured ASR provider ----------------
(function setupMicButton() {
    const micBtn = document.getElementById('mic-btn');
    if (!micBtn) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia ||
        typeof window.MediaRecorder === 'undefined') {
        micBtn.style.display = 'none';
        return;
    }

    let mediaRecorder = null;
    let stream = null;
    let chunks = [];
    let recording = false;

    const setIdle = () => {
        recording = false;
        micBtn.classList.remove('text-red-500', 'animate-pulse');
        micBtn.classList.add('text-slate-400');
        micBtn.querySelector('i').className = 'fas fa-microphone text-sm';
        micBtn.title = t('mic_idle_title');
    };
    const setRecording = () => {
        recording = true;
        micBtn.classList.remove('text-slate-400');
        micBtn.classList.add('text-red-500', 'animate-pulse');
        micBtn.querySelector('i').className = 'fas fa-stop text-sm';
        micBtn.title = t('mic_recording_title');
    };
    const setBusy = () => {
        micBtn.classList.remove('text-red-500', 'animate-pulse', 'text-slate-400');
        micBtn.classList.add('text-primary-500');
        micBtn.querySelector('i').className = 'fas fa-spinner fa-spin text-sm';
        micBtn.title = t('mic_busy_title');
    };

    const pickMimeType = () => {
        const candidates = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/mp4',
        ];
        for (const m of candidates) {
            if (window.MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) {
                return m;
            }
        }
        return '';
    };

    const stopStream = () => {
        if (stream) {
            stream.getTracks().forEach(t => t.stop());
            stream = null;
        }
    };

    let _micTipTimer = null;
    const flashError = (msg) => {
        console.warn('[mic]', msg);
        // Pop a small bubble above the mic so the user actually notices it.
        // The mic lives inside a relatively-positioned wrapper around the
        // textarea (see chat.html), so we hang the tip off that wrapper.
        const wrapper = micBtn.parentElement;
        if (!wrapper) return;
        let tip = wrapper.querySelector('.mic-tip');
        if (!tip) {
            tip = document.createElement('div');
            tip.className = 'mic-tip absolute right-1 bottom-full mb-2 px-2 py-1 rounded-md '
                + 'text-xs text-white bg-slate-800/90 dark:bg-slate-700/90 shadow-md '
                + 'pointer-events-none whitespace-nowrap z-10';
            wrapper.appendChild(tip);
        }
        tip.textContent = msg;
        tip.style.opacity = '1';
        if (_micTipTimer) clearTimeout(_micTipTimer);
        _micTipTimer = setTimeout(() => {
            tip.style.opacity = '0';
            tip.style.transition = 'opacity 200ms';
            setTimeout(() => tip.remove(), 250);
        }, 2000);
    };

    const upload = async (blob, ext) => {
        setBusy();
        const fd = new FormData();
        fd.append('file', blob, `recording.${ext}`);
        try {
            const resp = await fetch('/api/voice/asr', { method: 'POST', body: fd });
            const data = await resp.json();
            if (data.status === 'success' && data.text) {
                // Voice-message UX: drop the recording into the conversation
                // as a playable bubble with the caption underneath, then
                // dispatch the recognised text through the regular send path.
                sendVoiceMessage(data.text, data.audio_url);
            } else {
                flashError(data.message || t('mic_error'));
            }
        } catch (e) {
            flashError(t('mic_error') + ': ' + e.message);
        } finally {
            setIdle();
        }
    };

    const start = async () => {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (e) {
            flashError(t('mic_permission_denied'));
            return;
        }
        chunks = [];
        const mimeType = pickMimeType();
        try {
            mediaRecorder = mimeType
                ? new MediaRecorder(stream, { mimeType })
                : new MediaRecorder(stream);
        } catch (e) {
            stopStream();
            flashError(t('mic_error') + ': ' + e.message);
            return;
        }
        mediaRecorder.ondataavailable = (ev) => {
            if (ev.data && ev.data.size > 0) chunks.push(ev.data);
        };
        mediaRecorder.onstop = () => {
            stopStream();
            const blob = new Blob(chunks, { type: mediaRecorder.mimeType || 'audio/webm' });
            // Map mime -> extension so the server picks the right file suffix.
            const mt = (mediaRecorder.mimeType || 'audio/webm').split(';')[0];
            const extMap = {
                'audio/webm': 'webm', 'audio/ogg': 'ogg',
                'audio/mp4': 'm4a',   'audio/mpeg': 'mp3',
            };
            const ext = extMap[mt] || 'webm';
            // 256 bytes ~ container header only, no actual audio. Anything
            // below that we treat as "tapped by mistake".
            if (blob.size < 256) {
                setIdle();
                flashError(t('mic_too_short'));
                return;
            }
            upload(blob, ext);
        };
        // timeslice=250ms: force the recorder to flush a chunk every 250ms.
        // Without it some browsers wait for stop() before producing any data,
        // which loses the audio on very short taps.
        mediaRecorder.start(250);
        recordStartedAt = Date.now();
        setRecording();
    };

    let recordStartedAt = 0;

    const stopWithMinDuration = () => {
        const elapsed = Date.now() - recordStartedAt;
        const minMs = 350;
        if (elapsed < minMs) {
            // Give the recorder a moment to capture at least one chunk
            // before we tell it to stop.
            setTimeout(() => stop(), minMs - elapsed);
        } else {
            stop();
        }
    };

    const stop = () => {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
    };

    micBtn.addEventListener('click', () => {
        if (recording) {
            stopWithMinDuration();
        } else {
            start();
        }
    });

    setIdle();
})();

// Smart auto-scroll: pause when user scrolls up, resume when near bottom
let _autoScrollEnabled = true;
const _SCROLL_THRESHOLD = 80; // px from bottom to re-enable auto-scroll

messagesDiv.addEventListener('scroll', () => {
    const distFromBottom = messagesDiv.scrollHeight - messagesDiv.scrollTop - messagesDiv.clientHeight;
    _autoScrollEnabled = distFromBottom <= _SCROLL_THRESHOLD;
    _updateScrollToBottomBtn();
});

// Intercept internal navigation links in chat messages
messagesDiv.addEventListener('click', (e) => {
    // Code block copy button
    const codeCopyBtn = e.target.closest('.code-copy-btn');
    if (codeCopyBtn) {
        e.preventDefault();
        const wrapper = codeCopyBtn.closest('.code-block-wrapper');
        const codeEl = wrapper && wrapper.querySelector('pre code');
        if (codeEl) {
            const codeText = codeEl.textContent;
            copyToClipboard(codeText).then(() => {
                const icon = codeCopyBtn.querySelector('i');
                if (icon) { icon.className = 'fas fa-check'; setTimeout(() => { icon.className = 'fas fa-copy'; }, 1500); }
            });
        }
        return;
    }

    const copyBtn = e.target.closest('.copy-msg-btn');
    if (copyBtn) {
        e.preventDefault();
        const msgRoot = copyBtn.closest('.flex.gap-3');
        const answerEl = msgRoot && msgRoot.querySelector('.answer-content');
        const rawMd = answerEl && answerEl.dataset.rawMd;
        if (rawMd) {
            copyToClipboard(rawMd).then(() => {
                const icon = copyBtn.querySelector('i');
                if (icon) { icon.className = 'fas fa-check'; setTimeout(() => { icon.className = 'fas fa-copy'; }, 1500); }
            });
        }
        return;
    }

    // Edit user message
    const editBtn = e.target.closest('.edit-msg-btn');
    if (editBtn) {
        e.preventDefault();
        if (isCurrentSessionConversationActive()) return;
        const msgRoot = editBtn.closest('.user-message-group');
        if (msgRoot) editUserMessage(msgRoot);
        return;
    }

    // Regenerate bot response
    const regenerateBtn = e.target.closest('.regenerate-msg-btn');
    if (regenerateBtn) {
        e.preventDefault();
        const botMsgRoot = regenerateBtn.closest('.flex.gap-3');
        if (botMsgRoot) regenerateResponse(botMsgRoot);
        return;
    }

    // Delete message (user bubble only; bot bubbles intentionally lack a
    // delete button — removing only the bot reply would leave an orphan
    // user message that breaks LLM context alternation).
    const deleteBtn = e.target.closest('.delete-msg-btn');
    if (deleteBtn) {
        e.preventDefault();
        if (isCurrentSessionConversationActive()) return;
        const userMsgEl = deleteBtn.closest('.user-message-group');
        if (!userMsgEl) return;

        showConfirmModal(t('delete_message_title'), t('delete_message_confirm'), () => {
            // Find the next bot reply for this turn (skip non-message nodes).
            let botReplyEl = null;
            let sibling = userMsgEl.nextElementSibling;
            while (sibling) {
                if (sibling.classList && sibling.classList.contains('bot-message-group')) {
                    botReplyEl = sibling;
                    break;
                }
                sibling = sibling.nextElementSibling;
            }
            userMsgEl.remove();
            if (botReplyEl) botReplyEl.remove();

            const userSeq = userMsgEl.dataset.seq;
            if (userSeq) {
                fetch('/api/messages/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId, user_seq: parseInt(userSeq) })
                }).then(r => r.json()).then(data => {
                    if (data.status === 'success') console.log(`Deleted ${data.deleted} messages`);
                }).catch(err => console.error('Failed to delete:', err));
            }
        });
        return;
    }

    const a = e.target.closest('a');
    if (!a) return;
    const href = a.getAttribute('href') || '';
    if (href === '/memory/dreams') {
        e.preventDefault();
        navigateTo('memory');
        setTimeout(() => switchMemoryTab('dreams'), 50);
    } else if (href === '/memory/MEMORY.md') {
        e.preventDefault();
        navigateTo('memory');
        setTimeout(() => { switchMemoryTab('files'); openMemoryFile('MEMORY.md', 'memory'); }, 50);
    }
});
const attachmentPreview = document.getElementById('attachment-preview');

// Pending attachments: [{file_path, file_name, file_type, preview_url}]
// Items with _uploading=true are still in flight.
let pendingAttachments = [];
let uploadingCount = 0;

// Input history (like terminal arrow-key recall)
const inputHistory = [];
let historyIdx = -1;
let historySavedDraft = '';

// While an SSE stream is in flight, the send button morphs into a cancel
// button. Only one in-flight request is supported at a time.
let activeRequestId = null;
let sendBtnMode = 'send'; // 'send' | 'cancel'

function setSendBtnCancelMode(requestId) {
    activeRequestId = requestId;
    sendBtnMode = 'cancel';
    sendBtn.disabled = false;
    sendBtn.classList.add('send-btn-cancel');
    sendBtn.title = (currentLang === 'zh' ? '中止' : 'Cancel');
    sendBtn.innerHTML = '<i class="fas fa-stop text-sm"></i>';
}

function resetSendBtnSendMode() {
    activeRequestId = null;
    sendBtnMode = 'send';
    sendBtn.classList.remove('send-btn-cancel');
    sendBtn.title = '';
    sendBtn.innerHTML = '<i class="fas fa-paper-plane text-sm"></i>';
    updateSendBtnState();
}

function requestCancel() {
    const reqId = activeRequestId;
    if (!reqId) return;
    fetch('/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ request_id: reqId, session_id: sessionId, lang: currentLang }),
    }).catch(err => {
        console.warn('[cancel] request failed', err);
    });
    // Optimistic UI lock so the click visibly registers before the SSE
    // "cancelled" event arrives.
    sendBtn.disabled = true;
    sendBtn.title = (currentLang === 'zh' ? '已中止' : 'Cancelled');
}

// Button click is the only path to Cancel. Pressing Enter still calls
// sendMessage() so users can submit "/cancel" as a regular slash command.
sendBtn.addEventListener('click', () => {
    if (sendBtnMode === 'cancel') {
        requestCancel();
    } else {
        sendMessage();
    }
});

function updateSendBtnState() {
    if (sendBtnMode === 'cancel') {
        // Self-heal a stuck Cancel button: if there's no live stream backing
        // the current request, the cancel state leaked (e.g. a stream ended
        // without resetting). Recover to Send so the input isn't blocked.
        if (!activeRequestId || !activeStreams[activeRequestId]) {
            resetSendBtnSendMode();
        } else {
            // Don't downgrade a genuinely active Cancel button on input edits.
            return;
        }
    }
    sendBtn.disabled = uploadingCount > 0 || (!chatInput.value.trim() && pendingAttachments.length === 0);
}

function renderAttachmentPreview() {
    if (pendingAttachments.length === 0) {
        attachmentPreview.classList.add('hidden');
        attachmentPreview.innerHTML = '';
        updateSendBtnState();
        return;
    }
    attachmentPreview.classList.remove('hidden');
    attachmentPreview.innerHTML = pendingAttachments.map((att, idx) => {
        if (att._uploading) {
            const suffix = att.file_type === 'directory' && att.file_count
                ? ` (${att.file_count})`
                : '';
            return `<div class="att-chip att-uploading" data-idx="${idx}">
                <i class="fas fa-spinner fa-spin"></i>
                <span class="att-name">${escapeHtml(att.file_name)}${suffix}</span>
            </div>`;
        }
        if (att.file_type === 'image') {
            return `<div class="att-thumb" data-idx="${idx}">
                <img src="${att.preview_url}" alt="${escapeHtml(att.file_name)}">
                <button class="att-remove" onclick="removeAttachment(${idx})">&times;</button>
            </div>`;
        }
        const icon = att.file_type === 'video'
            ? 'fa-film'
            : (att.file_type === 'directory' ? 'fa-folder-tree' : 'fa-file-alt');
        const suffix = att.file_type === 'directory' && att.file_count
            ? ` (${att.file_count})`
            : '';
        return `<div class="att-chip" data-idx="${idx}">
            <i class="fas ${icon}"></i>
            <span class="att-name">${escapeHtml(att.file_name)}${suffix}</span>
            <button class="att-remove" onclick="removeAttachment(${idx})">&times;</button>
        </div>`;
    }).join('');
    updateSendBtnState();
}

function removeAttachment(idx) {
    if (pendingAttachments[idx]?._uploading) return;
    pendingAttachments.splice(idx, 1);
    renderAttachmentPreview();
}

function isAttachMenuVisible() {
    return attachMenu && !attachMenu.classList.contains('hidden');
}

function hideAttachMenu() {
    if (attachMenu) attachMenu.classList.add('hidden');
}

function toggleAttachMenu(event) {
    if (!attachMenu) return;
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    attachMenu.classList.toggle('hidden');
}

function triggerFileUpload() {
    hideAttachMenu();
    fileInput?.click();
}

function triggerFolderUpload() {
    if (!supportsDirectoryUpload) return;
    hideAttachMenu();
    folderInput?.click();
}

async function handleFileSelect(files) {
    if (!files || files.length === 0) return;
    const tasks = [];
    for (const file of files) {
        const placeholder = { file_name: file.name, file_type: 'file', _uploading: true };
        pendingAttachments.push(placeholder);
        uploadingCount++;
        renderAttachmentPreview();

        tasks.push((async () => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('session_id', sessionId);
            try {
                const resp = await fetch('/upload', { method: 'POST', body: formData });
                const data = await resp.json();
                if (data.status === 'success') {
                    placeholder.file_path = data.file_path;
                    placeholder.file_name = data.file_name;
                    placeholder.file_type = data.file_type;
                    placeholder.preview_url = data.preview_url;
                    delete placeholder._uploading;
                } else {
                    const i = pendingAttachments.indexOf(placeholder);
                    if (i !== -1) pendingAttachments.splice(i, 1);
                }
            } catch (e) {
                console.error('Upload failed:', e);
                const i = pendingAttachments.indexOf(placeholder);
                if (i !== -1) pendingAttachments.splice(i, 1);
            }
            uploadingCount--;
            renderAttachmentPreview();
        })());
    }
    await Promise.all(tasks);
}

function _makeUploadId() {
    return `dir_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function _groupDirectoryFiles(files) {
    const groups = new Map();
    for (const file of Array.from(files || [])) {
        const relPath = file.webkitRelativePath || file.name;
        const parts = relPath.split('/').filter(Boolean);
        const rootName = parts[0] || file.name;
        if (!groups.has(rootName)) groups.set(rootName, []);
        groups.get(rootName).push({ file, relPath });
    }
    return groups;
}

async function handleFolderSelect(files) {
    if (!files || files.length === 0) return;
    const groups = _groupDirectoryFiles(files);
    const groupTasks = [];

    for (const [rootName, entries] of groups.entries()) {
        const placeholder = {
            file_name: rootName,
            file_type: 'directory',
            file_count: entries.length,
            _uploading: true,
        };
        pendingAttachments.push(placeholder);
        uploadingCount++;
        renderAttachmentPreview();

        const uploadId = _makeUploadId();
        groupTasks.push((async () => {
            try {
                const formData = new FormData();
                formData.append('session_id', sessionId);
                formData.append('upload_id', uploadId);
                for (const { file, relPath } of entries) {
                    formData.append('files', file);
                    formData.append('relative_paths', relPath);
                }

                const resp = await fetch('/upload', { method: 'POST', body: formData });
                const data = await resp.json();
                if (data.status !== 'success') {
                    throw new Error(data.message || 'Upload failed');
                }
                if (!data.root_path) {
                    throw new Error('Directory root path missing');
                }
                placeholder.file_path = data.root_path;
                placeholder.file_name = data.root_name || rootName;
                delete placeholder._uploading;
            } catch (e) {
                console.error('Directory upload failed:', e);
                const i = pendingAttachments.indexOf(placeholder);
                if (i !== -1) pendingAttachments.splice(i, 1);
            } finally {
                uploadingCount--;
            }
            renderAttachmentPreview();
        })());
    }

    await Promise.all(groupTasks);
}

fileInput.addEventListener('change', function() {
    handleFileSelect(this.files);
    this.value = '';
});

folderInput.addEventListener('change', function() {
    handleFolderSelect(this.files);
    this.value = '';
});

document.addEventListener('click', (e) => {
    if (!isAttachMenuVisible()) return;
    if (attachMenu.contains(e.target) || attachBtn.contains(e.target)) return;
    hideAttachMenu();
});

// Drag-and-drop support on entire chat view
const chatView = document.getElementById('view-chat');
const chatInputArea = chatInput.closest('.flex-shrink-0');

// Create drag overlay for visual feedback
let dragOverlay = document.getElementById('drag-overlay');
if (!dragOverlay) {
    dragOverlay = document.createElement('div');
    dragOverlay.id = 'drag-overlay';
    dragOverlay.className = 'drag-overlay hidden';
    dragOverlay.innerHTML = `
        <div class="drag-overlay-content">
            <i class="fas fa-cloud-arrow-up"></i>
            <p>Drop files here to upload</p>
        </div>
    `;
    chatView.appendChild(dragOverlay);
}

let dragCounter = 0;

function showDragOverlay() {
    dragOverlay.classList.remove('hidden');
    dragOverlay.classList.add('active');
}

function hideDragOverlay() {
    dragOverlay.classList.remove('active');
    dragOverlay.classList.add('hidden');
}

chatView.addEventListener('dragenter', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter++;
    if (e.dataTransfer.types.includes('Files')) {
        showDragOverlay();
    }
});

chatView.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
    chatInputArea.classList.add('drag-over');
});

chatView.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter--;
    if (dragCounter === 0) {
        hideDragOverlay();
        chatInputArea.classList.remove('drag-over');
    }
});

chatView.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter = 0;
    hideDragOverlay();
    chatInputArea.classList.remove('drag-over');
    if (e.dataTransfer.files.length) {
        handleFileSelect(e.dataTransfer.files);
    }
});

document.body.addEventListener('dragover', (e) => {
    if (e.dataTransfer.types.includes('Files')) {
        e.preventDefault();
    }
});

document.body.addEventListener('drop', (e) => {
    if (e.dataTransfer.types.includes('Files')) {
        e.preventDefault();
    }
});

// Paste image support
chatInput.addEventListener('paste', (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const files = [];
    for (const item of items) {
        if (item.kind === 'file') {
            files.push(item.getAsFile());
        }
    }
    if (files.length) {
        e.preventDefault();
        handleFileSelect(files);
    }
});

chatInput.addEventListener('compositionstart', () => { isComposing = true; });
chatInput.addEventListener('compositionend', () => { setTimeout(() => { isComposing = false; }, 100); });

// ── Slash Command Menu ───────────────────────────────────────
// desc holds an i18n key, resolved via t() at render time so the menu follows
// the current UI language.
const SLASH_COMMANDS = [
    { cmd: '/help',                desc: 'slash_help' },
    { cmd: '/status',              desc: 'slash_status' },
    { cmd: '/context',             desc: 'slash_context' },
    { cmd: '/context clear',       desc: 'slash_context_clear' },
    { cmd: '/skill list',          desc: 'slash_skill_list' },
    { cmd: '/skill list --remote', desc: 'slash_skill_list_remote' },
    { cmd: '/skill search ',       desc: 'slash_skill_search' },
    { cmd: '/skill install ',      desc: 'slash_skill_install' },
    { cmd: '/skill uninstall ',    desc: 'slash_skill_uninstall' },
    { cmd: '/skill info ',         desc: 'slash_skill_info' },
    { cmd: '/skill enable ',       desc: 'slash_skill_enable' },
    { cmd: '/skill disable ',      desc: 'slash_skill_disable' },
    { cmd: '/memory dream ',       desc: 'slash_memory_dream' },
    { cmd: '/knowledge',           desc: 'slash_knowledge' },
    { cmd: '/knowledge list',      desc: 'slash_knowledge_list' },
    { cmd: '/knowledge on',        desc: 'slash_knowledge_on' },
    { cmd: '/knowledge off',       desc: 'slash_knowledge_off' },
    { cmd: '/config',              desc: 'slash_config' },
    { cmd: '/cancel',              desc: 'slash_cancel' },
    { cmd: '/logs',                desc: 'slash_logs' },
    { cmd: '/version',             desc: 'slash_version' },
];

const slashMenu = document.getElementById('slash-menu');
let slashActiveIdx = 0;
let slashFiltered = [];
let slashJustSelected = false;
let slashLastFilter = '';
let slashLastMouseX = -1;
let slashLastMouseY = -1;

function showSlashMenu(filter) {
    const q = filter.toLowerCase();
    if (q === slashLastFilter && !slashMenu.classList.contains('hidden')) return;
    slashLastFilter = q;

    const newFiltered = SLASH_COMMANDS.filter(c => c.cmd.toLowerCase().startsWith(q));
    if (newFiltered.length === 0) {
        hideSlashMenu();
        return;
    }

    const changed = newFiltered.length !== slashFiltered.length ||
        newFiltered.some((c, i) => c.cmd !== slashFiltered[i]?.cmd);
    slashFiltered = newFiltered;
    if (changed) slashActiveIdx = 0;
    slashActiveIdx = Math.min(slashActiveIdx, slashFiltered.length - 1);

    slashNavByKeyboard = true;
    renderSlashItems();
    slashMenu.classList.remove('hidden');
}

function hideSlashMenu() {
    slashMenu.classList.add('hidden');
    slashMenu.innerHTML = '';
    slashFiltered = [];
    slashActiveIdx = -1;
    slashLastFilter = '';
    slashNavByKeyboard = false;
    slashLastMouseX = -1;
    slashLastMouseY = -1;
}

function isSlashMenuVisible() {
    return !slashMenu.classList.contains('hidden') && slashFiltered.length > 0;
}

function renderSlashItems() {
    slashMenu.innerHTML =
        '<div class="slash-menu-header">Commands</div>' +
        slashFiltered.map((c, i) =>
            `<div class="slash-menu-item${i === slashActiveIdx ? ' active' : ''}" data-idx="${i}">` +
            `<span class="cmd">${escapeHtml(c.cmd)}</span>` +
            `<span class="desc">${escapeHtml(t(c.desc))}</span></div>`
        ).join('');

    const activeEl = slashMenu.querySelector('.slash-menu-item.active');
    if (activeEl) activeEl.scrollIntoView({ block: 'nearest' });
}

// Delegated events on the persistent slashMenu container (not destroyed by innerHTML)
// Use coordinate comparison to distinguish real mouse movement from DOM-rebuild phantom events.
slashMenu.addEventListener('mousemove', (e) => {
    if (e.clientX === slashLastMouseX && e.clientY === slashLastMouseY) return;
    slashLastMouseX = e.clientX;
    slashLastMouseY = e.clientY;
    if (!slashNavByKeyboard) return;
    slashNavByKeyboard = false;
    const item = e.target.closest('.slash-menu-item');
    if (!item) return;
    const idx = parseInt(item.dataset.idx);
    if (idx === slashActiveIdx) return;
    slashActiveIdx = idx;
    slashMenu.querySelectorAll('.slash-menu-item').forEach(el => {
        el.classList.toggle('active', parseInt(el.dataset.idx) === idx);
    });
});

slashMenu.addEventListener('mouseover', (e) => {
    if (slashNavByKeyboard) return;
    const item = e.target.closest('.slash-menu-item');
    if (!item) return;
    const idx = parseInt(item.dataset.idx);
    if (idx === slashActiveIdx) return;
    slashActiveIdx = idx;
    slashMenu.querySelectorAll('.slash-menu-item').forEach(el => {
        el.classList.toggle('active', parseInt(el.dataset.idx) === idx);
    });
});

slashMenu.addEventListener('mousedown', (e) => {
    const item = e.target.closest('.slash-menu-item');
    if (!item) return;
    e.preventDefault();
    selectSlashCommand(parseInt(item.dataset.idx));
});

function selectSlashCommand(idx) {
    if (idx < 0 || idx >= slashFiltered.length) return;
    const chosen = slashFiltered[idx].cmd;
    slashJustSelected = true;
    chatInput.value = chosen;
    chatInput.dispatchEvent(new Event('input'));
    hideSlashMenu();
    chatInput.focus();
    chatInput.selectionStart = chatInput.selectionEnd = chosen.length;
}

chatInput.addEventListener('input', function() {
    this.style.height = '42px';
    const scrollH = this.scrollHeight;
    const newH = Math.min(scrollH, 180);
    this.style.height = newH + 'px';
    this.style.overflowY = scrollH > 180 ? 'auto' : 'hidden';
    updateSendBtnState();

    const val = this.value;
    if (slashJustSelected) {
        slashJustSelected = false;
    } else if (val.startsWith('/')) {
        showSlashMenu(val);
    } else {
        hideSlashMenu();
    }
});

chatInput.addEventListener('keydown', function(e) {
    if (e.keyCode === 229 || e.isComposing || isComposing) return;

    if (e.key === 'Escape' && isAttachMenuVisible()) {
        hideAttachMenu();
        return;
    }

    if (isSlashMenuVisible()) {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            slashNavByKeyboard = true;
            slashActiveIdx = Math.min(slashActiveIdx + 1, slashFiltered.length - 1);
            renderSlashItems();
            return;
        }
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            slashNavByKeyboard = true;
            slashActiveIdx = Math.max(slashActiveIdx - 1, 0);
            renderSlashItems();
            return;
        }
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
            e.preventDefault();
            selectSlashCommand(slashActiveIdx);
            return;
        }
        if (e.key === 'Escape') {
            e.preventDefault();
            hideSlashMenu();
            return;
        }
        if (e.key === 'Tab') {
            e.preventDefault();
            selectSlashCommand(slashActiveIdx);
            return;
        }
    }

    // Arrow-key history recall (only when input is empty or already browsing history)
    if (e.key === 'ArrowUp' && inputHistory.length > 0 && !isSlashMenuVisible()) {
        const curVal = this.value.trim();
        const isSingleLine = !this.value.includes('\n');
        if (isSingleLine && (curVal === '' || historyIdx >= 0)) {
            e.preventDefault();
            if (historyIdx < 0) {
                historySavedDraft = this.value;
                historyIdx = inputHistory.length - 1;
            } else if (historyIdx > 0) {
                historyIdx--;
            }
            this.value = inputHistory[historyIdx];
            slashJustSelected = true;
            this.dispatchEvent(new Event('input'));
            hideSlashMenu();
            this.selectionStart = this.selectionEnd = this.value.length;
            return;
        }
    }
    if (e.key === 'ArrowDown' && historyIdx >= 0 && !isSlashMenuVisible()) {
        const isSingleLine = !this.value.includes('\n');
        if (isSingleLine) {
            e.preventDefault();
            if (historyIdx < inputHistory.length - 1) {
                historyIdx++;
                this.value = inputHistory[historyIdx];
            } else {
                historyIdx = -1;
                this.value = historySavedDraft;
                historySavedDraft = '';
            }
            slashJustSelected = true;
            this.dispatchEvent(new Event('input'));
            hideSlashMenu();
            this.selectionStart = this.selectionEnd = this.value.length;
            return;
        }
    }

    if ((e.ctrlKey || e.shiftKey) && e.key === 'Enter') {
        const start = this.selectionStart;
        const end = this.selectionEnd;
        this.value = this.value.substring(0, start) + '\n' + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + 1;
        this.dispatchEvent(new Event('input'));
        e.preventDefault();
    } else if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
        sendMessage();
        e.preventDefault();
    }
});

chatInput.addEventListener('blur', () => {
    setTimeout(hideSlashMenu, 150);
});

document.querySelectorAll('.example-card').forEach(card => {
    card.addEventListener('click', () => {
        // data-send overrides the visible text (e.g. show "查看全部命令" but send "/help")
        const sendText = card.dataset.send;
        if (sendText) {
            chatInput.value = sendText;
            chatInput.dispatchEvent(new Event('input'));
            chatInput.focus();
            return;
        }
        const textEl = card.querySelector('[data-i18n*="text"]');
        if (textEl) {
            chatInput.value = textEl.textContent;
            chatInput.dispatchEvent(new Event('input'));
            chatInput.focus();
        }
    });
});

// Voice-message variant of sendMessage(): renders a playable audio bubble
// with the ASR caption, then dispatches the recognised text to /message
// through the same SSE/loading flow as a typed message.
function sendVoiceMessage(text, audioUrl) {
    text = (text || '').trim();
    if (!text) return;

    inputHistory.push(text);
    historyIdx = -1;
    historySavedDraft = '';

    const ws = document.getElementById('welcome-screen');
    const isFirstMessage = !!ws;
    if (ws) ws.remove();

    const titleInfo = isFirstMessage ? { sid: sessionId, userMsg: text } : null;
    const timestamp = new Date();
    addUserVoiceMessage(audioUrl, text, timestamp);
    const loadingEl = addLoadingIndicator();

    const body = {
        session_id: sessionId,
        message: text,
        stream: true,
        timestamp: timestamp.toISOString(),
        is_voice: true,
        lang: currentLang,
    };

    const MAX_RETRIES = 2;
    const RETRY_DELAY_MS = 1000;
    function postWithRetry(attempt) {
        fetch('/message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                if (data.inline_reply) {
                    // Synchronous fast-path reply (e.g. /cancel); skip SSE.
                    loadingEl.remove();
                    addBotMessage(data.inline_reply, new Date());
                } else if (data.stream) {
                    setSendBtnCancelMode(data.request_id);
                    startSSE(data.request_id, loadingEl, timestamp, titleInfo);
                } else {
                    loadingContainers[data.request_id] = loadingEl;
                }
            } else {
                loadingEl.remove();
                addBotMessage(t('error_send'), new Date());
                resetSendBtnSendMode();
            }
        })
        .catch(err => {
            if (attempt < MAX_RETRIES) {
                setTimeout(() => postWithRetry(attempt + 1), RETRY_DELAY_MS * (attempt + 1));
                return;
            }
            loadingEl.remove();
            addBotMessage(t('error_send'), new Date());
        });
    }
    postWithRetry(0);
}

function addUserVoiceMessage(audioUrl, caption, timestamp) {
    const el = document.createElement('div');
    el.className = 'flex justify-end px-4 sm:px-6 py-3';
    // Voice-message bubble: compact voice pill on top, ASR caption beneath.
    // The bubble keeps the same primary tint as a normal user message so
    // it visually slots into the conversation flow.
    el.innerHTML = `
        <div class="max-w-[75%] sm:max-w-[60%]">
            <div class="bg-slate-100 dark:bg-white/10 text-slate-700 dark:text-slate-200 rounded-2xl px-3 py-2 msg-content user-bubble">
                <div class="user-voice-slot"></div>
                ${caption ? `<div class="text-xs mt-1.5 leading-snug text-slate-500 dark:text-slate-400 whitespace-pre-wrap break-words">${escapeHtml(caption)}</div>` : ''}
            </div>
            <div class="text-xs text-slate-400 dark:text-slate-500 mt-1.5 text-right">${formatTime(timestamp)}</div>
        </div>
    `;
    el.querySelector('.user-voice-slot').appendChild(renderVoicePill(audioUrl));
    messagesDiv.appendChild(el);
    _autoScrollEnabled = true;
    scrollChatToBottom(true);
}

// Clipboard helper with fallback for non-HTTPS environments
function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text);
    }
    // Fallback for HTTP environments
    return new Promise((resolve, reject) => {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            document.execCommand('copy') ? resolve() : reject(new Error('Copy failed'));
        } catch (err) {
            reject(err);
        } finally {
            textArea.remove();
        }
    });
}

// Edit user message: extract content, remove this and subsequent messages, fill input
async function editUserMessage(msgEl) {
    if (isCurrentSessionConversationActive()) return;
    const rawContent = msgEl.dataset.rawContent;
    if (!rawContent) return;

    // Delete this message and ALL subsequent messages from database (cascade)
    // Must await to ensure delete completes before user sends a new message
    const userSeq = msgEl.dataset.seq;
    if (userSeq) {
        try {
            const resp = await fetch('/api/messages/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    session_id: sessionId, 
                    user_seq: parseInt(userSeq),
                    delete_user: true,
                    cascade: true
                })
            });
            const data = await resp.json();
            if (data.status === 'success') console.log(`Deleted ${data.deleted} old messages`);
        } catch (err) {
            console.error('Failed to delete old messages:', err);
        }
    }

    // Remove this message bubble and every later bubble that belongs to
    // this or a subsequent turn. We mirror the backend cascade contract:
    // anything with a data-seq >= current seq, plus any live SSE bubble
    // that is still being streamed (no seq yet) after this point.
    const currentSeqNum = userSeq ? parseInt(userSeq) : null;
    const messagesToRemove = [];
    let current = msgEl;
    while (current) {
        if (current.classList && (current.classList.contains('user-message-group') || current.classList.contains('bot-message-group'))) {
            const seqAttr = current.dataset.seq;
            if (seqAttr === undefined || seqAttr === '') {
                // Live message without a persisted seq yet — treat as later.
                messagesToRemove.push(current);
            } else if (currentSeqNum === null || parseInt(seqAttr) >= currentSeqNum) {
                messagesToRemove.push(current);
            }
        }
        current = current.nextElementSibling;
    }
    messagesToRemove.forEach(el => {
        if (el && el.parentNode) el.parentNode.removeChild(el);
    });

    // Fill input with the original content
    chatInput.value = rawContent;
    chatInput.dispatchEvent(new Event("input", { bubbles: true }));
    chatInput.focus();
    chatInput.selectionStart = chatInput.selectionEnd = chatInput.value.length;
    scrollChatToBottom();
}

// Regenerate bot response: find the preceding user message and resend it
async function regenerateResponse(botMsgEl) {
    let prevEl = botMsgEl.previousElementSibling;
    while (prevEl && !prevEl.classList.contains('user-message-group')) {
        prevEl = prevEl.previousElementSibling;
    }

    if (!prevEl) {
        console.warn('No preceding user message found');
        return;
    }

    const userContent = prevEl.dataset.rawContent;
    if (!userContent) {
        console.warn('No content in preceding user message');
        return;
    }

    // Delete both the old user message AND bot reply from database
    // (because /message will create a fresh user message + new bot reply)
    // Must await to ensure delete completes before /message is sent
    const userSeq = prevEl.dataset.seq;
    if (userSeq) {
        try {
            const resp = await fetch('/api/messages/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    session_id: sessionId, 
                    user_seq: parseInt(userSeq),
                    delete_user: true
                })
            });
            const data = await resp.json();
            if (data.status === 'success') console.log(`Deleted ${data.deleted} old messages`);
        } catch (err) {
            console.error('Failed to delete old messages:', err);
        }
    }

    // Remove both the old user message and bot message from DOM
    if (prevEl.parentNode) prevEl.parentNode.removeChild(prevEl);
    if (botMsgEl.parentNode) botMsgEl.parentNode.removeChild(botMsgEl);

    // Re-add the user message to DOM (so it appears before the loading indicator)
    addUserMessage(userContent, new Date());

    // Show loading indicator
    const loadingEl = addLoadingIndicator();

    // Resend the message
    const timestamp = new Date();
    const body = { session_id: sessionId, message: userContent, stream: true, timestamp: timestamp.toISOString(), lang: currentLang };

    const MAX_RETRIES = 2;
    const RETRY_DELAY_MS = 1000;

    function postWithRetry(attempt) {
        fetch('/message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                if (data.inline_reply) {
                    loadingEl.remove();
                    addBotMessage(data.inline_reply, new Date());
                } else if (data.stream) {
                    setSendBtnCancelMode(data.request_id);
                    startSSE(data.request_id, loadingEl, timestamp, null);
                } else {
                    loadingContainers[data.request_id] = loadingEl;
                }
            } else {
                loadingEl.remove();
                addBotMessage(t('error_send'), new Date());
                resetSendBtnSendMode();
            }
        })
        .catch(err => {
            if (err.name === 'AbortError') {
                loadingEl.remove();
                addBotMessage(t('error_timeout'), new Date());
                resetSendBtnSendMode();
                return;
            }
            if (attempt < MAX_RETRIES) {
                console.warn(`[regenerateResponse] attempt ${attempt + 1} failed, retrying...`, err);
                setTimeout(() => postWithRetry(attempt + 1), RETRY_DELAY_MS * (attempt + 1));
                return;
            }
            loadingEl.remove();
            addBotMessage(t('error_send'), new Date());
            resetSendBtnSendMode();
        });
    }

    postWithRetry(0);
}

function sendMessage() {
    // Do NOT branch on sendBtnMode here: Enter should always send (so
    // typing "/cancel" submits normally). Cancel is wired only to the
    // send button's pointer click — see send-btn listener above.

    const text = chatInput.value.trim();
    if (!text && pendingAttachments.length === 0) return;

    if (text) {
        inputHistory.push(text);
        historyIdx = -1;
        historySavedDraft = '';
    }

    const ws = document.getElementById('welcome-screen');
    const isFirstMessage = !!ws;
    if (ws) ws.remove();

    const titleInfo = (isFirstMessage && text) ? { sid: sessionId, userMsg: text } : null;

    const timestamp = new Date();
    const attachments = [...pendingAttachments];
    addUserMessage(text, timestamp, attachments);

    const loadingEl = addLoadingIndicator();

    chatInput.value = '';
    chatInput.style.height = '42px';
    chatInput.style.overflowY = 'hidden';
    pendingAttachments = [];
    renderAttachmentPreview();
    sendBtn.disabled = true;

    const body = { session_id: sessionId, message: text, stream: true, timestamp: timestamp.toISOString(), lang: currentLang };
    if (attachments.length > 0) {
        body.attachments = attachments.map(a => ({
            file_path: a.file_path,
            file_name: a.file_name,
            file_type: a.file_type,
            file_count: a.file_count,
        }));
    }

    const MAX_RETRIES = 2;
    const RETRY_DELAY_MS = 1000;

    function postWithRetry(attempt) {
        fetch('/message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                if (data.inline_reply) {
                    // Channel handled synchronously (e.g. /cancel fast-path);
                    // render as a bot bubble and skip SSE entirely.
                    loadingEl.remove();
                    addBotMessage(data.inline_reply, new Date());
                } else if (data.stream) {
                    setSendBtnCancelMode(data.request_id);
                    startSSE(data.request_id, loadingEl, timestamp, titleInfo);
                } else {
                    loadingContainers[data.request_id] = loadingEl;
                }
            } else {
                loadingEl.remove();
                addBotMessage(t('error_send'), new Date());
                resetSendBtnSendMode();
            }
        })
        .catch(err => {
            if (err.name === 'AbortError') {
                loadingEl.remove();
                addBotMessage(t('error_timeout'), new Date());
                resetSendBtnSendMode();
                return;
            }
            if (attempt < MAX_RETRIES) {
                console.warn(`[sendMessage] attempt ${attempt + 1} failed, retrying...`, err);
                setTimeout(() => postWithRetry(attempt + 1), RETRY_DELAY_MS * (attempt + 1));
                return;
            }
            loadingEl.remove();
            addBotMessage(t('error_send'), new Date());
            resetSendBtnSendMode();
        });
    }

    postWithRetry(0);
}

function startSSE(requestId, loadingEl, timestamp, titleInfo, replayItems) {
    let botEl = null;
    let stepsEl = null;    // .agent-steps  (thinking summaries + tool indicators)
    let contentEl = null;  // .answer-content (final streaming answer)
    let mediaEl = null;    // .media-content (images & file attachments)
    let accumulatedText = '';
    const toolElements = new Map();
    let currentReasoningEl = null;  // live reasoning bubble
    let reasoningText = '';
    let reasoningStartTime = 0;
    let done = false;

    // The session this stream belongs to. Sessions run in parallel: the user
    // may switch to another session while this one is still streaming. The
    // stream keeps running in the background (so the reply still completes and
    // persists); when foreign it does not touch the view but still records
    // every event into a buffer, so returning to the session can rebuild the
    // bubble by replaying the buffer and then resume live rendering.
    const ownerSession = sessionId;
    const isActive = () => ownerSession === sessionId;
    sessionActiveRequest[ownerSession] = requestId;
    updateEditButtonsState();
    // Per-request event buffer used to rebuild the bubble on re-attach.
    const buffer = streamBuffers[requestId] || { items: [], timestamp };
    streamBuffers[requestId] = buffer;
    const clearOwnerRequest = () => {
        if (sessionActiveRequest[ownerSession] === requestId) {
            delete sessionActiveRequest[ownerSession];
            updateEditButtonsState();
        }
        delete streamBuffers[requestId];
    };

    const MAX_RECONNECTS = 10;
    const RECONNECT_BASE_MS = 1000;
    let reconnectCount = 0;

    function ensureBotEl() {
        if (botEl) return;
        if (loadingEl) { loadingEl.remove(); loadingEl = null; }
        botEl = document.createElement('div');
        botEl.className = 'flex gap-3 px-4 sm:px-6 py-3 bot-message-group';
        botEl.dataset.requestId = requestId;
        // Regenerate button starts hidden; it's revealed in the "done"
        // event handler once seq metadata arrives from the backend.
        botEl.innerHTML = `
            <img src="assets/logo.jpg" alt="LightAgent" class="w-8 h-8 rounded-lg flex-shrink-0">
            <div class="min-w-0 flex-1 max-w-[85%]">
                <div class="bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-2xl px-4 py-3 text-sm leading-relaxed msg-content text-slate-700 dark:text-slate-200">
                    <div class="agent-steps"></div>
                    <div class="answer-content sse-streaming"></div>
                    <div class="media-content"></div>
                    <div class="bot-audio-slot"></div>
                </div>
                <div class="flex items-center gap-2 mt-1.5">
                    <span class="text-xs text-slate-400 dark:text-slate-500">${formatTime(timestamp)}</span>
                    <button class="copy-msg-btn text-xs text-slate-300 dark:text-slate-600 hover:text-slate-500 dark:hover:text-slate-400 transition-colors cursor-pointer" title="${currentLang === 'zh' ? '复制' : 'Copy'}" style="display:none">
                        <i class="fas fa-copy"></i>
                    </button>
                    <button class="speak-msg-btn text-xs text-slate-300 dark:text-slate-600 hover:text-slate-500 dark:hover:text-slate-400 transition-colors cursor-pointer" title="${t('speak_msg')}" style="display:none;">
                        <i class="fas fa-volume-up"></i>
                    </button>
                    <button class="regenerate-msg-btn text-xs text-slate-300 dark:text-slate-600 hover:text-primary-400 dark:hover:text-primary-400 transition-colors cursor-pointer" title="${t('regenerate_response')}" style="display:none;">
                        <i class="fas fa-rotate-right"></i>
                    </button>
                </div>
            </div>
        `;
        messagesDiv.appendChild(botEl);
        stepsEl = botEl.querySelector('.agent-steps');
        contentEl = botEl.querySelector('.answer-content');
        mediaEl = botEl.querySelector('.media-content');
    }

    // Holds the live EventSource so terminal events (done/voice_attach/error)
    // can close it. During replay there is no live connection (null).
    let currentEs = null;

    // Render one SSE event into the bubble. Used by the live handler and by
    // re-attach replay alike, so both paths produce identical UI.
    function processSSEItem(item) {
            if (item.type === 'reasoning') {
                ensureBotEl();
                reasoningText += item.content;
                if (!currentReasoningEl) {
                    reasoningStartTime = Date.now();
                    currentReasoningEl = document.createElement('div');
                    currentReasoningEl.className = 'agent-step agent-thinking-step';
                    // During streaming, use a <pre> with a single text node and
                    // append-only updates. This avoids re-parsing markdown and
                    // re-setting innerHTML on every chunk, which is what causes
                    // the page to crash on long chains-of-thought.
                    currentReasoningEl.innerHTML = `
                        <div class="thinking-header" onclick="this.parentElement.classList.toggle('expanded')">
                            <i class="fas fa-lightbulb text-amber-400 flex-shrink-0"></i>
                            <span class="thinking-summary">${t('thinking_in_progress')}</span>
                            <i class="fas fa-chevron-right thinking-chevron"></i>
                        </div>
                        <div class="thinking-full"><pre class="thinking-stream-pre"></pre></div>`;
                    stepsEl.appendChild(currentReasoningEl);
                    const preEl = currentReasoningEl.querySelector('.thinking-stream-pre');
                    preEl.appendChild(document.createTextNode(''));
                    currentReasoningEl._streamTextNode = preEl.firstChild;
                    currentReasoningEl._streamPendingText = '';
                    currentReasoningEl._streamRafScheduled = false;
                    currentReasoningEl._streamCharsRendered = 0;
                    currentReasoningEl._streamCapped = false;
                }
                // Hard cap: once REASONING_RENDER_CAP chars are in the DOM, stop
                // appending further deltas. The full text is still kept in
                // `reasoningText` for finalize-time head+tail rendering.
                if (!currentReasoningEl._streamCapped) {
                    currentReasoningEl._streamPendingText += item.content;
                    if (!currentReasoningEl._streamRafScheduled) {
                        currentReasoningEl._streamRafScheduled = true;
                        const elRef = currentReasoningEl;
                        requestAnimationFrame(() => {
                            elRef._streamRafScheduled = false;
                            if (!elRef.isConnected || !elRef._streamTextNode) return;
                            let pending = elRef._streamPendingText;
                            elRef._streamPendingText = '';
                            if (!pending) return;
                            const remaining = REASONING_RENDER_CAP - elRef._streamCharsRendered;
                            if (remaining <= 0) {
                                elRef._streamCapped = true;
                            } else {
                                if (pending.length > remaining) {
                                    pending = pending.slice(0, remaining);
                                    elRef._streamCapped = true;
                                }
                                elRef._streamTextNode.appendData(pending);
                                elRef._streamCharsRendered += pending.length;
                                if (elRef._streamCapped) {
                                    elRef._streamTextNode.appendData(
                                        '\n\n... [reasoning truncated for display] ...'
                                    );
                                }
                            }
                            scrollChatToBottom();
                        });
                    }
                }

            } else if (item.type === 'delta') {
                ensureBotEl();
                if (currentReasoningEl) {
                    finalizeThinking(currentReasoningEl, reasoningStartTime, reasoningText);
                    currentReasoningEl = null;
                    reasoningText = '';
                }
                accumulatedText += item.content;
                contentEl.innerHTML = renderMarkdown(accumulatedText);
                scrollChatToBottom();

            } else if (item.type === 'message_end') {
                if (item.has_tool_calls && accumulatedText.trim()) {
                    ensureBotEl();
                    const frozenEl = document.createElement('div');
                    frozenEl.className = 'agent-step agent-content-step';
                    frozenEl.innerHTML = `<div class="agent-content-body">${renderMarkdown(accumulatedText.trim())}</div>`;
                    stepsEl.appendChild(frozenEl);
                    accumulatedText = '';
                    contentEl.innerHTML = '';
                    scrollChatToBottom();
                }

            } else if (item.type === 'tool_start') {
                ensureBotEl();
                if (currentReasoningEl) {
                    finalizeThinking(currentReasoningEl, reasoningStartTime, reasoningText);
                    currentReasoningEl = null;
                    reasoningText = '';
                }
                accumulatedText = '';
                contentEl.innerHTML = '';

                // Add tool execution indicator (collapsible)
                const toolEl = document.createElement('div');
                toolEl.className = 'agent-step agent-tool-step tool-streaming';
                toolEl.dataset.progressReceived = 'false';
                const argsStr = formatToolArgs(item.arguments || {});
                toolEl.innerHTML = `
                    <div class="tool-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <i class="fas fa-cog fa-spin text-primary-400 flex-shrink-0 tool-icon"></i>
                        <span class="tool-name">${item.tool}</span>
                        <i class="fas fa-chevron-right tool-chevron"></i>
                    </div>
                    <div class="tool-detail">
                        <div class="tool-detail-section">
                            <div class="tool-detail-label">Input</div>
                            <pre class="tool-detail-content">${argsStr}</pre>
                        </div>
                        <div class="tool-detail-section tool-output-section">
                            <div class="tool-detail-label tool-output-label">Output</div>
                            <pre class="tool-detail-content tool-live-output"></pre>
                        </div>
                    </div>`;
                stepsEl.appendChild(toolEl);
                toolElements.set(item.tool_call_id, toolEl);

                scrollChatToBottom();

            } else if (item.type === 'tool_progress') {
                const toolEl = toolElements.get(item.tool_call_id);
                if (toolEl) {
                    if (toolEl.dataset.progressReceived !== 'true') {
                        toolEl.classList.add('expanded');
                        toolEl.dataset.progressReceived = 'true';
                    }
                    toolEl.querySelector('.tool-live-output').textContent = String(item.content || '');
                    scrollChatToBottom();
                }

            } else if (item.type === 'tool_end') {
                const toolEl = toolElements.get(item.tool_call_id);
                if (toolEl) {
                    const isError = item.status !== 'success';
                    const icon = toolEl.querySelector('.tool-icon');
                    icon.className = isError
                        ? 'fas fa-times text-red-400 flex-shrink-0 tool-icon'
                        : 'fas fa-check text-primary-400 flex-shrink-0 tool-icon';

                    // Show execution time
                    const nameEl = toolEl.querySelector('.tool-name');
                    if (item.execution_time !== undefined) {
                        nameEl.innerHTML += ` <span class="tool-time">${item.execution_time}s</span>`;
                    }

                    // Fill output section
                    const outputLabel = toolEl.querySelector('.tool-output-label');
                    const outputEl = toolEl.querySelector('.tool-live-output');
                    if (outputLabel) outputLabel.textContent = isError ? 'Error' : 'Output';
                    if (outputEl) {
                        outputEl.textContent = item.result ? String(item.result) : '';
                        outputEl.classList.toggle('tool-error-text', isError);
                    }

                    toolEl.classList.remove('tool-streaming');
                    toolEl.classList.remove('expanded');
                    if (!item.result) {
                        const outputSection = toolEl.querySelector('.tool-output-section');
                        if (outputSection) outputSection.remove();
                    }
                    if (isError) toolEl.classList.add('tool-failed');
                    toolElements.delete(item.tool_call_id);
                }

            } else if (item.type === 'image') {
                ensureBotEl();
                const imgEl = document.createElement('img');
                imgEl.src = item.content;
                imgEl.alt = 'screenshot';
                imgEl.style.cssText = 'max-width:600px;border-radius:8px;margin:8px 0;cursor:zoom-in;box-shadow:0 1px 4px rgba(0,0,0,0.1);';
                imgEl.onclick = () => _openImageLightbox(imgEl.src);
                mediaEl.appendChild(imgEl);
                scrollChatToBottom();

            } else if (item.type === 'text') {
                // Intermediate text sent before media items; display it but keep SSE open.
                ensureBotEl();
                contentEl.classList.remove('sse-streaming');
                const textContent = item.content || accumulatedText;
                if (textContent) contentEl.innerHTML = renderMarkdown(textContent);
                applyHighlighting(botEl);
                scrollChatToBottom();

            } else if (item.type === 'video') {
                ensureBotEl();
                const wrapper = document.createElement('div');
                wrapper.innerHTML = _buildVideoHtml(item.content);
                mediaEl.appendChild(wrapper.firstElementChild || wrapper);
                scrollChatToBottom();

            } else if (item.type === 'file') {
                ensureBotEl();
                const fileName = item.file_name || item.content.split('/').pop();
                const fileEl = document.createElement('a');
                fileEl.href = item.content;
                fileEl.download = fileName;
                fileEl.target = '_blank';
                fileEl.className = 'file-attachment';
                fileEl.style.cssText = 'display:inline-flex;align-items:center;gap:6px;padding:8px 14px;margin:8px 0;border-radius:8px;background:var(--bg-secondary,#f3f4f6);color:var(--text-primary,#374151);text-decoration:none;font-size:14px;border:1px solid var(--border-color,#e5e7eb);';
                fileEl.innerHTML = `<i class="fas fa-file-download" style="color:#6b7280;"></i> ${fileName}`;
                mediaEl.appendChild(fileEl);
                scrollChatToBottom();

            } else if (item.type === 'phase') {
                // Coarse progress (e.g. lightagent install-browser); must not close SSE (unlike "done")
                ensureBotEl();
                const wrap = document.createElement('div');
                wrap.className = 'text-xs sm:text-sm text-slate-600 dark:text-slate-400 border-l-2 border-primary-400 pl-2 py-1 my-0.5';
                wrap.textContent = String(item.content || '');
                stepsEl.appendChild(wrap);
                scrollChatToBottom();

            } else if (item.type === 'cancelled') {
                // Agent acknowledged the stop; mark the bubble. A trailing
                // "done" still arrives with the partial answer.
                ensureBotEl();
                if (currentReasoningEl) {
                    finalizeThinking(currentReasoningEl, reasoningStartTime, reasoningText);
                    currentReasoningEl = null;
                    reasoningText = '';
                }
                if (!botEl.querySelector('.agent-cancelled-tag')) {
                    const tag = document.createElement('div');
                    tag.className = 'agent-cancelled-tag text-xs text-amber-600 dark:text-amber-400 mt-1';
                    tag.textContent = (currentLang === 'zh') ? '已中止' : 'Cancelled';
                    stepsEl.appendChild(tag);
                }
                resetSendBtnSendMode();

            } else if (item.type === 'done') {
                // Don't close the stream yet: the backend keeps it open
                // for a short tail to deliver async attachments such as
                // TTS audio (`voice_attach`). It will close the stream on
                // its own via onerror once the tail expires.
                done = true;
                clearOwnerRequest();
                resetSendBtnSendMode();

                const finalTextRaw = item.content || accumulatedText;
                const finalText = localizeCancelMarker(finalTextRaw);

                if (!botEl && finalText) {
                    if (loadingEl) { loadingEl.remove(); loadingEl = null; }
                    addBotMessage(finalText, new Date((item.timestamp || Date.now() / 1000) * 1000), requestId);
                } else if (botEl) {
                    contentEl.classList.remove('sse-streaming');
                    if (finalText) contentEl.innerHTML = renderMarkdown(finalText);
                    contentEl.dataset.rawMd = finalTextRaw || '';
                    const copyBtn = botEl.querySelector('.copy-msg-btn');
                    if (copyBtn && finalText) copyBtn.style.display = '';
                    applyHighlighting(botEl);
                }

                // Backfill seq metadata so edit/regenerate buttons can call
                // the delete API without a page refresh. Backend includes
                // user_seq / bot_seq on the done event after persistence.
                const targetBotEl = botEl || (requestId ? messagesDiv.querySelector(`[data-request-id="${requestId}"]`) : null);
                if (targetBotEl) {
                    if (item.bot_seq !== undefined && item.bot_seq !== null) {
                        targetBotEl.dataset.seq = item.bot_seq;
                    }
                    // Reveal regenerate button now that the seq is wired up.
                    const regenBtn = targetBotEl.querySelector('.regenerate-msg-btn');
                    if (regenBtn) regenBtn.style.display = '';
                    if (item.user_seq !== undefined && item.user_seq !== null) {
                        // Locate the preceding user bubble for this turn.
                        let prev = targetBotEl.previousElementSibling;
                        while (prev && !prev.classList.contains('user-message-group')) {
                            prev = prev.previousElementSibling;
                        }
                        if (prev && !prev.dataset.seq) {
                            prev.dataset.seq = item.user_seq;
                        }
                    }
                }
                renderBotSpeakerButton(botEl, finalText);
                scrollChatToBottom();

                if (titleInfo) {
                    generateSessionTitle(titleInfo.sid, titleInfo.userMsg, '');
                    titleInfo = null;
                } else if (sessionPanelOpen) {
                    loadSessionList();
                }

            } else if (item.type === 'voice_attach') {
                // TTS finished — attach a playable audio element to the
                // current bot bubble. The stream closes right after.
                if (botEl && item.url) {
                    attachAudioToBotBubble(botEl, item.url, { autoplay: true });
                }
                if (currentEs) { currentEs.close(); }
                delete activeStreams[requestId];
                clearOwnerRequest();

            } else if (item.type === 'error') {
                done = true;
                if (currentEs) { currentEs.close(); }
                delete activeStreams[requestId];
                clearOwnerRequest();
                if (loadingEl) { loadingEl.remove(); loadingEl = null; }
                addBotMessage(t('error_send'), new Date());
                resetSendBtnSendMode();
            }
    }

    function connect() {
        const es = new EventSource(`/stream?request_id=${encodeURIComponent(requestId)}`);
        currentEs = es;
        activeStreams[requestId] = es;

        es.onmessage = function(e) {
            let item;
            try { item = JSON.parse(e.data); } catch (_) { return; }

            // Successful data received, reset reconnect counter
            reconnectCount = 0;

            // Record every event for re-attach replay (capped to avoid
            // unbounded growth on very long streams).
            if (item.type === 'tool_progress' && item.tool_call_id) {
                const previousIndex = buffer.items.findIndex(
                    buffered => buffered.type === 'tool_progress'
                        && buffered.tool_call_id === item.tool_call_id
                );
                if (previousIndex >= 0) buffer.items.splice(previousIndex, 1);
            }
            if (buffer.items.length < 5000) buffer.items.push(item);

            // Background session: keep the stream alive so the reply finishes
            // and persists, but skip rendering into the now-foreign view. The
            // buffer above still grows so returning to the session can rebuild
            // the bubble and resume live rendering.
            if (ownerSession !== sessionId) {
                if (item.type === 'done' || item.type === 'error' || item.type === 'voice_attach') {
                    done = true;
                    es.close();
                    delete activeStreams[requestId];
                    clearOwnerRequest();
                }
                return;
            }

            processSSEItem(item);
        };

        es.onerror = function() {
            es.close();
            delete activeStreams[requestId];

            if (done) {
                // Normal close after the post-done tail expired; nothing to do.
                return;
            }

            if (currentReasoningEl) {
                finalizeThinking(currentReasoningEl, reasoningStartTime, reasoningText);
                currentReasoningEl = null;
                reasoningText = '';
            }

            if (reconnectCount < MAX_RECONNECTS) {
                reconnectCount++;
                const delay = Math.min(RECONNECT_BASE_MS * reconnectCount, 5000);
                console.warn(`[SSE] connection lost for ${requestId}, reconnecting in ${delay}ms (attempt ${reconnectCount}/${MAX_RECONNECTS})`);
                setTimeout(connect, delay);
                return;
            }

            // Exhausted retries. Only surface the failure in the owning view —
            // a background session must not mutate the currently shown chat.
            clearOwnerRequest();
            if (!isActive()) return;
            if (loadingEl) { loadingEl.remove(); loadingEl = null; }
            if (!botEl) {
                addBotMessage(t('error_send'), new Date());
            } else if (accumulatedText) {
                contentEl.classList.remove('sse-streaming');
                contentEl.innerHTML = renderMarkdown(accumulatedText);
                applyHighlighting(botEl);
                bindChatKnowledgeLinks(botEl);
            }
            resetSendBtnSendMode();
        };
    }

    // Re-attach replay: rebuild the bubble from buffered events (snapshot,
    // not animated) before connecting for the live tail. `processSSEItem`
    // is the same renderer used by the live onmessage handler, so the
    // snapshot matches exactly what live rendering would have produced.
    if (replayItems && replayItems.length) {
        for (const item of replayItems) {
            try { processSSEItem(item); } catch (_) {}
            if (item.type === 'done' || item.type === 'error' || item.type === 'voice_attach') {
                done = true;
            }
        }
        // If the buffered stream already finished, don't reconnect — the
        // reply is complete and persisted; show its final state and stop.
        if (done) {
            clearOwnerRequest();
            resetSendBtnSendMode();
            scrollChatToBottom(true);
            return;
        }
    }

    connect();
}

function startPolling() {
    const gen = ++pollGeneration;
    isPolling = true;
    let pollInFlight = false;

    function poll() {
        if (gen !== pollGeneration) return;
        if (pollInFlight) return;
        if (document.hidden) { setTimeout(poll, 10000); return; }

        pollInFlight = true;
        fetch('/poll', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        })
        .then(r => r.json())
        .then(data => {
            pollInFlight = false;
            if (gen !== pollGeneration) return;
            if (data.status === 'success' && data.has_content) {
                const rid = data.request_id;
                if (loadingContainers[rid]) {
                    loadingContainers[rid].remove();
                    delete loadingContainers[rid];
                }
                // Skip if this reply is already on screen. Happens when a reply
                // arrives via both the SSE stream and the poll queue (e.g. the
                // user switched away mid-run, leaving the queued reply to be
                // re-fetched on return) — render it only once.
                const already = rid && messagesDiv.querySelector(
                    `[data-request-id="${rid}"]`
                );
                if (!already) {
                    const welcomeScreen = document.getElementById('welcome-screen');
                    if (welcomeScreen) welcomeScreen.remove();
                    addBotMessage(data.content, new Date(data.timestamp * 1000), rid);
                    scrollChatToBottom();
                }
            }
            const delay = (data.status === 'success' && data.has_content) ? 5000 : 10000;
            setTimeout(poll, delay);
        })
        .catch(() => { pollInFlight = false; setTimeout(poll, 10000); });
    }
    poll();
}

function createUserMessageEl(content, timestamp, attachments) {
    const el = document.createElement('div');
    el.className = 'flex justify-end px-4 sm:px-6 py-3 user-message-group';

    let attachHtml = '';
    if (attachments && attachments.length > 0) {
        const items = attachments.map(a => {
            if (a.file_type === 'image') {
                return `<img src="${a.preview_url}" alt="${escapeHtml(a.file_name)}" class="user-msg-image">`;
            }
            const icon = a.file_type === 'video'
                ? 'fa-film'
                : (a.file_type === 'directory' ? 'fa-folder-tree' : 'fa-file-alt');
            const suffix = a.file_type === 'directory' && a.file_count
                ? ` (${a.file_count})`
                : '';
            return `<div class="user-msg-file"><i class="fas ${icon}"></i> ${escapeHtml(a.file_name)}${suffix}</div>`;
        }).join('');
        attachHtml = `<div class="user-msg-attachments">${items}</div>`;
    }

    const textHtml = content ? renderMarkdown(content) : '';
    el.innerHTML = `
        <div class="max-w-[75%] sm:max-w-[60%]">
            <div class="bg-primary-400 text-white rounded-2xl px-4 py-2.5 text-sm leading-relaxed msg-content user-bubble">
                ${attachHtml}${textHtml}
            </div>
            <div class="flex items-center justify-end gap-2 mt-1.5">
                <button class="edit-msg-btn text-xs text-slate-300 dark:text-slate-600 hover:text-primary-400 dark:hover:text-primary-400 transition-colors cursor-pointer" title="${t('edit_message')}">
                    <i class="fas fa-pen-to-square"></i>
                </button>
                <button class="delete-msg-btn text-xs text-slate-300 dark:text-slate-600 hover:text-red-500 dark:hover:text-red-400 transition-colors cursor-pointer" title="${t('delete_message_title')}">
                    <i class="fas fa-trash"></i>
                </button>
                <span class="text-xs text-slate-400 dark:text-slate-500">${formatTime(timestamp)}</span>
            </div>
        </div>
    `;
    // Store raw content for editing
    el.dataset.rawContent = content || '';
    return el;
}

function renderToolCallsHtml(toolCalls) {
    if (!toolCalls || toolCalls.length === 0) return '';
    return toolCalls.map(tc => {
        const argsStr = formatToolArgs(tc.arguments || {});
        const resultStr = tc.result ? escapeHtml(String(tc.result)) : '';
        const hasResult = !!resultStr;
        return `
<div class="agent-step agent-tool-step">
    <div class="tool-header" onclick="this.parentElement.classList.toggle('expanded')">
        <i class="fas fa-check text-primary-400 flex-shrink-0 tool-icon"></i>
        <span class="tool-name">${escapeHtml(tc.name || '')}</span>
        <i class="fas fa-chevron-right tool-chevron"></i>
    </div>
    <div class="tool-detail">
        <div class="tool-detail-section">
            <div class="tool-detail-label">Input</div>
            <pre class="tool-detail-content">${argsStr}</pre>
        </div>
        ${hasResult ? `
        <div class="tool-detail-section tool-output-section">
            <div class="tool-detail-label">Output</div>
            <pre class="tool-detail-content">${resultStr}</pre>
        </div>` : ''}
    </div>
</div>`;
    }).join('');
}

// Cap for rendering reasoning content in the bubble. Beyond this size,
// we skip markdown rendering entirely and show plain text head + tail to
// keep the page responsive (very long chains-of-thought can otherwise
// stall or crash the browser when re-parsed by marked.js).
// Keep this in sync with backend MAX_STORED_REASONING_CHARS and
// MAX_REASONING_STREAM_CHARS so storage / SSE / display stay aligned.
const REASONING_RENDER_CAP = 4 * 1024; // 4 KB

function _truncateReasoningForDisplay(text) {
    if (!text || text.length <= REASONING_RENDER_CAP) return { text, truncated: false, omitted: 0 };
    const half = Math.floor(REASONING_RENDER_CAP / 2);
    const head = text.slice(0, half);
    const tail = text.slice(-half);
    return {
        text: head + '\n\n... [' + (text.length - head.length - tail.length) + ' chars omitted] ...\n\n' + tail,
        truncated: true,
        omitted: text.length - head.length - tail.length,
    };
}

function _renderReasoningBody(text) {
    // For short reasoning, render as markdown. For long ones, fall back to
    // an escaped <pre> block to avoid expensive markdown parsing.
    const { text: shown, truncated } = _truncateReasoningForDisplay(text);
    if (truncated || shown.length > REASONING_RENDER_CAP) {
        return '<pre class="thinking-stream-pre">' + escapeHtml(shown) + '</pre>';
    }
    return renderMarkdown(shown);
}

function finalizeThinking(el, startTime, text) {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    el.querySelector('.thinking-summary').textContent = t('thinking_done');
    const fullDiv = el.querySelector('.thinking-full');
    fullDiv.innerHTML = `<div class="thinking-duration">${t('thinking_duration')} ${elapsed}s</div>` + _renderReasoningBody(text);
}

function renderThinkingHtml(text) {
    if (!text || !text.trim()) return '';
    const full = text.trim();
    return `
<div class="agent-step agent-thinking-step">
    <div class="thinking-header" onclick="this.parentElement.classList.toggle('expanded')">
        <i class="fas fa-lightbulb text-amber-400 flex-shrink-0"></i>
        <span class="thinking-summary">${t('thinking_done')}</span>
        <i class="fas fa-chevron-right thinking-chevron"></i>
    </div>
    <div class="thinking-full">${_renderReasoningBody(full)}</div>
</div>`;
}

function renderStepsHtml(steps) {
    if (!steps || steps.length === 0) return { stepsHtml: '', finalContent: '' };

    // Find the index of the last content step — it becomes the main answer, not a step
    let lastContentIdx = -1;
    for (let i = steps.length - 1; i >= 0; i--) {
        if (steps[i].type === 'content') { lastContentIdx = i; break; }
    }

    let html = '';
    let lastContentText = '';
    for (let i = 0; i < steps.length; i++) {
        const step = steps[i];
        if (step.type === 'thinking') {
            html += renderThinkingHtml(step.content);
        } else if (step.type === 'content') {
            if (i === lastContentIdx) {
                lastContentText = step.content;
            } else {
                html += `<div class="agent-step agent-content-step"><div class="agent-content-body">${renderMarkdown(step.content)}</div></div>`;
            }
        } else if (step.type === 'tool') {
            const argsStr = formatToolArgs(step.arguments || {});
            const resultStr = step.result ? escapeHtml(String(step.result)) : '';
            const isErr = step.is_error === true;
            const iconClass = isErr
                ? 'fas fa-times text-red-400 flex-shrink-0 tool-icon'
                : 'fas fa-check text-primary-400 flex-shrink-0 tool-icon';
            html += `
<div class="agent-step agent-tool-step${isErr ? ' tool-failed' : ''}">
    <div class="tool-header" onclick="this.parentElement.classList.toggle('expanded')">
        <i class="${iconClass}"></i>
        <span class="tool-name">${escapeHtml(step.name || '')}</span>
        <i class="fas fa-chevron-right tool-chevron"></i>
    </div>
    <div class="tool-detail">
        <div class="tool-detail-section">
            <div class="tool-detail-label">Input</div>
            <pre class="tool-detail-content">${argsStr}</pre>
        </div>
        ${resultStr ? `
        <div class="tool-detail-section tool-output-section">
            <div class="tool-detail-label">${isErr ? 'Error' : 'Output'}</div>
            <pre class="tool-detail-content${isErr ? ' tool-error-text' : ''}">${resultStr}</pre>
        </div>` : ''}
    </div>
</div>`;
            // If this tool sent a file (send/read tool), render the media inline
            // so it persists across page refreshes (SSE-only file events are not stored).
            const mediaHtml = _renderSentFileFromToolResult(step);
            if (mediaHtml) html += mediaHtml;
        }
    }
    return { stepsHtml: html, lastContentText };
}

// Extract file-to-send metadata from a tool's result and render an inline preview.
// Returns '' if the result isn't a file_to_send payload.
function _renderSentFileFromToolResult(step) {
    if (!step || !step.result) return '';
    let payload;
    try {
        payload = typeof step.result === 'string' ? JSON.parse(step.result) : step.result;
    } catch (_) { return ''; }
    if (!payload || payload.type !== 'file_to_send' || !payload.path) return '';
    const webUrl = _toWebUrl(payload.path);
    const fileType = payload.file_type || 'file';
    const fileName = payload.file_name || payload.path.split('/').pop();
    if (fileType === 'image') {
        return `<div class="agent-step">${_buildImageHtml(webUrl)}</div>`;
    }
    if (fileType === 'video') {
        return `<div class="agent-step">${_buildVideoHtml(webUrl)}</div>`;
    }
    return `<div class="agent-step"><a href="${webUrl}" download="${escapeHtml(fileName)}" target="_blank" ` +
        `style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;margin:8px 0;border-radius:8px;` +
        `background:var(--bg-secondary,#f3f4f6);color:var(--text-primary,#374151);text-decoration:none;font-size:14px;` +
        `border:1px solid var(--border-color,#e5e7eb);">` +
        `<i class="fas fa-file-download" style="color:#6b7280;"></i> ${escapeHtml(fileName)}</a></div>`;
}

// Cosmetic translator for cancel markers persisted in history.
// History keeps the English canonical form for the LLM; only display is localized.
function localizeCancelMarker(text) {
    if (!text) return text;
    if (currentLang !== 'zh') return text;
    return text
        .replace(/_\(Cancelled by user\)_/g, '_(用户已中止)_')
        .replace(/_\(Cancelled\)_/g, '_(已中止)_');
}

function createBotMessageEl(content, timestamp, requestId, msg) {
    const el = document.createElement('div');
    el.className = 'flex gap-3 px-4 sm:px-6 py-3 bot-message-group';
    if (requestId) el.dataset.requestId = requestId;

    let stepsHtml = '';
    let displayContent = localizeCancelMarker(content);

    if (msg && msg.steps && msg.steps.length > 0) {
        // New format: ordered steps with interleaved content
        const result = renderStepsHtml(msg.steps);
        stepsHtml = result.stepsHtml;
        // The final content (last text after all steps) is the main answer
        displayContent = content || result.lastContentText;
    } else {
        // Legacy format: separate tool_calls + optional reasoning
        const toolCalls = msg && msg.tool_calls;
        const reasoning = msg && msg.reasoning;
        stepsHtml = renderThinkingHtml(reasoning) + renderToolCallsHtml(toolCalls);
    }

    // Self-evolution bubbles get a small badge so the user can feel the agent
    // learned something on its own (text itself stays clean). History replay
    // carries msg.kind; live pushes are identified by the evolution_ request id.
    const isEvolution = (msg && msg.kind === 'evolution')
        || (typeof requestId === 'string' && requestId.startsWith('evolution_'));
    const evolutionBadge = isEvolution
        ? `<div class="flex items-center gap-1 mb-1.5 text-xs text-slate-400 dark:text-slate-500">
                <i class="fas fa-seedling text-[11px]"></i>
                <span>${t('evolution_badge')}</span>
           </div>`
        : '';

    el.innerHTML = `
        <img src="assets/logo.jpg" alt="LightAgent" class="w-8 h-8 rounded-lg flex-shrink-0">
        <div class="min-w-0 flex-1 max-w-[85%]">
            <div class="bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-2xl px-4 py-3 text-sm leading-relaxed msg-content text-slate-700 dark:text-slate-200">
                ${evolutionBadge}
                ${stepsHtml ? `<div class="agent-steps">${stepsHtml}</div>` : ''}
                <div class="answer-content">${renderMarkdown(displayContent)}</div>
                <div class="bot-audio-slot"></div>
            </div>
            <div class="flex items-center gap-2 mt-1.5">
                <span class="text-xs text-slate-400 dark:text-slate-500">${formatTime(timestamp)}</span>
                <button class="copy-msg-btn text-xs text-slate-300 dark:text-slate-600 hover:text-slate-500 dark:hover:text-slate-400 transition-colors cursor-pointer" title="${currentLang === 'zh' ? '复制' : 'Copy'}">
                    <i class="fas fa-copy"></i>
                </button>
                <button class="speak-msg-btn text-xs text-slate-300 dark:text-slate-600 hover:text-slate-500 dark:hover:text-slate-400 transition-colors cursor-pointer" title="${t('speak_msg')}" style="display:none;">
                    <i class="fas fa-volume-up"></i>
                </button>
                <button class="regenerate-msg-btn text-xs text-slate-300 dark:text-slate-600 hover:text-primary-400 dark:hover:text-primary-400 transition-colors cursor-pointer" title="${t('regenerate_response')}">
                    <i class="fas fa-rotate-right"></i>
                </button>
            </div>
        </div>
    `;
    el.querySelector('.answer-content').dataset.rawMd = displayContent;
    // Existing TTS attachment (history replay): mount the player up-front.
    const existingAudio = msg && msg.extras && msg.extras.audio && msg.extras.audio.url;
    if (existingAudio) {
        attachAudioToBotBubble(el, existingAudio, { autoplay: false });
    }
    renderBotSpeakerButton(el, displayContent);
    applyHighlighting(el);
    bindChatKnowledgeLinks(el);
    return el;
}

// Append (or replace) a small audio player inside a bot bubble's
// dedicated `.bot-audio-slot`. Used by both live TTS pushes and history
// replay. Silent failures: never throws.
function attachAudioToBotBubble(botEl, audioUrl, opts) {
    try {
        if (!botEl || !audioUrl) return;
        const slot = botEl.querySelector('.bot-audio-slot');
        if (!slot) return;
        slot.innerHTML = '';
        slot.style.marginTop = '6px';
        const pill = renderVoicePill(audioUrl, { autoplay: !!(opts && opts.autoplay) });
        slot.appendChild(pill);
        const speakBtn = botEl.querySelector('.speak-msg-btn');
        if (speakBtn) speakBtn.style.display = 'none';
    } catch (_) { /* silent */ }
}

// Build a compact play/pause + progress + duration pill that wraps a
// hidden <audio>. Returns the root element; safe to embed anywhere.
function renderVoicePill(audioUrl, opts) {
    opts = opts || {};
    const wrap = document.createElement('div');
    wrap.className = 'voice-pill';
    wrap.innerHTML = `
        <button type="button" class="voice-pill-btn" data-state="play" aria-label="play">
            <i class="fas fa-play"></i>
        </button>
        <div class="voice-pill-track"><div class="voice-pill-fill"></div></div>
        <span class="voice-pill-time">0:00</span>
        <audio preload="metadata" src="${audioUrl}"></audio>
    `;
    const btn = wrap.querySelector('.voice-pill-btn');
    const fill = wrap.querySelector('.voice-pill-fill');
    const timeEl = wrap.querySelector('.voice-pill-time');
    const audio = wrap.querySelector('audio');

    const fmt = (s) => {
        if (!isFinite(s) || s < 0) s = 0;
        const m = Math.floor(s / 60);
        const r = Math.floor(s % 60);
        return `${m}:${r < 10 ? '0' : ''}${r}`;
    };
    const setIcon = (state) => {
        btn.dataset.state = state;
        btn.querySelector('i').className = state === 'pause' ? 'fas fa-pause' : 'fas fa-play';
        btn.setAttribute('aria-label', state === 'pause' ? 'pause' : 'play');
    };

    audio.addEventListener('loadedmetadata', () => {
        if (audio.duration && isFinite(audio.duration)) timeEl.textContent = fmt(audio.duration);
    });
    audio.addEventListener('timeupdate', () => {
        const dur = audio.duration || 0;
        if (dur > 0) {
            fill.style.width = `${Math.min(100, (audio.currentTime / dur) * 100)}%`;
            timeEl.textContent = fmt(dur - audio.currentTime);
        }
    });
    audio.addEventListener('ended', () => {
        setIcon('play');
        fill.style.width = '0%';
        timeEl.textContent = fmt(audio.duration || 0);
    });
    audio.addEventListener('play',  () => setIcon('pause'));
    audio.addEventListener('pause', () => setIcon('play'));

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (audio.paused) {
            audio.play().catch(() => {});
        } else {
            audio.pause();
        }
    });

    if (opts.autoplay) {
        // Autoplay may be blocked by the browser; fall back silently and
        // let the user tap the play button.
        const tryPlay = () => audio.play().catch(() => {});
        if (audio.readyState >= 2) tryPlay();
        else audio.addEventListener('canplay', tryPlay, { once: true });
    }
    return wrap;
}

// Show the manual "read aloud" button when TTS is configured but the
// bubble has no audio yet. Lazily probes capability via /api/models so
// we don't expose the button when nothing can synthesize speech.
function renderBotSpeakerButton(botEl, text) {
    if (!botEl || !text || !text.trim()) return;
    const btn = botEl.querySelector('.speak-msg-btn');
    if (!btn) return;
    if (botEl.querySelector('.bot-audio-slot audio')) return;
    _isTtsReady().then(ready => {
        if (!ready) return;
        btn.style.display = '';
        btn.onclick = () => _triggerManualTts(btn, botEl, text);
    });
}

let _ttsReadyPromise = null;
let _ttsReadyTs = 0;
function _isTtsReady() {
    // Cache for 30s to avoid hammering /api/models on every bubble.
    if (_ttsReadyPromise && Date.now() - _ttsReadyTs < 30000) {
        return _ttsReadyPromise;
    }
    _ttsReadyTs = Date.now();
    _ttsReadyPromise = fetch('/api/models')
        .then(r => r.json())
        .then(data => {
            const tts = data && data.capabilities && data.capabilities.tts;
            if (!tts) return false;
            return Boolean(tts.current_provider || tts.suggested_provider);
        })
        .catch(() => false);
    return _ttsReadyPromise;
}

function _triggerManualTts(btn, botEl, text) {
    if (btn.dataset.busy === '1') return;
    btn.dataset.busy = '1';
    const icon = btn.querySelector('i');
    const prev = icon ? icon.className : '';
    if (icon) icon.className = 'fas fa-spinner fa-spin';
    fetch('/api/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, session_id: sessionId }),
    })
        .then(r => r.json())
        .then(data => {
            if (data && data.status === 'success' && data.audio_url) {
                attachAudioToBotBubble(botEl, data.audio_url, { autoplay: true });
            }
        })
        .catch(() => {})
        .finally(() => {
            btn.dataset.busy = '0';
            if (icon) icon.className = prev || 'fas fa-volume-up';
        });
}

function addUserMessage(content, timestamp, attachments) {
    const el = createUserMessageEl(content, timestamp, attachments);
    messagesDiv.appendChild(el);
    _autoScrollEnabled = true;
    scrollChatToBottom(true);
}

function addBotMessage(content, timestamp, requestId) {
    const el = createBotMessageEl(content, timestamp, requestId);
    messagesDiv.appendChild(el);
    scrollChatToBottom();
}

// Load conversation history from the server (page 1 = most recent messages).
// Subsequent pages prepend older messages when the user scrolls to the top.
function loadHistory(page) {
    if (historyLoading) return;
    historyLoading = true;

    fetch(`/api/history?session_id=${encodeURIComponent(sessionId)}&page=${page}&page_size=20`)
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success' || data.messages.length === 0) return;

            const prevScrollHeight = messagesDiv.scrollHeight;
            const isFirstLoad = page === 1;

            // On first load, remove the welcome screen if history exists
            if (isFirstLoad) {
                const ws = document.getElementById('welcome-screen');
                if (ws) ws.remove();
            }

            // Build a fragment of history message elements in chronological order
            const fragment = document.createDocumentFragment();

            if (data.has_more && page > 1) {
                // Keep the "load more" sentinel in place (inserted below)
            }

            const ctxStartSeq = data.context_start_seq || 0;
            let dividerInserted = false;

            data.messages.forEach(msg => {
                const hasContent = msg.content && msg.content.trim();
                const hasToolCalls = msg.role === 'assistant' && msg.tool_calls && msg.tool_calls.length > 0;
                if (!hasContent && !hasToolCalls) return;

                // Insert context divider when transitioning from above to below boundary
                if (ctxStartSeq > 0 && !dividerInserted && msg._seq !== undefined && msg._seq >= ctxStartSeq) {
                    dividerInserted = true;
                    const divider = document.createElement('div');
                    divider.className = 'context-divider';
                    divider.innerHTML = `<span>${t('context_cleared')}</span>`;
                    fragment.appendChild(divider);
                }

                const ts = new Date(msg.created_at * 1000);
                const el = msg.role === 'user'
                    ? createUserMessageEl(msg.content, ts)
                    : createBotMessageEl(msg.content || '', ts, null, msg);
                // Store seq for delete functionality
                if (msg._seq !== undefined) {
                    el.dataset.seq = msg._seq;
                }
                fragment.appendChild(el);
            });

            // If context was cleared but no new messages exist yet, append divider at the end
            if (ctxStartSeq > 0 && !dividerInserted) {
                const divider = document.createElement('div');
                divider.className = 'context-divider';
                divider.innerHTML = `<span>${t('context_cleared')}</span>`;
                fragment.appendChild(divider);
            }

            // Prepend history above any existing messages
            const sentinel = document.getElementById('history-load-more');
            const insertBefore = sentinel ? sentinel.nextSibling : messagesDiv.firstChild;
            messagesDiv.insertBefore(fragment, insertBefore);
            updateEditButtonsState();

            // Manage the "load more" sentinel at the very top
            if (data.has_more) {
                if (!document.getElementById('history-load-more')) {
                    const btn = document.createElement('div');
                    btn.id = 'history-load-more';
                    btn.className = 'flex justify-center py-3';
                    btn.innerHTML = `<button class="text-xs text-slate-400 dark:text-slate-500 hover:text-primary-400 transition-colors" onclick="loadHistory(historyPage + 1)">Load earlier messages</button>`;
                    messagesDiv.insertBefore(btn, messagesDiv.firstChild);
                }
            } else {
                const sentinel = document.getElementById('history-load-more');
                if (sentinel) sentinel.remove();
            }

            historyHasMore = data.has_more;
            historyPage = page;

            if (isFirstLoad) {
                // Scroll to the very bottom after the DOM settles. A single
                // rAF isn't enough: markdown/code-highlight/images keep growing
                // scrollHeight after the first paint, leaving the last bubble's
                // timestamp clipped. Re-pin a few times to catch late layout.
                requestAnimationFrame(() => scrollChatToBottom(true));
                [120, 350, 700].forEach(d => setTimeout(() => scrollChatToBottom(true), d));
            } else {
                // Restore scroll position so loading older messages doesn't jump the view
                messagesDiv.scrollTop = messagesDiv.scrollHeight - prevScrollHeight;
            }
        })
        .catch(() => {})
        .finally(() => { historyLoading = false; });
}

function addLoadingIndicator() {
    const el = document.createElement('div');
    el.className = 'flex gap-3 px-4 sm:px-6 py-3';
    el.innerHTML = `
        <img src="assets/logo.jpg" alt="LightAgent" class="w-8 h-8 rounded-lg flex-shrink-0">
        <div class="bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-2xl px-4 py-3">
            <div class="flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-primary-400 animate-pulse-dot" style="animation-delay: 0s"></span>
                <span class="w-2 h-2 rounded-full bg-primary-400 animate-pulse-dot" style="animation-delay: 0.2s"></span>
                <span class="w-2 h-2 rounded-full bg-primary-400 animate-pulse-dot" style="animation-delay: 0.4s"></span>
            </div>
        </div>
    `;
    messagesDiv.appendChild(el);
    scrollChatToBottom();
    return el;
}

function newChat(optimistic = true) {
    // Do NOT close active streams: other sessions keep streaming in the
    // background (each stream self-guards against the foreign view) and their
    // replies still complete and persist.

    // Generate a fresh session and persist it so the next page load also starts clean
    sessionId = generateSessionId();
    localStorage.setItem(SESSION_ID_KEY, sessionId);
    resetSendBtnSendMode();  // fresh session has no in-flight reply
    startPolling();  // bump generation so old loop self-cancels, new loop uses fresh sessionId
    messagesDiv.innerHTML = '';
    const ws = document.createElement('div');
    ws.id = 'welcome-screen';
    ws.className = 'flex flex-col items-center justify-center h-full px-6 pb-16';
    ws.style.paddingTop = '6vh';
    ws.innerHTML = `
        <img src="assets/logo.jpg" alt="LightAgent" class="w-16 h-16 rounded-2xl mb-6 shadow-lg shadow-primary-500/20">
        <h1 class="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-3">${appConfig.title || 'LightAgent'}</h1>
        <p class="text-slate-500 dark:text-slate-400 text-center max-w-lg mb-10 leading-relaxed" data-i18n="welcome_subtitle">${t('welcome_subtitle')}</p>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 w-full max-w-2xl">
            <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                <div class="flex items-center gap-2 mb-2">
                    <div class="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center">
                        <i class="fas fa-folder-open text-blue-500 text-xs"></i>
                    </div>
                    <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_sys_title">${t('example_sys_title')}</span>
                </div>
                <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_sys_text">${t('example_sys_text')}</p>
            </div>
            <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                <div class="flex items-center gap-2 mb-2">
                    <div class="w-7 h-7 rounded-lg bg-amber-50 dark:bg-amber-900/30 flex items-center justify-center">
                        <i class="fas fa-clock text-amber-500 text-xs"></i>
                    </div>
                    <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_task_title">${t('example_task_title')}</span>
                </div>
                <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_task_text">${t('example_task_text')}</p>
            </div>
            <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                <div class="flex items-center gap-2 mb-2">
                    <div class="w-7 h-7 rounded-lg bg-emerald-50 dark:bg-emerald-900/30 flex items-center justify-center">
                        <i class="fas fa-code text-emerald-500 text-xs"></i>
                    </div>
                    <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_code_title">${t('example_code_title')}</span>
                </div>
                <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_code_text">${t('example_code_text')}</p>
            </div>
            <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                <div class="flex items-center gap-2 mb-2">
                    <div class="w-7 h-7 rounded-lg bg-violet-50 dark:bg-violet-900/30 flex items-center justify-center">
                        <i class="fas fa-book text-violet-500 text-xs"></i>
                    </div>
                    <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_knowledge_title">${t('example_knowledge_title')}</span>
                </div>
                <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_knowledge_text">${t('example_knowledge_text')}</p>
            </div>
            <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200">
                <div class="flex items-center gap-2 mb-2">
                    <div class="w-7 h-7 rounded-lg bg-rose-50 dark:bg-rose-900/30 flex items-center justify-center">
                        <i class="fas fa-puzzle-piece text-rose-500 text-xs"></i>
                    </div>
                    <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_skill_title">${t('example_skill_title')}</span>
                </div>
                <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_skill_text">${t('example_skill_text')}</p>
            </div>
            <div class="example-card group bg-white dark:bg-[#1A1A1A] border border-slate-200 dark:border-white/10 rounded-xl p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-600 hover:shadow-md transition-all duration-200" data-send="/help">
                <div class="flex items-center gap-2 mb-2">
                    <div class="w-7 h-7 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
                        <i class="fas fa-terminal text-slate-500 text-xs"></i>
                    </div>
                    <span class="font-medium text-sm text-slate-700 dark:text-slate-200" data-i18n="example_web_title">${t('example_web_title')}</span>
                </div>
                <p class="text-sm text-slate-500 dark:text-slate-400 leading-relaxed" data-i18n="example_web_text">${t('example_web_text')}</p>
            </div>
        </div>
    `;
    messagesDiv.appendChild(ws);
    ws.querySelectorAll('.example-card').forEach(card => {
        card.addEventListener('click', () => {
            const sendText = card.dataset.send;
            if (sendText) {
                chatInput.value = sendText;
                chatInput.dispatchEvent(new Event('input'));
                chatInput.focus();
                return;
            }
            const textEl = card.querySelector('[data-i18n*="text"]');
            if (textEl) {
                chatInput.value = textEl.textContent;
                chatInput.dispatchEvent(new Event('input'));
                chatInput.focus();
            }
        });
    });
    if (currentView !== 'chat') navigateTo('chat');

    // Show panel and load full session list, then prepend the new session on top
    const panel = document.getElementById('session-panel');
    if (panel && !sessionPanelOpen) {
        sessionPanelOpen = true;
        panel.classList.remove('hidden');
        _showSessionOverlay();
        _persistPanelState();
    }
    // Only prepend an optimistic "new chat" item when this is a real new-chat
    // action. When called after deleting the current session, skip it: the
    // fresh session has no backend record yet, so inserting it would leave an
    // empty, undeletable item in the list (deleting it just spawns another).
    const newSid = sessionId;
    if (optimistic) {
        loadSessionList(() => _addOptimisticSessionItem(newSid));
    } else {
        loadSessionList();
    }
}

// =====================================================================
// Session Panel
// =====================================================================

const SESSION_PANEL_KEY = 'lightagent_session_panel_open';
let sessionPanelOpen = localStorage.getItem(SESSION_PANEL_KEY) === '1';

function _persistPanelState() {
    localStorage.setItem(SESSION_PANEL_KEY, sessionPanelOpen ? '1' : '0');
}

function _isMobileView() {
    return window.innerWidth <= 768;
}

function _showSessionOverlay() {
    if (!_isMobileView()) return;
    const overlay = document.getElementById('session-panel-overlay');
    if (overlay) overlay.classList.remove('hidden');
}

function _hideSessionOverlay() {
    const overlay = document.getElementById('session-panel-overlay');
    if (overlay) overlay.classList.add('hidden');
}

function closeSessionPanel() {
    const panel = document.getElementById('session-panel');
    if (!panel || !sessionPanelOpen) return;
    sessionPanelOpen = false;
    panel.classList.add('hidden');
    _hideSessionOverlay();
    _persistPanelState();
}

function toggleSessionPanel() {
    const panel = document.getElementById('session-panel');
    if (!panel) return;
    sessionPanelOpen = !sessionPanelOpen;
    panel.classList.toggle('hidden', !sessionPanelOpen);
    if (sessionPanelOpen) {
        _showSessionOverlay();
    } else {
        _hideSessionOverlay();
    }
    _persistPanelState();
    if (sessionPanelOpen) loadSessionList();
}

function openSessionPanel() {
    const panel = document.getElementById('session-panel');
    if (!panel || sessionPanelOpen) return;
    sessionPanelOpen = true;
    panel.classList.remove('hidden');
    _showSessionOverlay();
    _persistPanelState();
    loadSessionList();
}

function _restoreSessionPanel() {
    const panel = document.getElementById('session-panel');
    if (!panel) return;
    if (sessionPanelOpen && !_isMobileView()) {
        panel.classList.remove('hidden');
        _showSessionOverlay();
        loadSessionList();
    } else {
        panel.classList.add('hidden');
        _hideSessionOverlay();
    }
}

function _applyInputTooltips() {
    const set = (id, key, pos) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.setAttribute('data-tooltip', t(key));
        el.removeAttribute('title');
        if (pos) el.setAttribute('data-tooltip-pos', pos);
    };
    set('new-chat-btn', 'tip_new_chat');
    set('clear-context-btn', 'tip_clear_context');
    set('attach-btn', 'tip_attach');
    set('session-toggle-btn', 'session_history', 'bottom');
}

function _addOptimisticSessionItem(sid) {
    const container = document.getElementById('session-list');
    if (!container) return;

    const emptyEl = container.querySelector('.session-empty');
    if (emptyEl) emptyEl.remove();

    document.querySelectorAll('.session-item.active').forEach(el => el.classList.remove('active'));

    const todayLabel = t('today');
    let firstGroup = container.querySelector('.session-group-label');
    if (!firstGroup || firstGroup.textContent !== todayLabel) {
        const header = document.createElement('div');
        header.className = 'session-group-label';
        header.textContent = todayLabel;
        container.prepend(header);
        firstGroup = header;
    }

    const title = t('new_chat');
    const item = document.createElement('div');
    item.className = 'session-item active';
    item.dataset.sessionId = sid;
    item.innerHTML = `
        <i class="fas fa-message session-icon"></i>
        <span class="session-title" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
        <button class="session-rename" onclick="event.stopPropagation(); renameSession('${sid}')" title="${escapeHtml(t('rename_session'))}">
            <i class="fas fa-pen"></i>
        </button>
        <button class="session-delete" onclick="event.stopPropagation(); deleteSession('${sid}')" title="Delete">
            <i class="fas fa-trash-can"></i>
        </button>
    `;
    item.addEventListener('click', () => switchSession(sid));
    firstGroup.insertAdjacentElement('afterend', item);
}

function _sessionTimeGroup(ts) {
    const now = new Date();
    const d = new Date(ts * 1000);
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
    if (d >= today) return t('today');
    if (d >= yesterday) return t('yesterday');
    return t('earlier');
}

let _sessionPage = 1;
let _sessionHasMore = false;
let _sessionLoading = false;
const _SESSION_PAGE_SIZE = 50;

function loadSessionList(onDone) {
    const container = document.getElementById('session-list');
    if (!container) return;

    _sessionPage = 1;
    _sessionHasMore = false;

    _fetchSessionPage(1, true, onDone);
}

function _fetchSessionPage(page, clear, onDone) {
    if (_sessionLoading) return;
    _sessionLoading = true;

    const container = document.getElementById('session-list');
    if (!container) { _sessionLoading = false; return; }

    // Remove existing "load more" sentinel before fetching
    const oldSentinel = container.querySelector('.session-load-more');
    if (oldSentinel) oldSentinel.remove();

    fetch(`/api/sessions?page=${page}&page_size=${_SESSION_PAGE_SIZE}`)
        .then(r => r.json())
        .then(data => {
            _sessionLoading = false;
            if (data.status !== 'success') return;

            if (clear) container.innerHTML = '';

            const sessions = data.sessions || [];
            _sessionPage = page;
            _sessionHasMore = !!data.has_more;

            if (sessions.length === 0 && page === 1) {
                container.innerHTML = '<div class="session-empty">' + t('untitled_session') + '</div>';
                if (typeof onDone === 'function') onDone();
                return;
            }

            // Track last group label already in the container
            const existingLabels = container.querySelectorAll('.session-group-label');
            let lastGroup = existingLabels.length > 0
                ? existingLabels[existingLabels.length - 1].textContent
                : '';

            sessions.forEach(s => {
                const group = _sessionTimeGroup(s.last_active);
                if (group !== lastGroup) {
                    lastGroup = group;
                    const header = document.createElement('div');
                    header.className = 'session-group-label';
                    header.textContent = group;
                    container.appendChild(header);
                }

                const item = document.createElement('div');
                const isActive = s.session_id === sessionId;
                item.className = 'session-item' + (isActive ? ' active' : '');
                item.dataset.sessionId = s.session_id;

                const title = s.title || t('untitled_session');
                item.innerHTML = `
                    <i class="fas fa-message session-icon"></i>
                    <span class="session-title" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
                    <button class="session-rename" onclick="event.stopPropagation(); renameSession('${s.session_id}')" title="${escapeHtml(t('rename_session'))}">
                        <i class="fas fa-pen"></i>
                    </button>
                    <button class="session-delete" onclick="event.stopPropagation(); deleteSession('${s.session_id}')" title="Delete">
                        <i class="fas fa-trash-can"></i>
                    </button>
                `;
                item.addEventListener('click', () => switchSession(s.session_id));
                container.appendChild(item);
            });

            if (typeof onDone === 'function') onDone();
        })
        .catch(() => { _sessionLoading = false; });
}

function _onSessionListScroll() {
    if (!_sessionHasMore || _sessionLoading) return;
    const container = document.getElementById('session-list');
    if (!container) return;
    // Trigger when scrolled near the bottom (within 60px)
    if (container.scrollHeight - container.scrollTop - container.clientHeight < 60) {
        _fetchSessionPage(_sessionPage + 1, false);
    }
}

// Attach scroll listener once DOM is ready
(function _initSessionScroll() {
    const el = document.getElementById('session-list');
    if (el) {
        el.addEventListener('scroll', _onSessionListScroll);
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            const el2 = document.getElementById('session-list');
            if (el2) el2.addEventListener('scroll', _onSessionListScroll);
        });
    }
})();

// Returning to a session whose reply is still streaming in the background.
// Close the background EventSource, rebuild the bubble from the buffered
// events (snapshot), then resume live streaming via a fresh connection that
// reads the remaining tail from the backend queue. Returns true if a stream
// was re-attached. The user's own bubble is already in history (persisted
// eagerly), so it was rendered by loadHistory before this runs.
function _reattachStream(sid) {
    const requestId = sessionActiveRequest[sid];
    if (!requestId) return false;
    const buffer = streamBuffers[requestId];
    if (!buffer) return false;

    // If the buffered stream already finished, the assistant reply is already
    // persisted and rendered by loadHistory — re-attaching would duplicate it.
    // Just clean up the buffer/cursor and rely on history.
    const finished = buffer.items.some(
        it => it.type === 'done' || it.type === 'error'
    );
    if (finished) {
        const oldEs = activeStreams[requestId];
        if (oldEs) { try { oldEs.close(); } catch (_) {} delete activeStreams[requestId]; }
        delete streamBuffers[requestId];
        delete sessionActiveRequest[sid];
        resetSendBtnSendMode();
        return false;
    }

    // Stop the background stream so the rebuilt one is the sole consumer of
    // the backend queue (the queue survives until "done", so the new
    // connection picks up any remaining events).
    const oldEs = activeStreams[requestId];
    if (oldEs) { try { oldEs.close(); } catch (_) {} delete activeStreams[requestId]; }

    // Snapshot the buffered events into the replay, then start a fresh stream
    // that replays them and reconnects for the live tail.
    const replay = buffer.items.slice();
    startSSE(requestId, null, buffer.timestamp || new Date(), null, replay);
    return true;
}

function switchSession(newSessionId) {
    if (newSessionId === sessionId) {
        if (currentView !== 'chat') navigateTo('chat');
        return;
    }

    // Do NOT close active streams here: sessions run in parallel, so any
    // in-flight reply for another session must keep streaming in the
    // background (it self-guards against rendering into the foreign view).
    // Switching back re-attaches and resumes live streaming.

    sessionId = newSessionId;
    updateEditButtonsState();
    localStorage.setItem(SESSION_ID_KEY, sessionId);

    historyPage = 0;
    historyHasMore = false;
    historyLoading = false;

    messagesDiv.innerHTML = '';
    loadHistory(1);
    startPolling();

    // Restore the send button to match this session's stream state, and if a
    // reply is still streaming in the background, re-attach to resume showing
    // it live (the user turn itself comes from history above).
    const pendingReq = sessionActiveRequest[sessionId];
    if (pendingReq) {
        setSendBtnCancelMode(pendingReq);
        _reattachStream(sessionId);
    } else {
        resetSendBtnSendMode();
    }

    document.querySelectorAll('.session-item').forEach(el => {
        el.classList.toggle('active', el.dataset.sessionId === sessionId);
    });

    if (_isMobileView()) closeSessionPanel();
    if (currentView !== 'chat') navigateTo('chat');
}

// In-place rename a session title: replace the title <span> with an <input>,
// commit on Enter/blur, cancel on Escape. Persists via PUT /api/sessions/<id>.
function renameSession(sid) {
    const item = document.querySelector(`.session-item[data-session-id="${sid}"]`);
    if (!item) return;
    const titleEl = item.querySelector('.session-title');
    if (!titleEl || item.querySelector('.session-title-input')) return;

    const oldTitle = titleEl.textContent;

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'session-title-input';
    input.value = oldTitle;
    input.maxLength = 100;

    // Avoid switching session while interacting with the input
    const stop = e => e.stopPropagation();
    input.addEventListener('click', stop);
    input.addEventListener('mousedown', stop);

    titleEl.replaceWith(input);
    input.focus();
    input.select();

    let done = false;

    const restore = (title) => {
        if (done) return;
        done = true;
        const span = document.createElement('span');
        span.className = 'session-title';
        span.title = title;
        span.textContent = title;
        input.replaceWith(span);
    };

    const commit = () => {
        if (done) return;
        const newTitle = input.value.trim();
        if (!newTitle || newTitle === oldTitle) {
            restore(oldTitle);
            return;
        }
        // Optimistically show the new title, then persist.
        restore(newTitle);
        fetch(`/api/sessions/${encodeURIComponent(sid)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle })
        })
            .then(r => r.json())
            .then(data => {
                if (data.status !== 'success') {
                    // Revert UI on failure
                    const span = item.querySelector('.session-title');
                    if (span) {
                        span.title = oldTitle;
                        span.textContent = oldTitle;
                    }
                }
            })
            .catch(() => {
                const span = item.querySelector('.session-title');
                if (span) {
                    span.title = oldTitle;
                    span.textContent = oldTitle;
                }
            });
    };

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); commit(); }
        else if (e.key === 'Escape') { e.preventDefault(); restore(oldTitle); }
    });
    input.addEventListener('blur', commit);
}

function deleteSession(sid) {
    showConfirmModal(t('delete_session_title'), t('delete_session_confirm'), () => {
        // Before deleting, find the next real session to fall back to when the
        // current one is removed (the sibling item in the list, which is sorted
        // newest-first). Falls back to the welcome screen if none remain.
        const nextSid = sid === sessionId ? _findNextSessionId(sid) : null;

        fetch(`/api/sessions/${encodeURIComponent(sid)}`, { method: 'DELETE' })
            .then(r => r.json())
            .then(data => {
                if (data.status !== 'success') return;
                if (sid !== sessionId) {
                    loadSessionList();
                    return;
                }
                if (nextSid) {
                    // Switch to an existing session; refresh the list afterwards
                    // so the deleted item disappears.
                    switchSession(nextSid);
                    loadSessionList();
                } else {
                    // No other sessions: reset to a fresh empty session without
                    // inserting an optimistic placeholder (it has no backend
                    // record and would be an empty, undeletable item).
                    newChat(false);
                }
            })
            .catch(() => {});
    });
}

// Pick the session to show after deleting `sid` (the current session): prefer
// the next item below it in the list, otherwise the previous one. Returns null
// if no other session exists.
function _findNextSessionId(sid) {
    const items = Array.from(document.querySelectorAll('.session-item[data-session-id]'));
    const idx = items.findIndex(el => el.dataset.sessionId === sid);
    if (idx === -1) {
        const other = items.find(el => el.dataset.sessionId !== sid);
        return other ? other.dataset.sessionId : null;
    }
    const next = items[idx + 1] || items[idx - 1];
    return next ? next.dataset.sessionId : null;
}

function showConfirmModal(title, message, onConfirm) {
    let overlay = document.getElementById('confirm-modal-overlay');
    if (overlay) overlay.remove();

    overlay = document.createElement('div');
    overlay.id = 'confirm-modal-overlay';
    overlay.className = 'confirm-overlay';

    const modal = document.createElement('div');
    modal.className = 'confirm-modal';
    modal.innerHTML = `
        <div class="confirm-title">${escapeHtml(title)}</div>
        <div class="confirm-message">${escapeHtml(message)}</div>
        <div class="confirm-actions">
            <button class="confirm-btn confirm-btn-cancel">${t('confirm_cancel')}</button>
            <button class="confirm-btn confirm-btn-ok">${t('confirm_yes')}</button>
        </div>
    `;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    requestAnimationFrame(() => overlay.classList.add('visible'));

    const close = () => {
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 200);
    };

    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    modal.querySelector('.confirm-btn-cancel').addEventListener('click', close);
    modal.querySelector('.confirm-btn-ok').addEventListener('click', () => {
        close();
        onConfirm();
    });
}

function clearContext() {
    fetch(`/api/sessions/${encodeURIComponent(sessionId)}/clear_context`, { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') return;
            // Insert a visual divider in the chat
            const divider = document.createElement('div');
            divider.className = 'context-divider';
            divider.innerHTML = `<span>${t('context_cleared')}</span>`;
            messagesDiv.appendChild(divider);
            scrollChatToBottom();
        })
        .catch(() => {});
}

function generateSessionTitle(sid, userMsg, assistantReply) {
    fetch(`/api/sessions/${encodeURIComponent(sid)}/generate_title`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_message: userMsg, assistant_reply: assistantReply }),
    })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success' && sessionPanelOpen) {
                loadSessionList();
            }
        })
        .catch(() => {});
}

// =====================================================================
// Utilities
// =====================================================================
function formatTime(date) {
    const now = new Date();
    const sameDay = date.getFullYear() === now.getFullYear()
        && date.getMonth() === now.getMonth()
        && date.getDate() === now.getDate();
    const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (sameDay) return time;
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    if (date.getFullYear() === now.getFullYear()) return `${m}-${d} ${time}`;
    return `${date.getFullYear()}-${m}-${d} ${time}`;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function escapeJs(str) {
    return String(str || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function ChannelsHandler_maskSecret(val) {
    if (!val || val.length <= 8) return val;
    return val.slice(0, 4) + '*'.repeat(val.length - 8) + val.slice(-4);
}

function formatToolArgs(args) {
    if (!args || Object.keys(args).length === 0) return '(none)';
    try {
        return escapeHtml(JSON.stringify(args, null, 2));
    } catch (_) {
        return escapeHtml(String(args));
    }
}

function scrollChatToBottom(force) {
    if (force || _autoScrollEnabled) {
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
}

function _updateScrollToBottomBtn() {
    const btn = document.getElementById('scroll-to-bottom-btn');
    if (!btn) return;
    const distFromBottom = messagesDiv.scrollHeight - messagesDiv.scrollTop - messagesDiv.clientHeight;
    btn.classList.toggle('hidden', distFromBottom <= _SCROLL_THRESHOLD);
}

function applyHighlighting(container) {
    const root = container || document;
    setTimeout(() => {
        const hljsLib = getHljs();
        root.querySelectorAll('pre code').forEach(block => {
            if (!block.classList.contains('hljs')) {
                hljsLib.highlightElement(block);
            }
        });
        // Add language labels and copy buttons to code blocks
        _addCodeBlockHeaders(root);
    }, 0);
}

// =====================================================================
// Config View
// =====================================================================
let configProviders = {};
let configApiBases = {};
let configApiKeys = {};
let configCurrentModel = '';
let cfgProviderValue = '';
let cfgModelValue = '';

// --- Custom dropdown helper ---
function initDropdown(el, options, selectedValue, onChange, opts) {
    // opts.placeholder: when set AND selectedValue is empty, render that text
    // in a dim style instead of auto-selecting options[0]. Useful for
    // "pick or empty" capabilities (asr / embedding) where we want the
    // user to make an explicit choice.
    opts = opts || {};
    const textEl = el.querySelector('.cfg-dropdown-text');
    const menuEl = el.querySelector('.cfg-dropdown-menu');
    const selEl = el.querySelector('.cfg-dropdown-selected');

    el._ddValue = selectedValue || '';
    el._ddOnChange = onChange;

    function render() {
        menuEl.innerHTML = '';
        options.forEach(opt => {
            const item = document.createElement('div');
            item.className = 'cfg-dropdown-item' + (opt.value === el._ddValue ? ' active' : '');
            item.dataset.value = opt.value;
            // Hint is an optional dim secondary label rendered on the right
            // side of the row (e.g. friendly brand name next to a technical
            // model id). When absent the row degrades to the original
            // single-string layout.
            if (opt.hint) {
                const labelEl = document.createElement('span');
                labelEl.className = 'cfg-dropdown-label';
                labelEl.textContent = opt.label;
                const hintEl = document.createElement('span');
                hintEl.className = 'cfg-dropdown-hint';
                hintEl.textContent = opt.hint;
                item.appendChild(labelEl);
                item.appendChild(hintEl);
            } else {
                item.textContent = opt.label;
            }
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                el._ddValue = opt.value;
                textEl.textContent = opt.label;
                menuEl.querySelectorAll('.cfg-dropdown-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                el.classList.remove('open');
                if (el._ddOnChange) el._ddOnChange(opt.value);
            });
            menuEl.appendChild(item);
        });
        const sel = options.find(o => o.value === el._ddValue);
        if (sel) {
            textEl.textContent = sel.label;
            textEl.classList.remove('text-slate-400', 'dark:text-slate-500');
        } else if (opts.placeholder && !el._ddValue) {
            // No selection yet — show the placeholder in muted style.
            // Do NOT write a fallback value, so the dropdown stays
            // "unsaved" until the user explicitly picks.
            textEl.textContent = opts.placeholder;
            textEl.classList.add('text-slate-400', 'dark:text-slate-500');
        } else {
            textEl.textContent = options[0] ? options[0].label : '--';
            textEl.classList.remove('text-slate-400', 'dark:text-slate-500');
            if (options[0]) el._ddValue = options[0].value;
        }
    }

    render();

    if (!el._ddBound) {
        selEl.addEventListener('click', (e) => {
            e.stopPropagation();
            document.querySelectorAll('.cfg-dropdown.open').forEach(d => { if (d !== el) d.classList.remove('open'); });
            el.classList.toggle('open');
        });
        el._ddBound = true;
    }
}

document.addEventListener('click', () => {
    document.querySelectorAll('.cfg-dropdown.open').forEach(d => d.classList.remove('open'));
});

function getDropdownValue(el) { return el._ddValue || ''; }

// --- Config init ---
function initConfigView(data) {
    configProviders = data.providers || {};
    configApiBases = data.api_bases || {};
    configApiKeys = data.api_keys || {};
    configCurrentModel = data.model || '';

    const providerEl = document.getElementById('cfg-provider');
    const providerOpts = Object.entries(configProviders).map(([pid, p]) => ({ value: pid, label: localizedLabel(p.label) }));

    // if use_linkai is enabled, always select linkai as the provider
    // Otherwise prefer bot_type from config, fall back to model-based detection
    const detected = data.use_linkai ? 'linkai'
        : (data.bot_type && configProviders[data.bot_type] ? data.bot_type : detectProvider(configCurrentModel));
    cfgProviderValue = detected || (providerOpts[0] ? providerOpts[0].value : '');

    initDropdown(providerEl, providerOpts, cfgProviderValue, onProviderChange);

    onProviderChange(cfgProviderValue);
    syncModelSelection(configCurrentModel);

    document.getElementById('cfg-max-tokens').value = data.agent_max_context_tokens || 50000;
    document.getElementById('cfg-max-turns').value = data.agent_max_context_turns || 20;
    document.getElementById('cfg-max-steps').value = data.agent_max_steps || 20;
    document.getElementById('cfg-enable-thinking').checked = data.enable_thinking === true;
    document.getElementById('cfg-self-evolution').checked = data.self_evolution_enabled === true;

    // Reflect the current UI language (already resolved, may include the user's
    // local choice) on the selector so it stays in sync with the top-right toggle.
    const langSel = document.getElementById('cfg-lang-select');
    if (langSel) {
        initDropdown(
            langSel,
            [{ value: 'zh', label: '中文' }, { value: 'en', label: 'English' }],
            currentLang,
            (val) => setLanguage(val)
        );
    }

    const pwdInput = document.getElementById('cfg-password');
    const maskedPwd = data.web_password_masked || '';
    pwdInput.value = maskedPwd;
    pwdInput.dataset.masked = maskedPwd ? '1' : '';
    pwdInput.dataset.maskedVal = maskedPwd;
    pwdInput.classList.toggle('cfg-key-masked', !!maskedPwd);

    if (maskedPwd) {
        pwdInput.placeholder = '••••••••';
    } else {
        pwdInput.placeholder = '';
    }

    if (!pwdInput._cfgBound) {
        pwdInput.addEventListener('focus', function() {
            if (this.dataset.masked === '1') {
                this.value = '';
                this.dataset.masked = '';
                this.classList.remove('cfg-key-masked');
            }
        });
        pwdInput.addEventListener('input', function() {
            this.dataset.masked = '';
        });
        pwdInput._cfgBound = true;
    }
}

function detectProvider(model) {
    if (!model) return Object.keys(configProviders)[0] || '';
    for (const [pid, p] of Object.entries(configProviders)) {
        if (pid === 'linkai') continue;
        if (p.models && p.models.includes(model)) return pid;
    }
    return Object.keys(configProviders)[0] || '';
}

function onProviderChange(pid) {
    cfgProviderValue = pid || getDropdownValue(document.getElementById('cfg-provider'));
    const p = configProviders[cfgProviderValue];
    if (!p) return;

    const customTip = document.getElementById('cfg-custom-tip');
    if (customTip) customTip.classList.toggle('hidden', cfgProviderValue !== 'custom');

    const modelEl = document.getElementById('cfg-model-select');
    const modelOpts = (p.models || []).map(m => ({ value: m, label: m }));
    modelOpts.push({ value: '__custom__', label: t('config_custom_option') });

    initDropdown(modelEl, modelOpts, modelOpts[0] ? modelOpts[0].value : '', onModelSelectChange);

    // API Key
    const keyField = p.api_key_field;
    const keyWrap = document.getElementById('cfg-api-key-wrap');
    const keyInput = document.getElementById('cfg-api-key');
    if (keyField) {
        keyWrap.classList.remove('hidden');
        keyInput.classList.add('cfg-key-masked');
        const maskedVal = configApiKeys[keyField] || '';
        keyInput.value = maskedVal;
        keyInput.dataset.field = keyField;
        keyInput.dataset.masked = maskedVal ? '1' : '';
        keyInput.dataset.maskedVal = maskedVal;
        const toggleIcon = document.querySelector('#cfg-api-key-toggle i');
        if (toggleIcon) toggleIcon.className = 'fas fa-eye text-xs';

        if (!keyInput._cfgBound) {
            keyInput.addEventListener('focus', function() {
                if (this.dataset.masked === '1') {
                    this.value = '';
                    this.dataset.masked = '';
                    this.classList.remove('cfg-key-masked');
                }
            });
            keyInput.addEventListener('blur', function() {
                if (!this.value.trim() && this.dataset.maskedVal) {
                    this.value = this.dataset.maskedVal;
                    this.dataset.masked = '1';
                    this.classList.add('cfg-key-masked');
                }
            });
            keyInput.addEventListener('input', function() {
                this.dataset.masked = '';
            });
            keyInput._cfgBound = true;
        }
    } else {
        keyWrap.classList.add('hidden');
        keyInput.value = '';
        keyInput.dataset.field = '';
    }

    // API Base
    const apiBaseInput = document.getElementById('cfg-api-base');
    if (p.api_base_key) {
        document.getElementById('cfg-api-base-wrap').classList.remove('hidden');
        apiBaseInput.value = configApiBases[p.api_base_key] || p.api_base_default || '';
        // Hint the version-path tail (e.g. /v1) so users are reminded to
        // include it themselves. We don't auto-rewrite anything server-side.
        apiBaseInput.placeholder = p.api_base_placeholder || 'https://...';
    } else {
        document.getElementById('cfg-api-base-wrap').classList.add('hidden');
        apiBaseInput.value = '';
        apiBaseInput.placeholder = 'https://...';
    }

    onModelSelectChange(modelOpts[0] ? modelOpts[0].value : '');
}

function onModelSelectChange(val) {
    cfgModelValue = val || getDropdownValue(document.getElementById('cfg-model-select'));
    const customWrap = document.getElementById('cfg-model-custom-wrap');
    if (cfgModelValue === '__custom__') {
        customWrap.classList.remove('hidden');
        document.getElementById('cfg-model-custom').focus();
    } else {
        customWrap.classList.add('hidden');
        document.getElementById('cfg-model-custom').value = '';
    }
}

function syncModelSelection(model) {
    const p = configProviders[cfgProviderValue];
    if (!p) return;

    const modelEl = document.getElementById('cfg-model-select');
    if (p.models && p.models.includes(model)) {
        const modelOpts = (p.models || []).map(m => ({ value: m, label: m }));
        modelOpts.push({ value: '__custom__', label: t('config_custom_option') });
        initDropdown(modelEl, modelOpts, model, onModelSelectChange);
        cfgModelValue = model;
        document.getElementById('cfg-model-custom-wrap').classList.add('hidden');
    } else {
        cfgModelValue = '__custom__';
        const modelOpts = (p.models || []).map(m => ({ value: m, label: m }));
        modelOpts.push({ value: '__custom__', label: t('config_custom_option') });
        initDropdown(modelEl, modelOpts, '__custom__', onModelSelectChange);
        document.getElementById('cfg-model-custom-wrap').classList.remove('hidden');
        document.getElementById('cfg-model-custom').value = model;
    }
}

function getSelectedModel() {
    if (cfgModelValue === '__custom__') {
        return document.getElementById('cfg-model-custom').value.trim();
    }
    return cfgModelValue;
}

function toggleApiKeyVisibility() {
    const input = document.getElementById('cfg-api-key');
    const icon = document.querySelector('#cfg-api-key-toggle i');
    if (input.classList.contains('cfg-key-masked')) {
        input.classList.remove('cfg-key-masked');
        icon.className = 'fas fa-eye-slash text-xs';
    } else {
        input.classList.add('cfg-key-masked');
        icon.className = 'fas fa-eye text-xs';
    }
}

function showStatus(elId, msgKey, isError) {
    const el = document.getElementById(elId);
    el.textContent = t(msgKey);
    el.classList.toggle('text-red-500', !!isError);
    el.classList.toggle('text-primary-500', !isError);
    el.classList.remove('opacity-0');
    setTimeout(() => el.classList.add('opacity-0'), 2500);
}

function saveModelConfig() {
    const model = getSelectedModel();
    if (!model) return;

    const updates = { model: model };
    const p = configProviders[cfgProviderValue];
    updates.use_linkai = (cfgProviderValue === 'linkai');
    if (cfgProviderValue === 'linkai') {
        updates.bot_type = '';
    } else {
        updates.bot_type = cfgProviderValue;
    }
    if (p && p.api_base_key) {
        const base = document.getElementById('cfg-api-base').value.trim();
        if (base) updates[p.api_base_key] = base;
    }
    if (p && p.api_key_field) {
        const keyInput = document.getElementById('cfg-api-key');
        const rawVal = keyInput.value.trim();
        if (rawVal && keyInput.dataset.masked !== '1') {
            updates[p.api_key_field] = rawVal;
        }
    }

    const btn = document.getElementById('cfg-model-save');
    btn.disabled = true;
    fetch('/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            configCurrentModel = model;
            if (data.applied) {
                const keyInput = document.getElementById('cfg-api-key');
                Object.entries(data.applied).forEach(([k, v]) => {
                    if (k === 'model') return;
                    if (k.includes('api_key')) {
                        const masked = v.length > 8
                            ? v.substring(0, 4) + '*'.repeat(v.length - 8) + v.substring(v.length - 4)
                            : v;
                        configApiKeys[k] = masked;
                        if (keyInput.dataset.field === k) {
                            keyInput.value = masked;
                            keyInput.dataset.masked = '1';
                            keyInput.dataset.maskedVal = masked;
                            keyInput.classList.add('cfg-key-masked');
                            const toggleIcon = document.querySelector('#cfg-api-key-toggle i');
                            if (toggleIcon) toggleIcon.className = 'fas fa-eye text-xs';
                        }
                    } else {
                        configApiBases[k] = v;
                    }
                });
            }
            showStatus('cfg-model-status', 'config_saved', false);
        } else {
            showStatus('cfg-model-status', 'config_save_error', true);
        }
    })
    .catch(() => showStatus('cfg-model-status', 'config_save_error', true))
    .finally(() => { btn.disabled = false; });
}

function saveAgentConfig() {
    const updates = {
        agent_max_context_tokens: parseInt(document.getElementById('cfg-max-tokens').value) || 50000,
        agent_max_context_turns: parseInt(document.getElementById('cfg-max-turns').value) || 20,
        agent_max_steps: parseInt(document.getElementById('cfg-max-steps').value) || 20,
        enable_thinking: document.getElementById('cfg-enable-thinking').checked,
        self_evolution_enabled: document.getElementById('cfg-self-evolution').checked,
    };

    const btn = document.getElementById('cfg-agent-save');
    btn.disabled = true;
    fetch('/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            showStatus('cfg-agent-status', 'config_saved', false);
        } else {
            showStatus('cfg-agent-status', 'config_save_error', true);
        }
    })
    .catch(() => showStatus('cfg-agent-status', 'config_save_error', true))
    .finally(() => { btn.disabled = false; });
}

function savePasswordConfig() {
    const input = document.getElementById('cfg-password');
    if (input.dataset.masked === '1') {
        showStatus('cfg-password-status', 'config_saved', false);
        return;
    }
    const newPwd = input.value.trim();
    const btn = document.getElementById('cfg-password-save');
    btn.disabled = true;
    fetch('/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: { web_password: newPwd } })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            if (newPwd) {
                showStatus('cfg-password-status', 'config_password_changed', false);
                setTimeout(() => { window.location.reload(); }, 1500);
            } else {
                input.dataset.masked = '';
                input.dataset.maskedVal = '';
                input.classList.remove('cfg-key-masked');
                showStatus('cfg-password-status', 'config_password_cleared', false);
            }
        } else {
            showStatus('cfg-password-status', 'config_save_error', true);
        }
    })
    .catch(() => showStatus('cfg-password-status', 'config_save_error', true))
    .finally(() => { btn.disabled = false; });
}

function loadConfigView() {
    fetch('/config').then(r => r.json()).then(data => {
        if (data.status !== 'success') return;
        appConfig = data;
        initConfigView(data);
    }).catch(() => {});
}

// =====================================================================
// Skills View
// =====================================================================
let toolsLoaded = false;

const TOOL_ICONS = {
    bash: 'fa-terminal',
    edit: 'fa-pen-to-square',
    read: 'fa-file-lines',
    write: 'fa-file-pen',
    ls: 'fa-folder-open',
    send: 'fa-paper-plane',
    web_search: 'fa-magnifying-glass',
    browser: 'fa-globe',
    env_config: 'fa-key',
    scheduler: 'fa-clock',
    memory_get: 'fa-brain',
    memory_search: 'fa-brain',
};

function getToolIcon(name) {
    return TOOL_ICONS[name] || 'fa-wrench';
}

function loadSkillsView() {
    loadToolsSection();
    loadSkillsSection();
}

function loadToolsSection() {
    if (toolsLoaded) return;
    const emptyEl = document.getElementById('tools-empty');
    const listEl = document.getElementById('tools-list');
    const badge = document.getElementById('tools-count-badge');

    fetch('/api/tools').then(r => r.json()).then(data => {
        if (data.status !== 'success') return;
        const tools = data.tools || [];
        emptyEl.classList.add('hidden');
        if (tools.length === 0) {
            emptyEl.classList.remove('hidden');
            emptyEl.innerHTML = `<span class="text-sm text-slate-400 dark:text-slate-500">${currentLang === 'zh' ? '暂无内置工具' : 'No built-in tools'}</span>`;
            return;
        }
        badge.textContent = tools.length;
        badge.classList.remove('hidden');
        listEl.innerHTML = '';
        tools.forEach(tool => {
            const card = document.createElement('div');
            card.className = 'bg-white dark:bg-[#1A1A1A] rounded-xl border border-slate-200 dark:border-white/10 p-4 flex items-start gap-3';
            card.innerHTML = `
                <div class="w-9 h-9 rounded-lg bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center flex-shrink-0">
                    <i class="fas ${getToolIcon(tool.name)} text-blue-500 dark:text-blue-400 text-sm"></i>
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                        <span class="font-medium text-sm text-slate-700 dark:text-slate-200 font-mono">${escapeHtml(tool.name)}</span>
                    </div>
                    <p class="text-xs text-slate-400 dark:text-slate-500 mt-1 line-clamp-2">${escapeHtml(tool.description || '--')}</p>
                </div>`;
            listEl.appendChild(card);
        });
        listEl.classList.remove('hidden');
        toolsLoaded = true;
    }).catch(() => {
        emptyEl.classList.remove('hidden');
        emptyEl.innerHTML = `<span class="text-sm text-slate-400 dark:text-slate-500">${currentLang === 'zh' ? '加载失败' : 'Failed to load'}</span>`;
    });
}

function loadSkillsSection() {
    const emptyEl = document.getElementById('skills-empty');
    const listEl = document.getElementById('skills-list');
    const badge = document.getElementById('skills-count-badge');

    fetch('/api/skills').then(r => r.json()).then(data => {
        if (data.status !== 'success') return;
        const skills = data.skills || [];
        if (skills.length === 0) {
            const p = emptyEl.querySelector('p');
            if (p) p.textContent = currentLang === 'zh' ? '暂无技能' : 'No skills found';
            return;
        }
        badge.textContent = skills.length;
        badge.classList.remove('hidden');
        emptyEl.classList.add('hidden');
        listEl.innerHTML = '';

        skills.forEach(sk => {
            const card = document.createElement('div');
            card.className = 'bg-white dark:bg-[#1A1A1A] rounded-xl border border-slate-200 dark:border-white/10 p-4 flex items-start gap-3 transition-opacity';
            card.dataset.skillName = sk.name;
            card.dataset.skillDesc = sk.description || '';
            card.dataset.enabled = sk.enabled ? '1' : '0';
            renderSkillCard(card, sk);
            listEl.appendChild(card);
        });
    }).catch(() => {});
}

function renderSkillCard(card, sk) {
    const enabled = sk.enabled;
    const iconColor = enabled ? 'text-primary-400' : 'text-slate-300 dark:text-slate-600';
    const trackClass = enabled
        ? 'bg-primary-400'
        : 'bg-slate-200 dark:bg-slate-700';
    const thumbTranslate = enabled ? 'translate-x-3' : 'translate-x-0.5';
    card.innerHTML = `
        <div class="w-9 h-9 rounded-lg bg-amber-50 dark:bg-amber-900/20 flex items-center justify-center flex-shrink-0">
            <i class="fas fa-bolt ${iconColor} text-sm"></i>
        </div>
        <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
                <span class="font-medium text-sm text-slate-700 dark:text-slate-200 truncate flex-1">${escapeHtml(sk.display_name || sk.name)}</span>
                <button
                    role="switch"
                    aria-checked="${enabled}"
                    onclick="toggleSkill('${escapeHtml(sk.name)}', ${enabled})"
                    class="relative inline-flex h-4 w-7 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none ${trackClass}"
                    title="${enabled ? (currentLang === 'zh' ? '点击禁用' : 'Click to disable') : (currentLang === 'zh' ? '点击启用' : 'Click to enable')}"
                >
                    <span class="inline-block h-3 w-3 mt-0.5 rounded-full bg-white shadow transform transition-transform duration-200 ease-in-out ${thumbTranslate}"></span>
                </button>
            </div>
            <p class="text-xs text-slate-400 dark:text-slate-500 line-clamp-2">${escapeHtml(sk.description || '--')}</p>
        </div>`;
}

function toggleSkill(name, currentlyEnabled) {
    const action = currentlyEnabled ? 'close' : 'open';
    const card = document.querySelector(`[data-skill-name="${CSS.escape(name)}"]`);
    if (card) card.style.opacity = '0.5';

    fetch('/api/skills', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, name })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            if (card) {
                const desc = card.dataset.skillDesc || '';
                card.dataset.enabled = currentlyEnabled ? '0' : '1';
                card.style.opacity = '1';
                renderSkillCard(card, { name, description: desc, enabled: !currentlyEnabled });
            }
        } else {
            if (card) card.style.opacity = '1';
            alert(currentLang === 'zh' ? '操作失败，请稍后再试' : 'Operation failed, please try again');
        }
    })
    .catch(() => {
        if (card) card.style.opacity = '1';
        alert(currentLang === 'zh' ? '操作失败，请稍后再试' : 'Operation failed, please try again');
    });
}

// =====================================================================
// Memory View
// =====================================================================
let memoryPage = 1;
let memoryCategory = 'memory';   // 'memory' | 'evolution'
const memoryPageSize = 10;

function switchMemoryTab(tab) {
    document.querySelectorAll('.memory-tab').forEach(el => el.classList.remove('active'));
    document.getElementById('memory-tab-' + tab).classList.add('active');
    // The "dreams" tab now surfaces self-evolution logs (merged with dream diaries).
    memoryCategory = tab === 'dreams' ? 'evolution' : 'memory';
    loadMemoryView(1);
}

function loadMemoryView(page) {
    page = page || 1;
    memoryPage = page;
    fetch(`/api/memory?page=${page}&page_size=${memoryPageSize}&category=${memoryCategory}`).then(r => r.json()).then(data => {
        if (data.status !== 'success') return;
        const emptyEl = document.getElementById('memory-empty');
        const listEl = document.getElementById('memory-list');
        const files = data.list || [];
        const total = data.total || 0;

        if (total === 0) {
            const emptyIcon = emptyEl.querySelector('i');
            const emptyTitle = emptyEl.querySelector('p');
            if (memoryCategory === 'evolution') {
                emptyIcon.className = 'fas fa-seedling text-emerald-400 text-xl';
                emptyTitle.textContent = currentLang === 'zh' ? '暂无进化记录' : 'No evolution records yet';
            } else {
                emptyIcon.className = 'fas fa-brain text-purple-400 text-xl';
                emptyTitle.textContent = currentLang === 'zh' ? '暂无记忆文件' : 'No memory files';
            }
            emptyEl.classList.remove('hidden');
            listEl.classList.add('hidden');
            return;
        }
        emptyEl.classList.add('hidden');
        listEl.classList.remove('hidden');

        const tbody = document.getElementById('memory-table-body');
        tbody.innerHTML = '';
        files.forEach(f => {
            const tr = document.createElement('tr');
            tr.className = 'border-b border-slate-100 dark:border-white/5 hover:bg-slate-50 dark:hover:bg-white/5 cursor-pointer transition-colors';
            // In the merged evolution tab, resolve each file by its own origin
            // (evolution logs vs dream diaries live in different dirs).
            const fileCategory = (f.type === 'dream' || f.type === 'evolution') ? f.type : memoryCategory;
            tr.onclick = () => openMemoryFile(f.filename, fileCategory);
            let typeLabel;
            if (f.type === 'global') {
                typeLabel = '<span class="px-2 py-0.5 rounded-full text-xs bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400">Global</span>';
            } else if (f.type === 'evolution') {
                typeLabel = '<span class="px-2 py-0.5 rounded-full text-xs bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400">Evolution</span>';
            } else if (f.type === 'dream') {
                typeLabel = '<span class="px-2 py-0.5 rounded-full text-xs bg-violet-50 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400">Dream</span>';
            } else {
                typeLabel = '<span class="px-2 py-0.5 rounded-full text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">Daily</span>';
            }
            const sizeStr = f.size < 1024 ? f.size + ' B' : (f.size / 1024).toFixed(1) + ' KB';
            tr.innerHTML = `
                <td class="px-4 py-3 text-sm font-mono text-slate-700 dark:text-slate-200">${escapeHtml(f.filename)}</td>
                <td class="px-4 py-3 text-sm">${typeLabel}</td>
                <td class="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">${sizeStr}</td>
                <td class="px-4 py-3 text-sm text-slate-500 dark:text-slate-400">${escapeHtml(f.updated_at)}</td>`;
            tbody.appendChild(tr);
        });

        // Pagination
        const totalPages = Math.ceil(total / memoryPageSize);
        const pagEl = document.getElementById('memory-pagination');
        if (totalPages <= 1) { pagEl.innerHTML = ''; return; }
        let pagHtml = `<span>${page} / ${totalPages}</span><div class="flex gap-2">`;
        if (page > 1) pagHtml += `<button onclick="loadMemoryView(${page - 1})" class="px-3 py-1 rounded-lg border border-slate-200 dark:border-white/10 hover:bg-slate-100 dark:hover:bg-white/10 text-xs">Prev</button>`;
        if (page < totalPages) pagHtml += `<button onclick="loadMemoryView(${page + 1})" class="px-3 py-1 rounded-lg border border-slate-200 dark:border-white/10 hover:bg-slate-100 dark:hover:bg-white/10 text-xs">Next</button>`;
        pagHtml += '</div>';
        pagEl.innerHTML = pagHtml;
    }).catch(() => {});
}

function openMemoryFile(filename, category) {
    category = category || 'memory';
    fetch(`/api/memory/content?filename=${encodeURIComponent(filename)}&category=${category}`).then(r => r.json()).then(data => {
        if (data.status !== 'success') return;
        document.getElementById('memory-panel-list').classList.add('hidden');
        const panel = document.getElementById('memory-panel-viewer');
        document.getElementById('memory-viewer-title').textContent = filename;
        document.getElementById('memory-viewer-content').innerHTML = renderMarkdown(data.content || '');
        panel.classList.remove('hidden');
        applyHighlighting(panel);
    }).catch(() => {});
}

function closeMemoryViewer() {
    document.getElementById('memory-panel-viewer').classList.add('hidden');
    document.getElementById('memory-panel-list').classList.remove('hidden');
}

// =====================================================================
// Custom Confirm Dialog
// =====================================================================
function showConfirmDialog({ title, message, okText, cancelText, onConfirm, hideCancel }) {
    const overlay = document.getElementById('confirm-dialog-overlay');
    document.getElementById('confirm-dialog-title').textContent = title || '';
    document.getElementById('confirm-dialog-message').textContent = message || '';
    document.getElementById('confirm-dialog-ok').textContent = okText || 'OK';
    const cancelBtn = document.getElementById('confirm-dialog-cancel');
    cancelBtn.textContent = cancelText || t('channels_cancel');
    cancelBtn.classList.toggle('hidden', !!hideCancel);

    function cleanup() {
        overlay.classList.add('hidden');
        okBtn.removeEventListener('click', onOk);
        cancelBtn.removeEventListener('click', onCancel);
        overlay.removeEventListener('click', onOverlayClick);
    }
    function onOk() { cleanup(); if (onConfirm) onConfirm(); }
    function onCancel() { cleanup(); }
    function onOverlayClick(e) { if (e.target === overlay) cleanup(); }

    const okBtn = document.getElementById('confirm-dialog-ok');
    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
    overlay.addEventListener('click', onOverlayClick);
    overlay.classList.remove('hidden');
}

// =====================================================================
// Models View
// =====================================================================
// Capability cards rendered on the Models page. Order matters — main model
// comes first because it transitively decides defaults for vision and image.
// Icon palette is grouped by capability family:
//   - chat                       → primary (brand green; the "main" capability)
//   - vision + image             → blue    (everything visual)
//   - asr + tts                  → amber   (everything audio)
//   - embedding                  → purple  (vectors)
//   - search                     → orange  (retrieval)
// Each card uses an explicit `iconClass` string so Tailwind's CDN JIT can
// see the literal class names — dynamic `bg-${color}-50` strings would not
// be picked up reliably.
const MODELS_CAPABILITY_DEFS = [
    { id: 'chat',      icon: 'fa-microchip',        editable: true,  needsModel: true,  titleKey: 'models_capability_chat',      descKey: 'models_capability_chat_desc',
      iconChip: 'bg-primary-50 dark:bg-primary-900/30',  iconGlyph: 'text-primary-500' },
    { id: 'vision',    icon: 'fa-eye',              editable: true,  needsModel: true,  titleKey: 'models_capability_vision',    descKey: 'models_capability_vision_desc',
      iconChip: 'bg-blue-50 dark:bg-blue-900/30',        iconGlyph: 'text-blue-500' },
    { id: 'image',     icon: 'fa-image',            editable: true,  needsModel: true,  titleKey: 'models_capability_image',     descKey: 'models_capability_image_desc',
      iconChip: 'bg-blue-50 dark:bg-blue-900/30',        iconGlyph: 'text-blue-500' },
    { id: 'asr',       icon: 'fa-microphone',       editable: true,  needsModel: true,  titleKey: 'models_capability_asr',       descKey: 'models_capability_asr_desc',
      iconChip: 'bg-amber-50 dark:bg-amber-900/30',      iconGlyph: 'text-amber-500' },
    { id: 'tts',       icon: 'fa-volume-high',      editable: true,  needsModel: true,  titleKey: 'models_capability_tts',       descKey: 'models_capability_tts_desc',
      iconChip: 'bg-amber-50 dark:bg-amber-900/30',      iconGlyph: 'text-amber-500' },
    { id: 'embedding', icon: 'fa-vector-square',    editable: true,  needsModel: true,  titleKey: 'models_capability_embedding', descKey: 'models_capability_embedding_desc',
      iconChip: 'bg-purple-50 dark:bg-purple-900/30',    iconGlyph: 'text-purple-500' },
    { id: 'search',    icon: 'fa-magnifying-glass', editable: true,  needsModel: false, titleKey: 'models_capability_search',    descKey: 'models_capability_search_desc',
      iconChip: 'bg-orange-50 dark:bg-orange-900/30',    iconGlyph: 'text-orange-500' },
];

// Provider logos: when a real SVG exists under static/logos/<id>.svg we use
// it; otherwise we fall back to a neutral monogram chip. SVGs are fetched
// via <img> with a hidden onerror so layout stays stable when files are
// absent. Vendors whose mark is rendered in pure (or near-pure) black are
// listed in MODELS_PROVIDER_LOGO_DARK_INVERT — for those, we apply a CSS
// invert filter in dark mode so the glyph stays visible against #1A1A1A.
const MODELS_PROVIDER_LOGO_PATH = 'assets/logos';
const MODELS_PROVIDER_LOGO_DARK_INVERT = new Set([
    'openai',     // black wordmark
    'moonshot',   // dark monogram
    'zhipu',      // dark monogram
    'custom',     // single-color slider glyph
]);

let modelsState = { providers: [], capabilities: {} };

// One-shot: { capabilityId, providerId } stashed before a Models reload,
// consumed by renderCapabilityBody to preselect a just-configured vendor.
let pendingCapabilitySelection = null;

// `opts.preserveScroll` keeps the page's vertical scroll position across the
// refresh. We capture it before unhiding the loading skeleton (which collapses
// content height to zero) and restore it after the new content is mounted.
// This matters when the user configures a vendor from inside a capability
// card's dropdown — without preservation, the post-save reload bounces them
// back to the top of the page, away from the card they were configuring.
function loadModelsView(opts) {
    const loading = document.getElementById('models-loading');
    const content = document.getElementById('models-content');
    if (!loading || !content) return;
    const preserveScroll = !!(opts && opts.preserveScroll);
    // The Models pane has its own scrollable container; capture its position
    // (not window.scrollY) so we can put the user back exactly where they were.
    const scroller = document.querySelector('#view-models .overflow-y-auto');
    const savedTop = preserveScroll && scroller ? scroller.scrollTop : null;

    loading.classList.remove('hidden');
    content.classList.add('hidden');

    fetch('/api/models').then(r => r.json()).then(data => {
        if (data.status !== 'success') {
            loading.innerHTML = `<span class="text-sm text-red-400">${escapeHtml(data.message || 'Failed to load')}</span>`;
            return;
        }
        modelsState.providers = data.providers || [];
        modelsState.capabilities = data.capabilities || {};
        renderModelsView();
        loading.classList.add('hidden');
        content.classList.remove('hidden');
        if (savedTop !== null && scroller) {
            // Wait one frame for the new layout to settle, otherwise the
            // restored scrollTop snaps to the previous (smaller) max.
            requestAnimationFrame(() => { scroller.scrollTop = savedTop; });
        }
    }).catch(err => {
        loading.innerHTML = `<span class="text-sm text-red-400">${escapeHtml(String(err))}</span>`;
    });
}

function renderModelsView() {
    const container = document.getElementById('models-content');
    container.innerHTML = '';
    container.appendChild(renderVendorsSection());
    MODELS_CAPABILITY_DEFS.forEach(def => container.appendChild(renderCapabilityCard(def)));
}

// True when a provider card is one of the expanded custom (OpenAI-compatible)
// providers (id "custom:<id>") — shown in the vendor grid alongside built-in
// vendors, but edited via the dedicated custom-provider modal.
function isCustomProviderCard(p) {
    return !!(p && p.is_custom && p.custom_name);
}

// ---------- Vendor section (Layer 1) -----------------------------------

function renderVendorsSection() {
    const wrap = document.createElement('div');
    wrap.className = 'bg-white dark:bg-[#1A1A1A] rounded-xl border border-slate-200 dark:border-white/10 p-6';

    // Custom providers always show once created (even without an api key,
    // e.g. a local vLLM/Ollama endpoint); built-in vendors show when configured.
    const configured = modelsState.providers.filter(p => p.configured || isCustomProviderCard(p));

    const header = `
        <div class="flex items-start gap-3 mb-5">
            <div class="w-9 h-9 rounded-lg bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center flex-shrink-0">
                <i class="fas fa-key text-primary-500 text-sm"></i>
            </div>
            <div class="flex-1 min-w-0">
                <h3 class="font-semibold text-slate-800 dark:text-slate-100">${t('models_section_vendors')}</h3>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">${t('models_section_vendors_desc')}</p>
            </div>
        </div>`;

    let body;
    if (configured.length === 0) {
        body = `
            <div class="flex flex-col items-center justify-center py-8 px-4 rounded-lg border border-dashed border-slate-200 dark:border-white/10">
                <p class="text-sm text-slate-500 dark:text-slate-400 text-center">${t('models_not_configured')}</p>
                <button onclick="openVendorModal('')"
                        class="mt-3 px-3 py-1.5 rounded-lg text-xs font-medium bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 hover:bg-primary-100 dark:hover:bg-primary-900/50 cursor-pointer transition-colors">
                    <i class="fas fa-plus text-[10px] mr-1"></i>${t('models_add_vendor')}
                </button>
            </div>`;
    } else {
        body = `<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            ${configured.map(renderVendorChip).join('')}
        </div>`;
    }

    wrap.innerHTML = header + body;
    return wrap;
}

function renderVendorChip(p) {
    // The masked API key is intentionally not surfaced here; it is shown
    // inside the edit modal so the chip stays uncluttered and scannable.
    // Custom providers open their dedicated modal (name + base + key);
    // their ids are server-generated hex, safe to inline.
    const onclick = isCustomProviderCard(p)
        ? `openCustomProviderModal('${escapeHtml(p.custom_id)}')`
        : `openVendorModal('${escapeHtml(p.id)}')`;
    return `
        <button onclick="${onclick}"
                class="group flex items-center gap-3 px-3 py-2.5 rounded-lg border border-slate-200 dark:border-white/10
                       bg-slate-50 dark:bg-white/5 hover:border-primary-300 dark:hover:border-primary-500/50
                       cursor-pointer transition-colors duration-150 text-left">
            ${renderProviderLogo(p, 28)}
            <span class="flex-1 min-w-0 text-sm font-medium text-slate-800 dark:text-slate-100 truncate">${escapeHtml(localizedLabel(p.label))}</span>
            <i class="fas fa-pen-to-square text-[11px] text-slate-400 dark:text-slate-500 group-hover:text-primary-500 transition-colors"></i>
        </button>`;
}

// Render a uniformly-styled logo for a provider. Tries an SVG asset first; if
// it 404s the <img> swaps itself for a monogram fallback via onerror.
function renderProviderLogo(p, sizePx) {
    const initial = (localizedLabel(p.label) || p.id || '?').slice(0, 1).toUpperCase();
    const sz = sizePx || 32;
    const url = `${MODELS_PROVIDER_LOGO_PATH}/${encodeURIComponent(p.id)}.svg`;
    const fallbackId = `pl-${p.id}-${Math.random().toString(36).slice(2, 8)}`;
    const imgClass = MODELS_PROVIDER_LOGO_DARK_INVERT.has(p.id)
        ? 'absolute inset-0 m-auto provider-logo-img provider-logo-invert-dark'
        : 'absolute inset-0 m-auto provider-logo-img';
    return `
        <span class="relative flex items-center justify-center rounded-lg bg-slate-100 dark:bg-white/10
                     text-slate-600 dark:text-slate-300 flex-shrink-0 overflow-hidden"
              style="width:${sz}px;height:${sz}px;">
            <span id="${fallbackId}" class="text-xs font-bold">${escapeHtml(initial)}</span>
            <img src="${url}" alt="" aria-hidden="true"
                 class="${imgClass}"
                 style="width:${Math.round(sz * 0.65)}px;height:${Math.round(sz * 0.65)}px;"
                 onload="(function(el){var f=document.getElementById('${fallbackId}');if(f)f.style.display='none';})(this)"
                 onerror="this.remove();">
        </span>`;
}

function getCustomProviderCards() {
    return modelsState.providers.filter(isCustomProviderCard);
}

// ---------- Capability cards (Layer 2) ---------------------------------

function renderCapabilityCard(def) {
    const cap = modelsState.capabilities[def.id] || {};
    const wrap = document.createElement('div');
    wrap.className = 'bg-white dark:bg-[#1A1A1A] rounded-xl border border-slate-200 dark:border-white/10 p-6';
    wrap.id = `models-card-${def.id}`;

    const headerRight = renderCapabilityHeaderTag(def, cap);

    wrap.innerHTML = `
        <div class="flex items-start gap-3 mb-5">
            <div class="w-9 h-9 rounded-lg ${def.iconChip} flex items-center justify-center flex-shrink-0">
                <i class="fas ${def.icon} ${def.iconGlyph} text-sm"></i>
            </div>
            <div class="flex-1 min-w-0">
                <h3 class="font-semibold text-slate-800 dark:text-slate-100">${t(def.titleKey)}</h3>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">${t(def.descKey)}</p>
            </div>
            ${headerRight}
        </div>
        <div class="space-y-4" data-cap-body="${def.id}"></div>`;

    const body = wrap.querySelector(`[data-cap-body="${def.id}"]`);
    renderCapabilityBody(def, cap, body);
    return wrap;
}

function renderCapabilityHeaderTag(def, cap) {
    return '';
}

function _searchProviderLabel(cap, providerId) {
    const list = (cap && cap.providers) || [];
    const hit = list.find(p => p.id === providerId);
    return hit ? localizedLabel(hit.label) : providerId;
}

// Search card body: strategy picker + (when fixed) provider picker + a
// status row that surfaces which providers are ready and how to add the
// missing ones. Three of the four backends piggy-back on model-vendor
// credentials (zhipu / qianfan / linkai); bocha / serper / jina own keys
// under tools.web_search and share a minimal credential modal.
function renderSearchCapability(def, cap, body) {
    const providers = cap.providers || [];
    const configuredIds = cap.configured_providers || [];
    const hasAny = configuredIds.length > 0;
    const strategy = cap.strategy || 'auto';

    body.innerHTML = `
        <div>
            <label class="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('models_search_strategy_label')}</label>
            <div id="cap-search-strategy" class="cfg-dropdown" tabindex="0">
                <div class="cfg-dropdown-selected">
                    <span class="cfg-dropdown-text">--</span>
                    <i class="fas fa-chevron-down cfg-dropdown-arrow"></i>
                </div>
                <div class="cfg-dropdown-menu"></div>
            </div>
        </div>
        <div id="cap-search-provider-wrap" class="hidden">
            <label class="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('models_provider')}</label>
            <div id="cap-search-provider" class="cfg-dropdown" tabindex="0">
                <div class="cfg-dropdown-selected">
                    <span class="cfg-dropdown-text">--</span>
                    <i class="fas fa-chevron-down cfg-dropdown-arrow"></i>
                </div>
                <div class="cfg-dropdown-menu"></div>
            </div>
        </div>
        <div id="cap-search-summary"></div>
        <div class="flex items-center justify-end gap-3 pt-1">
            <span id="cap-search-status" class="text-xs text-primary-500 opacity-0 transition-opacity duration-300"></span>
            <button onclick="saveSearchCapability()"
                    class="px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium
                           cursor-pointer transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed">
                ${t('save')}
            </button>
        </div>
    `;

    // Strategy dropdown — when no provider is configured the strategy
    // value is meaningless, so we show a "待配置" placeholder instead of
    // a default selection. Once any provider gets configured the saved
    // strategy (or "auto") becomes the active value.
    initDropdown(
        body.querySelector('#cap-search-strategy'),
        [
            { value: 'auto',  label: t('models_strategy_auto'),         hint: t('models_search_strategy_auto_hint') },
            { value: 'fixed', label: t('models_search_strategy_fixed'), hint: t('models_search_strategy_fixed_hint') },
        ],
        hasAny ? strategy : '',
        (value) => _onSearchStrategyChange(cap, value, body),
        hasAny ? null : { placeholder: t('models_pending_config') },
    );

    // Provider dropdown — populated with configured providers only;
    // unconfigured ones cannot be pinned (they'd silently fall back).
    const provOpts = configuredIds.map(id => ({
        value: id,
        label: _searchProviderLabel(cap, id),
    }));
    if (provOpts.length === 0) provOpts.push({ value: '', label: '--' });
    initDropdown(
        body.querySelector('#cap-search-provider'),
        provOpts,
        cap.fixed_provider || configuredIds[0] || '',
        () => {},
    );

    _renderSearchSummary(body, cap);
    _setSearchProviderPickerVisible(body, strategy === 'fixed' && hasAny);
}

function _onSearchStrategyChange(cap, value, body) {
    const configuredIds = cap.configured_providers || [];
    _setSearchProviderPickerVisible(body, value === 'fixed' && configuredIds.length > 0);
}

function _setSearchProviderPickerVisible(body, visible) {
    const wrap = body.querySelector('#cap-search-provider-wrap');
    if (!wrap) return;
    if (visible) wrap.classList.remove('hidden');
    else wrap.classList.add('hidden');
}

// Search summary line: just lists configured providers + a trailing "+
// add" button. Unconfigured backends are hidden — the user picks one from
// a small chooser when they click add. Empty state surfaces the same add
// button as a primary CTA.
function _renderSearchSummary(body, cap) {
    const host = body.querySelector('#cap-search-summary');
    if (!host) return;
    const providers = cap.providers || [];
    const configured = providers.filter(p => p.configured);
    const missing = providers.filter(p => !p.configured);

    const addBtn = missing.length
        ? `<button type="button" id="cap-search-add-btn"
                  class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-md cursor-pointer
                         bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400
                         hover:bg-slate-200 dark:hover:bg-white/10 transition-colors">
              <i class="fas fa-plus text-[10px]"></i>${t('models_search_add_provider')}
           </button>`
        : '';

    if (configured.length === 0) {
        host.innerHTML = `
            <div class="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <i class="fas fa-circle-info text-[10px] text-amber-500"></i>
                <span>${t('models_search_none_configured')}</span>
                ${addBtn}
            </div>
        `;
    } else {
        const chips = configured.map(p => `
            <button type="button" data-search-edit-provider="${p.id}"
                    title="${t('models_search_edit_hint')}"
                    class="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] rounded-md cursor-pointer
                           bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400
                           hover:bg-emerald-100 dark:hover:bg-emerald-900/50 transition-colors">
                <i class="fas fa-check text-[10px]"></i>${escapeHtml(localizedLabel(p.label))}
            </button>
        `).join('');
        host.innerHTML = `
            <div class="flex items-center flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span>${t('models_search_available_label')}</span>
                ${chips}
                ${addBtn}
            </div>
        `;
    }

    const addBtnEl = host.querySelector('#cap-search-add-btn');
    if (addBtnEl) {
        addBtnEl.addEventListener('click', (ev) => {
            ev.preventDefault();
            openSearchAddProviderPicker(missing);
        });
    }
    host.querySelectorAll('[data-search-edit-provider]').forEach(el => {
        el.addEventListener('click', (ev) => {
            ev.preventDefault();
            const pid = el.getAttribute('data-search-edit-provider');
            const meta = (cap.providers || []).find(p => p.id === pid);
            _launchSearchProviderConfig(pid, meta);
        });
    });
}

// Two-step add flow: click "+ 添加厂商" -> chooser dialog -> per-provider
// credential editor. Dedicated search providers land on the search key modal;
// the others piggy-back on the existing vendor credential modal.
function openSearchAddProviderPicker(missingProviders) {
    if (!missingProviders || missingProviders.length === 0) return;
    if (missingProviders.length === 1) {
        _launchSearchProviderConfig(missingProviders[0].id);
        return;
    }

    const existing = document.getElementById('search-add-modal');
    if (existing) existing.remove();

    const rows = missingProviders.map(p => `
        <button type="button" data-pid="${p.id}"
                class="w-full flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer
                       bg-slate-50 dark:bg-white/5 hover:bg-slate-100 dark:hover:bg-white/10
                       text-sm text-slate-700 dark:text-slate-200 transition-colors">
            <span>${escapeHtml(localizedLabel(p.label))}</span>
            <i class="fas fa-chevron-right text-[10px] text-slate-400"></i>
        </button>
    `).join('');

    const modal = document.createElement('div');
    modal.id = 'search-add-modal';
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm';
    modal.innerHTML = `
        <div class="bg-white dark:bg-[#1A1A1A] rounded-xl border border-slate-200 dark:border-white/10
                    w-full max-w-md mx-4 p-6 shadow-xl">
            <h3 class="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-1">${t('models_search_add_provider')}</h3>
            <p class="text-xs text-slate-500 dark:text-slate-400 mb-4">${t('models_search_add_desc')}</p>
            <div class="space-y-2">${rows}</div>
            <div class="flex items-center justify-end mt-5">
                <button type="button" onclick="document.getElementById('search-add-modal').remove()"
                        class="px-3 py-1.5 rounded-md text-sm text-slate-600 dark:text-slate-300
                               hover:bg-slate-100 dark:hover:bg-white/5 transition-colors">
                    ${t('cancel')}
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelectorAll('[data-pid]').forEach(el => {
        el.addEventListener('click', () => {
            const pid = el.getAttribute('data-pid');
            modal.remove();
            _launchSearchProviderConfig(pid);
        });
    });
}

function _launchSearchProviderConfig(providerId, providerMeta) {
    if (providerMeta && providerMeta.needs_dedicated_key) {
        openSearchCredentialModal(providerId, providerMeta);
    } else if (['bocha', 'serper', 'jina'].includes(providerId)) {
        openSearchCredentialModal(providerId, providerMeta);
    } else {
        openVendorModal(providerId, () => loadModelsView({ preserveScroll: true }));
    }
}

function saveSearchCapability() {
    const strategyDd = document.getElementById('cap-search-strategy');
    const providerDd = document.getElementById('cap-search-provider');
    const strategy = strategyDd ? getDropdownValue(strategyDd) : 'auto';
    const provider = (strategy === 'fixed' && providerDd) ? getDropdownValue(providerDd) : '';

    fetch('/api/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'set_capability',
            capability: 'search',
            strategy,
            provider,
        }),
    }).then(r => r.json()).then(data => {
        if (data.status === 'success') {
            showStatus('cap-search-status', 'models_save_success', false);
            setTimeout(() => loadModelsView({ preserveScroll: true }), 400);
        } else {
            showStatus('cap-search-status', 'models_save_failed', true);
        }
    }).catch(() => showStatus('cap-search-status', 'models_save_failed', true));
}

const SEARCH_DEDICATED_PROVIDERS = {
    bocha: {
        titleKey: 'models_search_bocha_title',
        descKey: 'models_search_bocha_desc',
        applyUrl: 'https://open.bochaai.com/',
    },
    serper: {
        titleKey: 'models_search_serper_title',
        descKey: 'models_search_serper_desc',
        applyUrl: 'https://serper.dev/',
    },
    jina: {
        titleKey: 'models_search_jina_title',
        descKey: 'models_search_jina_desc',
        applyUrl: 'https://jina.ai/',
    },
};

// Minimal search API-key modal. Bocha, Serper and Jina are search-only
// providers, so they store credentials under tools.web_search instead of the
// model-vendor credential table.
function openSearchCredentialModal(providerId, providerMeta) {
    const provider = providerId || 'bocha';
    const providerCfg = SEARCH_DEDICATED_PROVIDERS[provider];
    if (!providerCfg) return;

    const modalId = `search-${provider}-modal`;
    const existing = document.getElementById(modalId);
    if (existing) existing.remove();

    let masked = (providerMeta && providerMeta.api_key_masked) || '';
    if (!masked) {
        const searchCap = (modelsState && modelsState.capabilities && modelsState.capabilities.search) || {};
        const providerInfo = (searchCap.providers || []).find(p => p.id === provider);
        if (providerInfo && providerInfo.api_key_masked) masked = providerInfo.api_key_masked;
    }
    const hasKey = !!masked;
    const clearBtnHtml = hasKey
        ? `<button type="button" id="search-credential-clear"
                  class="px-3 py-1.5 rounded-md text-xs text-red-500 dark:text-red-400
                         hover:bg-red-50 dark:hover:bg-red-900/20 cursor-pointer transition-colors">
              ${t('models_clear_credential')}
           </button>`
        : '';

    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm';
    modal.innerHTML = `
        <div id="search-credential-modal-card"
             class="bg-white dark:bg-[#1A1A1A] rounded-xl border border-slate-200 dark:border-white/10
                    w-full max-w-md mx-4 p-6 shadow-xl">
            <h3 class="text-lg font-semibold text-slate-800 dark:text-slate-100 mb-1">${t(providerCfg.titleKey)}</h3>
            <p class="text-xs text-slate-500 dark:text-slate-400 mb-2">${t(providerCfg.descKey)}</p>
            <a href="${providerCfg.applyUrl}" target="_blank" rel="noopener noreferrer"
               class="inline-flex items-center gap-1 text-xs text-primary-500 hover:text-primary-600 dark:hover:text-primary-400 mb-4">
                ${t('models_search_apply_link')}<i class="fas fa-arrow-up-right-from-square text-[10px]"></i>
            </a>
            <label class="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">API Key</label>
            <input id="search-credential-key" type="text" autocomplete="off" data-1p-ignore data-lpignore="true"
                   class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600
                          bg-slate-50 dark:bg-white/5 text-sm text-slate-800 dark:text-slate-100
                          focus:outline-none focus:border-primary-500 font-mono ${hasKey ? 'cfg-key-masked' : ''}"
                   value="${escapeHtml(masked)}"
                   data-masked="${hasKey ? '1' : ''}"
                   placeholder="sk-..." />
            <div class="flex items-center justify-between gap-3 mt-5">
                <div>${clearBtnHtml}</div>
                <div class="flex items-center gap-3">
                    <button type="button" data-search-credential-cancel
                            class="px-3 py-1.5 rounded-md text-sm text-slate-600 dark:text-slate-300
                                   hover:bg-slate-100 dark:hover:bg-white/5 transition-colors">
                        ${t('cancel')}
                    </button>
                    <button type="button" id="search-credential-save"
                            class="px-4 py-1.5 rounded-md bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium
                                   cursor-pointer transition-colors">
                        ${t('save')}
                    </button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // Reset masked sentinel as soon as the user starts editing so the save
    // handler can tell apart "kept the existing key" vs "typed a new one".
    const input = document.getElementById('search-credential-key');
    if (input) {
        const unmask = () => {
            if (input.dataset.masked === '1') {
                input.value = '';
                input.dataset.masked = '';
                input.classList.remove('cfg-key-masked');
            }
        };
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Tab' || e.key === 'Escape') return;
            unmask();
        });
        input.addEventListener('paste', unmask);
        if (!hasKey) setTimeout(() => input.focus(), 50);
    }
    const clearBtn = document.getElementById('search-credential-clear');
    if (clearBtn) clearBtn.addEventListener('click', () => _clearSearchCredential(provider, modalId));
    const saveBtn = document.getElementById('search-credential-save');
    if (saveBtn) saveBtn.addEventListener('click', () => _saveSearchCredential(provider, modalId));
    modal.querySelector('[data-search-credential-cancel]')?.addEventListener('click', () => modal.remove());

    modal.addEventListener('mousedown', (e) => {
        if (e.target === modal) modal.remove();
    });
    const onKey = (e) => {
        if (e.key === 'Escape') {
            modal.remove();
            document.removeEventListener('keydown', onKey);
        }
    };
    document.addEventListener('keydown', onKey);
}

function _saveSearchCredential(provider, modalId) {
    const input = document.getElementById('search-credential-key');
    if (!input) return;
    // Untouched masked value => no change requested; close silently.
    if (input.dataset.masked === '1') {
        const modal = document.getElementById(modalId);
        if (modal) modal.remove();
        return;
    }
    const apiKey = input.value.trim();
    if (!apiKey) {
        input.focus();
        return;
    }
    fetch('/api/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'set_search_credential', provider, api_key: apiKey }),
    }).then(r => r.json()).then(data => {
        if (data.status === 'success') {
            const modal = document.getElementById(modalId);
            if (modal) modal.remove();
            loadModelsView({ preserveScroll: true });
        }
    });
}

function _clearSearchCredential(provider, modalId) {
    fetch('/api/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'set_search_credential', provider, api_key: '' }),
    }).then(r => r.json()).then(data => {
        if (data.status === 'success') {
            const modal = document.getElementById(modalId);
            if (modal) modal.remove();
            loadModelsView({ preserveScroll: true });
        }
    });
}

function formatChatFailoverDuration(seconds) {
    const value = Math.max(1, Number.parseInt(seconds, 10) || 300);
    if (value % 60 === 0) {
        return t('models_chat_failover_minutes').replace('{value}', String(value / 60));
    }
    return t('models_chat_failover_seconds').replace('{value}', String(value));
}

function renderChatFallbacksSection(cap) {
    const fallbacks = Array.isArray(cap.model_fallbacks) ? cap.model_fallbacks : [];
    const rowsHtml = fallbacks.map((item, idx) => renderChatFallbackRow(idx, item)).join('');
    const threshold = Math.max(1, Number.parseInt(cap.model_failover_failure_threshold, 10) || 3);
    const cooldown = formatChatFailoverDuration(cap.model_failover_cooldown_seconds);
    const circuitText = t('models_chat_failover_circuit')
        .replace('{threshold}', String(threshold))
        .replace('{cooldown}', cooldown);
    return `
        <div id="cap-chat-fallbacks"
             class="rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-3 space-y-3">
            <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                    <label class="block text-sm font-medium text-slate-600 dark:text-slate-400">${t('models_chat_fallbacks')}</label>
                    <p class="text-xs text-slate-400 dark:text-slate-500 mt-0.5">${t('models_chat_fallbacks_desc')}</p>
                </div>
                <button type="button" onclick="addChatFallbackRow()"
                        class="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium
                               bg-white dark:bg-[#111111] border border-slate-200 dark:border-white/10
                               text-slate-600 dark:text-slate-300 hover:border-primary-300 dark:hover:border-primary-500/50
                               cursor-pointer transition-colors">
                    <i class="fas fa-plus text-[10px]"></i>${t('models_chat_fallback_add')}
                </button>
            </div>
            <div id="cap-chat-fallbacks-list" class="space-y-2">${rowsHtml}</div>
            <div class="border-t border-slate-200 dark:border-white/10 pt-3"
                 role="note" aria-label="${escapeHtml(t('models_chat_failover_title'))}">
                <div class="flex items-start gap-2.5">
                    <i class="fas fa-shield-alt mt-0.5 text-xs text-primary-500" aria-hidden="true"></i>
                    <div class="min-w-0">
                        <p class="text-sm font-medium text-slate-700 dark:text-slate-300">${t('models_chat_failover_title')}</p>
                        <p class="mt-0.5 text-xs leading-5 text-slate-500 dark:text-slate-400">${t('models_chat_failover_scope')}</p>
                        <ul class="mt-1.5 list-disc space-y-1 pl-4 text-xs leading-5 text-slate-500 dark:text-slate-400">
                            <li>${t('models_chat_failover_immediate')}</li>
                            <li>${circuitText}</li>
                            <li>${t('models_chat_failover_recovery')}</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>`;
}

function renderChatFallbackRow(index, fallback) {
    const item = fallback || {};
    const providerId = String(item.provider_id || item.provider || item.bot_type || '').trim();
    const model = String(item.model || '').trim();
    return `
        <div class="grid grid-cols-1 md:grid-cols-[minmax(180px,0.9fr)_minmax(220px,1.1fr)_auto] gap-2 items-start"
             data-chat-fallback-row data-fallback-provider="${escapeHtml(providerId)}">
            <div id="cap-chat-fallback-provider-${index}" data-chat-fallback-provider class="cfg-dropdown" tabindex="0">
                <div class="cfg-dropdown-selected">
                    <span class="cfg-dropdown-text">--</span>
                    <i class="fas fa-chevron-down cfg-dropdown-arrow"></i>
                </div>
                <div class="cfg-dropdown-menu"></div>
            </div>
            <input id="cap-chat-fallback-model-${index}" data-chat-fallback-model type="text"
                   value="${escapeHtml(model)}" placeholder="${escapeHtml(t('models_model'))}"
                   class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600
                          bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100
                          focus:outline-none focus:border-primary-500 font-mono transition-colors">
            <button type="button" onclick="removeChatFallbackRow(this)"
                    title="${escapeHtml(t('models_chat_fallback_remove'))}"
                    aria-label="${escapeHtml(t('models_chat_fallback_remove'))}"
                    class="h-10 w-10 inline-flex items-center justify-center rounded-lg border border-slate-200 dark:border-white/10
                           text-slate-400 hover:text-red-500 hover:border-red-200 dark:hover:border-red-500/40
                           bg-white dark:bg-[#111111] cursor-pointer transition-colors">
                <i class="fas fa-trash text-xs"></i>
            </button>
        </div>`;
}

function buildChatFallbackProviderOptions(currentProvider) {
    const chatDef = MODELS_CAPABILITY_DEFS.find(d => d.id === 'chat') || { id: 'chat' };
    const chatCap = modelsState.capabilities.chat || {};
    const opts = [{ value: '', label: t('models_chat_fallback_infer_provider') }];
    buildCapabilityProviderOptions(chatDef, chatCap)
        .filter(o => !o._isAuto && (o._configured || o.value === currentProvider))
        .forEach(o => {
            if (!opts.some(existing => existing.value === o.value)) {
                opts.push({ value: o.value, label: o.label });
            }
        });
    if (currentProvider && !opts.some(o => o.value === currentProvider)) {
        opts.push({ value: currentProvider, label: currentProvider });
    }
    return opts;
}

function initChatFallbackRows(scope) {
    const root = scope || document;
    const rows = [];
    if (root.matches && root.matches('[data-chat-fallback-row]')) rows.push(root);
    root.querySelectorAll('[data-chat-fallback-row]').forEach(row => rows.push(row));
    rows.forEach(row => {
        const providerId = row.dataset.fallbackProvider || '';
        const dd = row.querySelector('[data-chat-fallback-provider]');
        if (dd && !dd._chatFallbackBound) {
            initDropdown(dd, buildChatFallbackProviderOptions(providerId), providerId, () => {});
            dd._chatFallbackBound = true;
        }
    });
}

function addChatFallbackRow() {
    const list = document.getElementById('cap-chat-fallbacks-list');
    if (!list) return;
    const index = Date.now();
    const temp = document.createElement('div');
    temp.innerHTML = renderChatFallbackRow(index, {});
    const row = temp.firstElementChild;
    if (!row) return;
    list.appendChild(row);
    initChatFallbackRows(row);
    const input = row.querySelector('[data-chat-fallback-model]');
    if (input) input.focus();
}

function removeChatFallbackRow(button) {
    const row = button ? button.closest('[data-chat-fallback-row]') : null;
    if (row) row.remove();
}

function readChatFallbackRows() {
    const rows = document.querySelectorAll('#cap-chat-fallbacks-list [data-chat-fallback-row]');
    const fallbacks = [];
    rows.forEach(row => {
        const dd = row.querySelector('[data-chat-fallback-provider]');
        const input = row.querySelector('[data-chat-fallback-model]');
        const providerId = dd ? getDropdownValue(dd) : '';
        const model = input ? String(input.value || '').trim() : '';
        if (!providerId && !model) return;
        fallbacks.push({ provider_id: providerId, model });
    });
    return fallbacks;
}

function renderCapabilityBody(def, cap, body) {
    if (def.id === 'search') {
        renderSearchCapability(def, cap, body);
        return;
    }

    // Editable cards: provider dropdown + (optional) model dropdown + save row
    const providerOpts = buildCapabilityProviderOptions(def, cap);
    const pickerCurrentProvider = cap.legacy_configured_provider ? '' : cap.current_provider;
    const pickerCurrentModel = (cap.legacy_configured_provider || capabilityUsesAutoProvider(def.id, pickerCurrentProvider)) ? '' : cap.current_model;
    const pickerCurrentVoice = cap.legacy_configured_provider ? '' : cap.current_voice;
    const invalidProvider = String(cap.invalid_configured_provider || '').trim();
    const invalidProviderHtml = (
        (def.id === 'asr' || def.id === 'tts') && invalidProvider
    ) ? `
        <div data-cap-invalid-provider="${def.id}" role="alert"
             class="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2
                    text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
            <i class="fas fa-triangle-exclamation mt-0.5 flex-shrink-0" aria-hidden="true"></i>
            <span>
                <span data-i18n="models_invalid_voice_provider">${t('models_invalid_voice_provider')}</span>
                <span class="font-mono break-all">${escapeHtml(invalidProvider)}</span>
            </span>
        </div>` : '';
    const legacyProvider = String(cap.legacy_configured_provider || '').trim();
    const legacyProviderHtml = (
        (def.id === 'asr' || def.id === 'tts') && legacyProvider
    ) ? `
        <div data-cap-legacy-provider="${def.id}" role="alert"
             class="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2
                    text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">
            <i class="fas fa-triangle-exclamation mt-0.5 flex-shrink-0" aria-hidden="true"></i>
            <span>
                <span data-i18n="models_legacy_voice_provider">${t('models_legacy_voice_provider')}</span>
                <span class="font-mono break-all">${escapeHtml(legacyProvider)}</span>
            </span>
        </div>` : '';
    const providerHtml = `
        <div>
            <label class="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('models_provider')}</label>
            <div id="cap-${def.id}-provider" class="cfg-dropdown" tabindex="0">
                <div class="cfg-dropdown-selected">
                    <span class="cfg-dropdown-text">--</span>
                    <i class="fas fa-chevron-down cfg-dropdown-arrow"></i>
                </div>
                <div class="cfg-dropdown-menu"></div>
            </div>
        </div>`;

    // The model-picker container is always emitted so the provider-change
    // handler can show/hide it; for `auto` capabilities it starts hidden and
    // gets toggled by setCapabilityModelPickerVisible.
    const modelHtml = def.needsModel ? `
        <div id="cap-${def.id}-model-wrap">
            <label class="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('models_model')}</label>
            <div id="cap-${def.id}-model" class="cfg-dropdown" tabindex="0">
                <div class="cfg-dropdown-selected">
                    <span class="cfg-dropdown-text">--</span>
                    <i class="fas fa-chevron-down cfg-dropdown-arrow"></i>
                </div>
                <div class="cfg-dropdown-menu"></div>
            </div>
            <div id="cap-${def.id}-model-custom-wrap" class="mt-2 hidden">
                <input id="cap-${def.id}-model-custom" type="text"
                       class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600
                              bg-slate-50 dark:bg-white/5 text-sm text-slate-800 dark:text-slate-100
                              focus:outline-none focus:border-primary-500 font-mono transition-colors"
                       placeholder="custom model name">
            </div>
        </div>` : '';

    const dimHtml = (def.id === 'embedding' && cap.current_dim) ? `
        <p class="text-xs text-slate-400 dark:text-slate-500">
            <i class="fas fa-cube text-[10px] mr-1"></i>${t('models_dim_label')}: <span class="font-mono">${cap.current_dim}</span>
        </p>` : '';
    const chatFallbacksHtml = def.id === 'chat' ? renderChatFallbacksSection(cap) : '';

    // Footer layout: a "hint slot" (filled later by renderCapabilityHints for
    // auto-mode cards) sits on the left while status + save stay anchored on
    // the right. Keeping them on the same row means the save button hugs the
    // inputs above instead of being pushed down by a separate hint line.
    const footer = `
        <div class="flex items-center justify-between gap-3 pt-1">
            <div data-cap-hint="${def.id}" class="flex-1 min-w-0"></div>
            <div class="flex items-center gap-3 flex-shrink-0">
                <span id="cap-${def.id}-status" class="text-xs text-primary-500 opacity-0 transition-opacity duration-300"></span>
                <button onclick="saveCapability('${def.id}')"
                        class="px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium
                               cursor-pointer transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed">
                    ${t('save')}
                </button>
            </div>
        </div>`;

    body.innerHTML = invalidProviderHtml + legacyProviderHtml + providerHtml + modelHtml + chatFallbacksHtml + dimHtml + footer;

    // TTS: mount reply-mode above provider; defer off-mode toggle to the end.
    if (def.id === 'tts') {
        renderVoiceReplyMode(body, cap.reply_mode || 'off', { skipVisibilityToggle: true });
        // Voice-timbre picker depends on provider+model; rebuilt by callbacks.
        const modelWrap = body.querySelector(`#cap-${def.id}-model-wrap`);
        if (modelWrap) {
            const voiceWrap = document.createElement('div');
            voiceWrap.id = `cap-${def.id}-voice-wrap`;
            voiceWrap.innerHTML = `
                <label class="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('models_voice')}</label>
                <div id="cap-${def.id}-voice" class="cfg-dropdown" tabindex="0">
                    <div class="cfg-dropdown-selected">
                        <span class="cfg-dropdown-text">--</span>
                        <i class="fas fa-chevron-down cfg-dropdown-arrow"></i>
                    </div>
                    <div class="cfg-dropdown-menu"></div>
                </div>
                <div id="cap-${def.id}-voice-custom-wrap" class="hidden mt-2">
                    <input id="cap-${def.id}-voice-custom" type="text"
                           class="w-full px-3 py-2 text-sm rounded-md border border-slate-200 dark:border-slate-700
                                  bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200
                                  placeholder:text-slate-400 dark:placeholder:text-slate-500
                                  focus:outline-none focus:ring-2 focus:ring-primary-500"
                           placeholder="voice id" />
                </div>
            `;
            modelWrap.parentNode.insertBefore(voiceWrap, modelWrap.nextSibling);
        }
    }

    // `body` is still detached from `document`; scope lookups locally.
    const provDd = body.querySelector(`#cap-${def.id}-provider`);
    // Strip private fields before handing to the generic initDropdown helper.
    const ddOpts = providerOpts.map(o => ({ value: o.value, label: o.label }));

    let pendingProvider = null;
    if (pendingCapabilitySelection
            && pendingCapabilitySelection.capabilityId === def.id
            && providerOpts.some(o => o.value === pendingCapabilitySelection.providerId)) {
        pendingProvider = pendingCapabilitySelection.providerId;
        pendingCapabilitySelection = null;
    }

    // Auto strategy => leave empty sentinel selected. `suggested_provider`
    // is a UI-only preselect (not persisted until the user clicks Save).
    // No current + no suggestion => leave unselected with a placeholder.
    //
    // Pending-config takes priority over both "auto" and "pick provider":
    // when no real (non-sentinel) configured option exists, surfacing
    // "auto" or "pick" misleads the user — there's nothing to auto-route
    // to or pick from. Force a "待配置" placeholder instead so all
    // capabilities behave consistently on a fresh environment.
    const hasConfiguredOpt = providerOpts.some(o => !o._isAuto && o._configured);
    const noSelectionAndNoHint = !pickerCurrentProvider && !cap.suggested_provider;
    let initialProviderValue;
    let dropdownPlaceholder = null;
    if (!hasConfiguredOpt) {
        initialProviderValue = '';
        dropdownPlaceholder = { placeholder: t('models_pending_config') };
    } else {
        initialProviderValue = pendingProvider
            ? pendingProvider
            : ((cap.strategy === 'auto' && capabilitySupportsAuto(def.id))
                ? ''
                : (pickerCurrentProvider
                    || cap.suggested_provider
                    || (noSelectionAndNoHint ? '' : (ddOpts[0] && ddOpts[0].value))
                    || ''));
        if (noSelectionAndNoHint) {
            dropdownPlaceholder = { placeholder: t('models_pick_provider') };
        }
    }
    initDropdown(
        provDd,
        ddOpts,
        initialProviderValue,
        (value) => onCapabilityProviderChange(def, value, body),
        dropdownPlaceholder,
    );
    decorateCapabilityProviderDropdown(def, provDd, providerOpts);

    if (def.needsModel) {
        rebuildCapabilityModelDropdown(def, initialProviderValue, pickerCurrentModel || '', body);
        // Embedding: hide model picker when no provider is selected.
        const showModel = def.id === 'embedding' ? initialProviderValue !== '' :
            !capabilityUsesAutoProvider(def.id, initialProviderValue);
        setCapabilityModelPickerVisible(def, showModel, body);
    }

    if (def.id === 'tts') {
        rebuildCapabilityVoiceDropdown(
            initialProviderValue,
            pickerCurrentVoice || '',
            body,
            pickerCurrentModel || ''
        );
    }

    // Inject auto/router-pending hint banners before the action footer.
    renderCapabilityHints(def, cap, body, initialProviderValue);
    if (def.id === 'chat') {
        initChatFallbackRows(body);
    }

    if (def.id === 'tts') {
        _setTtsConfigVisible(body, (cap.reply_mode || 'off') !== 'off');
    }
}

// TTS reply-policy dropdown (off / voice_if_voice / always). Persists on
// change. When off, hides the rest of the TTS card.
function renderVoiceReplyMode(host, currentMode, options) {
    options = options || {};
    const opts = [
        { value: 'off',            label: t('voice_reply_off') },
        { value: 'voice_if_voice', label: t('voice_reply_if_voice') },
        { value: 'always',         label: t('voice_reply_always') },
    ];
    const wrap = document.createElement('div');
    wrap.id = 'voice-reply-mode-wrap';
    wrap.innerHTML = `
        <label class="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('voice_reply_mode_label')}</label>
        <div id="voice-reply-mode-dd" class="cfg-dropdown" tabindex="0">
            <div class="cfg-dropdown-selected">
                <span class="cfg-dropdown-text">--</span>
                <i class="fas fa-chevron-down cfg-dropdown-arrow"></i>
            </div>
            <div class="cfg-dropdown-menu"></div>
        </div>
    `;
    host.prepend(wrap);

    const dd = wrap.querySelector('#voice-reply-mode-dd');
    const valid = ['off', 'voice_if_voice', 'always'];
    const initial = valid.includes(currentMode) ? currentMode : 'off';
    if (!options.skipVisibilityToggle) _setTtsConfigVisible(host, initial !== 'off');
    initDropdown(dd, opts, initial, (mode) => {
        if (!valid.includes(mode)) return;
        _setTtsConfigVisible(host, mode !== 'off');
        fetch('/api/models', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'set_voice_reply_mode', mode }),
        })
            .then(r => r.json())
            .then(data => {
                if (data && data.status === 'success') {
                    _ttsReadyPromise = null;  // force re-probe on next bubble
                }
            })
            .catch(() => {});
    });
}

// Show/hide everything in the TTS card below the reply-mode dropdown.
function _setTtsConfigVisible(host, visible) {
    if (!host) return;
    Array.from(host.children).forEach((child) => {
        if (child.id === 'voice-reply-mode-wrap'
                || child.hasAttribute('data-cap-invalid-provider')
                || child.hasAttribute('data-cap-legacy-provider')) return;
        child.classList.toggle('hidden', !visible);
    });
}

// Toggle wrapper visibility instead of re-rendering so dropdown state survives.
function setCapabilityModelPickerVisible(def, visible, scope) {
    const root = scope || document;
    const wrap = root.querySelector(`#cap-${def.id}-model-wrap`);
    if (!wrap) return;
    wrap.classList.toggle('hidden', !visible);
}

function renderCapabilityHints(def, cap, body, currentProvider) {
    // Capabilities that can be in "auto" mode show a fallback hint right
    // under the inputs so users always know what'd actually be hit. The
    // image card additionally surfaces a "router pending" warning until the
    // standalone dispatcher lands.
    // The hint slot is co-located with the save button in the footer row
    // (see renderCapabilityBody) so the save button stays close to the
    // inputs above. We just rewrite the slot's innerHTML — emptying it
    // when the card leaves auto mode, or rendering a one-line hint when
    // it's in auto mode.
    const slot = body.querySelector(`[data-cap-hint="${def.id}"]`);
    if (!slot) return;
    slot.innerHTML = '';

    if (currentProvider !== '' || !capabilitySupportsAuto(def.id)) return;

    // The hint mirrors what the runtime would actually pick when in auto
    // mode. fallback_provider/model are pre-computed on the backend (see
    // _predict_vision_auto, _predict_image_auto) so we can trust them
    // here without re-implementing the provider chain.
    const fbProv = cap.fallback_provider || '';
    const fbModel = cap.fallback_model || '';
    if (!fbProv && !fbModel) return;
    // Show the vendor's display label (e.g. "LinkAI") instead of the raw
    // id ("linkai") when we know it. Falls back to the id when the
    // provider isn't in our vendor table (rare).
    const provMeta = modelsState.providers.find(p => p.id === fbProv);
    const fbProvLabel = (provMeta && localizedLabel(provMeta.label)) || fbProv;
    const fbText = fbModel ? `${fbProvLabel} / ${fbModel}` : fbProvLabel;
    slot.innerHTML = `
        <p class="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500 min-w-0">
            <i class="fas fa-circle-info text-[10px] flex-shrink-0"></i>
            <span class="flex-shrink-0">${t('models_auto_using')}</span>
            <span class="font-mono text-slate-500 dark:text-slate-400 truncate">${escapeHtml(fbText)}</span>
        </p>`;
}

function buildCapabilityProviderOptions(def, cap) {
    // Show ALL vendors in capability dropdowns so users can see at a glance
    // who's configured (green check) and who isn't (gray dot, click to set
    // up). The list order puts configured vendors first; clicking an
    // unconfigured row opens the vendor modal in-place. ASR/TTS engines that
    // aren't tracked by PROVIDER_MODELS (azure/baidu/google etc.) are treated
    // as "always available" — no credential gate.
    const knownProviderMap = {};
    modelsState.providers.forEach(p => { knownProviderMap[p.id] = p; });

    const explicitList = cap.providers && cap.providers.length ? cap.providers : null;
    let providerIds = explicitList ? explicitList.slice() : modelsState.providers.map(p => p.id);
    if (cap.current_provider
            && cap.current_provider !== cap.invalid_configured_provider
            && cap.current_provider !== cap.legacy_configured_provider
            && !providerIds.includes(cap.current_provider)) {
        providerIds = [cap.current_provider, ...providerIds];
    }

    const opts = providerIds.map(pid => {
        const meta = knownProviderMap[pid];
        const tracked = !!meta;
        const configured = !tracked || !!meta.configured;
        return {
            value: pid,
            label: (meta && localizedLabel(meta.label)) || pid,
            _tracked: tracked,
            _configured: configured,
        };
    });

    opts.sort((a, b) => {
        if (a._configured === b._configured) return 0;
        return a._configured ? -1 : 1;
    });

    // Capabilities with a fallback ("auto") strategy expose it as a sentinel
    // option pinned to the top of the list. We use empty-string as the auto
    // value so the existing save handler propagates it untouched to the
    // backend, which interprets "" as "fall back to the main model".
    // Skip the sentinel when no real vendor is configured — "auto" would
    // route to nothing useful and the renderer will show "待配置" instead.
    const hasAnyConfigured = opts.some(o => o._configured);
    if ((cap.strategy === 'auto' || cap.strategy === 'specified') && hasAnyConfigured) {
        if (capabilitySupportsAuto(def.id)) {
            opts.unshift({
                value: '',
                label: t('models_strategy_auto'),
                _tracked: false,
                _configured: true,
                _isAuto: true,
            });
        }
    }
    return opts;
}

function capabilitySupportsAuto(capId) {
    // Embedding is intentionally NOT here: runtime only auto-falls back to
    // OpenAI/LinkAI, so dressing it up as "auto" hides reality from users.
    return capId === 'image' || capId === 'vision';
}

function capabilityUsesAutoProvider(capId, providerId) {
    return providerId === '' && (capabilitySupportsAuto(capId) || capId === 'asr');
}

// After initDropdown renders the capability provider menu, decorate each
// row with the right-aligned configuration cue:
//   - configured rows: nothing extra — the .active marker (a brand-green ✓)
//     already comes from initDropdown's selected-state CSS for the row the
//     user currently picked. Other configured rows show no chrome, mirroring
//     a plain "switch to this" selector.
//   - unconfigured rows: a subdued gear icon hints at "click to configure".
//     The row's whole click handler is swapped to launch the vendor modal
//     in place rather than selecting an unusable value.
function decorateCapabilityProviderDropdown(def, ddEl, opts) {
    if (!ddEl) return;
    const menu = ddEl.querySelector('.cfg-dropdown-menu');
    if (!menu) return;

    const optByValue = {};
    opts.forEach(o => { optByValue[o.value] = o; });

    menu.querySelectorAll('.cfg-dropdown-item').forEach(item => {
        const value = item.dataset.value;
        const opt = optByValue[value];
        if (!opt) return;
        item.classList.add('cap-provider-item');
        if (!opt._configured) item.classList.add('cap-provider-unconfigured');

        // Wrap the label so the trailing affordance lines up via flex:auto.
        const labelText = item.textContent;
        item.textContent = '';
        const labelEl = document.createElement('span');
        labelEl.className = 'cap-provider-label';
        labelEl.textContent = labelText;
        item.appendChild(labelEl);

        if (!opt._configured) {
            // Trailing gear icon as the "configure this vendor" affordance.
            const gear = document.createElement('i');
            gear.className = 'fas fa-gear cap-provider-gear';
            item.appendChild(gear);
        }

        if (!opt._configured && opt._tracked) {
            // Hijack the click: open the vendor modal instead of selecting
            // an unusable value, and remember which capability the user was
            // configuring so the post-save reload can preselect the vendor.
            const newItem = item.cloneNode(true);
            item.replaceWith(newItem);
            newItem.addEventListener('click', (e) => {
                e.stopPropagation();
                ddEl.classList.remove('open');
                openVendorModal(value, (savedProviderId) => {
                    pendingCapabilitySelection = {
                        capabilityId: def.id,
                        providerId: savedProviderId || value,
                    };
                    loadModelsView({ preserveScroll: true });
                });
            });
        }
    });
}

// Lightweight decorator for the "add vendor" modal's provider picker:
// every configured vendor row gets a trailing brand-green ✓ so the user can
// see at a glance who's already set up, without having to read each row.
// Unlike decorateCapabilityProviderDropdown we don't hijack clicks here —
// picking an unconfigured vendor in this modal *is* the intended action.
function decorateVendorModalPicker(ddEl, opts) {
    if (!ddEl) return;
    const menu = ddEl.querySelector('.cfg-dropdown-menu');
    if (!menu) return;

    const optByValue = {};
    opts.forEach(o => { optByValue[o.value] = o; });

    menu.querySelectorAll('.cfg-dropdown-item').forEach(item => {
        const opt = optByValue[item.dataset.value];
        if (!opt) return;
        // Tag the row so the global active-row ✓ rule is suppressed in CSS
        // (otherwise configured AND selected rows would render two checks).
        item.classList.add('vendor-picker-item');
        if (opt._isAddNew) {
            // "Custom" is an add-new action (multiple entries allowed),
            // so show a trailing + instead of the configured ✓.
            const plus = document.createElement('i');
            plus.className = 'fas fa-plus vendor-picker-add-mark';
            item.appendChild(plus);
            return;
        }
        if (!opt._configured) return;
        const check = document.createElement('i');
        check.className = 'fas fa-check vendor-picker-configured-mark';
        item.appendChild(check);
    });
}

function rebuildCapabilityModelDropdown(def, providerId, selectedModel, scope) {
    // `scope` lets the caller (renderCapabilityBody) target a still-detached
    // subtree. After the card is mounted, callers may pass `document` instead.
    const root = scope || document;
    const el = root.querySelector(`#cap-${def.id}-model`);
    if (!el) return;

    // Prefer the capability-scoped model list when the backend provides one
    // (vision / image). It reflects the models the runtime can actually
    // dispatch to for this capability, instead of the vendor's full chat-
    // model catalog. Fall back to the generic provider.models for chat /
    // embedding / tts where any vendor model is fair game.
    //
    // Entries may be plain strings or {value, hint} objects (image catalog
    // uses the latter to surface brand aliases like "Nano Banana 2" next to
    // the technical Gemini model id). We normalize to {value, label, hint}
    // before handing off to initDropdown.
    const cap = modelsState.capabilities[def.id] || {};
    const capModelMap = cap.provider_models || {};
    let rawList;
    if (capModelMap[providerId]) {
        rawList = capModelMap[providerId].slice();
    } else if (providerId.startsWith('custom:') && capModelMap['custom']) {
        // Expanded custom:<id> entries share the same preset model list
        rawList = capModelMap['custom'].slice();
    } else {
        const provider = modelsState.providers.find(p => p.id === providerId);
        rawList = (provider && provider.models) ? provider.models.slice() : [];
    }
    const modelValues = [];
    const opts = rawList.map(entry => {
        if (typeof entry === 'string') {
            modelValues.push(entry);
            return { value: entry, label: entry };
        }
        modelValues.push(entry.value);
        return { value: entry.value, label: entry.label || entry.value, hint: entry.hint || '' };
    });
    opts.push({ value: '__custom__', label: currentLang === 'zh' ? '自定义' : 'Custom' });

    let initialValue = selectedModel || '';
    if (initialValue && !modelValues.includes(initialValue)) {
        initialValue = '__custom__';
    }
    if (!initialValue && opts.length) initialValue = opts[0].value;

    initDropdown(el, opts, initialValue, (value) => {
        const customWrap = document.getElementById(`cap-${def.id}-model-custom-wrap`);
        if (customWrap) {
            if (value === '__custom__') {
                customWrap.classList.remove('hidden');
                const input = document.getElementById(`cap-${def.id}-model-custom`);
                if (input && !input.value) input.value = selectedModel || '';
            } else {
                customWrap.classList.add('hidden');
            }
        }
        // TTS voice catalog may be scoped per engine model (aggregating
        // gateways). Rebuild the voice picker whenever the model changes.
        if (def.id === 'tts') {
            const provDd = document.getElementById('cap-tts-provider');
            const provId = provDd ? getDropdownValue(provDd) : '';
            rebuildCapabilityVoiceDropdown(provId, '', null, value);
        }
    });

    const customWrap = root.querySelector(`#cap-${def.id}-model-custom-wrap`);
    if (customWrap) {
        if (initialValue === '__custom__') {
            customWrap.classList.remove('hidden');
            const input = root.querySelector(`#cap-${def.id}-model-custom`);
            if (input) input.value = selectedModel || '';
        } else {
            customWrap.classList.add('hidden');
        }
    }
}

// TTS-only: rebuild the voice timbre picker against the provider's
// curated voice list. Hidden when no provider is picked.
//
// Each voice entry may be:
//   - a bare string  (code = label)
//   - {value, label, hint?}   so we can show a friendly Chinese name
//     while persisting the raw API code that the runtime sends.
function rebuildCapabilityVoiceDropdown(providerId, selectedVoice, scope, modelId) {
    const root = scope || document;
    const wrap = root.querySelector(`#cap-tts-voice-wrap`);
    const el = root.querySelector(`#cap-tts-voice`);
    if (!wrap || !el) return;
    const cap = modelsState.capabilities.tts || {};
    const voicesByProvider = cap.provider_voices || {};
    let raw = (providerId && voicesByProvider[providerId]) || [];
    // Some providers (gateways) scope voices by engine model id.
    if (raw && !Array.isArray(raw) && typeof raw === 'object') {
        const activeModel = modelId
            || (root.querySelector(`#cap-tts-model`) ? getDropdownValue(root.querySelector(`#cap-tts-model`)) : '');
        raw = (activeModel && raw[activeModel]) || [];
    }
    const customProvider = String(providerId || '').startsWith('custom:');
    if ((!raw || raw.length === 0) && !customProvider) {
        wrap.classList.add('hidden');
        return;
    }
    if (!raw) raw = [];
    wrap.classList.remove('hidden');
    // Voice picker: friendly name on the left, raw API code as right-hand
    // hint. Persisted/sent value is always the raw code.
    const codes = [];
    const opts = raw.map(entry => {
        if (typeof entry === 'string') {
            codes.push(entry);
            return { value: entry, label: entry };
        }
        codes.push(entry.value);
        const code = entry.value;
        const desc = entry.hint || entry.label || code;
        return {
            value: code,
            label: desc,
            hint: desc === code ? '' : code,
        };
    });
    opts.push({ value: '__custom__', label: currentLang === 'zh' ? '自定义' : 'Custom' });

    // Off-catalog values route through the custom branch.
    let initial = selectedVoice || '';
    const isCustom = initial && !codes.includes(initial);
    if (isCustom) initial = '__custom__';
    if (!initial) initial = codes.length ? codes[0] : '__custom__';

    initDropdown(el, opts, initial, (value) => {
        const customWrap = root.querySelector(`#cap-tts-voice-custom-wrap`);
        if (!customWrap) return;
        if (value === '__custom__') {
            customWrap.classList.remove('hidden');
            const input = root.querySelector(`#cap-tts-voice-custom`);
            if (input && !input.value) input.value = isCustom ? selectedVoice : '';
        } else {
            customWrap.classList.add('hidden');
        }
    });

    const customWrap = root.querySelector(`#cap-tts-voice-custom-wrap`);
    if (customWrap) {
        if (initial === '__custom__') {
            customWrap.classList.remove('hidden');
            const input = root.querySelector(`#cap-tts-voice-custom`);
            if (input) input.value = isCustom ? selectedVoice : '';
        } else {
            customWrap.classList.add('hidden');
        }
    }
}

function onCapabilityProviderChange(def, providerId, scope) {
    if (def.needsModel) {
        // Embedding: hide model picker when no provider is selected.
        const showModel = def.id === 'embedding' ? providerId !== '' :
            !capabilityUsesAutoProvider(def.id, providerId);
        if (showModel) {
            rebuildCapabilityModelDropdown(def, providerId, '', scope);
        }
        setCapabilityModelPickerVisible(def, showModel, scope);
    }
    if (def.id === 'tts') {
        rebuildCapabilityVoiceDropdown(providerId, '', scope);
    }
    const body = scope || document.querySelector(`[data-cap-body="${def.id}"]`);
    if (body) {
        const cap = modelsState.capabilities[def.id] || {};
        renderCapabilityHints(def, cap, body, providerId);
    }
}

function getCapabilityModelValue(def) {
    if (!def.needsModel) return '';
    const dd = document.getElementById(`cap-${def.id}-model`);
    if (!dd) return '';
    const v = getDropdownValue(dd);
    if (v === '__custom__') {
        const input = document.getElementById(`cap-${def.id}-model-custom`);
        return input ? input.value.trim() : '';
    }
    return v || '';
}

function saveCapability(capId) {
    const def = MODELS_CAPABILITY_DEFS.find(d => d.id === capId);
    if (!def || !def.editable) return;
    // Search has its own form (strategy + provider, no model picker).
    if (capId === 'search') { saveSearchCapability(); return; }
    const provDd = document.getElementById(`cap-${capId}-provider`);
    const provider = provDd ? getDropdownValue(provDd) : '';
    const capState = modelsState.capabilities[capId] || {};
    const blockedVoiceProvider = (
        (capId === 'asr' || capId === 'tts')
        && !provider
        && (capState.invalid_configured_provider || capState.legacy_configured_provider)
    );
    if (blockedVoiceProvider) {
        showStatus(`cap-${capId}-status`, 'models_voice_provider_required', true);
        return;
    }
    // When the user is in auto mode (provider == ""), the model picker is
    // hidden and any value left in it is stale; persist an empty model so
    // the backend treats this as "fall back to the runtime chain".
    const isAuto = capabilityUsesAutoProvider(capId, provider);
    // Embedding without a provider similarly means "cleared" — don't leak
    // a stale model value into config.
    const model = (isAuto || (capId === 'embedding' && !provider)) ? '' : getCapabilityModelValue(def);
    // TTS carries an extra voice timbre (supports free-text custom ids).
    let voice = '';
    if (capId === 'tts' && !isAuto) {
        const voiceDd = document.getElementById(`cap-${capId}-voice`);
        voice = voiceDd ? getDropdownValue(voiceDd) : '';
        if (voice === '__custom__') {
            const input = document.getElementById(`cap-${capId}-voice-custom`);
            voice = input ? input.value.trim() : '';
        }
    }
    const extras = { voice };
    if (capId === 'chat') {
        extras.fallbacks = readChatFallbackRows();
    }

    // Embedding changes invalidate any pre-existing vector index because
    // dimensions / vendor differ. Gate the save behind a confirm, and on
    // success surface a dedicated info dialog telling the user how to
    // rebuild — both via the in-app custom dialog, not the native alert.
    if (capId === 'embedding') {
        const cap = modelsState.capabilities[capId] || {};
        const before = (cap.current_provider || '').trim();
        const after = (provider || '').trim();
        if (before !== after) {
            showConfirmDialog({
                title: t('models_embedding_change_title'),
                message: t('models_embedding_change_msg'),
                okText: t('save'),
                cancelText: t('cancel'),
                onConfirm: () => _persistCapability(capId, provider, model, () => {
                    showConfirmDialog({
                        title: t('models_embedding_saved_title'),
                        message: t('models_embedding_saved_msg'),
                        okText: t('models_embedding_saved_ok'),
                        hideCancel: true,
                        onConfirm: () => {
                            navigateTo('chat');
                            // Defer focus + value set: navigateTo may
                            // re-render the chat panel; setting value before
                            // the input is mounted would be lost.
                            setTimeout(() => {
                                const input = document.getElementById('chat-input');
                                if (!input) return;
                                input.value = '/memory rebuild-index';
                                input.focus();
                                // Trigger any input listeners (autosize, send-button enable, etc.)
                                input.dispatchEvent(new Event('input', { bubbles: true }));
                            }, 60);
                        },
                    });
                }),
            });
            return;
        }
    }
    _persistCapability(capId, provider, model, undefined, extras);
}

function _persistCapability(capId, provider, model, onAfterSuccess, extras) {
    const payload = { action: 'set_capability', capability: capId, provider_id: provider, model: model };
    if (extras && extras.voice !== undefined) payload.voice = extras.voice;
    if (extras && extras.fallbacks !== undefined) payload.fallbacks = extras.fallbacks;
    fetch('/api/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    }).then(r => r.json()).then(data => {
        if (data.status === 'success') {
            // Flash "Saved" before reload so the status survives the rebuild.
            showStatus(`cap-${capId}-status`, 'models_save_success', false);
            setTimeout(() => {
                loadModelsView({ preserveScroll: true });
                if (onAfterSuccess) onAfterSuccess();
            }, 400);
        } else {
            showStatus(`cap-${capId}-status`, 'models_save_failed', true);
        }
    }).catch(() => showStatus(`cap-${capId}-status`, 'models_save_failed', true));
}

// ---------- Vendor credential modal ------------------------------------

let vendorModalState = { providerId: '', onSaved: null };

function openVendorModal(providerId, onSaved) {
    vendorModalState = { providerId: providerId || '', onSaved: onSaved || null };

    const overlay = document.getElementById('vendor-modal-overlay');
    const titleEl = document.getElementById('vendor-modal-title');
    const subEl = document.getElementById('vendor-modal-subtitle');
    const pickerWrap = document.getElementById('vendor-modal-picker-wrap');
    const baseWrap = document.getElementById('vendor-modal-base-wrap');
    const baseInput = document.getElementById('vendor-modal-base');
    const baseHint = document.getElementById('vendor-modal-base-hint');
    const keyInput = document.getElementById('vendor-modal-key');
    const clearBtn = document.getElementById('vendor-modal-clear');

    // Reset any leftover status (e.g. previous "Saved" message)
    const statusEl = document.getElementById('vendor-modal-status');
    if (statusEl) {
        statusEl.textContent = '';
        statusEl.classList.add('opacity-0');
    }

    if (!providerId) {
        // Add flow — show provider picker, default to the first unconfigured one.
        // We render every configured vendor with a trailing green ✓ via the
        // dropdown decorator, mirroring the visual language used by the
        // capability provider dropdowns. The .active row already shows the
        // currently selected vendor via its own background highlight, so we
        // intentionally suppress the global active-row ✓ for this picker
        // (see CSS) — otherwise configured + selected rows would show two.
        // Expanded custom provider cards ("custom:<id>") are edited via their
        // dedicated modal, so they are excluded from this picker. Picking the
        // "custom" entry creates a *new* custom provider via that modal —
        // this is how multiple OpenAI-compatible endpoints are added.
        const builtinProviders = modelsState.providers.filter(p => !isCustomProviderCard(p));
        const pickerOpts = builtinProviders.map(p => ({
            value: p.id,
            label: localizedLabel(p.label),
            _configured: !!p.configured,
        }));
        // In multi-provider mode the backend replaces the bare "custom" card
        // with the expanded ones; re-add it here so the entry stays available.
        if (!pickerOpts.some(o => o.value === 'custom')) {
            pickerOpts.push({ value: 'custom', label: t('models_custom_vendor_label'), _configured: false });
        }
        // "Custom" always behaves as an add-new action (multiple entries
        // allowed), so it shows a + mark instead of the configured ✓.
        pickerOpts.forEach(o => { if (o.value === 'custom') { o._isAddNew = true; o._configured = false; } });
        const unconfigured = builtinProviders.filter(p => !p.configured);
        const defaultId = (unconfigured[0] && unconfigured[0].id) || (builtinProviders[0] && builtinProviders[0].id) || 'custom';
        pickerWrap.classList.remove('hidden');
        const pickerEl = document.getElementById('vendor-modal-picker');
        const onPick = (val) => {
            if (val === 'custom') {
                // "Custom" in the add flow always creates a new
                // OpenAI-compatible provider entry via the dedicated modal
                // (name + base + key), supporting multiple custom endpoints.
                closeVendorModal();
                openCustomProviderModal('');
                return;
            }
            fillVendorModalForProvider(val);
        };
        initDropdown(pickerEl, pickerOpts, defaultId, onPick);
        decorateVendorModalPicker(pickerEl, pickerOpts);
        onPick(defaultId);
    } else {
        pickerWrap.classList.add('hidden');
        fillVendorModalForProvider(providerId);
    }

    overlay.classList.remove('hidden');

    document.getElementById('vendor-modal-cancel').onclick = closeVendorModal;
    document.getElementById('vendor-modal-save').onclick = saveVendorModal;
    clearBtn.onclick = clearVendorModal;

    // Once the user edits the masked value, drop the "masked sentinel" dataset
    // so the save handler treats their input as a real new key. We compare on
    // the next tick because keydown fires before the new char lands in .value.
    keyInput.oninput = function () {
        if (keyInput.dataset.masked === '1' && keyInput.value !== keyInput.dataset.maskedVal) {
            keyInput.dataset.masked = '';
        }
    };

    function onOverlayClick(e) {
        if (e.target === overlay) {
            closeVendorModal();
            overlay.removeEventListener('click', onOverlayClick);
        }
    }
    overlay.addEventListener('click', onOverlayClick);
    keyInput.focus();
}

function fillVendorModalForProvider(providerId) {
    const meta = modelsState.providers.find(p => p.id === providerId);
    if (!meta) return;
    document.getElementById('vendor-modal-title').textContent = localizedLabel(meta.label);
    document.getElementById('vendor-modal-subtitle').textContent = meta.id;

    // ----- API Base -----
    // Always reflect the *current effective* base as the input value so the
    // user can see (and edit) what's in use today. Placeholder is reserved
    // strictly for the "not yet typed anything" state and shows the official
    // default — never mixed with the actual value.
    const baseWrap = document.getElementById('vendor-modal-base-wrap');
    const baseInput = document.getElementById('vendor-modal-base');
    const baseHint = document.getElementById('vendor-modal-base-hint');
    if (meta.api_base_field) {
        baseWrap.classList.remove('hidden');
        baseInput.placeholder = meta.api_base_default || meta.api_base_placeholder || '';
        baseInput.value = meta.api_base || '';
        baseHint.classList.add('hidden');
    } else {
        baseWrap.classList.add('hidden');
        baseInput.value = '';
    }

    // ----- API Key -----
    // For configured vendors, surface the masked key as the input *value* so
    // it shows up in the same dark text as a real entry — making "configured"
    // visually unambiguous. The masked form (e.g. "sk-r***zRU") is also a
    // sentinel: the save handler treats untouched masked input as "no change".
    const keyInput = document.getElementById('vendor-modal-key');
    if (meta.configured && meta.api_key_masked) {
        keyInput.value = meta.api_key_masked;
        keyInput.dataset.masked = '1';
        keyInput.dataset.maskedVal = meta.api_key_masked;
        keyInput.placeholder = '';
    } else {
        keyInput.value = '';
        keyInput.dataset.masked = '';
        keyInput.dataset.maskedVal = '';
        keyInput.placeholder = 'sk-...';
    }

    const clearBtn = document.getElementById('vendor-modal-clear');
    clearBtn.classList.toggle('hidden', !meta.configured);

    vendorModalState.providerId = providerId;
}

function closeVendorModal() {
    document.getElementById('vendor-modal-overlay').classList.add('hidden');
}

function saveVendorModal() {
    const providerId = vendorModalState.providerId;
    if (!providerId) return;
    const keyInput = document.getElementById('vendor-modal-key');
    const apiBase = document.getElementById('vendor-modal-base').value.trim();

    // Treat "input still equals the masked value we surfaced on open" as "no
    // change" — the backend uses missing/empty api_key to skip the field.
    let apiKey = keyInput.value.trim();
    const masked = keyInput.dataset.masked === '1';
    const maskedVal = keyInput.dataset.maskedVal || '';
    if (masked && apiKey === maskedVal) {
        apiKey = '';
    }

    if (!apiKey && !masked) {
        // First-time setup with no key entered → nudge the user.
        keyInput.focus();
        return;
    }

    const btn = document.getElementById('vendor-modal-save');
    btn.disabled = true;
    const payload = { action: 'set_provider', provider_id: providerId, api_base: apiBase };
    if (apiKey) payload.api_key = apiKey;
    fetch('/api/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    }).then(r => r.json()).then(data => {
        btn.disabled = false;
        if (data.status === 'success') {
            closeVendorModal();
            const onSaved = vendorModalState.onSaved;
            if (onSaved) {
                try { onSaved(providerId); } catch (e) { /* noop */ }
            } else {
                loadModelsView();
            }
        } else {
            showStatus('vendor-modal-status', 'models_save_failed', true);
        }
    }).catch(() => {
        btn.disabled = false;
        showStatus('vendor-modal-status', 'models_save_failed', true);
    });
}

function clearVendorModal() {
    const providerId = vendorModalState.providerId;
    if (!providerId) return;
    showConfirmDialog({
        title: t('models_clear_confirm_title'),
        message: t('models_clear_confirm_msg'),
        okText: t('models_clear_credential'),
        cancelText: t('cancel'),
        onConfirm: () => {
            fetch('/api/models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'delete_provider', provider_id: providerId }),
            }).then(r => r.json()).then(data => {
                if (data.status === 'success') {
                    closeVendorModal();
                    loadModelsView();
                } else {
                    showStatus('vendor-modal-status', 'models_clear_failed', true);
                }
            }).catch(() => showStatus('vendor-modal-status', 'models_clear_failed', true));
        }
    });
}

// =====================================================================
// Custom (OpenAI-compatible) provider modal — add / edit
// =====================================================================
// State for the dedicated custom-provider modal. `editId` is empty when
// adding and set to the provider id when editing.
let customProviderModalState = { editId: '' };

function openCustomProviderModal(providerId) {
    const editing = !!providerId;
    customProviderModalState = { editId: editing ? providerId : '' };

    const card = editing ? getCustomProviderCards().find(p => p.custom_id === providerId) : null;

    const overlay = document.getElementById('custom-provider-modal-overlay');
    if (!overlay) return;

    document.getElementById('custom-provider-modal-title').textContent =
        editing ? t('models_custom_edit_title') : t('models_custom_add_title');

    const nameInput = document.getElementById('custom-provider-name');
    const baseInput = document.getElementById('custom-provider-base');
    const keyInput = document.getElementById('custom-provider-key');

    nameInput.value = card ? (card.custom_name || '') : '';
    baseInput.value = card ? (card.api_base || '') : '';

    // Surface the masked key as the value for configured providers so the
    // "already set" state is unambiguous; an untouched masked value means
    // "keep the existing key" on save (mirrors the vendor modal contract).
    if (card && card.configured && card.api_key_masked) {
        keyInput.value = card.api_key_masked;
        keyInput.dataset.masked = '1';
        keyInput.dataset.maskedVal = card.api_key_masked;
    } else {
        keyInput.value = '';
        keyInput.dataset.masked = '';
        keyInput.dataset.maskedVal = '';
    }
    keyInput.oninput = function () {
        if (keyInput.dataset.masked === '1' && keyInput.value !== keyInput.dataset.maskedVal) {
            keyInput.dataset.masked = '';
        }
    };

    const statusEl = document.getElementById('custom-provider-modal-status');
    if (statusEl) { statusEl.textContent = ''; statusEl.classList.add('opacity-0'); }

    overlay.classList.remove('hidden');
    document.getElementById('custom-provider-modal-cancel').onclick = closeCustomProviderModal;
    document.getElementById('custom-provider-modal-save').onclick = saveCustomProviderModal;

    // Delete is only available when editing an existing provider.
    const deleteBtn = document.getElementById('custom-provider-modal-delete');
    if (deleteBtn) {
        deleteBtn.classList.toggle('hidden', !editing);
        deleteBtn.onclick = editing ? () => deleteCustomProvider(providerId) : null;
    }

    function onOverlayClick(e) {
        if (e.target === overlay) {
            closeCustomProviderModal();
            overlay.removeEventListener('click', onOverlayClick);
        }
    }
    overlay.addEventListener('click', onOverlayClick);
    nameInput.focus();
}

function closeCustomProviderModal() {
    const overlay = document.getElementById('custom-provider-modal-overlay');
    if (overlay) overlay.classList.add('hidden');
}

function saveCustomProviderModal() {
    const name = document.getElementById('custom-provider-name').value.trim();
    const apiBase = document.getElementById('custom-provider-base').value.trim();
    const keyInput = document.getElementById('custom-provider-key');

    if (!name) {
        showStatus('custom-provider-modal-status', 'models_custom_name_required', true);
        document.getElementById('custom-provider-name').focus();
        return;
    }
    const editing = !!customProviderModalState.editId;
    if (!editing && !apiBase) {
        showStatus('custom-provider-modal-status', 'models_custom_base_required', true);
        document.getElementById('custom-provider-base').focus();
        return;
    }

    // Untouched masked key => no change (omit from payload).
    let apiKey = keyInput.value.trim();
    if (keyInput.dataset.masked === '1' && apiKey === (keyInput.dataset.maskedVal || '')) {
        apiKey = '';
    }

    const payload = {
        action: 'set_custom_provider',
        name: name,
        api_base: apiBase,
    };
    if (apiKey) payload.api_key = apiKey;
    if (editing) payload.id = customProviderModalState.editId;

    const btn = document.getElementById('custom-provider-modal-save');
    btn.disabled = true;
    fetch('/api/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    }).then(r => r.json()).then(data => {
        btn.disabled = false;
        if (data.status === 'success') {
            closeCustomProviderModal();
            loadModelsView();
        } else {
            showStatus('custom-provider-modal-status', 'models_save_failed', true);
        }
    }).catch(() => {
        btn.disabled = false;
        showStatus('custom-provider-modal-status', 'models_save_failed', true);
    });
}

function deleteCustomProvider(providerId) {
    showConfirmDialog({
        title: t('models_custom_delete_confirm_title'),
        message: t('models_custom_delete_confirm_msg'),
        okText: t('models_custom_delete'),
        cancelText: t('cancel'),
        onConfirm: () => {
            fetch('/api/models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'delete_custom_provider', id: providerId }),
            }).then(r => r.json()).then(data => {
                if (data.status === 'success') {
                    closeCustomProviderModal();
                    loadModelsView();
                }
            }).catch(() => { /* noop */ });
        }
    });
}

// =====================================================================
// Channels View
// =====================================================================
let channelsData = [];

function loadChannelsView() {
    const container = document.getElementById('channels-content');
    container.innerHTML = `<div class="flex items-center gap-2 py-8 justify-center text-slate-400 dark:text-slate-500 text-sm">
        <i class="fas fa-spinner fa-spin text-xs"></i><span>Loading...</span></div>`;

    fetch('/api/channels').then(r => r.json()).then(data => {
        if (data.status !== 'success') return;
        channelsData = data.channels || [];
        renderActiveChannels();
    }).catch(() => {
        container.innerHTML = '<p class="text-sm text-red-400 py-8 text-center">Failed to load channels</p>';
    });
}

let groupsActiveSection = 'basic';
let groupsMemoryState = {
    selectedRoomId: '',
    loadedRoomId: '',
    activeTab: 'manual',
    loading: false,
    learningLoading: false,
    profileEvolutionLoading: false,
    memories: [],
    runs: [],
    profileEvolutionRuns: [],
    profileEvolutionStatus: null,
    summary: null,
    search: '',
    preview: null,
};
let groupsProfilesState = {
    loading: false,
    profiles: [],
    members: [],
    total: 0,
    query: '',
    roomFilter: '',
    loadedQuery: null,
    loadedRoomFilter: null,
    loadedMembersRoom: '',
    selectedSenderId: '',
};
let groupsEmotionState = {
    selectedRoomId: '',
    loadedRoomId: '',
    loading: false,
    state: null,
    lastDecision: {},
    worker: {},
};
let groupsFocusState = {
    selectedRoomId: '',
    loadedKey: '',
    loading: false,
    active: [],
    archive: [],
    search: '',
};
let groupsStyleState = {
    selectedRoomId: '',
    loadedRoomId: '',
    loading: false,
    active: [],
    candidates: [],
};
let groupsStickerState = {
    selectedRoomId: '',
    loadedKey: '',
    loading: false,
    listRequestId: 0,
    stickers: [],
    search: '',
    status: '',
    onlineQuery: '',
    onlineResults: [],
    configDraft: null,
    onlineLoading: false,
    descriptionStatus: null,
    descriptionStatusRoomId: '',
    descriptionStatusLoadingRoomId: '',
    descriptionStatusError: '',
    descriptionStatusErrorRoomId: '',
    descriptionStarting: false,
    editingStickerId: '',
    editingDescription: '',
    editingOriginalDescription: '',
    savingStickerId: '',
    editError: '',
};
let groupsStickerDescriptionPollTimer = null;
let groupsAdminState = {
    roomId: '',
    query: '',
    members: [],
    selectedSenderIds: new Set(),
    expandedPermissionIds: new Set(),
    loading: false,
    requestId: 0,
};
let groupsBlacklistState = {
    roomId: '',
    query: '',
    members: [],
    selectedSenderIds: new Set(),
    loading: false,
    requestId: 0,
};
let wechatGroupRoomsAutoRefreshTriggered = false;

function loadGroupsView() {
    const container = document.getElementById('groups-content');
    if (container) {
        container.innerHTML = `<div class="h-full flex items-center justify-center text-slate-400 dark:text-slate-500 text-sm">
            <i class="fas fa-spinner fa-spin text-xs mr-2"></i>${t('groups_loading')}</div>`;
    }
    fetch('/api/channels').then(r => r.json()).then(data => {
        if (data.status !== 'success') {
            showGroupsStatus('groups_load_failed', true);
            return;
        }
        channelsData = data.channels || [];
        renderGroupsView();
        maybeAutoRefreshWechatGroupRooms();
    }).catch(() => showGroupsStatus('groups_load_failed', true));
}

function getWechatGroupChannel() {
    return channelsData.find(item => item.name === 'wechat_group') || null;
}

function maybeAutoRefreshWechatGroupRooms() {
    if (wechatGroupRoomsAutoRefreshTriggered) return;
    const ch = getWechatGroupChannel();
    if (!ch) return;
    const loginStatus = String(ch.login_status || '').trim();
    const rooms = Array.isArray(ch.extra?.rooms) ? ch.extra.rooms : [];
    if (!['logged_in', 'connected'].includes(loginStatus)) return;
    if (rooms.length) return;
    wechatGroupRoomsAutoRefreshTriggered = true;
    refreshWechatGroupRooms({ silent: true });
}

function showGroupsStatus(keyOrText, isError) {
    const el = document.getElementById('groups-status');
    if (!el) return;
    const translated = translateGroupsStatusText(keyOrText);
    const hasTranslation = (I18N[currentLang] && I18N[currentLang][translated]) || I18N.en[translated];
    el.textContent = hasTranslation ? t(translated) : String(translated || '');
    el.classList.toggle('text-red-500', !!isError);
    el.classList.toggle('text-primary-500', !isError);
    el.classList.remove('opacity-0');
    el.classList.add('opacity-100');
    clearTimeout(el._timer);
    el._timer = setTimeout(() => {
        el.classList.add('opacity-0');
        el.classList.remove('opacity-100');
    }, 2500);
}

function translateGroupsStatusText(keyOrText) {
    const text = String(keyOrText || '').trim();
    if (!text) return '';
    if ((I18N[currentLang] && I18N[currentLang][text]) || I18N.en[text]) return text;
    const normalized = text.toLowerCase();
    if (normalized === 'room_id is required') return 'groups_error_room_required';
    if (normalized === 'sender_id is required') return 'groups_error_sender_required';
    if (normalized === 'summary load failed') return 'groups_error_summary_load_failed';
    if (normalized === 'memory load failed') return 'groups_error_memory_load_failed';
    if (normalized === 'runs load failed') return 'groups_error_runs_load_failed';
    if (normalized === 'save failed') return 'groups_error_save_failed';
    if (normalized === 'disable failed') return 'groups_error_disable_failed';
    if (normalized === 'preview failed') return 'groups_error_preview_failed';
    if (normalized === 'description must be between 1 and 200 characters') return 'groups_sticker_description_invalid';
    if (normalized === 'description must contain semantic content') return 'groups_sticker_description_semantic_required';
    if (normalized === 'sticker description changed; refresh and try again') return 'groups_sticker_description_changed';
    if (normalized === 'sticker_id is not found in this room') return 'groups_sticker_description_not_found';
    if (normalized === 'no processable sticker descriptions') return 'groups_sticker_description_no_processable';
    if (normalized === 'another sticker description job is already running') return 'groups_sticker_description_job_running';
    if (normalized === 'learning failed') return 'groups_error_learning_failed';
    if (normalized === 'approve failed') return 'groups_error_approve_failed';
    if (normalized === 'reject failed') return 'groups_error_reject_failed';
    if (normalized.includes('load failed')) return 'groups_load_failed';
    if (normalized.includes('refresh failed')) return 'groups_load_failed';
    if (normalized.includes('review failed')) return 'channels_save_error';
    if (normalized.includes('disable failed')) return 'groups_error_disable_failed';
    if (normalized.startsWith('unknown action')) return 'groups_error_unknown_action';
    return text;
}

function translateWechatGroupActivityLevel(level) {
    const key = `wechat_group_free_reply_level_${String(level || '').trim()}`;
    const translated = t(key);
    return translated === key ? String(level || '-') : translated;
}

function translateGroupsMemoryRunStatus(status) {
    const key = `groups_memory_auto_status_${String(status || '').trim()}`;
    const translated = t(key);
    return translated === key ? String(status || '') : translated;
}

function captureGroupsStickerConfigDraft() {
    if (groupsActiveSection !== 'sticker') return;
    if (!document.getElementById('groups-sticker-enabled')) return;
    groupsStickerState.configDraft = readGroupsStickerConfig(groupsStickerState.configDraft || {});
}

function getGroupsStickerConfigForRender(extra = {}) {
    return groupsStickerState.configDraft || extra.sticker || {};
}

function buildGroupsMobileSectionSelect() {
    const sections = [
        ['basic', 'groups_nav_basic'],
        ['rooms', 'groups_nav_rooms'],
        ['humanization', 'groups_nav_humanization'],
        ['free_reply', 'groups_nav_free_reply'],
        ['voice_interaction', 'groups_nav_voice_interaction'],
        ['focus', 'groups_nav_focus'],
        ['style', 'groups_nav_style'],
        ['emotion', 'groups_nav_emotion'],
        ['sticker', 'groups_nav_sticker'],
        ['image', 'groups_nav_image'],
        ['persona', 'groups_nav_persona'],
        ['memory', 'groups_nav_memory'],
        ['profiles', 'groups_nav_profiles'],
    ];
    const options = sections.map(([section, labelKey]) => (
        `<option value="${section}" ${groupsActiveSection === section ? 'selected' : ''}>${t(labelKey)}</option>`
    )).join('');
    return `<div class="md:hidden flex-shrink-0 border-b border-slate-200 dark:border-white/10 p-3">
        <select id="groups-section-select" onchange="switchGroupsSection(this.value)" aria-label="${t('groups_title')}"
            class="w-full min-h-11 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500">
            ${options}
        </select>
    </div>`;
}

function renderGroupsView() {
    const container = document.getElementById('groups-content');
    if (!container) return;
    captureGroupsStickerConfigDraft();
    const ch = getWechatGroupChannel();
    const extra = ch?.extra || {};
    container.innerHTML = `<div class="h-full min-h-0 flex flex-col md:flex-row rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#1A1A1A] overflow-hidden">
        ${buildGroupsMobileSectionSelect()}
        <aside class="hidden md:block w-56 flex-shrink-0 border-r border-slate-200 dark:border-white/10 p-3 space-y-1 overflow-y-auto">
            ${buildGroupsSectionButton('basic', 'fa-sliders', 'groups_nav_basic', 'groups_nav_basic_hint')}
            ${buildGroupsSectionButton('rooms', 'fa-comments', 'groups_nav_rooms', 'groups_nav_rooms_hint')}
            ${buildGroupsSectionButton('humanization', 'fa-user-check', 'groups_nav_humanization', 'groups_nav_humanization_hint')}
            ${buildGroupsSectionButton('free_reply', 'fa-comment-dots', 'groups_nav_free_reply', 'groups_nav_free_reply_hint')}
            ${buildGroupsSectionButton('voice_interaction', 'fa-microphone-lines', 'groups_nav_voice_interaction', 'groups_nav_voice_interaction_hint')}
            ${buildGroupsSectionButton('focus', 'fa-list-check', 'groups_nav_focus', 'groups_nav_focus_hint')}
            ${buildGroupsSectionButton('style', 'fa-masks-theater', 'groups_nav_style', 'groups_nav_style_hint')}
            ${buildGroupsSectionButton('emotion', 'fa-heart-pulse', 'groups_nav_emotion', 'groups_nav_emotion_hint')}
            ${buildGroupsSectionButton('sticker', 'fa-face-laugh-squint', 'groups_nav_sticker', 'groups_nav_sticker_hint')}
            ${buildGroupsSectionButton('image', 'fa-image', 'groups_nav_image', 'groups_nav_image_hint')}
            ${buildGroupsSectionButton('persona', 'fa-user-pen', 'groups_nav_persona', 'groups_nav_persona_hint')}
            ${buildGroupsSectionButton('memory', 'fa-brain', 'groups_nav_memory', 'groups_nav_memory_hint')}
            ${buildGroupsSectionButton('profiles', 'fa-id-card', 'groups_nav_profiles', 'groups_nav_profiles_hint')}
            <div class="pt-3 mt-3 border-t border-slate-200 dark:border-white/10">
                <div class="rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 px-3 py-2">
                    <div class="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-200">
                        <span class="h-2 w-2 rounded-full ${ch?.active ? 'bg-primary-400' : 'bg-slate-400'}"></span>
                        ${ch?.active ? t('channels_connected') : t('channels_empty')}
                    </div>
                    <p class="text-[11px] text-slate-400 dark:text-slate-500 mt-1 truncate">${escapeHtml(ch?.login_status || 'wechat_group')}</p>
                </div>
            </div>
        </aside>
        <main class="flex-1 min-w-0 min-h-0 overflow-y-auto p-3 md:p-5">
            ${groupsActiveSection === 'basic' ? buildGroupsBasicPanel(extra) : ''}
            ${groupsActiveSection === 'rooms' ? buildGroupsRoomsPanel(extra) : ''}
            ${groupsActiveSection === 'humanization' ? buildGroupsHumanizationPanel(extra) : ''}
            ${groupsActiveSection === 'free_reply' ? renderWechatGroupFreeReplySettings(extra) : ''}
            ${groupsActiveSection === 'voice_interaction' ? buildGroupsVoiceInteractionPanel(extra) : ''}
            ${groupsActiveSection === 'focus' ? buildGroupsFocusPanel(extra) : ''}
            ${groupsActiveSection === 'style' ? buildGroupsStylePanel(extra) : ''}
            ${groupsActiveSection === 'emotion' ? buildGroupsEmotionPanel(extra) : ''}
            ${groupsActiveSection === 'sticker' ? buildGroupsStickerPanel(extra) : ''}
            ${groupsActiveSection === 'image' ? buildGroupsImagePanel(extra) : ''}
            ${groupsActiveSection === 'persona' ? buildGroupsPersonaPanel(extra) : ''}
            ${groupsActiveSection === 'memory' ? buildGroupsMemoryPanel(extra) : ''}
            ${groupsActiveSection === 'profiles' ? buildGroupsProfilesPanel(extra) : ''}
        </main>
    </div>`;
    if (groupsActiveSection === 'memory') {
        ensureGroupsMemoryLoaded(extra);
    }
    if (groupsActiveSection === 'profiles') {
        ensureGroupsProfilesLoaded(extra);
    }
    if (groupsActiveSection === 'free_reply') {
        syncFreeReplyProfileFields(extra.free_reply || {});
    }
    if (groupsActiveSection === 'focus') {
        ensureGroupsFocusLoaded(extra);
    }
    if (groupsActiveSection === 'style') {
        ensureGroupsStyleLoaded(extra);
    }
    if (groupsActiveSection === 'emotion') {
        ensureGroupsEmotionLoaded(extra);
    }
    if (groupsActiveSection === 'sticker') {
        ensureGroupsStickerLoaded(extra);
    }
}

function buildGroupsSectionButton(section, icon, labelKey, hintKey) {
    const active = groupsActiveSection === section;
    return `<button type="button" onclick="switchGroupsSection('${section}')"
        class="w-full text-left rounded-lg px-3 py-2.5 cursor-pointer transition-colors ${active ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-300' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5'}">
        <span class="flex items-center gap-2 text-sm font-medium"><i class="fas ${icon} text-xs w-4"></i>${t(labelKey)}</span>
        <span class="block text-xs text-slate-400 dark:text-slate-500 mt-1 truncate">${t(hintKey)}</span>
    </button>`;
}

function switchGroupsSection(section) {
    if (section !== 'sticker') {
        groupsStickerState.configDraft = null;
    }
    groupsActiveSection = section;
    renderGroupsView();
}

function buildGroupsPanelTitle(icon, titleKey, descKey) {
    return `<div class="flex items-start gap-3 mb-5">
        <span class="w-9 h-9 rounded-lg bg-primary-50 dark:bg-primary-900/20 text-primary-500 flex items-center justify-center flex-shrink-0">
            <i class="fas ${icon} text-sm"></i>
        </span>
        <div class="min-w-0">
            <h3 class="text-base font-semibold text-slate-800 dark:text-slate-100">${t(titleKey)}</h3>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t(descKey)}</p>
        </div>
    </div>`;
}

function buildGroupsBasicPanel(extra) {
    const basic = extra.basic || {};
    const aliasSyncCooldownMinutes = Number(basic.alias_sync_cooldown_minutes || 1);
    const proxy = String(basic.proxy || '');
    return `<div class="h-full w-full">
        ${buildGroupsPanelTitle('fa-sliders', 'groups_basic_title', 'groups_basic_desc')}
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
            ${buildGroupsNumberField('groups-alias-sync-cooldown-minutes', 'groups_alias_sync_cooldown_minutes', 'groups_alias_sync_cooldown_minutes_hint', aliasSyncCooldownMinutes)}
            ${buildGroupsTextField('groups-basic-proxy', 'groups_basic_proxy', 'groups_basic_proxy_hint', proxy, 'http://127.0.0.1:7890')}
        </div>
        ${buildGroupsGithubCommitNotifyPanel(extra)}
    </div>`;
}

function buildGroupsGithubCommitNotifyPanel(extra) {
    const saved = extra.github_commit_notify || {};
    const branches = Array.isArray(saved.branches) ? saved.branches.join(', ') : '';
    const selectedTarget = String(saved.stable_room_id || '').trim();
    const targetRoomOptions = buildGroupsGithubTargetRoomOptions(extra, selectedTarget);
    const environmentManaged = saved.secret_source === 'environment';
    const secretStatusKey = environmentManaged
        ? 'groups_github_secret_from_environment'
        : saved.secret_configured ? 'groups_github_secret_from_config' : 'groups_github_secret_not_configured';
    const secretPlaceholder = saved.secret_configured
        ? String(saved.secret_masked || '********')
        : t('groups_github_secret_placeholder');
    const webhookPath = String(saved.webhook_path || '/api/github/webhook');
    let webhookUrl = webhookPath;
    try {
        webhookUrl = new URL(webhookPath, window.location.origin).toString();
    } catch (_) {
        webhookUrl = webhookPath;
    }
    return `<section class="mt-8 pt-6 border-t border-slate-200 dark:border-white/10" aria-labelledby="groups-github-notify-title">
        <div class="flex items-start gap-3 mb-5">
            <span class="w-9 h-9 rounded-lg bg-slate-100 dark:bg-white/10 text-slate-700 dark:text-slate-200 flex items-center justify-center flex-shrink-0" aria-hidden="true">
                <i class="fab fa-github text-base"></i>
            </span>
            <div class="min-w-0">
                <h4 id="groups-github-notify-title" class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_github_notify_title')}</h4>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_github_notify_desc')}</p>
            </div>
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
            ${buildGroupsHumanizationToggle('groups-github-notify-enabled', 'groups_github_notify_enabled', 'groups_github_notify_enabled_hint', saved.enabled === true)}
            ${buildGroupsTextField('groups-github-repository', 'groups_github_repository', 'groups_github_repository_hint', saved.repository || '', 'owner/repository')}
            ${buildGroupsTextField('groups-github-branches', 'groups_github_branches', 'groups_github_branches_hint', branches, 'main, develop')}
            <label class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 block">
                <span class="text-sm font-medium text-slate-800 dark:text-slate-100">${t('groups_github_target_room')}</span>
                <span id="groups-github-target-room-hint" class="block text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_github_target_room_hint')}</span>
                <select id="groups-github-target-room" aria-describedby="groups-github-target-room-hint" ${targetRoomOptions.disabled ? 'disabled' : ''}
                    class="mt-3 w-full min-h-10 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    ${targetRoomOptions.html}
                </select>
            </label>
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
            ${buildGroupsNumberField('groups-github-max-commits', 'groups_github_max_commits', 'groups_github_max_commits_hint', saved.max_commits ?? 8, 1, 20)}
            ${buildGroupsNumberField('groups-github-retry-hours', 'groups_github_retry_hours', 'groups_github_retry_hours_hint', saved.retry_hours ?? 72, 1, 720)}
            ${buildGroupsNumberField('groups-github-retention-days', 'groups_github_retention_days', 'groups_github_retention_days_hint', saved.delivery_retention_days ?? 30, 1, 365)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4">
            <label class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 block">
                <span class="text-sm font-medium text-slate-800 dark:text-slate-100">${t('groups_github_webhook_url')}</span>
                <span id="groups-github-webhook-url-hint" class="block text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_github_webhook_url_hint')}</span>
                <input id="groups-github-webhook-url" type="url" readonly aria-readonly="true" aria-describedby="groups-github-webhook-url-hint"
                    value="${escapeHtml(webhookUrl)}" class="mt-3 w-full min-h-10 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-slate-100 dark:bg-white/5 text-sm font-mono text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-primary-500/20 break-all">
            </label>
            <label class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 block">
                <span class="text-sm font-medium text-slate-800 dark:text-slate-100">${t('groups_github_secret')}</span>
                <span id="groups-github-secret-hint" class="block text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_github_secret_hint')}</span>
                <span class="relative mt-3 block">
                    <input id="groups-github-webhook-secret" type="password" value="" placeholder="${escapeHtml(secretPlaceholder)}"
                        autocomplete="new-password" spellcheck="false" aria-describedby="groups-github-secret-hint groups-github-secret-status" ${environmentManaged ? 'disabled' : ''}
                        class="w-full min-h-10 pl-3 pr-12 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    <button id="groups-github-secret-toggle" type="button" onclick="toggleGroupsGithubSecretVisibility()" ${environmentManaged ? 'disabled' : ''}
                        class="absolute inset-y-0 right-0 w-11 inline-flex items-center justify-center text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary-500 rounded-r-lg disabled:opacity-40 disabled:cursor-not-allowed"
                        title="${escapeHtml(t('groups_github_secret_show'))}" aria-label="${escapeHtml(t('groups_github_secret_show'))}">
                        <i class="fas fa-eye" aria-hidden="true"></i>
                    </button>
                </span>
                <span id="groups-github-secret-status" class="block text-xs ${saved.secret_configured ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-700 dark:text-amber-400'} mt-2">${t(secretStatusKey)}</span>
            </label>
        </div>
    </section>`;
}

function buildGroupsGithubTargetRoomOptions(extra, selectedTarget) {
    const stableSelectedIds = Array.isArray(extra.stable_selected_room_ids)
        ? extra.stable_selected_room_ids.map(value => String(value || '').trim()).filter(value => value.startsWith('wgr_'))
        : [];
    const fallbackSelectedIds = Array.isArray(extra.selected_room_ids)
        ? extra.selected_room_ids.map(value => String(value || '').trim()).filter(value => value.startsWith('wgr_'))
        : [];
    const selectedIds = stableSelectedIds.length ? stableSelectedIds : fallbackSelectedIds;
    const roomNameById = new Map();
    (extra.rooms || []).forEach(room => {
        const name = String(room.name || room.topic || '').trim();
        [room.stable_room_id, room.id].forEach(value => {
            const roomId = String(value || '').trim();
            if (roomId.startsWith('wgr_') && name) roomNameById.set(roomId, name);
        });
    });
    selectedIds.forEach((roomId, index) => {
        const savedName = String(extra.selected_room_names?.[index] || '').trim();
        if (savedName && !roomNameById.has(roomId)) roomNameById.set(roomId, savedName);
    });
    const uniqueIds = [...new Set(selectedIds)];
    const savedTargetMissing = selectedTarget.startsWith('wgr_') && !uniqueIds.includes(selectedTarget);
    if (savedTargetMissing) uniqueIds.push(selectedTarget);
    if (!uniqueIds.length) {
        return {
            disabled: true,
            html: `<option value="" selected>${t('groups_github_target_room_empty')}</option>`,
        };
    }
    const placeholder = `<option value="" ${selectedTarget ? '' : 'selected'}>${t('groups_github_target_room_placeholder')}</option>`;
    const options = uniqueIds.map(roomId => {
        const suffix = savedTargetMissing && roomId === selectedTarget ? ` (${t('groups_github_target_room_saved')})` : '';
        const label = `${roomNameById.get(roomId) || roomId}${suffix}`;
        return `<option value="${escapeHtml(roomId)}" ${roomId === selectedTarget ? 'selected' : ''}>${escapeHtml(label)}</option>`;
    }).join('');
    return { disabled: false, html: placeholder + options };
}

function toggleGroupsGithubSecretVisibility() {
    const input = document.getElementById('groups-github-webhook-secret');
    const button = document.getElementById('groups-github-secret-toggle');
    if (!input || !button || input.disabled) return;
    const showSecret = input.type === 'password';
    input.type = showSecret ? 'text' : 'password';
    const label = t(showSecret ? 'groups_github_secret_hide' : 'groups_github_secret_show');
    button.title = label;
    button.setAttribute('aria-label', label);
    const icon = button.querySelector('i');
    if (icon) icon.className = `fas ${showSecret ? 'fa-eye-slash' : 'fa-eye'}`;
    input.focus();
}

function readGroupsGithubCommitNotifySettings(saved = {}) {
    const branchesInput = document.getElementById('groups-github-branches');
    const branches = branchesInput
        ? [...new Set(String(branchesInput.value || '').split(/[\r\n,]+/).map(value => value.trim()).filter(Boolean))]
        : (Array.isArray(saved.branches) ? saved.branches : []);
    const settings = {
        enabled: document.getElementById('groups-github-notify-enabled')
            ? !!document.getElementById('groups-github-notify-enabled').checked
            : saved.enabled === true,
        repository: document.getElementById('groups-github-repository')
            ? String(document.getElementById('groups-github-repository').value || '').trim()
            : String(saved.repository || '').trim(),
        branches,
        stable_room_id: document.getElementById('groups-github-target-room')
            ? String(document.getElementById('groups-github-target-room').value || '').trim()
            : String(saved.stable_room_id || '').trim(),
        max_commits: clampNumber(document.getElementById('groups-github-max-commits')?.value, 1, 20, saved.max_commits ?? 8),
        retry_hours: clampNumber(document.getElementById('groups-github-retry-hours')?.value, 1, 720, saved.retry_hours ?? 72),
        delivery_retention_days: clampNumber(document.getElementById('groups-github-retention-days')?.value, 1, 365, saved.delivery_retention_days ?? 30),
    };
    const secretInput = document.getElementById('groups-github-webhook-secret');
    if (secretInput && !secretInput.disabled && secretInput.value) {
        settings.webhook_secret = secretInput.value;
    }
    return settings;
}

function buildGroupsVoiceInteractionPanel(extra) {
    const saved = extra.voice_interaction || {};
    const mode = readWechatGroupVoiceInteractionMode(saved);
    const options = [
        {
            value: 'force_reply',
            label: 'groups_voice_interaction_force_reply',
            hint: 'groups_voice_interaction_force_reply_hint',
        },
        {
            value: 'free_reply',
            label: 'groups_voice_interaction_free_reply',
            hint: 'groups_voice_interaction_free_reply_hint',
        },
    ];
    return `<div class="h-full w-full">
        ${buildGroupsPanelTitle('fa-microphone-lines', 'groups_voice_interaction_title', 'groups_voice_interaction_desc')}
        <fieldset>
            <legend class="sr-only">${t('groups_voice_interaction_title')}</legend>
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-3">
                ${options.map(option => `<label class="flex items-start gap-3 rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 cursor-pointer hover:border-primary-300 dark:hover:border-primary-500 transition-colors">
                    <input type="radio" name="groups-voice-interaction-mode" value="${option.value}"
                        class="mt-0.5 h-4 w-4 accent-primary-500 flex-shrink-0" ${mode === option.value ? 'checked' : ''}>
                    <span class="min-w-0">
                        <span class="block text-sm font-medium text-slate-800 dark:text-slate-100">${t(option.label)}</span>
                        <span class="block text-xs text-slate-500 dark:text-slate-400 mt-1">${t(option.hint)}</span>
                    </span>
                </label>`).join('')}
            </div>
        </fieldset>
    </div>`;
}

function readWechatGroupVoiceInteractionMode(saved = {}) {
    const selected = document.querySelector('input[name="groups-voice-interaction-mode"]:checked');
    const mode = String(selected?.value || saved.mode || 'force_reply').trim().toLowerCase();
    return mode === 'free_reply' ? 'free_reply' : 'force_reply';
}

function buildGroupsHumanizationPanel(extra) {
    const humanization = extra.humanization || {};
    const recent = extra.recent_context || {};
    const settings = readWechatGroupHumanizationSettings(humanization, recent);
    return `<div class="h-full w-full">
        ${buildGroupsPanelTitle('fa-user-check', 'groups_humanization_title', 'groups_humanization_desc')}
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
            ${buildGroupsHumanizationToggle('groups-humanization-enabled', 'groups_humanization_enabled', 'groups_humanization_enabled_hint', settings.enabled)}
            ${buildGroupsHumanizationToggle('groups-humanization-persist-raw-user-only', 'groups_humanization_persist_raw_user_only', 'groups_humanization_persist_raw_user_only_hint', settings.persist_raw_user_only)}
            ${buildGroupsHumanizationToggle('groups-humanization-reply-policy-enabled', 'groups_humanization_reply_policy_enabled', 'groups_humanization_reply_policy_enabled_hint', settings.reply_policy_enabled)}
            ${buildGroupsHumanizationToggle('groups-humanization-recent-enabled', 'groups_humanization_recent_enabled', 'groups_humanization_recent_enabled_hint', settings.recent_enabled)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
            ${buildGroupsNumberField('groups-humanization-recent-limit', 'groups_humanization_recent_limit', 'groups_recent_limit_hint', settings.recent_limit)}
            ${buildGroupsNumberField('groups-humanization-recent-minutes', 'groups_humanization_recent_minutes', 'groups_recent_minutes_hint', settings.recent_minutes)}
            ${buildGroupsNumberField('groups-humanization-archive-evidence-limit', 'groups_humanization_archive_evidence_limit', 'groups_recent_limit_hint', settings.archive_evidence_limit)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4 mt-4">
            ${buildGroupsHumanizationToggle('groups-humanization-archive-evidence-enabled', 'groups_humanization_archive_evidence_enabled', 'groups_humanization_archive_evidence_enabled', settings.archive_evidence_enabled)}
            ${buildGroupsHumanizationToggle('groups-humanization-local-summary-enabled', 'groups_humanization_local_summary_enabled', 'groups_humanization_local_summary_enabled', settings.local_summary_enabled)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
            ${buildGroupsNumberField('groups-humanization-archive-evidence-days', 'groups_humanization_archive_evidence_days', 'groups_humanization_archive_evidence_days', settings.archive_evidence_days)}
            ${buildGroupsNumberField('groups-humanization-archive-evidence-recent-limit', 'groups_humanization_archive_evidence_recent_limit', 'groups_humanization_archive_evidence_recent_limit', settings.archive_evidence_recent_limit)}
            ${buildGroupsNumberField('groups-humanization-local-summary-limit', 'groups_humanization_local_summary_limit', 'groups_humanization_local_summary_limit', settings.local_summary_limit)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
            ${buildGroupsNumberField('groups-humanization-local-summary-hours', 'groups_humanization_local_summary_hours', 'groups_humanization_local_summary_hours', settings.local_summary_hours)}
            ${buildGroupsNumberField('groups-humanization-response-cleanup-max-chars', 'groups_humanization_response_cleanup_max_chars', 'groups_humanization_response_cleanup_max_chars', settings.response_cleanup_max_chars)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
            ${buildGroupsHumanizationToggle('groups-humanization-reference-policy-enabled', 'groups_humanization_reference_policy_enabled', 'groups_humanization_reference_policy_enabled', settings.reference_policy_enabled)}
            ${buildGroupsHumanizationToggle('groups-humanization-link-policy-enabled', 'groups_humanization_link_policy_enabled', 'groups_humanization_link_policy_enabled', settings.link_policy_enabled)}
            ${buildGroupsHumanizationToggle('groups-humanization-response-cleanup-enabled', 'groups_humanization_response_cleanup_enabled', 'groups_humanization_response_cleanup_enabled', settings.response_cleanup_enabled)}
        </div>
    </div>`;
}

function readWechatGroupHumanizationSettings(saved = {}, recentCompat = {}) {
    const boolValue = (id, fallback) => document.getElementById(id) ? !!document.getElementById(id).checked : fallback;
    const numberValue = (id, fallback, min = 1) => {
        const el = document.getElementById(id);
        const value = el ? Number(el.value || fallback) : Number(fallback);
        return Math.max(min, Number.isFinite(value) ? value : Number(fallback));
    };
    const recentSource = {
        enabled: saved.recent_enabled ?? recentCompat.enabled ?? true,
        limit: saved.recent_limit ?? recentCompat.limit ?? 100,
        minutes: saved.recent_minutes ?? recentCompat.minutes ?? 1440,
    };
    return {
        enabled: boolValue('groups-humanization-enabled', saved.enabled !== false),
        persist_raw_user_only: boolValue('groups-humanization-persist-raw-user-only', saved.persist_raw_user_only !== false),
        reply_policy_enabled: boolValue('groups-humanization-reply-policy-enabled', saved.reply_policy_enabled !== false),
        recent_enabled: boolValue('groups-humanization-recent-enabled', recentSource.enabled !== false),
        recent_limit: numberValue('groups-humanization-recent-limit', Number(recentSource.limit || 100)),
        recent_minutes: numberValue('groups-humanization-recent-minutes', Number(recentSource.minutes || 1440)),
        archive_evidence_enabled: boolValue('groups-humanization-archive-evidence-enabled', saved.archive_evidence_enabled !== false),
        archive_evidence_limit: numberValue('groups-humanization-archive-evidence-limit', Number(saved.archive_evidence_limit || 48)),
        archive_evidence_days: numberValue('groups-humanization-archive-evidence-days', Number(saved.archive_evidence_days || 90)),
        archive_evidence_recent_limit: numberValue('groups-humanization-archive-evidence-recent-limit', Number(saved.archive_evidence_recent_limit ?? 16), 0),
        local_summary_enabled: boolValue('groups-humanization-local-summary-enabled', saved.local_summary_enabled !== false),
        local_summary_limit: numberValue('groups-humanization-local-summary-limit', Number(saved.local_summary_limit || 100)),
        local_summary_hours: numberValue('groups-humanization-local-summary-hours', Number(saved.local_summary_hours || 24)),
        reference_policy_enabled: boolValue('groups-humanization-reference-policy-enabled', saved.reference_policy_enabled !== false),
        link_policy_enabled: boolValue('groups-humanization-link-policy-enabled', saved.link_policy_enabled !== false),
        response_cleanup_enabled: boolValue('groups-humanization-response-cleanup-enabled', saved.response_cleanup_enabled !== false),
        response_cleanup_max_chars: numberValue('groups-humanization-response-cleanup-max-chars', Number(saved.response_cleanup_max_chars || 800), 100),
    };
}

function buildGroupsHumanizationToggle(id, labelKey, hintKey, enabled) {
    return `<div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
        <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
                <h4 class="text-sm font-medium text-slate-800 dark:text-slate-100">${t(labelKey)}</h4>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t(hintKey)}</p>
            </div>
            <label class="relative inline-flex items-center justify-center w-11 h-11 cursor-pointer flex-shrink-0">
                <input id="${id}" type="checkbox" class="sr-only peer" aria-label="${escapeHtml(t(labelKey))}" ${enabled ? 'checked' : ''}>
                <div class="w-10 h-5 bg-slate-300 dark:bg-slate-600 rounded-full peer peer-checked:bg-primary-500 peer-focus-visible:ring-2 peer-focus-visible:ring-primary-500 peer-focus-visible:ring-offset-2 dark:peer-focus-visible:ring-offset-[#111111] after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:h-4 after:w-4 after:rounded-full after:transition-all peer-checked:after:translate-x-5"></div>
            </label>
        </div>
    </div>`;
}

function buildGroupsNumberField(id, labelKey, hintKey, value, min = 1, max = null) {
    const maxAttribute = max == null ? '' : `max="${Number(max)}"`;
    return `<label class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 flex flex-col">
        <span class="text-sm font-medium text-slate-800 dark:text-slate-100">${t(labelKey)}</span>
        <span class="block text-xs text-slate-500 dark:text-slate-400 mt-1">${t(hintKey)}</span>
        <span class="mt-auto pt-3">
            <input id="${id}" type="number" min="${Number(min)}" ${maxAttribute} value="${Number(value ?? min)}"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-colors">
        </span>
    </label>`;
}

function buildGroupsTextField(id, labelKey, hintKey, value, placeholder) {
    return `<label class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 block">
        <span class="text-sm font-medium text-slate-800 dark:text-slate-100">${t(labelKey)}</span>
        <span class="block text-xs text-slate-500 dark:text-slate-400 mt-1">${t(hintKey)}</span>
        <input id="${id}" type="text" value="${escapeHtml(String(value || ''))}" placeholder="${escapeHtml(String(placeholder || ''))}"
            class="mt-3 w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors">
    </label>`;
}

function buildGroupsImagePanel(extra) {
    const image = extra.image || {};
    const understandingEnabled = image.understanding_enabled !== false;
    const commentEnabled = image.comment_enabled !== false;
    const freeReplyUnderstandingEnabled = image.free_reply_understanding_enabled === true;
    const prompt = String(image.understanding_prompt || '');
    const cacheMinutes = Number(image.cache_minutes || 30);
    const createHourlyLimit = Number(image.create_hourly_limit ?? 5);
    const videoUnderstandingEnabled = image.video_understanding_enabled === true;
    const forwardPreviewEnabled = image.forward_preview_enabled !== false;
    const quoteContextEnabled = image.quote_context_enabled !== false;
    const multimodalContextEnabled = image.multimodal_context_enabled !== false;
    const multimodalImageContextEnabled = image.multimodal_image_understanding_context_enabled !== false;
    const multimodalFreeReplyImageContextEnabled = image.multimodal_free_reply_image_context_enabled === true;
    const multimodalSameSenderWindowSeconds = Number(image.multimodal_same_sender_window_seconds || 120);
    const multimodalUniqueImageWindowSeconds = Number(image.multimodal_unique_image_window_seconds || 120);
    const multimodalQuoteSenderWindowMinutes = Number(image.multimodal_quote_sender_window_minutes || 30);
    const multimodalMaxRecentMessages = Number(image.multimodal_max_recent_messages || 20);
    const generationProxyEnabled = image.generation_proxy_enabled === true;
    const generationProxyDomains = Array.isArray(image.generation_proxy_domains)
        ? image.generation_proxy_domains.join('\n')
        : String(image.generation_proxy_domains || 'assets.grok.com\n*.grok.com');
    return `<div class="h-full w-full space-y-4">
        ${buildGroupsPanelTitle('fa-image', 'groups_image_title', 'groups_image_desc')}
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
            ${buildGroupsImageToggle('groups-image-understanding-enabled', 'groups_image_understanding_enabled', 'groups_image_understanding_enabled_hint', understandingEnabled)}
            ${buildGroupsImageToggle('groups-image-comment-enabled', 'groups_image_comment_enabled', 'groups_image_comment_enabled_hint', commentEnabled)}
            ${buildGroupsImageToggle('groups-image-free-reply-understanding-enabled', 'groups_image_free_reply_understanding_enabled', 'groups_image_free_reply_understanding_enabled_hint', freeReplyUnderstandingEnabled)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
            ${buildGroupsImageToggle('groups-multimodal-context-enabled', 'groups_multimodal_context_enabled', 'groups_multimodal_context_enabled_hint', multimodalContextEnabled)}
            ${buildGroupsImageToggle('groups-multimodal-image-context-enabled', 'groups_multimodal_image_context_enabled', 'groups_multimodal_image_context_enabled_hint', multimodalImageContextEnabled)}
            ${buildGroupsImageToggle('groups-multimodal-free-reply-image-context-enabled', 'groups_multimodal_free_reply_image_context_enabled', 'groups_multimodal_free_reply_image_context_enabled_hint', multimodalFreeReplyImageContextEnabled)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
            ${buildGroupsImageToggle('groups-video-understanding-enabled', 'groups_video_understanding_enabled', 'groups_video_understanding_enabled_hint', videoUnderstandingEnabled)}
            ${buildGroupsImageToggle('groups-forward-preview-enabled', 'groups_forward_preview_enabled', 'groups_forward_preview_enabled_hint', forwardPreviewEnabled)}
            ${buildGroupsImageToggle('groups-quote-context-enabled', 'groups_quote_context_enabled', 'groups_quote_context_enabled_hint', quoteContextEnabled)}
        </div>
        <label class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 block">
            <span class="text-sm font-medium text-slate-800 dark:text-slate-100">${t('groups_image_prompt')}</span>
            <span class="block text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_image_prompt_hint')}</span>
            <textarea id="groups-image-understanding-prompt" rows="4"
                class="mt-3 w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors resize-y">${escapeHtml(prompt)}</textarea>
        </label>
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
            ${buildGroupsImageNumberField('groups-image-cache-minutes', 'groups_image_cache_minutes', 'groups_image_cache_minutes_hint', cacheMinutes, 1, 120)}
            ${buildGroupsImageNumberField('groups-image-create-hourly-limit', 'groups_image_create_hourly_limit', 'groups_image_create_hourly_limit_hint', createHourlyLimit, 0, 100)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-[minmax(240px,0.7fr)_minmax(320px,1.3fr)] gap-4">
            ${buildGroupsImageToggle('groups-image-generation-proxy-enabled', 'groups_image_generation_proxy_enabled', 'groups_image_generation_proxy_enabled_hint', generationProxyEnabled)}
            <label class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 block">
                <span class="text-sm font-medium text-slate-800 dark:text-slate-100">${t('groups_image_generation_proxy_domains')}</span>
                <span class="block text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_image_generation_proxy_domains_hint')}</span>
                <textarea id="groups-image-generation-proxy-domains" rows="3" placeholder="${escapeHtml(t('groups_image_generation_proxy_domains_placeholder'))}"
                    class="mt-3 w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors resize-y">${escapeHtml(generationProxyDomains)}</textarea>
            </label>
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-4 gap-4">
            ${buildGroupsImageNumberField('groups-multimodal-same-sender-window-seconds', 'groups_multimodal_same_sender_window_seconds', 'groups_multimodal_same_sender_window_seconds_hint', multimodalSameSenderWindowSeconds, 5, 600)}
            ${buildGroupsImageNumberField('groups-multimodal-unique-image-window-seconds', 'groups_multimodal_unique_image_window_seconds', 'groups_multimodal_unique_image_window_seconds_hint', multimodalUniqueImageWindowSeconds, 5, 600)}
            ${buildGroupsImageNumberField('groups-multimodal-quote-sender-window-minutes', 'groups_multimodal_quote_sender_window_minutes', 'groups_multimodal_quote_sender_window_minutes_hint', multimodalQuoteSenderWindowMinutes, 1, 120)}
            ${buildGroupsImageNumberField('groups-multimodal-max-recent-messages', 'groups_multimodal_max_recent_messages', 'groups_multimodal_max_recent_messages_hint', multimodalMaxRecentMessages, 1, 100)}
        </div>
    </div>`;
}

function buildGroupsImageToggle(id, labelKey, hintKey, checked) {
    return `<div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
        <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
                <h4 class="text-sm font-medium text-slate-800 dark:text-slate-100">${t(labelKey)}</h4>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t(hintKey)}</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer flex-shrink-0">
                <input id="${id}" type="checkbox" class="sr-only peer" ${checked ? 'checked' : ''}>
                <div class="w-10 h-5 bg-slate-300 dark:bg-slate-600 rounded-full peer peer-checked:bg-primary-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:h-4 after:w-4 after:rounded-full after:transition-all peer-checked:after:translate-x-5"></div>
            </label>
        </div>
    </div>`;
}

function buildGroupsImageNumberField(id, labelKey, hintKey, value, min, max) {
    return `<label class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 block">
        <span class="text-sm font-medium text-slate-800 dark:text-slate-100">${t(labelKey)}</span>
        <span class="block text-xs text-slate-500 dark:text-slate-400 mt-1">${t(hintKey)}</span>
        <input id="${id}" type="number" min="${min}" max="${max}" step="1" value="${Number(value)}"
            class="mt-3 w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors">
    </label>`;
}

function getGroupsManagedRooms(extra) {
    const selectedIds = Array.isArray(extra.selected_room_ids) ? extra.selected_room_ids : [];
    const selectedNames = Array.isArray(extra.selected_room_names) ? extra.selected_room_names : [];
    const rooms = Array.isArray(extra.rooms) ? extra.rooms : [];
    const roomNameMap = new Map(rooms.map(room => [String(room.id || ''), String(room.name || room.id || '')]));
    const resolved = selectedIds.map((roomId, idx) => ({
        id: String(roomId || ''),
        name: roomNameMap.get(String(roomId || '')) || selectedNames[idx] || String(roomId || ''),
    })).filter(item => item.id);
    if (resolved.length) return resolved;
    return rooms.map(room => ({
        id: String(room.id || ''),
        name: String(room.name || room.id || ''),
    })).filter(item => item.id);
}

function ensureGroupsFocusLoaded(extra) {
    const rooms = getGroupsManagedRooms(extra || {});
    if (!rooms.length) return;
    if (!groupsFocusState.selectedRoomId || !rooms.some(item => item.id === groupsFocusState.selectedRoomId)) {
        groupsFocusState.selectedRoomId = rooms[0].id;
        groupsFocusState.loadedKey = '';
        groupsFocusState.active = [];
        groupsFocusState.archive = [];
    }
    if (groupsFocusState.loading) return;
    const loadKey = `${groupsFocusState.selectedRoomId}|${groupsFocusState.search.trim()}`;
    if (groupsFocusState.loadedKey === loadKey) return;
    refreshGroupsFocusData(groupsFocusState.selectedRoomId);
}

function selectGroupsFocusRoom(roomId) {
    groupsFocusState.selectedRoomId = String(roomId || '');
    groupsFocusState.loadedKey = '';
    groupsFocusState.active = [];
    groupsFocusState.archive = [];
    renderGroupsView();
    if (groupsFocusState.selectedRoomId) {
        refreshGroupsFocusData(groupsFocusState.selectedRoomId);
    }
}

function applyGroupsFocusSearch() {
    groupsFocusState.search = (document.getElementById('groups-focus-search')?.value || '').trim();
    groupsFocusState.loadedKey = '';
    refreshGroupsFocusData(groupsFocusState.selectedRoomId);
}

function refreshGroupsFocusData(roomId) {
    const targetRoomId = String(roomId || groupsFocusState.selectedRoomId || '').trim();
    if (!targetRoomId) return;
    const query = groupsFocusState.search.trim();
    const loadKey = `${targetRoomId}|${query}`;
    groupsFocusState.loading = true;
    groupsFocusState.selectedRoomId = targetRoomId;
    renderGroupsView();
    const activeUrl = `/api/wechat-group/focus/active?stable_room_id=${encodeURIComponent(targetRoomId)}&room_id=${encodeURIComponent(targetRoomId)}&limit=10`;
    const archiveUrl = `/api/wechat-group/focus/archive?stable_room_id=${encodeURIComponent(targetRoomId)}&room_id=${encodeURIComponent(targetRoomId)}&limit=20&q=${encodeURIComponent(query)}`;
    Promise.all([fetch(activeUrl), fetch(archiveUrl)])
        .then(responses => Promise.all(responses.map(item => item.json())))
        .then(([activeData, archiveData]) => {
            if (activeData.status !== 'success') throw new Error(activeData.message || 'focus active load failed');
            if (archiveData.status !== 'success') throw new Error(archiveData.message || 'focus archive load failed');
            groupsFocusState.active = Array.isArray(activeData.focus) ? activeData.focus : [];
            groupsFocusState.archive = Array.isArray(archiveData.focus) ? archiveData.focus : [];
            groupsFocusState.loadedKey = loadKey;
        })
        .catch(err => {
            showGroupsStatus(err.message || 'groups_load_failed', true);
            groupsFocusState.active = [];
            groupsFocusState.archive = [];
            groupsFocusState.loadedKey = loadKey;
        })
        .finally(() => {
            groupsFocusState.loading = false;
            renderGroupsView();
        });
}

function refreshGroupsFocusSummary() {
    const roomId = String(groupsFocusState.selectedRoomId || '').trim();
    if (!roomId) {
        showGroupsStatus('groups_focus_empty', true);
        return;
    }
    fetch('/api/wechat-group/focus/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stable_room_id: roomId, room_id: roomId }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'focus refresh failed');
        showGroupsStatus('groups_focus_refresh_done', false);
        groupsFocusState.loadedKey = '';
        refreshGroupsFocusData(roomId);
    }).catch(err => showGroupsStatus(err.message || 'groups_load_failed', true));
}

function buildGroupsFocusPanel(extra) {
    const focus = extra.focus || {};
    const rooms = getGroupsManagedRooms(extra);
    const selectedRoomId = groupsFocusState.selectedRoomId || (rooms[0]?.id || '');
    const loading = groupsFocusState.loading;
    const roomOptions = rooms.length
        ? rooms.map(room => `<option value="${escapeHtml(room.id)}" ${room.id === selectedRoomId ? 'selected' : ''}>${escapeHtml(room.name || room.id)}</option>`).join('')
        : '';
    const summaryItems = [
        [t('groups_focus_enabled'), focus.enabled !== false ? t('groups_style_on') : t('groups_style_off')],
        [t('groups_focus_recent_message_limit'), Number(focus.recent_message_limit ?? 30)],
        [t('groups_focus_context_message_limit'), Number(focus.context_message_limit ?? 8)],
        [t('groups_focus_stack_depth'), Number(focus.stack_depth ?? 4)],
        [t('groups_focus_stale_rounds'), Number(focus.stale_rounds ?? 20)],
        [t('groups_focus_archive_recall_limit'), Number(focus.archive_recall_limit ?? 20)],
    ];
    const contentHtml = !rooms.length
        ? `<p class="text-sm text-slate-500 dark:text-slate-400">${t('groups_focus_empty')}</p>`
        : loading
            ? `<p class="text-sm text-slate-500 dark:text-slate-400"><i class="fas fa-spinner fa-spin mr-2"></i>${t('groups_focus_loading')}</p>`
            : `<div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
                    <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">${t('groups_focus_active_title')}</h4>
                    ${renderGroupsFocusCards(groupsFocusState.active, 'groups_focus_no_active')}
                </div>
                <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
                    <div class="flex items-center justify-between gap-3 mb-3">
                        <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_focus_archive_title')}</h4>
                        <span class="text-xs text-slate-400 dark:text-slate-500">${escapeHtml(String(groupsFocusState.archive.length))}</span>
                    </div>
                    ${renderGroupsFocusCards(groupsFocusState.archive, 'groups_focus_no_archive')}
                </div>
            </div>`;
    return `<div class="h-full w-full space-y-4">
        ${buildGroupsPanelTitle('fa-list-check', 'groups_focus_title', 'groups_focus_desc')}
        <div class="grid grid-cols-1 xl:grid-cols-[minmax(260px,0.85fr)_minmax(0,1.15fr)] gap-4">
            <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 space-y-3">
                <div>
                    <label class="block text-sm font-medium text-slate-800 dark:text-slate-100 mb-1.5">${t('groups_focus_room')}</label>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mb-2">${t('groups_focus_room_hint')}</p>
                    <select id="groups-focus-room" onchange="selectGroupsFocusRoom(this.value)"
                        class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                        ${roomOptions}
                    </select>
                </div>
                <label class="block">
                    <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_focus_archive_title')}</span>
                    <div class="flex gap-2">
                        <input id="groups-focus-search" type="text" value="${escapeHtml(groupsFocusState.search)}"
                            placeholder="${escapeHtml(t('groups_focus_search_placeholder'))}"
                            onkeydown="if(event.key==='Enter'){event.preventDefault();applyGroupsFocusSearch();}"
                            class="flex-1 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                        <button type="button" onclick="applyGroupsFocusSearch()"
                            class="px-3 py-2 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">${t('groups_focus_refresh')}</button>
                    </div>
                </label>
                <div class="flex flex-wrap gap-2">
                    <button type="button" onclick="refreshGroupsFocusSummary()"
                        class="px-3 py-1.5 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-xs font-medium cursor-pointer transition-colors">${t('groups_focus_refresh')}</button>
                </div>
                <div class="grid grid-cols-2 gap-2 text-xs">
                    ${summaryItems.map(([label, value]) => `
                        <div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] px-3 py-2">
                            <div class="text-slate-400 dark:text-slate-500">${escapeHtml(String(label))}</div>
                            <div class="mt-1 font-medium text-slate-700 dark:text-slate-200">${escapeHtml(String(value))}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="space-y-4">
                ${contentHtml}
            </div>
        </div>
    </div>`;
}

function renderGroupsFocusCards(focus, emptyKey) {
    const list = Array.isArray(focus) ? focus : [];
    if (!list.length) {
        return `<p class="text-xs text-slate-500 dark:text-slate-400">${t(emptyKey)}</p>`;
    }
    return `<div class="space-y-3">${list.map(item => renderGroupsFocusCard(item)).join('')}</div>`;
}

function renderGroupsFocusCard(focus) {
    const keywords = Array.isArray(focus?.topic) ? focus.topic : [];
    const participants = Array.isArray(focus?.participants) ? focus.participants : [];
    const conclusions = Array.isArray(focus?.conclusions) ? focus.conclusions : [];
    return `<div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
        <div class="flex items-center justify-between gap-3 mb-2">
            <div class="min-w-0">
                <div class="text-sm font-semibold text-slate-800 dark:text-slate-100 break-words">${escapeHtml(String(focus?.title || '-'))}</div>
                <div class="text-xs text-slate-400 dark:text-slate-500 mt-1">${escapeHtml(String(focus?.frame_id || ''))}</div>
            </div>
            <span class="inline-flex items-center rounded-full bg-slate-100 dark:bg-white/10 px-2 py-0.5 text-[11px] text-slate-600 dark:text-slate-300">${t('groups_focus_frame_message_count')}: ${escapeHtml(String(focus?.hit_count ?? 0))}</span>
        </div>
        <div class="space-y-1.5 text-sm text-slate-700 dark:text-slate-200 break-words">
            <div><span class="text-slate-500 dark:text-slate-400">${t('groups_focus_frame_summary')}:</span> ${escapeHtml(String(focus?.summary || '-'))}</div>
            <div><span class="text-slate-500 dark:text-slate-400">${t('groups_focus_frame_keywords')}:</span> ${renderGroupsFocusInlineList(keywords)}</div>
            <div><span class="text-slate-500 dark:text-slate-400">${t('groups_focus_frame_participants')}:</span> ${renderGroupsFocusInlineList(participants)}</div>
            <div><span class="text-slate-500 dark:text-slate-400">${t('groups_focus_frame_conclusions')}:</span> ${renderGroupsFocusInlineList(conclusions)}</div>
            <div><span class="text-slate-500 dark:text-slate-400">${t('groups_focus_frame_updated_at')}:</span> ${escapeHtml(formatGroupsEmotionTimestamp(focus?.last_seen_at))}</div>
        </div>
    </div>`;
}

function renderGroupsFocusInlineList(items) {
    const list = Array.isArray(items) ? items.filter(item => String(item || '').trim()) : [];
    if (!list.length) return '-';
    return list.map(item => `<span class="inline-block rounded bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-300 px-1.5 py-0.5 mr-1 mb-1">${escapeHtml(String(item))}</span>`).join('');
}

function ensureGroupsStyleLoaded(extra) {
    const rooms = getGroupsManagedRooms(extra || {});
    if (!rooms.length) return;
    if (!groupsStyleState.selectedRoomId || !rooms.some(item => item.id === groupsStyleState.selectedRoomId)) {
        groupsStyleState.selectedRoomId = rooms[0].id;
        groupsStyleState.loadedRoomId = '';
        groupsStyleState.active = [];
        groupsStyleState.candidates = [];
    }
    if (groupsStyleState.loading) return;
    if (groupsStyleState.loadedRoomId === groupsStyleState.selectedRoomId) return;
    refreshGroupsStyleData(groupsStyleState.selectedRoomId);
}

function selectGroupsStyleRoom(roomId) {
    groupsStyleState.selectedRoomId = String(roomId || '');
    groupsStyleState.loadedRoomId = '';
    groupsStyleState.active = [];
    groupsStyleState.candidates = [];
    renderGroupsView();
    if (groupsStyleState.selectedRoomId) {
        refreshGroupsStyleData(groupsStyleState.selectedRoomId);
    }
}

function refreshGroupsStyleData(roomId) {
    const targetRoomId = String(roomId || groupsStyleState.selectedRoomId || '').trim();
    if (!targetRoomId) return;
    groupsStyleState.loading = true;
    groupsStyleState.selectedRoomId = targetRoomId;
    renderGroupsView();
    const activeUrl = `/api/wechat-group/styles/active?stable_room_id=${encodeURIComponent(targetRoomId)}&room_id=${encodeURIComponent(targetRoomId)}&limit=20`;
    const candidatesUrl = `/api/wechat-group/styles/candidates?stable_room_id=${encodeURIComponent(targetRoomId)}&room_id=${encodeURIComponent(targetRoomId)}&limit=20`;
    Promise.all([fetch(activeUrl), fetch(candidatesUrl)])
        .then(responses => Promise.all(responses.map(item => item.json())))
        .then(([activeData, candidateData]) => {
            if (activeData.status !== 'success') throw new Error(activeData.message || 'style active load failed');
            if (candidateData.status !== 'success') throw new Error(candidateData.message || 'style candidates load failed');
            groupsStyleState.active = Array.isArray(activeData.cards) ? activeData.cards : [];
            groupsStyleState.candidates = Array.isArray(candidateData.cards) ? candidateData.cards : [];
            groupsStyleState.loadedRoomId = targetRoomId;
        })
        .catch(err => {
            showGroupsStatus(err.message || 'groups_load_failed', true);
            groupsStyleState.active = [];
            groupsStyleState.candidates = [];
            groupsStyleState.loadedRoomId = targetRoomId;
        })
        .finally(() => {
            groupsStyleState.loading = false;
            renderGroupsView();
        });
}

function reviewGroupsStyleCard(styleId, action) {
    const roomId = String(groupsStyleState.selectedRoomId || '').trim();
    const cardId = String(styleId || '').trim();
    if (!roomId || !cardId) {
        showGroupsStatus('groups_load_failed', true);
        return;
    }
    fetch('/api/wechat-group/styles/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            stable_room_id: roomId,
            room_id: roomId,
            style_id: cardId,
            action: action || 'approve',
        }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'style review failed');
        showGroupsStatus('groups_style_review_saved', false);
        groupsStyleState.loadedRoomId = '';
        refreshGroupsStyleData(roomId);
    }).catch(err => showGroupsStatus(err.message || 'groups_load_failed', true));
}

function buildGroupsStylePanel(extra) {
    const style = extra.style || {};
    const rooms = getGroupsManagedRooms(extra);
    const selectedRoomId = groupsStyleState.selectedRoomId || (rooms[0]?.id || '');
    const loading = groupsStyleState.loading;
    const roomOptions = rooms.length
        ? rooms.map(room => `<option value="${escapeHtml(room.id)}" ${room.id === selectedRoomId ? 'selected' : ''}>${escapeHtml(room.name || room.id)}</option>`).join('')
        : '';
    const summaryItems = [
        [t('groups_style_enabled'), style.enabled !== false ? t('groups_style_on') : t('groups_style_off')],
        [t('groups_style_learning_enabled'), style.learning_enabled !== false ? t('groups_style_on') : t('groups_style_off')],
        [t('groups_style_auto_apply_enabled'), style.auto_apply_enabled ? t('groups_style_on') : t('groups_style_off')],
        [t('groups_style_context_limit'), Number(style.context_limit ?? 3)],
        [t('groups_style_candidate_min_evidence'), Number(style.candidate_min_evidence ?? 2)],
        [t('groups_style_learning_batch_limit'), Number(style.learning_batch_limit ?? 100)],
    ];
    const contentHtml = !rooms.length
        ? `<p class="text-sm text-slate-500 dark:text-slate-400">${t('groups_style_empty')}</p>`
        : loading
            ? `<p class="text-sm text-slate-500 dark:text-slate-400"><i class="fas fa-spinner fa-spin mr-2"></i>${t('groups_style_loading')}</p>`
            : `<div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
                    <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">${t('groups_style_active_title')}</h4>
                    ${renderGroupsStyleCards(groupsStyleState.active, 'active')}
                </div>
                <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
                    <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">${t('groups_style_candidates_title')}</h4>
                    ${renderGroupsStyleCards(groupsStyleState.candidates, 'candidate')}
                </div>
            </div>`;
    return `<div class="h-full w-full space-y-4">
        ${buildGroupsPanelTitle('fa-masks-theater', 'groups_style_title', 'groups_style_desc')}
        <div class="grid grid-cols-1 xl:grid-cols-[minmax(260px,0.85fr)_minmax(0,1.15fr)] gap-4">
            <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 space-y-3">
                <div>
                    <label class="block text-sm font-medium text-slate-800 dark:text-slate-100 mb-1.5">${t('groups_style_room')}</label>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mb-2">${t('groups_style_room_hint')}</p>
                    <select id="groups-style-room" onchange="selectGroupsStyleRoom(this.value)"
                        class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                        ${roomOptions}
                    </select>
                </div>
                <div class="flex flex-wrap gap-2">
                    <button type="button" onclick="refreshGroupsStyleData()"
                        class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">${t('groups_style_refresh')}</button>
                </div>
                <div class="grid grid-cols-2 gap-2">
                    ${summaryItems.map(([label, value]) => buildGroupsEmotionMetric(label, value)).join('')}
                </div>
            </div>
            ${contentHtml}
        </div>
    </div>`;
}

function renderGroupsStyleCards(cards, mode) {
    const list = Array.isArray(cards) ? cards : [];
    if (!list.length) {
        const emptyKey = mode === 'active' ? 'groups_style_no_active' : 'groups_style_no_candidates';
        return `<p class="text-xs text-slate-500 dark:text-slate-400">${t(emptyKey)}</p>`;
    }
    return `<div class="space-y-3">${list.map(card => renderGroupsStyleCard(card, mode)).join('')}</div>`;
}

function renderGroupsStyleCard(card, mode) {
    const styleId = String(card?.style_id || '');
    const actions = mode === 'candidate'
        ? `<div class="flex flex-wrap gap-2 mt-3">
                <button type="button" onclick="reviewGroupsStyleCard('${escapeHtml(styleId)}', 'approve')"
                    class="px-3 py-1.5 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-xs font-medium cursor-pointer transition-colors">${t('groups_style_approve')}</button>
                <button type="button" onclick="reviewGroupsStyleCard('${escapeHtml(styleId)}', 'reject')"
                    class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">${t('groups_style_reject')}</button>
            </div>`
        : `<div class="flex flex-wrap gap-2 mt-3">
                <button type="button" onclick="reviewGroupsStyleCard('${escapeHtml(styleId)}', 'disable')"
                    class="px-3 py-1.5 rounded-lg border border-amber-200 dark:border-amber-900/30 text-xs text-amber-600 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/10 cursor-pointer transition-colors">${t('groups_style_disable')}</button>
            </div>`;
    return `<div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
        <div class="flex items-center justify-between gap-3 mb-2">
            <span class="text-xs font-medium text-slate-500 dark:text-slate-400">${escapeHtml(styleId || '-')}</span>
            <span class="inline-flex items-center rounded-full bg-slate-100 dark:bg-white/10 px-2 py-0.5 text-[11px] text-slate-600 dark:text-slate-300">${t('groups_style_evidence_count')}: ${escapeHtml(String(card?.evidence_count ?? 0))}</span>
        </div>
        <div class="space-y-1.5 text-sm text-slate-700 dark:text-slate-200 break-words">
            <div><span class="text-slate-500 dark:text-slate-400">${t('groups_style_intent')}:</span> ${escapeHtml(String(card?.intent || '-'))}</div>
            <div><span class="text-slate-500 dark:text-slate-400">${t('groups_style_tone')}:</span> ${escapeHtml(String(card?.tone || '-'))}</div>
            <div><span class="text-slate-500 dark:text-slate-400">${t('groups_style_trigger_rule')}:</span> ${escapeHtml(String(card?.trigger_rule || '-'))}</div>
            <div><span class="text-slate-500 dark:text-slate-400">${t('groups_style_avoid_rule')}:</span> ${escapeHtml(String(card?.avoid_rule || '-'))}</div>
            <div><span class="text-slate-500 dark:text-slate-400">${t('groups_style_example')}:</span> ${escapeHtml(String(card?.example || '-'))}</div>
        </div>
        ${actions}
    </div>`;
}

function ensureGroupsEmotionLoaded(extra) {
    const rooms = getGroupsManagedRooms(extra || {});
    if (!rooms.length) return;
    if (!groupsEmotionState.selectedRoomId || !rooms.some(item => item.id === groupsEmotionState.selectedRoomId)) {
        groupsEmotionState.selectedRoomId = rooms[0].id;
        groupsEmotionState.loadedRoomId = '';
        groupsEmotionState.state = null;
    }
    if (groupsEmotionState.loading) return;
    if (groupsEmotionState.loadedRoomId === groupsEmotionState.selectedRoomId && groupsEmotionState.state) return;
    refreshGroupsEmotionState(groupsEmotionState.selectedRoomId);
}

function selectGroupsEmotionRoom(roomId) {
    groupsEmotionState.selectedRoomId = String(roomId || '');
    groupsEmotionState.loadedRoomId = '';
    groupsEmotionState.state = null;
    renderGroupsView();
    if (groupsEmotionState.selectedRoomId) {
        refreshGroupsEmotionState(groupsEmotionState.selectedRoomId);
    }
}

function refreshGroupsEmotionState(roomId) {
    const targetRoomId = String(roomId || groupsEmotionState.selectedRoomId || '').trim();
    if (!targetRoomId) return;
    groupsEmotionState.loading = true;
    groupsEmotionState.selectedRoomId = targetRoomId;
    renderGroupsView();
    fetch(`/api/wechat-group/emotion/state?stable_room_id=${encodeURIComponent(targetRoomId)}&room_id=${encodeURIComponent(targetRoomId)}`)
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') throw new Error(data.message || 'emotion load failed');
            groupsEmotionState.state = data.state || null;
            groupsEmotionState.lastDecision = data.last_decision || {};
            groupsEmotionState.worker = data.worker || {};
            groupsEmotionState.loadedRoomId = targetRoomId;
        })
        .catch(err => {
            showGroupsStatus(err.message || 'groups_load_failed', true);
            groupsEmotionState.state = null;
            groupsEmotionState.lastDecision = {};
            groupsEmotionState.worker = {};
            groupsEmotionState.loadedRoomId = targetRoomId;
        })
        .finally(() => {
            groupsEmotionState.loading = false;
            renderGroupsView();
        });
}

function formatGroupsEmotionTimestamp(value) {
    const ts = Number(value || 0);
    if (!Number.isFinite(ts) || ts <= 0) return '-';
    try {
        return new Date(ts * 1000).toLocaleString();
    } catch (_) {
        return '-';
    }
}

function renderGroupsEmotionDecision(decision = {}) {
    if (!decision || !Object.keys(decision).length) {
        return `<p class="text-xs text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_no_decision')}</p>`;
    }
    const reasons = Array.isArray(decision.reasons) ? decision.reasons : [];
    const suppressions = Array.isArray(decision.suppressions) ? decision.suppressions : [];
    return `<div class="space-y-2 text-xs text-slate-600 dark:text-slate-300">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
            <span>${t('wechat_group_free_reply_decision_score')}: ${escapeHtml(String(decision.score ?? 0))}</span>
            <span>${t('wechat_group_free_reply_decision_threshold')}: ${escapeHtml(String(decision.threshold ?? 0))}</span>
            <span>${t('wechat_group_free_reply_level')}: ${escapeHtml(translateWechatGroupActivityLevel(decision.activity_level || '-'))}</span>
        </div>
        <div><span class="text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_decision_reasons')}：</span>${reasons.length ? reasons.map(item => `<span class="inline-block rounded bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-300 px-1.5 py-0.5 mr-1 mb-1">${escapeHtml(String(item))}</span>`).join('') : '-'}</div>
        <div><span class="text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_decision_suppressions')}：</span>${suppressions.length ? suppressions.map(item => `<span class="inline-block rounded bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-300 px-1.5 py-0.5 mr-1 mb-1">${escapeHtml(String(item))}</span>`).join('') : '-'}</div>
        <div class="break-words"><span class="text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_decision_preview')}：</span>${escapeHtml(String(decision.text_preview || ''))}</div>
    </div>`;
}

function buildGroupsEmotionPanel(extra) {
    const emotion = extra.emotion || {};
    const rooms = getGroupsManagedRooms(extra);
    const selectedRoomId = groupsEmotionState.selectedRoomId || (rooms[0]?.id || '');
    const state = groupsEmotionState.state || {};
    const loading = groupsEmotionState.loading;
    const rulesJson = JSON.stringify(Array.isArray(emotion.free_reply_time_rules) ? emotion.free_reply_time_rules : [], null, 2);
    const roomOptions = rooms.length
        ? rooms.map(room => `<option value="${escapeHtml(room.id)}" ${room.id === selectedRoomId ? 'selected' : ''}>${escapeHtml(room.name || room.id)}</option>`).join('')
        : '';
    const stateHtml = !rooms.length
        ? `<p class="text-sm text-slate-500 dark:text-slate-400">${t('groups_emotion_empty')}</p>`
        : loading
            ? `<p class="text-sm text-slate-500 dark:text-slate-400"><i class="fas fa-spinner fa-spin mr-2"></i>${t('groups_emotion_loading')}</p>`
            : `<div class="grid grid-cols-2 xl:grid-cols-5 gap-3">
                ${buildGroupsEmotionMetric(t('groups_emotion_metric_valence'), state.valence, 'number')}
                ${buildGroupsEmotionMetric(t('groups_emotion_metric_energy'), state.energy, 'number')}
                ${buildGroupsEmotionMetric(t('groups_emotion_metric_sociability'), state.sociability, 'number')}
                ${buildGroupsEmotionMetric(t('groups_emotion_reply_count'), state.reply_count_1h)}
                ${buildGroupsEmotionMetric(t('groups_emotion_interpreted_state'), state.interpreted_state || '-', 'state')}
            </div>
            <div class="mt-3 text-xs text-slate-500 dark:text-slate-400">
                ${t('groups_emotion_last_reply')}：${escapeHtml(formatGroupsEmotionTimestamp(state.last_reply_at))}
            </div>`;
    return `<div class="h-full w-full space-y-4">
        ${buildGroupsPanelTitle('fa-heart-pulse', 'groups_emotion_title', 'groups_emotion_desc')}
        <div class="grid grid-cols-1 xl:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.2fr)] gap-4">
            <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 space-y-3">
                <div>
                    <label class="block text-sm font-medium text-slate-800 dark:text-slate-100 mb-1.5">${t('groups_emotion_room')}</label>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mb-2">${t('groups_emotion_room_hint')}</p>
                    <select id="groups-emotion-room" onchange="selectGroupsEmotionRoom(this.value)"
                        class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                        ${roomOptions}
                    </select>
                </div>
                <div class="flex flex-wrap gap-2">
                    <button type="button" onclick="refreshGroupsEmotionState()"
                        class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">${t('groups_emotion_refresh')}</button>
                    <button type="button" onclick="resetGroupsEmotionState()"
                        class="px-3 py-1.5 rounded-lg border border-amber-200 dark:border-amber-900/30 text-xs text-amber-600 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/10 cursor-pointer transition-colors">${t('groups_emotion_reset')}</button>
                </div>
            </div>
            <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
                <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">${t('groups_emotion_state')}</h4>
                ${stateHtml}
            </div>
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
            ${buildGroupsImageToggle('groups-emotion-enabled', 'groups_emotion_enabled', 'groups_emotion_enabled_hint', emotion.enabled !== false)}
            ${buildGroupsImageToggle('groups-emotion-time-rules-enabled', 'groups_emotion_time_rules_enabled', 'groups_emotion_time_rules_enabled_hint', !!emotion.free_reply_time_rules_enabled)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-4 gap-4">
            ${buildGroupsImageNumberField('groups-emotion-decay-minutes', 'groups_emotion_decay_minutes', 'groups_emotion_decay_minutes_hint', emotion.decay_minutes ?? 10, 1, 240)}
            ${buildGroupsImageNumberField('groups-emotion-default-valence', 'groups_emotion_default_valence', 'groups_emotion_decay_minutes_hint', emotion.default_valence ?? 0, -1, 1)}
            ${buildGroupsImageNumberField('groups-emotion-default-energy', 'groups_emotion_default_energy', 'groups_emotion_decay_minutes_hint', emotion.default_energy ?? 0.5, 0, 1)}
            ${buildGroupsImageNumberField('groups-emotion-default-sociability', 'groups_emotion_default_sociability', 'groups_emotion_decay_minutes_hint', emotion.default_sociability ?? 0.45, 0, 1)}
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
            ${buildGroupsImageToggle('groups-emotion-typing-delay-enabled', 'groups_emotion_typing_delay_enabled', 'groups_emotion_typing_delay_enabled_hint', emotion.free_reply_typing_delay_enabled !== false)}
            ${buildGroupsImageNumberField('groups-emotion-typing-cps', 'groups_emotion_typing_chars_per_second', 'groups_emotion_typing_chars_per_second_hint', emotion.free_reply_typing_chars_per_second ?? 7, 1, 30)}
        </div>
        <label class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 block">
            <span class="text-sm font-medium text-slate-800 dark:text-slate-100">${t('groups_emotion_time_rules')}</span>
            <span class="block text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_emotion_time_rules_hint')}</span>
            <textarea id="groups-emotion-time-rules" rows="6"
                class="mt-3 w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors font-mono resize-y">${escapeHtml(rulesJson)}</textarea>
        </label>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">${t('groups_emotion_last_decision')}</h4>
            ${renderGroupsEmotionDecision(groupsEmotionState.lastDecision)}
        </div>
        <div class="flex items-center justify-end gap-3">
            <button type="button" id="groups-emotion-save" onclick="saveGroupsEmotionConfig()"
                class="px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                ${t('groups_emotion_save')}
            </button>
        </div>
    </div>`;
}

function translateGroupsEmotionState(value) {
    const key = String(value || '').trim().toLowerCase();
    const labels = {
        withdrawn: t('groups_emotion_state_withdrawn'),
        engaged: t('groups_emotion_state_engaged'),
        guarded: t('groups_emotion_state_guarded'),
        steady: t('groups_emotion_state_steady')
    };
    return labels[key] || String(value || '-');
}

function formatGroupsEmotionMetricValue(value, type = '') {
    if (type === 'number') {
        const number = Number(value);
        return Number.isFinite(number) ? number.toFixed(2) : String(value ?? '-');
    }
    if (type === 'state') {
        return translateGroupsEmotionState(value);
    }
    return String(value ?? '-');
}

function buildGroupsEmotionMetric(label, value, type = '') {
    const displayValue = formatGroupsEmotionMetricValue(value, type);
    return `<div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] px-3 py-3">
        <div class="text-[11px] uppercase tracking-wide text-slate-400 dark:text-slate-500">${escapeHtml(String(label))}</div>
        <div class="mt-1 text-base font-semibold text-slate-800 dark:text-slate-100 break-words">${escapeHtml(displayValue)}</div>
    </div>`;
}

function parseGroupsEmotionTimeRulesInput() {
    const raw = document.getElementById('groups-emotion-time-rules')?.value || '[]';
    if (!raw.trim()) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
        throw new Error('time rules must be a JSON array');
    }
    return parsed;
}

function saveGroupsEmotionConfig() {
    const btn = document.getElementById('groups-emotion-save');
    if (btn) btn.disabled = true;
    let timeRules;
    try {
        timeRules = parseGroupsEmotionTimeRulesInput();
    } catch (_) {
        showGroupsStatus('groups_emotion_time_rules_invalid', true);
        if (btn) btn.disabled = false;
        return;
    }
    fetch('/api/wechat-group/emotion/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            wechat_group_emotion_enabled: !!document.getElementById('groups-emotion-enabled')?.checked,
            wechat_group_emotion_decay_minutes: clampNumber(document.getElementById('groups-emotion-decay-minutes')?.value, 1, 240, 10),
            wechat_group_emotion_default_valence: clampNumber(document.getElementById('groups-emotion-default-valence')?.value, -1, 1, 0),
            wechat_group_emotion_default_energy: clampNumber(document.getElementById('groups-emotion-default-energy')?.value, 0, 1, 0.5),
            wechat_group_emotion_default_sociability: clampNumber(document.getElementById('groups-emotion-default-sociability')?.value, 0, 1, 0.45),
            wechat_group_free_reply_time_rules_enabled: !!document.getElementById('groups-emotion-time-rules-enabled')?.checked,
            wechat_group_free_reply_time_rules: timeRules,
            wechat_group_free_reply_typing_delay_enabled: !!document.getElementById('groups-emotion-typing-delay-enabled')?.checked,
            wechat_group_free_reply_typing_chars_per_second: clampNumber(document.getElementById('groups-emotion-typing-cps')?.value, 1, 30, 7),
        }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'save failed');
        showGroupsStatus('groups_emotion_saved', false);
        loadGroupsView();
    }).catch(err => showGroupsStatus(err.message || 'channels_save_error', true))
      .finally(() => { if (btn) btn.disabled = false; });
}

function resetGroupsEmotionState() {
    const roomId = String(groupsEmotionState.selectedRoomId || '').trim();
    if (!roomId) {
        showGroupsStatus('groups_emotion_empty', true);
        return;
    }
    if (!window.confirm(t('groups_emotion_reset_confirm'))) return;
    fetch('/api/wechat-group/emotion/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stable_room_id: roomId, room_id: roomId }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'reset failed');
        groupsEmotionState.state = data.state || null;
        groupsEmotionState.loadedRoomId = roomId;
        showGroupsStatus('groups_emotion_reset_done', false);
        renderGroupsView();
    }).catch(err => showGroupsStatus(err.message || 'groups_load_failed', true));
}

function formatGroupsStickerText(key, values = {}) {
    let text = t(key);
    Object.entries(values).forEach(([name, value]) => {
        text = text.split(`{${name}}`).join(String(value));
    });
    return text;
}

function clearGroupsStickerDescriptionPoll() {
    if (groupsStickerDescriptionPollTimer) {
        clearTimeout(groupsStickerDescriptionPollTimer);
        groupsStickerDescriptionPollTimer = null;
    }
}

function resetGroupsStickerDescriptionEditor() {
    groupsStickerState.editingStickerId = '';
    groupsStickerState.editingDescription = '';
    groupsStickerState.editingOriginalDescription = '';
    groupsStickerState.savingStickerId = '';
    groupsStickerState.editError = '';
}

function currentGroupsStickerDescriptionJob() {
    return groupsStickerState.descriptionStatus?.job || { status: 'idle' };
}

function isGroupsStickerDescriptionJobActive(job) {
    return ['running', 'busy'].includes(String(job?.status || ''));
}

function scheduleGroupsStickerDescriptionPoll(roomId) {
    clearGroupsStickerDescriptionPoll();
    const targetRoomId = String(roomId || '').trim();
    if (
        groupsActiveSection !== 'sticker'
        || !targetRoomId
        || !isGroupsStickerDescriptionJobActive(currentGroupsStickerDescriptionJob())
    ) return;
    groupsStickerDescriptionPollTimer = setTimeout(() => {
        refreshGroupsStickerDescriptionJobStatus(targetRoomId);
    }, 1200);
}

function refreshGroupsStickerDescriptionStatus(roomId, options = {}) {
    const targetRoomId = String(roomId || groupsStickerState.selectedRoomId || '').trim();
    if (!targetRoomId) return Promise.resolve();
    if (groupsStickerState.descriptionStatusLoadingRoomId === targetRoomId && !options.force) {
        return Promise.resolve();
    }
    groupsStickerState.descriptionStatusLoadingRoomId = targetRoomId;
    if (options.force && groupsStickerState.descriptionStatusErrorRoomId === targetRoomId) {
        groupsStickerState.descriptionStatusError = '';
        groupsStickerState.descriptionStatusErrorRoomId = '';
    }
    return fetch(`/api/wechat-group/stickers/description-status?stable_room_id=${encodeURIComponent(targetRoomId)}&room_id=${encodeURIComponent(targetRoomId)}`)
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') throw new Error(data.message || 'sticker description status load failed');
            if (groupsStickerState.selectedRoomId !== targetRoomId) return;
            groupsStickerState.descriptionStatus = data.description_status || null;
            groupsStickerState.descriptionStatusRoomId = targetRoomId;
            groupsStickerState.descriptionStatusError = '';
            groupsStickerState.descriptionStatusErrorRoomId = '';
            scheduleGroupsStickerDescriptionPoll(targetRoomId);
        })
        .catch(err => {
            if (groupsStickerState.selectedRoomId === targetRoomId) {
                groupsStickerState.descriptionStatusError = t('groups_sticker_description_status_failed');
                groupsStickerState.descriptionStatusErrorRoomId = targetRoomId;
                showGroupsStatus('groups_sticker_description_status_failed', true);
            }
        })
        .finally(() => {
            if (groupsStickerState.descriptionStatusLoadingRoomId === targetRoomId) {
                groupsStickerState.descriptionStatusLoadingRoomId = '';
            }
            if (groupsStickerState.selectedRoomId === targetRoomId) renderGroupsView();
        });
}

function refreshGroupsStickerDescriptionJobStatus(roomId) {
    const targetRoomId = String(roomId || groupsStickerState.selectedRoomId || '').trim();
    if (!targetRoomId) return;
    fetch(`/api/wechat-group/stickers/describe-status?stable_room_id=${encodeURIComponent(targetRoomId)}&room_id=${encodeURIComponent(targetRoomId)}`)
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') throw new Error(data.message || 'sticker description job load failed');
            if (groupsStickerState.selectedRoomId !== targetRoomId) return;
            const previousStatus = String(currentGroupsStickerDescriptionJob().status || 'idle');
            groupsStickerState.descriptionStatus = {
                ...(groupsStickerState.descriptionStatus || {}),
                job: data.job || { status: 'idle' },
            };
            groupsStickerState.descriptionStatusRoomId = targetRoomId;
            renderGroupsView();
            if (isGroupsStickerDescriptionJobActive(data.job)) {
                scheduleGroupsStickerDescriptionPoll(targetRoomId);
                return;
            }
            clearGroupsStickerDescriptionPoll();
            refreshGroupsStickerDescriptionStatus(targetRoomId, { force: true });
            if (previousStatus === 'running') {
                groupsStickerState.loadedKey = '';
                refreshGroupsStickerData(targetRoomId);
            }
        })
        .catch(err => {
            if (groupsStickerState.selectedRoomId !== targetRoomId) return;
            showGroupsStatus(err.message || 'groups_load_failed', true);
            scheduleGroupsStickerDescriptionPoll(targetRoomId);
        });
}

function ensureGroupsStickerLoaded(extra) {
    const rooms = getGroupsManagedRooms(extra || {});
    if (!rooms.length) return;
    if (!groupsStickerState.selectedRoomId || !rooms.some(item => item.id === groupsStickerState.selectedRoomId)) {
        clearGroupsStickerDescriptionPoll();
        groupsStickerState.selectedRoomId = rooms[0].id;
        groupsStickerState.loadedKey = '';
        groupsStickerState.stickers = [];
        groupsStickerState.descriptionStatus = null;
        groupsStickerState.descriptionStatusRoomId = '';
        groupsStickerState.descriptionStatusError = '';
        groupsStickerState.descriptionStatusErrorRoomId = '';
        resetGroupsStickerDescriptionEditor();
    }
    if (
        groupsStickerState.descriptionStatusRoomId !== groupsStickerState.selectedRoomId
        && groupsStickerState.descriptionStatusLoadingRoomId !== groupsStickerState.selectedRoomId
        && groupsStickerState.descriptionStatusErrorRoomId !== groupsStickerState.selectedRoomId
    ) {
        refreshGroupsStickerDescriptionStatus(groupsStickerState.selectedRoomId);
    }
    if (groupsStickerState.loading) return;
    const loadKey = `${groupsStickerState.selectedRoomId}|${groupsStickerState.search.trim()}|${groupsStickerState.status}`;
    if (groupsStickerState.loadedKey === loadKey) return;
    refreshGroupsStickerData(groupsStickerState.selectedRoomId);
}

function selectGroupsStickerRoom(roomId) {
    clearGroupsStickerDescriptionPoll();
    groupsStickerState.selectedRoomId = String(roomId || '');
    groupsStickerState.loadedKey = '';
    groupsStickerState.stickers = [];
    groupsStickerState.descriptionStatus = null;
    groupsStickerState.descriptionStatusRoomId = '';
    groupsStickerState.descriptionStatusLoadingRoomId = '';
    groupsStickerState.descriptionStatusError = '';
    groupsStickerState.descriptionStatusErrorRoomId = '';
    resetGroupsStickerDescriptionEditor();
    renderGroupsView();
    if (groupsStickerState.selectedRoomId) {
        refreshGroupsStickerData(groupsStickerState.selectedRoomId);
        refreshGroupsStickerDescriptionStatus(groupsStickerState.selectedRoomId);
    }
}

function applyGroupsStickerFilters() {
    groupsStickerState.search = (document.getElementById('groups-sticker-search')?.value || '').trim();
    groupsStickerState.status = String(document.getElementById('groups-sticker-status')?.value || '').trim();
    groupsStickerState.loadedKey = '';
    refreshGroupsStickerData(groupsStickerState.selectedRoomId);
}

function refreshGroupsStickerData(roomId) {
    const targetRoomId = String(roomId || groupsStickerState.selectedRoomId || '').trim();
    if (!targetRoomId) return;
    const query = groupsStickerState.search.trim();
    const status = groupsStickerState.status.trim();
    const loadKey = `${targetRoomId}|${query}|${status}`;
    const requestId = ++groupsStickerState.listRequestId;
    groupsStickerState.loading = true;
    groupsStickerState.selectedRoomId = targetRoomId;
    renderGroupsView();
    fetch(`/api/wechat-group/stickers/list?stable_room_id=${encodeURIComponent(targetRoomId)}&room_id=${encodeURIComponent(targetRoomId)}&limit=30&q=${encodeURIComponent(query)}&status=${encodeURIComponent(status)}`)
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') throw new Error(data.message || 'sticker load failed');
            if (requestId !== groupsStickerState.listRequestId || groupsStickerState.selectedRoomId !== targetRoomId) return;
            groupsStickerState.stickers = Array.isArray(data.stickers) ? data.stickers : [];
            groupsStickerState.loadedKey = loadKey;
        })
        .catch(err => {
            if (requestId !== groupsStickerState.listRequestId || groupsStickerState.selectedRoomId !== targetRoomId) return;
            showGroupsStatus(err.message || 'groups_load_failed', true);
            groupsStickerState.stickers = [];
            groupsStickerState.loadedKey = loadKey;
        })
        .finally(() => {
            if (requestId !== groupsStickerState.listRequestId || groupsStickerState.selectedRoomId !== targetRoomId) return;
            groupsStickerState.loading = false;
            renderGroupsView();
        });
}

function retryGroupsStickerDescriptionStatus() {
    const roomId = String(groupsStickerState.selectedRoomId || '').trim();
    if (!roomId || groupsStickerState.descriptionStatusLoadingRoomId === roomId) return;
    groupsStickerState.descriptionStatusError = '';
    groupsStickerState.descriptionStatusErrorRoomId = '';
    refreshGroupsStickerDescriptionStatus(roomId, { force: true });
    renderGroupsView();
}

function beginGroupsStickerDescriptionEdit(stickerId) {
    const targetStickerId = String(stickerId || '').trim();
    const sticker = groupsStickerState.stickers.find(item => String(item?.sticker_id || '') === targetStickerId);
    if (!sticker) return;
    groupsStickerState.editingStickerId = targetStickerId;
    groupsStickerState.editingDescription = String(sticker.description || '');
    groupsStickerState.editingOriginalDescription = String(sticker.description || '');
    groupsStickerState.savingStickerId = '';
    groupsStickerState.editError = '';
    renderGroupsView();
    requestAnimationFrame(() => document.getElementById('groups-sticker-description-edit')?.focus());
}

function updateGroupsStickerDescriptionDraft(value) {
    groupsStickerState.editingDescription = String(value || '');
    groupsStickerState.editError = '';
}

function cancelGroupsStickerDescriptionEdit() {
    if (groupsStickerState.savingStickerId) return;
    resetGroupsStickerDescriptionEditor();
    renderGroupsView();
}

function handleGroupsStickerDescriptionKeydown(event) {
    if (event.key === 'Escape') {
        event.preventDefault();
        cancelGroupsStickerDescriptionEdit();
        return;
    }
    if (event.key === 'Enter') {
        event.preventDefault();
        saveGroupsStickerDescription();
    }
}

function translatedGroupsStickerError(message) {
    const key = translateGroupsStatusText(message);
    const hasTranslation = (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key];
    return hasTranslation ? t(key) : String(message || t('groups_load_failed'));
}

function saveGroupsStickerDescription() {
    const roomId = String(groupsStickerState.selectedRoomId || '').trim();
    const stickerId = String(groupsStickerState.editingStickerId || '').trim();
    const input = document.getElementById('groups-sticker-description-edit');
    const description = String(input?.value ?? groupsStickerState.editingDescription ?? '').trim();
    if (!roomId || !stickerId || groupsStickerState.savingStickerId) return;
    groupsStickerState.editingDescription = description;
    if (!description || description.length > 200) {
        groupsStickerState.editError = t('groups_sticker_description_invalid');
        renderGroupsView();
        requestAnimationFrame(() => document.getElementById('groups-sticker-description-edit')?.focus());
        return;
    }
    groupsStickerState.savingStickerId = stickerId;
    groupsStickerState.editError = '';
    renderGroupsView();
    fetch('/api/wechat-group/stickers/update-description', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            stable_room_id: roomId,
            room_id: roomId,
            sticker_id: stickerId,
            description,
            expected_description: groupsStickerState.editingOriginalDescription,
        }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'sticker description update failed');
        if (groupsStickerState.selectedRoomId !== roomId) return;
        groupsStickerState.stickers = groupsStickerState.stickers.map(item => (
            String(item?.sticker_id || '') === stickerId ? { ...item, ...(data.sticker || {}) } : item
        ));
        groupsStickerState.descriptionStatus = data.description_status || groupsStickerState.descriptionStatus;
        groupsStickerState.descriptionStatusRoomId = roomId;
        groupsStickerState.descriptionStatusError = '';
        groupsStickerState.descriptionStatusErrorRoomId = '';
        resetGroupsStickerDescriptionEditor();
        showGroupsStatus('groups_sticker_description_saved', false);
        groupsStickerState.loadedKey = '';
        refreshGroupsStickerData(roomId);
    }).catch(err => {
        if (groupsStickerState.selectedRoomId !== roomId) return;
        groupsStickerState.savingStickerId = '';
        groupsStickerState.editError = translatedGroupsStickerError(err.message);
        renderGroupsView();
        requestAnimationFrame(() => document.getElementById('groups-sticker-description-edit')?.focus());
    });
}

function startGroupsStickerDescriptionBatch() {
    const roomId = String(groupsStickerState.selectedRoomId || '').trim();
    const processable = Number(groupsStickerState.descriptionStatus?.processable || 0);
    const job = currentGroupsStickerDescriptionJob();
    if (!roomId || processable <= 0 || groupsStickerState.descriptionStarting || isGroupsStickerDescriptionJobActive(job)) return;
    const confirmation = formatGroupsStickerText('groups_sticker_describe_confirm', { count: processable });
    if (!window.confirm(confirmation)) return;
    groupsStickerState.descriptionStarting = true;
    renderGroupsView();
    fetch('/api/wechat-group/stickers/describe-pending', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stable_room_id: roomId, room_id: roomId }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'sticker description job start failed');
        if (groupsStickerState.selectedRoomId !== roomId) return;
        groupsStickerState.descriptionStatus = {
            ...(groupsStickerState.descriptionStatus || {}),
            job: data.job || { status: 'running' },
        };
        groupsStickerState.descriptionStatusRoomId = roomId;
        showGroupsStatus('groups_sticker_describe_started', false);
        if (isGroupsStickerDescriptionJobActive(data.job)) {
            scheduleGroupsStickerDescriptionPoll(roomId);
        } else {
            groupsStickerState.loadedKey = '';
            refreshGroupsStickerDescriptionStatus(roomId, { force: true });
            refreshGroupsStickerData(roomId);
        }
    }).catch(err => {
        if (groupsStickerState.selectedRoomId !== roomId) return;
        showGroupsStatus(err.message || 'groups_load_failed', true);
    }).finally(() => {
        groupsStickerState.descriptionStarting = false;
        renderGroupsView();
    });
}

function testGroupsStickerOnlineSearch() {
    const roomId = String(groupsStickerState.selectedRoomId || document.getElementById('groups-sticker-room')?.value || '').trim();
    const query = String(document.getElementById('groups-sticker-online-query')?.value || groupsStickerState.onlineQuery || '').trim();
    if (!roomId) return;
    groupsStickerState.onlineQuery = query;
    groupsStickerState.onlineLoading = true;
    renderGroupsView();
    fetch(`/api/wechat-group/stickers/search-online?stable_room_id=${encodeURIComponent(roomId)}&room_id=${encodeURIComponent(roomId)}&limit=6&q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') throw new Error(data.message || 'sticker online search failed');
            groupsStickerState.onlineResults = Array.isArray(data.stickers) ? data.stickers : [];
            showGroupsStatus('groups_sticker_online_test_done', false);
        })
        .catch(err => {
            groupsStickerState.onlineResults = [];
            showGroupsStatus(err.message || 'groups_load_failed', true);
        })
        .finally(() => {
            groupsStickerState.onlineLoading = false;
            renderGroupsView();
        });
}

function disableGroupsSticker(stickerId) {
    const roomId = String(groupsStickerState.selectedRoomId || '').trim();
    const targetStickerId = String(stickerId || '').trim();
    if (!roomId || !targetStickerId) return;
    if (!window.confirm(t('groups_sticker_disable_confirm'))) return;
    fetch('/api/wechat-group/stickers/disable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            stable_room_id: roomId,
            room_id: roomId,
            sticker_id: targetStickerId,
        }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'sticker disable failed');
        showGroupsStatus('groups_sticker_disabled_done', false);
        groupsStickerState.loadedKey = '';
        refreshGroupsStickerData(roomId);
    }).catch(err => showGroupsStatus(err.message || 'groups_load_failed', true));
}

function readGroupsStickerConfig(saved = {}) {
    const readBool = (id, fallback) => {
        const el = document.getElementById(id);
        return el ? !!el.checked : fallback;
    };
    const readNumber = (id, fallback) => {
        const el = document.getElementById(id);
        const value = Number(el?.value ?? fallback);
        return Number.isFinite(value) ? value : fallback;
    };
    const readText = (id, fallback = '') => {
        const el = document.getElementById(id);
        return el ? String(el.value || '').trim() : String(fallback || '').trim();
    };
    const allowedDomainsRaw = readText(
        'groups-sticker-online-allowed-domains',
        Array.isArray(saved.online_allowed_domains) ? saved.online_allowed_domains.join('\n') : ''
    );
    return {
        enabled: readBool('groups-sticker-enabled', saved.enabled !== false),
        auto_collect_enabled: readBool('groups-sticker-auto-collect-enabled', saved.auto_collect_enabled !== false),
        context_limit: readNumber('groups-sticker-context-limit', Number(saved.context_limit ?? 5)),
        reply_percent: readNumber('groups-sticker-reply-percent', Number(saved.reply_percent ?? 20)),
        max_size_mb: readNumber('groups-sticker-max-size-mb', Number(saved.max_size_mb ?? 2)),
        daily_send_limit: readNumber('groups-sticker-daily-send-limit', Number(saved.daily_send_limit ?? 20)),
        storage_dir: readText('groups-sticker-storage-dir', saved.storage_dir || ''),
        online_search_enabled: readBool('groups-sticker-online-search-enabled', saved.online_search_enabled !== false),
        online_provider: readText('groups-sticker-online-provider', saved.online_provider || 'xiaoapi') || 'xiaoapi',
        online_endpoint: readText('groups-sticker-online-endpoint', saved.online_endpoint || 'https://api.suol.cc/v1/meme.php'),
        online_allowed_domains: allowedDomainsRaw.split(/[\n,，;；\t ]+/).map(item => item.trim()).filter(Boolean),
        online_allow_gif: readBool('groups-sticker-online-allow-gif', saved.online_allow_gif !== false),
        online_search_count: readNumber('groups-sticker-online-search-count', Number(saved.online_search_count ?? 10)),
        cooldown_seconds: readNumber('groups-sticker-cooldown-seconds', Number(saved.cooldown_seconds ?? 30)),
    };
}

function saveGroupsStickerConfig() {
    const ch = getWechatGroupChannel();
    if (!ch) return;
    const sticker = readGroupsStickerConfig(groupsStickerState.configDraft || ch.extra?.sticker || {});
    const btn = document.getElementById('groups-sticker-save');
    if (btn) btn.disabled = true;
    fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'save',
            channel: 'wechat_group',
            config: {
                wechat_group_sticker_enabled: sticker.enabled,
                wechat_group_sticker_auto_collect_enabled: sticker.auto_collect_enabled,
                wechat_group_sticker_context_limit: sticker.context_limit,
                wechat_group_sticker_reply_percent: sticker.reply_percent,
                wechat_group_sticker_max_size_mb: sticker.max_size_mb,
                wechat_group_sticker_daily_send_limit: sticker.daily_send_limit,
                wechat_group_sticker_storage_dir: sticker.storage_dir,
                wechat_group_sticker_online_search_enabled: sticker.online_search_enabled,
                wechat_group_sticker_online_provider: sticker.online_provider,
                wechat_group_sticker_online_endpoint: sticker.online_endpoint,
                wechat_group_sticker_online_allowed_domains: sticker.online_allowed_domains,
                wechat_group_sticker_online_allow_gif: sticker.online_allow_gif,
                wechat_group_sticker_online_search_count: sticker.online_search_count,
                wechat_group_sticker_cooldown_seconds: sticker.cooldown_seconds,
            },
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'save failed');
        groupsStickerState.configDraft = null;
        showGroupsStatus('groups_sticker_saved', false);
        loadGroupsView();
    })
    .catch(err => showGroupsStatus(err.message || 'channels_save_error', true))
    .finally(() => { if (btn) btn.disabled = false; });
}

function renderGroupsStickerDescriptionControls() {
    const roomId = String(groupsStickerState.selectedRoomId || '').trim();
    const status = groupsStickerState.descriptionStatusRoomId === roomId
        ? groupsStickerState.descriptionStatus
        : null;
    const loading = groupsStickerState.descriptionStatusLoadingRoomId === roomId && !status;
    const loadError = groupsStickerState.descriptionStatusErrorRoomId === roomId
        ? groupsStickerState.descriptionStatusError
        : '';
    if (loadError) {
        return `<div class="min-h-11 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-200 dark:border-white/10 pb-3 mb-3">
            <p class="text-xs text-red-600 dark:text-red-400" role="alert">${escapeHtml(loadError)}</p>
            <button type="button" onclick="retryGroupsStickerDescriptionStatus()"
                class="min-h-11 px-3 py-2 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-white/5 cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500">
                <i class="fas fa-rotate-right mr-1.5" aria-hidden="true"></i>${t('groups_sticker_description_status_retry')}
            </button>
        </div>`;
    }
    if (loading || !status) {
        return `<div class="min-h-11 flex items-center border-b border-slate-200 dark:border-white/10 pb-3 mb-3 text-xs text-slate-500 dark:text-slate-400" aria-live="polite">
            <i class="fas fa-spinner fa-spin mr-2" aria-hidden="true"></i>${t('groups_sticker_description_status_loading')}
        </div>`;
    }
    const pending = Math.max(0, Number(status.pending || 0));
    const processable = Math.max(0, Number(status.processable || 0));
    const missing = Math.max(0, Number(status.missing_files || 0));
    const empty = Math.max(0, Number(status.empty_files || 0));
    const job = status.job || { status: 'idle' };
    const jobStatus = String(job.status || 'idle');
    const jobActive = isGroupsStickerDescriptionJobActive(job);
    const disabled = processable <= 0 || groupsStickerState.descriptionStarting || jobActive;
    const summary = formatGroupsStickerText('groups_sticker_description_pending_summary', { pending, processable });
    const fileIssues = missing || empty
        ? formatGroupsStickerText('groups_sticker_description_file_issues', { missing, empty })
        : '';
    let buttonLabel = t('groups_sticker_describe_pending');
    let buttonIcon = '<i class="fas fa-wand-magic-sparkles mr-1.5" aria-hidden="true"></i>';
    if (groupsStickerState.descriptionStarting) {
        buttonLabel = t('groups_sticker_describe_starting');
        buttonIcon = '<i class="fas fa-spinner fa-spin mr-1.5" aria-hidden="true"></i>';
    } else if (jobStatus === 'running') {
        buttonLabel = formatGroupsStickerText('groups_sticker_describe_running', {
            processed: Number(job.processed || 0),
            total: Number(job.total || 0),
        });
        buttonIcon = '<i class="fas fa-spinner fa-spin mr-1.5" aria-hidden="true"></i>';
    } else if (jobStatus === 'busy') {
        buttonLabel = t('groups_sticker_describe_busy');
        buttonIcon = '<i class="fas fa-clock mr-1.5" aria-hidden="true"></i>';
    }

    let jobHtml = '';
    if (jobStatus === 'running') {
        const processed = Math.max(0, Number(job.processed || 0));
        const total = Math.max(0, Number(job.total || 0));
        const progress = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
        jobHtml = `<div class="mt-3" aria-live="polite">
            <div class="flex items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400 mb-1.5">
                <span>${formatGroupsStickerText('groups_sticker_describe_running', { processed, total })}</span>
                <span class="tabular-nums">${progress}%</span>
            </div>
            <div class="h-2 rounded-full bg-slate-200 dark:bg-white/10 overflow-hidden" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}">
                <div class="h-full bg-primary-500 transition-[width] duration-200 motion-reduce:transition-none" style="width:${progress}%"></div>
            </div>
        </div>`;
    } else if (['completed', 'partial_failed'].includes(jobStatus)) {
        const failed = Number(job.failed || 0) + Number(job.missing_files || 0) + Number(job.empty_files || 0);
        const result = formatGroupsStickerText('groups_sticker_describe_result', {
            updated: Number(job.updated || 0),
            failed,
            skipped: Number(job.skipped_changed || 0),
        });
        const resultKey = jobStatus === 'completed'
            ? 'groups_sticker_describe_completed'
            : 'groups_sticker_describe_partial_failed';
        const resultClass = jobStatus === 'completed'
            ? 'text-emerald-700 dark:text-emerald-400'
            : 'text-amber-700 dark:text-amber-300';
        jobHtml = `<p class="mt-3 text-xs ${resultClass}" aria-live="polite">${t(resultKey)}：${escapeHtml(result)}</p>`;
    } else if (jobStatus === 'failed') {
        jobHtml = `<p class="mt-3 text-xs text-red-600 dark:text-red-400" role="alert">${t('groups_sticker_describe_failed')}</p>`;
    }

    return `<div class="border-b border-slate-200 dark:border-white/10 pb-3 mb-3">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div class="min-w-0" aria-live="polite">
                <p class="text-sm font-medium text-slate-700 dark:text-slate-200">${escapeHtml(summary)}</p>
                ${fileIssues ? `<p class="text-xs text-amber-700 dark:text-amber-300 mt-1">${escapeHtml(fileIssues)}</p>` : ''}
            </div>
            <button type="button" id="groups-sticker-describe-pending" onclick="startGroupsStickerDescriptionBatch()"
                ${disabled ? 'disabled' : ''} aria-disabled="${disabled ? 'true' : 'false'}"
                class="min-h-11 px-3 py-2 rounded-lg bg-primary-600 hover:bg-primary-700 text-white text-xs font-medium cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-[#111111] disabled:opacity-50 disabled:cursor-not-allowed">
                ${buttonIcon}${escapeHtml(buttonLabel)}
            </button>
        </div>
        ${jobHtml}
    </div>`;
}

function buildGroupsStickerPanel(extra) {
    const sticker = getGroupsStickerConfigForRender(extra);
    const rooms = getGroupsManagedRooms(extra);
    const selectedRoomId = groupsStickerState.selectedRoomId || (rooms[0]?.id || '');
    const loading = groupsStickerState.loading;
    const roomOptions = rooms.length
        ? rooms.map(room => `<option value="${escapeHtml(room.id)}" ${room.id === selectedRoomId ? 'selected' : ''}>${escapeHtml(room.name || room.id)}</option>`).join('')
        : '';
    const statusOptions = [
        ['', t('groups_sticker_status_all')],
        ['active', t('groups_sticker_status_active')],
        ['disabled', t('groups_sticker_status_disabled')],
    ];
    const contentHtml = !rooms.length
        ? `<p class="text-sm text-slate-500 dark:text-slate-400">${t('groups_sticker_empty')}</p>`
        : `<div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <div class="flex items-center justify-between gap-3 mb-3">
                <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_sticker_list_title')}</h4>
                <span class="text-xs text-slate-400 dark:text-slate-500 tabular-nums">${escapeHtml(String(groupsStickerState.stickers.length))}</span>
            </div>
            ${renderGroupsStickerDescriptionControls()}
            ${loading
                ? `<p class="min-h-28 flex items-center justify-center text-sm text-slate-500 dark:text-slate-400"><i class="fas fa-spinner fa-spin mr-2" aria-hidden="true"></i>${t('groups_sticker_loading')}</p>`
                : renderGroupsStickerCards(groupsStickerState.stickers)}
        </div>`;
    return `<div class="h-full w-full space-y-4">
        ${buildGroupsPanelTitle('fa-face-laugh-squint', 'groups_sticker_title', 'groups_sticker_desc')}
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 space-y-4">
            <div>
                <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_sticker_settings_title')}</h4>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_sticker_settings_hint')}</p>
            </div>
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                ${buildGroupsImageToggle('groups-sticker-enabled', 'groups_sticker_enabled', 'groups_sticker_enabled_hint', sticker.enabled !== false)}
                ${buildGroupsImageToggle('groups-sticker-auto-collect-enabled', 'groups_sticker_auto_collect_enabled', 'groups_sticker_auto_collect_enabled_hint', sticker.auto_collect_enabled !== false)}
                ${buildGroupsImageToggle('groups-sticker-online-search-enabled', 'groups_sticker_online_search_enabled', 'groups_sticker_online_search_enabled_hint', sticker.online_search_enabled !== false)}
                ${buildGroupsImageToggle('groups-sticker-online-allow-gif', 'groups_sticker_online_allow_gif', 'groups_sticker_online_allow_gif_hint', sticker.online_allow_gif !== false)}
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                ${buildGroupsImageNumberField('groups-sticker-context-limit', 'groups_sticker_context_limit', 'groups_sticker_context_limit_hint', sticker.context_limit ?? 5, 1, 100)}
                ${buildGroupsImageNumberField('groups-sticker-reply-percent', 'groups_sticker_reply_percent', 'groups_sticker_reply_percent_hint', sticker.reply_percent ?? 20, 0, 100)}
                ${buildGroupsImageNumberField('groups-sticker-max-size-mb', 'groups_sticker_max_size_mb', 'groups_sticker_max_size_mb_hint', sticker.max_size_mb ?? 2, 1, 20)}
                ${buildGroupsImageNumberField('groups-sticker-daily-send-limit', 'groups_sticker_daily_send_limit', 'groups_sticker_daily_send_limit_hint', sticker.daily_send_limit ?? 20, 0, 200)}
                ${buildGroupsImageNumberField('groups-sticker-cooldown-seconds', 'groups_sticker_cooldown_seconds', 'groups_sticker_cooldown_seconds_hint', sticker.cooldown_seconds ?? 30, 5, 600)}
                ${buildGroupsImageNumberField('groups-sticker-online-search-count', 'groups_sticker_online_search_count', 'groups_sticker_online_search_count_hint', sticker.online_search_count ?? 10, 1, 40)}
            </div>
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <label class="block">
                    <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_sticker_online_provider')}</span>
                    <input id="groups-sticker-online-provider" type="text" value="${escapeHtml(sticker.online_provider || 'xiaoapi')}"
                        class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                </label>
                <label class="block">
                    <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_sticker_storage_dir')}</span>
                    <input id="groups-sticker-storage-dir" type="text" value="${escapeHtml(sticker.storage_dir || '')}"
                        class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                </label>
            </div>
            <label class="block">
                <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_sticker_online_endpoint')}</span>
                <input id="groups-sticker-online-endpoint" type="text" value="${escapeHtml(sticker.online_endpoint || 'https://api.suol.cc/v1/meme.php')}"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
            </label>
            <label class="block">
                <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_sticker_online_allowed_domains')}</span>
                <textarea id="groups-sticker-online-allowed-domains" rows="3" placeholder="${escapeHtml(t('groups_sticker_online_allowed_domains_placeholder'))}"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 resize-y">${escapeHtml((Array.isArray(sticker.online_allowed_domains) ? sticker.online_allowed_domains : []).join('\n'))}</textarea>
            </label>
            <div class="flex flex-wrap gap-2">
                <button type="button" id="groups-sticker-save" onclick="saveGroupsStickerConfig()"
                    class="px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">${t('groups_sticker_save')}</button>
            </div>
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-[minmax(280px,0.9fr)_minmax(0,1.1fr)] gap-4">
            <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 space-y-3">
                <div>
                    <label class="block text-sm font-medium text-slate-800 dark:text-slate-100 mb-1.5">${t('groups_sticker_room')}</label>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mb-2">${t('groups_sticker_room_hint')}</p>
                    <select id="groups-sticker-room" onchange="selectGroupsStickerRoom(this.value)"
                        class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                        ${roomOptions}
                    </select>
                </div>
                <div class="grid grid-cols-1 gap-3">
                    <label class="block">
                        <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_sticker_description')}</span>
                        <input id="groups-sticker-search" type="text" value="${escapeHtml(groupsStickerState.search)}"
                            placeholder="${escapeHtml(t('groups_sticker_search_placeholder'))}"
                            onkeydown="if(event.key==='Enter'){event.preventDefault();applyGroupsStickerFilters();}"
                            class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                    </label>
                    <label class="block">
                        <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_sticker_status')}</span>
                        <select id="groups-sticker-status" onchange="applyGroupsStickerFilters()"
                            class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                            ${statusOptions.map(([value, label]) => `<option value="${escapeHtml(value)}" ${value === groupsStickerState.status ? 'selected' : ''}>${escapeHtml(label)}</option>`).join('')}
                        </select>
                    </label>
                </div>
                <div class="flex flex-wrap gap-2">
                    <button type="button" onclick="applyGroupsStickerFilters()"
                        class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">${t('groups_sticker_refresh')}</button>
                </div>
            </div>
            <div class="space-y-4">
                ${contentHtml}
            </div>
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 space-y-3">
            <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_sticker_online_test')}</h4>
            <div class="flex flex-col sm:flex-row gap-2">
                <input id="groups-sticker-online-query" type="text" value="${escapeHtml(groupsStickerState.onlineQuery)}"
                    placeholder="${escapeHtml(t('groups_sticker_online_test_placeholder'))}"
                    onkeydown="if(event.key==='Enter'){event.preventDefault();testGroupsStickerOnlineSearch();}"
                    class="flex-1 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                <button type="button" onclick="testGroupsStickerOnlineSearch()"
                    class="px-3 py-2 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">${groupsStickerState.onlineLoading ? '<i class="fas fa-spinner fa-spin mr-1"></i>' : ''}${t('groups_sticker_online_test')}</button>
            </div>
            ${renderGroupsStickerCards(groupsStickerState.onlineResults)}
        </div>
    </div>`;
}

function renderGroupsStickerCards(stickers) {
    const list = Array.isArray(stickers) ? stickers : [];
    if (!list.length) {
        return `<p class="text-xs text-slate-500 dark:text-slate-400">${t('groups_sticker_no_items')}</p>`;
    }
    return `<div class="space-y-3">${list.map(item => renderGroupsStickerCard(item)).join('')}</div>`;
}

function renderGroupsStickerCard(sticker) {
    const stickerId = String(sticker?.sticker_id || '');
    const onlineId = String(sticker?.online_id || '');
    const displayId = stickerId || onlineId || '-';
    const previewUrl = String(sticker?.preview_url || '');
    const mediaPath = String(sticker?.media_path || '');
    const description = String(sticker?.description || '');
    const isEditing = !!stickerId && groupsStickerState.editingStickerId === stickerId;
    const isSaving = isEditing && groupsStickerState.savingStickerId === stickerId;
    const editError = isEditing ? String(groupsStickerState.editError || '') : '';
    const descriptionHtml = isEditing
        ? `<div class="space-y-2">
            <label for="groups-sticker-description-edit" class="block text-xs font-medium text-slate-600 dark:text-slate-300">${t('groups_sticker_description_edit_label')}</label>
            <input id="groups-sticker-description-edit" type="text" maxlength="200"
                value="${escapeHtml(groupsStickerState.editingDescription)}"
                oninput="updateGroupsStickerDescriptionDraft(this.value)"
                onkeydown="handleGroupsStickerDescriptionKeydown(event)"
                aria-describedby="groups-sticker-description-hint${editError ? ' groups-sticker-description-error' : ''}"
                aria-invalid="${editError ? 'true' : 'false'}" ${isSaving ? 'disabled' : ''}
                class="w-full min-h-11 px-3 py-2 rounded-lg border ${editError ? 'border-red-400 dark:border-red-500' : 'border-slate-200 dark:border-slate-600'} bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:opacity-60">
            <p id="groups-sticker-description-hint" class="text-xs text-slate-500 dark:text-slate-400">${t('groups_sticker_description_edit_hint')}</p>
            ${editError ? `<p id="groups-sticker-description-error" class="text-xs text-red-600 dark:text-red-400" role="alert">${escapeHtml(editError)}</p>` : ''}
            <div class="flex flex-wrap gap-2">
                <button type="button" onclick="saveGroupsStickerDescription()" ${isSaving ? 'disabled' : ''}
                    class="min-h-11 px-3 py-2 rounded-lg bg-primary-600 hover:bg-primary-700 text-white text-xs font-medium cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-[#111111] disabled:opacity-50 disabled:cursor-not-allowed">
                    ${isSaving ? '<i class="fas fa-spinner fa-spin mr-1.5" aria-hidden="true"></i>' : '<i class="fas fa-check mr-1.5" aria-hidden="true"></i>'}${t('groups_sticker_description_save')}
                </button>
                <button type="button" onclick="cancelGroupsStickerDescriptionEdit()" ${isSaving ? 'disabled' : ''}
                    class="min-h-11 px-3 py-2 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed">
                    ${t('groups_sticker_description_cancel')}
                </button>
            </div>
        </div>`
        : `<div><span class="text-slate-500 dark:text-slate-400">${t('groups_sticker_description')}:</span> ${escapeHtml(description || '-')}</div>`;
    return `<div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
        <div class="flex flex-col xl:flex-row gap-3">
            <div class="w-full xl:w-32 xl:flex-shrink-0">
                ${previewUrl ? `
                    <div class="rounded-lg overflow-hidden border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5">
                        <img src="${escapeHtml(previewUrl)}" alt="${escapeHtml(description || t('groups_sticker_preview_alt'))}" loading="lazy" class="w-full h-28 object-contain" onerror="this.parentElement.innerHTML='<div class=&quot;h-28 flex items-center justify-center text-xs text-slate-400 dark:text-slate-500 px-2&quot;>${escapeHtml(t('groups_sticker_preview_alt'))}</div>';">
                    </div>
                ` : `<div class="h-28 rounded-lg border border-dashed border-slate-200 dark:border-white/10 flex items-center justify-center text-xs text-slate-400 dark:text-slate-500">${escapeHtml(t('groups_sticker_preview_alt'))}</div>`}
            </div>
            <div class="min-w-0 flex-1">
                <div class="flex items-center justify-between gap-3 mb-2">
                    <div class="min-w-0">
                        <div class="text-sm font-semibold text-slate-800 dark:text-slate-100 break-all">${escapeHtml(displayId)}</div>
                        <div class="text-xs text-slate-400 dark:text-slate-500 mt-1 break-all">${escapeHtml(mediaPath || '')}</div>
                    </div>
                    <span class="inline-flex items-center rounded-full bg-slate-100 dark:bg-white/10 px-2 py-0.5 text-[11px] text-slate-600 dark:text-slate-300">${escapeHtml(String(sticker?.source || sticker?.status || ''))}</span>
                </div>
                <div class="space-y-1.5 text-sm text-slate-700 dark:text-slate-200 break-words">
                    ${descriptionHtml}
                    <div><span class="text-slate-500 dark:text-slate-400">${t('groups_sticker_file_name')}:</span> ${escapeHtml(String(sticker?.file_name || '-'))}</div>
                    <div><span class="text-slate-500 dark:text-slate-400">${t('groups_sticker_source_message_id')}:</span> ${escapeHtml(String(sticker?.source_message_id || '-'))}</div>
                    <div><span class="text-slate-500 dark:text-slate-400">${t('groups_sticker_use_count')}:</span> ${escapeHtml(String(sticker?.use_count ?? 0))}</div>
                    <div><span class="text-slate-500 dark:text-slate-400">${t('groups_sticker_updated_at')}:</span> ${escapeHtml(formatGroupsEmotionTimestamp(sticker?.updated_at))}</div>
                </div>
                ${!stickerId || isEditing ? '' : `<div class="flex flex-wrap gap-2 mt-3">
                    <button type="button" data-sticker-id="${escapeHtml(stickerId)}" onclick="beginGroupsStickerDescriptionEdit(this.dataset.stickerId)"
                        class="min-h-11 px-3 py-2 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500">
                        <i class="fas fa-pen mr-1.5" aria-hidden="true"></i>${t('groups_sticker_description_edit')}
                    </button>
                    ${String(sticker?.status || '') === 'disabled' ? '' : `<button type="button" data-sticker-id="${escapeHtml(stickerId)}" onclick="disableGroupsSticker(this.dataset.stickerId)"
                        class="min-h-11 px-3 py-2 rounded-lg border border-amber-200 dark:border-amber-900/30 text-xs text-amber-600 dark:text-amber-300 hover:bg-amber-50 dark:hover:bg-amber-900/10 cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500">
                        <i class="fas fa-ban mr-1.5" aria-hidden="true"></i>${t('groups_sticker_disable')}
                    </button>`}
                </div>`}
            </div>
        </div>
    </div>`;
}

function buildGroupsRoomsPanel(extra) {
    const rooms = Array.isArray(extra.rooms) ? extra.rooms : [];
    const selectedIds = Array.isArray(extra.selected_room_ids) ? extra.selected_room_ids : [];
    const selectedNames = Array.isArray(extra.selected_room_names) ? extra.selected_room_names : [];
    const admin = extra.admin || {};
    const adminMembers = Array.isArray(admin.members) ? admin.members : [];
    const blacklistMembers = Array.isArray(admin.blacklist_members) ? admin.blacklist_members : [];
    const requiredPermissions = admin.required_permissions || {};
    const permissionDefinitions = Array.isArray(admin.permission_definitions) ? admin.permission_definitions : [];
    const currentRoomId = groupsAdminState.roomId || selectedIds[0] || '';
    groupsAdminState.roomId = currentRoomId;
    const currentBlacklistRoomId = groupsBlacklistState.roomId || selectedIds[0] || '';
    groupsBlacklistState.roomId = currentBlacklistRoomId;
    return `<div class="h-full w-full flex flex-col min-h-0">
        <div class="flex items-start justify-between gap-4 mb-5 flex-shrink-0">
            ${buildGroupsPanelTitle('fa-user-shield', 'groups_rooms_title', 'groups_rooms_desc')}
            <button type="button" onclick="refreshWechatGroupRooms()"
                class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 cursor-pointer transition-colors">
                <i class="fas fa-rotate-right mr-1"></i>${t('wechat_group_rooms_refresh')}
            </button>
        </div>
        <div class="space-y-4">
            <section class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
                <label class="block text-sm font-medium text-slate-800 dark:text-slate-100 mb-2">${t('groups_rooms_select_label')}</label>
                ${buildGroupsRoomDropdown(rooms, selectedIds)}
                <div id="groups-room-selected-list" class="mt-3 min-h-[80px] max-h-[180px] overflow-y-auto rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-2">
                    ${renderGroupsSelectedRooms(rooms, selectedIds, selectedNames)}
                </div>
            </section>
            ${buildGroupsAdminPanel(rooms, selectedIds, adminMembers)}
            ${buildGroupsBlacklistPanel(rooms, selectedIds, blacklistMembers)}
            ${buildGroupsAdminPermissionsPanel(requiredPermissions, permissionDefinitions)}
        </div>
    </div>`;
}

function renderGroupsSelectedRooms(rooms, selectedIds, selectedNames) {
    const roomNameById = new Map();
    (rooms || []).forEach(room => {
        const name = String(room.name || '');
        [room.stable_room_id, room.id, room.runtime_room_id].forEach(key => {
            const id = String(key || '').trim();
            if (id && name) roomNameById.set(id, name);
        });
    });
    const selectedItems = (selectedIds || []).map((id, idx) => ({
        id: String(id || ''),
        label: roomNameById.get(String(id)) || selectedNames[idx] || t('groups_room_saved').replace('{n}', String(idx + 1)),
    }));
    return selectedItems.length ? `<div class="flex flex-wrap gap-1.5">${selectedItems.map(item => `
        <span class="inline-flex items-center gap-1 rounded-md bg-slate-100 dark:bg-white/10 px-2 py-1 text-xs text-slate-600 dark:text-slate-300 max-w-full">
            <span class="truncate">${escapeHtml(item.label)}</span>
            <button type="button" data-groups-selected-room-id="${escapeHtml(item.id)}" onclick="removeGroupsSelectedRoom(this.dataset.groupsSelectedRoomId, this)" class="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer" title="${escapeHtml(t('groups_rooms_remove'))}">
                <i class="fas fa-xmark text-[10px]"></i>
            </button>
        </span>`).join('')}</div>` : `<p class="text-xs text-slate-500 dark:text-slate-400">${t('groups_rooms_none_selected')}</p>`;
}

function resolveGroupsSelectedRoomIdsForSave(extra, checkedRoomIds, roomControlsPresent) {
    const persistedRoomIds = Array.isArray(extra.selected_room_ids)
        ? extra.selected_room_ids.map(id => String(id || '')).filter(Boolean)
        : [];
    if (!roomControlsPresent) return persistedRoomIds;
    const selectableRooms = (extra.rooms || []).filter(room => isWechatGroupRoomSelectable(room));
    const selectableRoomIds = new Set(
        selectableRooms
            .map(room => getWechatGroupRoomOptionId(room))
            .filter(Boolean)
    );
    // Also index runtime ids so a persisted stable id still maps to a selectable room.
    const selectableByAnyId = new Map();
    selectableRooms.forEach(room => {
        const optionId = getWechatGroupRoomOptionId(room);
        [room.stable_room_id, room.id, room.runtime_room_id].forEach(key => {
            const id = String(key || '').trim();
            if (id && optionId) selectableByAnyId.set(id, optionId);
        });
    });
    const checkedSet = new Set((checkedRoomIds || []).map(id => String(id || '')).filter(Boolean));
    const resolved = [];
    persistedRoomIds.forEach(roomId => {
        const optionId = selectableByAnyId.get(roomId) || roomId;
        const isSelectable = selectableRoomIds.has(optionId) || selectableByAnyId.has(roomId);
        if (!isSelectable || checkedSet.has(roomId) || checkedSet.has(optionId)) {
            if (!resolved.includes(optionId.startsWith('wgr_') ? optionId : roomId)) {
                resolved.push(optionId.startsWith('wgr_') ? optionId : roomId);
            }
        }
    });
    checkedSet.forEach(roomId => {
        const optionId = selectableByAnyId.get(roomId) || roomId;
        if (!resolved.includes(optionId)) resolved.push(optionId);
    });
    return resolved;
}

function getWechatGroupRoomOptionId(room = {}) {
    // Prefer stable room id so checkbox values match wechat_group_stable_room_ids.
    return String(room.stable_room_id || room.id || room.runtime_room_id || '').trim();
}

function isWechatGroupRoomSelected(room = {}, selectedSet) {
    if (!selectedSet || !selectedSet.size) return false;
    const candidates = [
        room.stable_room_id,
        room.id,
        room.runtime_room_id,
    ].map(value => String(value || '').trim()).filter(Boolean);
    return candidates.some(id => selectedSet.has(id));
}

function buildGroupsRoomDropdown(rooms, selectedIds) {
    const selectedSet = new Set((selectedIds || []).map(String).filter(Boolean));
    const items = rooms.length ? rooms.map(room => {
        const id = getWechatGroupRoomOptionId(room);
        const name = String(room.name || t('groups_room_unnamed'));
        const selectable = isWechatGroupRoomSelectable(room);
        const checked = selectable && isWechatGroupRoomSelected(room, selectedSet) ? 'checked' : '';
        const disabled = selectable ? '' : 'disabled';
        return `<label class="groups-room-option flex items-center gap-2 px-2.5 py-2 rounded-lg text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 ${selectable ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'}" data-room-name="${escapeHtml(name.toLowerCase())}">
            <input type="checkbox" class="accent-primary-500" data-groups-room-id="${escapeHtml(id)}" onchange="updateGroupsRoomSelectedCount()" ${checked} ${disabled}>
            <span class="flex-1 min-w-0 truncate">${escapeHtml(name)}</span>
            ${selectable ? '' : `<span class="text-[11px] text-amber-500">${escapeHtml(String(room.binding_status || 'identity_unresolved'))}</span>`}
        </label>`;
    }).join('') : `<p class="px-2 py-4 text-center text-xs text-slate-500 dark:text-slate-400">${t('wechat_group_rooms_empty')}</p>`;
    return `<div class="relative" id="groups-room-dropdown">
        <button type="button" onclick="toggleGroupsRoomDropdown()"
            class="w-full h-10 px-3 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 flex items-center justify-between gap-2 cursor-pointer transition-colors">
            <span>${selectedIds.length ? t('groups_rooms_selected_count').replace('{count}', String(selectedIds.length)) : t('groups_rooms_select_placeholder')}</span>
            <i class="fas fa-chevron-down text-xs text-slate-400"></i>
        </button>
        <div id="groups-room-dropdown-menu" class="hidden absolute left-0 right-0 top-[calc(100%+4px)] z-50 rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#1A1A1A] shadow-lg p-2">
            <div class="relative mb-2">
                <i class="fas fa-search absolute left-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-400"></i>
                <input id="groups-room-search" oninput="filterGroupsRooms()" placeholder="${escapeHtml(t('groups_rooms_search_placeholder'))}"
                    class="w-full pl-8 pr-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-white/5 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
            </div>
            <div id="groups-room-options" class="max-h-64 overflow-y-auto space-y-1">${items}</div>
        </div>
    </div>`;
}

function isWechatGroupRoomSelectable(room = {}) {
    const stableRoomId = String(room.stable_room_id || '').trim();
    const bindingStatus = String(room.binding_status || '').trim();
    const pendingStatuses = ['suspected', 'legacy_imported', 'conflict', 'identity_unresolved'];
    return !!stableRoomId
        && room.identity_requires_confirmation !== true
        && !pendingStatuses.includes(bindingStatus);
}

function buildGroupsAdminPanel(rooms, selectedIds, adminMembers) {
    const selectedSet = new Set((selectedIds || []).map(String).filter(Boolean));
    const selectableRooms = rooms.filter(room => isWechatGroupRoomSelected(room, selectedSet));
    const roomOptions = selectableRooms.map(room => {
        const id = getWechatGroupRoomOptionId(room);
        const name = String(room.name || id);
        return `<option value="${escapeHtml(id)}" ${groupsAdminState.roomId === id ? 'selected' : ''}>${escapeHtml(name)}</option>`;
    }).join('');
    return `<section class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
        <div class="mb-3">
            <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_admin_title')}</h4>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_admin_desc')}</p>
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-[260px_minmax(0,1fr)] gap-3">
            <label class="block">
                <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_admin_room_label')}</span>
                <select id="groups-admin-room" onchange="changeGroupsAdminRoom(this.value)"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                    ${roomOptions || `<option value="">${t('groups_admin_no_room')}</option>`}
                </select>
            </label>
            <div class="min-w-0">
                <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_admin_member_label')}</span>
                <div class="flex flex-col md:flex-row gap-2">
                    <input id="groups-admin-member-query" value="${escapeHtml(groupsAdminState.query || '')}"
                        onkeydown="if (event.key === 'Enter') searchGroupsAdminMembers()"
                        placeholder="${escapeHtml(t('groups_admin_member_search_placeholder'))}"
                        class="flex-1 min-w-0 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                    <button type="button" onclick="searchGroupsAdminMembers()"
                        class="px-3 py-2 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">
                        ${groupsAdminState.loading ? '<i class="fas fa-spinner fa-spin"></i>' : t('groups_admin_member_search')}
                    </button>
                    <button type="button" onclick="addGroupsSelectedAdmins()"
                        class="px-3 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-xs font-medium cursor-pointer transition-colors">
                        ${t('groups_admin_add_selected')}
                    </button>
                </div>
                <div id="groups-admin-member-results" class="mt-3 max-h-56 overflow-y-auto space-y-1">
                    ${renderGroupsAdminMemberResults()}
                </div>
            </div>
        </div>
        <div class="mt-4">
            <h5 class="text-xs font-semibold text-slate-600 dark:text-slate-300 mb-2">${t('groups_admin_selected_title')}</h5>
            <div id="groups-admin-selected-list" class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-2 min-h-[80px]">
                ${renderGroupsAdminSelectedList(adminMembers, rooms)}
            </div>
        </div>
    </section>`;
}

function renderGroupsAdminMemberResults() {
    const members = Array.isArray(groupsAdminState.members) ? groupsAdminState.members : [];
    if (!groupsAdminState.roomId) {
        return `<p class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] px-3 py-2 text-xs text-slate-500 dark:text-slate-400">${t('groups_admin_no_room')}</p>`;
    }
    if (!members.length) {
        return `<p class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] px-3 py-2 text-xs text-slate-500 dark:text-slate-400">${t('groups_admin_no_members')}</p>`;
    }
    const selected = groupsAdminState.selectedSenderIds || new Set();
    return members.map(member => {
        const senderId = String(member.sender_id || '');
        const stableMemberId = String(member.stable_member_id || '');
        const confirmed = !!stableMemberId && member.identity_status === 'confirmed';
        const nickname = String(member.sender_nickname || senderId);
        const wechatId = String(member.wechat_id || '');
        return `<label class="flex items-start gap-2 rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] px-3 py-2 text-sm text-slate-700 dark:text-slate-200 ${confirmed ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'}">
            <input type="checkbox" class="mt-1 accent-primary-500" onchange="toggleGroupsAdminCandidate('${escapeHtml(senderId)}', this.checked)" ${selected.has(senderId) ? 'checked' : ''} ${confirmed ? '' : 'disabled'}>
            <span class="min-w-0 flex-1">
                <span class="block font-medium break-words">${escapeHtml(nickname)}</span>
                <span class="block text-xs text-slate-400 dark:text-slate-500 font-mono break-all">${escapeHtml(wechatId || senderId)}</span>
                ${confirmed ? '' : `<span class="block text-[11px] text-amber-500 mt-1">${t('groups_identity_member_pending')}</span>`}
            </span>
        </label>`;
    }).join('');
}

function renderGroupsAdminSelectedList(adminMembers, rooms) {
    const members = Array.isArray(adminMembers) ? adminMembers : [];
    if (!members.length) {
        return `<p class="text-xs text-slate-500 dark:text-slate-400">${t('groups_admin_no_admins')}</p>`;
    }
    const roomNameById = new Map((rooms || []).map(room => [String(room.id || ''), String(room.name || '')]));
    return `<div class="flex flex-wrap gap-1.5">${members.map(member => {
        const roomId = String(member.room_id || '');
        const senderId = String(member.sender_id || '');
        const roomName = String(member.room_name || roomNameById.get(roomId) || roomId);
        const nickname = String(member.sender_nickname || member.wechat_id || senderId);
        return `<span class="inline-flex items-center gap-1 rounded-md bg-slate-100 dark:bg-white/10 px-2 py-1 text-xs text-slate-600 dark:text-slate-300 max-w-full">
            <span class="truncate">${escapeHtml(roomName)} / ${escapeHtml(nickname)}</span>
            <button type="button" onclick="removeGroupsAdminMember('${escapeHtml(roomId)}', '${escapeHtml(senderId)}')" class="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer" title="${escapeHtml(t('groups_admin_remove'))}">
                <i class="fas fa-xmark text-[10px]"></i>
            </button>
        </span>`;
    }).join('')}</div>`;
}

function changeGroupsAdminRoom(roomId) {
    groupsAdminState.roomId = roomId || '';
    groupsAdminState.members = [];
    groupsAdminState.selectedSenderIds = new Set();
    searchGroupsAdminMembers();
}

function searchGroupsAdminMembers() {
    const roomId = document.getElementById('groups-admin-room')?.value || '';
    const query = document.getElementById('groups-admin-member-query')?.value || '';
    const requestedRoomId = roomId;
    const requestedRequestId = (groupsAdminState.requestId || 0) + 1;
    groupsAdminState.roomId = roomId;
    groupsAdminState.query = query;
    groupsAdminState.requestId = requestedRequestId;
    if (!roomId) {
        groupsAdminState.members = [];
        renderGroupsView();
        return;
    }
    groupsAdminState.loading = true;
    renderGroupsView();
    fetch(`/api/wechat-group/members?stable_room_id=${encodeURIComponent(roomId)}&q=${encodeURIComponent(query)}&limit=500`)
        .then(r => r.json())
        .then(data => {
            if (groupsAdminState.roomId !== requestedRoomId) return;
            if (groupsAdminState.requestId !== requestedRequestId) return;
            groupsAdminState.members = data.status === 'success' ? (data.members || []) : [];
        })
        .catch(() => {
            if (groupsAdminState.roomId !== requestedRoomId) return;
            if (groupsAdminState.requestId !== requestedRequestId) return;
            groupsAdminState.members = [];
        })
        .finally(() => {
            if (groupsAdminState.roomId !== requestedRoomId) return;
            if (groupsAdminState.requestId !== requestedRequestId) return;
            groupsAdminState.loading = false;
            renderGroupsView();
        });
}

function toggleGroupsAdminCandidate(senderId, checked) {
    const next = new Set(groupsAdminState.selectedSenderIds || []);
    if (checked) next.add(senderId);
    else next.delete(senderId);
    groupsAdminState.selectedSenderIds = next;
}

function addGroupsSelectedAdmins() {
    const ch = getWechatGroupChannel();
    if (!ch) return;
    const extra = ch.extra || {};
    const roomId = groupsAdminState.roomId || document.getElementById('groups-admin-room')?.value || '';
    const selected = groupsAdminState.selectedSenderIds || new Set();
    const rooms = Array.isArray(extra.rooms) ? extra.rooms : [];
    const room = rooms.find(item => String(item.id || '') === roomId) || {};
    const current = Array.isArray(extra.admin?.members) ? extra.admin.members : [];
    const byKey = new Map(current.map(item => [`${item.room_id}::${item.sender_id}`, item]));
    (groupsAdminState.members || []).forEach(member => {
        const senderId = String(member.sender_id || '');
        const stableMemberId = String(member.stable_member_id || '');
        const runtimeSenderId = String(member.runtime_sender_id || member.sender_id || '');
        if (!selected.has(senderId) || !stableMemberId || member.identity_status !== 'confirmed') return;
        byKey.set(`${roomId}::${stableMemberId}`, {
            stable_room_id: roomId,
            stable_member_id: stableMemberId,
            room_id: roomId,
            room_name: String(room.name || ''),
            sender_id: stableMemberId,
            legacy_room_id: String(room.runtime_room_id || ''),
            legacy_sender_id: runtimeSenderId,
            identity_status: 'confirmed',
            sender_nickname: String(member.sender_nickname || senderId),
            wechat_id: String(member.wechat_id || ''),
        });
    });
    extra.admin = extra.admin || {};
    extra.admin.members = Array.from(byKey.values());
    groupsAdminState.selectedSenderIds = new Set();
    renderGroupsView();
}

function removeGroupsAdminMember(roomId, senderId) {
    const ch = getWechatGroupChannel();
    if (!ch) return;
    const extra = ch.extra || {};
    extra.admin = extra.admin || {};
    extra.admin.members = (extra.admin.members || []).filter(item => (
        String(item.room_id || '') !== String(roomId || '')
        || String(item.sender_id || '') !== String(senderId || '')
    ));
    renderGroupsView();
}

function buildGroupsBlacklistPanel(rooms, selectedIds, blacklistMembers) {
    const selectedSet = new Set((selectedIds || []).map(String).filter(Boolean));
    const selectableRooms = rooms.filter(room => isWechatGroupRoomSelected(room, selectedSet));
    const roomOptions = selectableRooms.map(room => {
        const id = getWechatGroupRoomOptionId(room);
        const name = String(room.name || id);
        return `<option value="${escapeHtml(id)}" ${groupsBlacklistState.roomId === id ? 'selected' : ''}>${escapeHtml(name)}</option>`;
    }).join('');
    return `<section class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
        <div class="mb-3">
            <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_blacklist_title')}</h4>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_blacklist_desc')}</p>
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-[260px_minmax(0,1fr)] gap-3">
            <label class="block">
                <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_blacklist_room_label')}</span>
                <select id="groups-blacklist-room" onchange="changeGroupsBlacklistRoom(this.value)"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                    ${roomOptions || `<option value="">${t('groups_blacklist_no_room')}</option>`}
                </select>
            </label>
            <div class="min-w-0">
                <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_blacklist_member_label')}</span>
                <div class="flex flex-col md:flex-row gap-2">
                    <input id="groups-blacklist-member-query" value="${escapeHtml(groupsBlacklistState.query || '')}"
                        onkeydown="if (event.key === 'Enter') searchGroupsBlacklistMembers()"
                        placeholder="${escapeHtml(t('groups_blacklist_member_search_placeholder'))}"
                        class="flex-1 min-w-0 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                    <button type="button" onclick="searchGroupsBlacklistMembers()"
                        class="px-3 py-2 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">
                        ${groupsBlacklistState.loading ? '<i class="fas fa-spinner fa-spin"></i>' : t('groups_blacklist_member_search')}
                    </button>
                    <button type="button" onclick="addGroupsSelectedBlacklistMembers()"
                        class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-900 dark:bg-slate-600 dark:hover:bg-slate-500 text-white text-xs font-medium cursor-pointer transition-colors">
                        ${t('groups_blacklist_add_selected')}
                    </button>
                </div>
                <div id="groups-blacklist-member-results" class="mt-3 max-h-56 overflow-y-auto space-y-1">
                    ${renderGroupsBlacklistMemberResults()}
                </div>
            </div>
        </div>
        <div class="mt-4">
            <h5 class="text-xs font-semibold text-slate-600 dark:text-slate-300 mb-2">${t('groups_blacklist_selected_title')}</h5>
            <div id="groups-blacklist-selected-list" class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-2 min-h-[80px]">
                ${renderGroupsBlacklistSelectedList(blacklistMembers, rooms)}
            </div>
        </div>
    </section>`;
}

function renderGroupsBlacklistMemberResults() {
    const members = Array.isArray(groupsBlacklistState.members) ? groupsBlacklistState.members : [];
    if (!groupsBlacklistState.roomId) {
        return `<p class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] px-3 py-2 text-xs text-slate-500 dark:text-slate-400">${t('groups_blacklist_no_room')}</p>`;
    }
    if (!members.length) {
        return `<p class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] px-3 py-2 text-xs text-slate-500 dark:text-slate-400">${t('groups_blacklist_no_members')}</p>`;
    }
    const selected = groupsBlacklistState.selectedSenderIds || new Set();
    return members.map(member => {
        const senderId = String(member.sender_id || '');
        const stableMemberId = String(member.stable_member_id || '');
        const confirmed = !!stableMemberId && member.identity_status === 'confirmed';
        const nickname = String(member.sender_nickname || senderId);
        const wechatId = String(member.wechat_id || '');
        return `<label class="flex items-start gap-2 rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] px-3 py-2 text-sm text-slate-700 dark:text-slate-200 ${confirmed ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'}">
            <input type="checkbox" class="mt-1 accent-primary-500" onchange="toggleGroupsBlacklistCandidate('${escapeHtml(senderId)}', this.checked)" ${selected.has(senderId) ? 'checked' : ''} ${confirmed ? '' : 'disabled'}>
            <span class="min-w-0 flex-1">
                <span class="block font-medium break-words">${escapeHtml(nickname)}</span>
                <span class="block text-xs text-slate-400 dark:text-slate-500 font-mono break-all">${escapeHtml(wechatId || senderId)}</span>
                ${confirmed ? '' : `<span class="block text-[11px] text-amber-500 mt-1">${t('groups_identity_member_pending')}</span>`}
            </span>
        </label>`;
    }).join('');
}

function renderGroupsBlacklistSelectedList(blacklistMembers, rooms) {
    const members = Array.isArray(blacklistMembers) ? blacklistMembers : [];
    if (!members.length) {
        return `<p class="text-xs text-slate-500 dark:text-slate-400">${t('groups_blacklist_no_items')}</p>`;
    }
    const roomNameById = new Map();
    (rooms || []).forEach(room => {
        const name = String(room.name || '');
        [room.id, room.stable_room_id, room.runtime_room_id].forEach(key => {
            const id = String(key || '').trim();
            if (id && name) roomNameById.set(id, name);
        });
    });
    return `<div class="flex flex-wrap gap-1.5">${members.map(member => {
        const roomId = String(member.room_id || member.stable_room_id || '');
        const senderId = String(member.sender_id || member.stable_member_id || '');
        const roomName = String(member.room_name || roomNameById.get(roomId) || roomId);
        const nickname = String(member.sender_nickname || member.wechat_id || senderId);
        return `<span class="inline-flex items-center gap-1 rounded-md bg-slate-100 dark:bg-white/10 px-2 py-1 text-xs text-slate-600 dark:text-slate-300 max-w-full">
            <span class="truncate">${escapeHtml(roomName)} / ${escapeHtml(nickname)}</span>
            <button type="button" onclick="removeGroupsBlacklistMember('${escapeHtml(roomId)}', '${escapeHtml(senderId)}')" class="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 cursor-pointer" title="${escapeHtml(t('groups_blacklist_remove'))}">
                <i class="fas fa-xmark text-[10px]"></i>
            </button>
        </span>`;
    }).join('')}</div>`;
}

function changeGroupsBlacklistRoom(roomId) {
    groupsBlacklistState.roomId = roomId || '';
    groupsBlacklistState.members = [];
    groupsBlacklistState.selectedSenderIds = new Set();
    searchGroupsBlacklistMembers();
}

function searchGroupsBlacklistMembers() {
    const roomId = document.getElementById('groups-blacklist-room')?.value || '';
    const query = document.getElementById('groups-blacklist-member-query')?.value || '';
    const requestedRoomId = roomId;
    const requestedRequestId = (groupsBlacklistState.requestId || 0) + 1;
    groupsBlacklistState.roomId = roomId;
    groupsBlacklistState.query = query;
    groupsBlacklistState.requestId = requestedRequestId;
    if (!roomId) {
        groupsBlacklistState.members = [];
        renderGroupsView();
        return;
    }
    groupsBlacklistState.loading = true;
    renderGroupsView();
    fetch(`/api/wechat-group/members?stable_room_id=${encodeURIComponent(roomId)}&q=${encodeURIComponent(query)}&limit=500`)
        .then(r => r.json())
        .then(data => {
            if (groupsBlacklistState.roomId !== requestedRoomId) return;
            if (groupsBlacklistState.requestId !== requestedRequestId) return;
            groupsBlacklistState.members = data.status === 'success' ? (data.members || []) : [];
        })
        .catch(() => {
            if (groupsBlacklistState.roomId !== requestedRoomId) return;
            if (groupsBlacklistState.requestId !== requestedRequestId) return;
            groupsBlacklistState.members = [];
        })
        .finally(() => {
            if (groupsBlacklistState.roomId !== requestedRoomId) return;
            if (groupsBlacklistState.requestId !== requestedRequestId) return;
            groupsBlacklistState.loading = false;
            renderGroupsView();
        });
}

function toggleGroupsBlacklistCandidate(senderId, checked) {
    const next = new Set(groupsBlacklistState.selectedSenderIds || []);
    if (checked) next.add(senderId);
    else next.delete(senderId);
    groupsBlacklistState.selectedSenderIds = next;
}

function addGroupsSelectedBlacklistMembers() {
    const ch = getWechatGroupChannel();
    if (!ch) return;
    const extra = ch.extra || {};
    const roomId = groupsBlacklistState.roomId || document.getElementById('groups-blacklist-room')?.value || '';
    const selected = groupsBlacklistState.selectedSenderIds || new Set();
    const rooms = Array.isArray(extra.rooms) ? extra.rooms : [];
    const room = rooms.find(item => (
        String(item.id || '') === roomId
        || String(item.stable_room_id || '') === roomId
        || String(item.runtime_room_id || '') === roomId
    )) || {};
    const current = Array.isArray(extra.admin?.blacklist_members) ? extra.admin.blacklist_members : [];
    const byKey = new Map(current.map(item => [`${item.room_id}::${item.sender_id}`, item]));
    (groupsBlacklistState.members || []).forEach(member => {
        const senderId = String(member.sender_id || '');
        const stableMemberId = String(member.stable_member_id || '');
        const runtimeSenderId = String(member.runtime_sender_id || member.sender_id || '');
        if (!selected.has(senderId) || !stableMemberId || member.identity_status !== 'confirmed') return;
        byKey.set(`${roomId}::${stableMemberId}`, {
            stable_room_id: roomId,
            stable_member_id: stableMemberId,
            room_id: roomId,
            room_name: String(room.name || ''),
            sender_id: stableMemberId,
            legacy_room_id: String(room.runtime_room_id || ''),
            legacy_sender_id: runtimeSenderId,
            identity_status: 'confirmed',
            sender_nickname: String(member.sender_nickname || senderId),
            wechat_id: String(member.wechat_id || ''),
        });
    });
    extra.admin = extra.admin || {};
    extra.admin.blacklist_members = Array.from(byKey.values());
    groupsBlacklistState.selectedSenderIds = new Set();
    renderGroupsView();
}

function removeGroupsBlacklistMember(roomId, senderId) {
    const ch = getWechatGroupChannel();
    if (!ch) return;
    const extra = ch.extra || {};
    extra.admin = extra.admin || {};
    extra.admin.blacklist_members = (extra.admin.blacklist_members || []).filter(item => (
        String(item.room_id || item.stable_room_id || '') !== String(roomId || '')
        || String(item.sender_id || item.stable_member_id || '') !== String(senderId || '')
    ));
    renderGroupsView();
}

const WECHAT_GROUP_ADMIN_PERMISSION_FALLBACKS = [
    { id: 'knowledge_write', label: '写入知识库', summary: '限制普通成员把资料保存、导入或整理到知识库。', blocked_behavior: '保存、导入、更新知识库或知识页。', allowed_behavior: '查询、引用、总结已有知识库内容。', examples: ['保存到知识库', '把这个资料学习一下'], guard_layers: ['通道意图识别', 'Agent 工具过滤', 'Prompt 权限提示'], affected_objects: ['knowledge/**', 'write', 'edit', '知识库索引'], default_enabled: true },
    { id: 'memory_write', label: '写入全局永久记忆', summary: '限制普通成员写入全局长期记忆。', blocked_behavior: '写入 MEMORY.md、每日记忆或全局长期记忆。', allowed_behavior: '搜索、读取、基于记忆回答。', examples: ['加入你的记忆库', '以后记住这件事'], guard_layers: ['通道意图识别', 'Agent 工具过滤', 'Prompt 权限提示'], affected_objects: ['MEMORY.md', 'memory/**', 'write', 'edit'], default_enabled: true },
    { id: 'wechat_group_memory_write', label: '写入/禁用群永久记忆', summary: '限制普通成员修改当前群的永久记忆。', blocked_behavior: '新增、更新、禁用当前群永久记忆。', allowed_behavior: '查询当前群记忆、基于群记忆回答。', examples: ['记到本群永久记忆', '删掉这条群记忆'], guard_layers: ['通道意图识别', '微信群工具过滤', 'Prompt 权限提示'], affected_objects: ['wechat_group_group_memories', '群记忆服务'], default_enabled: true },
    { id: 'wechat_group_profile_write', label: '管理群友画像', summary: '限制普通成员手动修改群友画像和别名。', blocked_behavior: '新增或修改群友画像、别名、常用词、发言风格。', allowed_behavior: '查询群友画像、基于画像调整称呼。', examples: ['把张三画像改成产品负责人', '给他加个别名'], guard_layers: ['通道意图识别', '微信群工具过滤', 'Prompt 权限提示'], affected_objects: ['wechat_group_member_profiles', 'wechat_group_member_profile_names'], default_enabled: true },
    { id: 'wechat_group_learning', label: '触发微信群学习沉淀', summary: '限制普通成员手动触发归档学习与沉淀任务。', blocked_behavior: '手动触发群学习任务，从归档批量沉淀画像或群记忆。', allowed_behavior: '普通聊天过程中被动归档消息。', examples: ['跑一次群学习', '把最近聊天沉淀一下'], guard_layers: ['通道意图识别', 'Web API 保护', 'Prompt 权限提示'], affected_objects: ['WechatGroupLearner', 'learning runs'], default_enabled: true },
    { id: 'self_evolution', label: '触发自主进化', summary: '限制普通成员要求机器人修改自身长期能力。', blocked_behavior: '触发自主进化、技能沉淀、长期能力修改。', allowed_behavior: '普通建议、反馈和问答。', examples: ['你进化一下', '把这次经验沉淀成技能'], guard_layers: ['通道意图识别', 'Agent 工具过滤', 'Prompt 权限提示'], affected_objects: ['agent/evolution', 'evolution_undo'], default_enabled: true },
    { id: 'workspace_write', label: '写入/编辑工作区文件', summary: '限制普通成员要求机器人改写本地工作区。', blocked_behavior: '创建、覆盖、编辑 workspace 文件或通过 shell 修改文件。', allowed_behavior: '读取允许访问的文件摘要，给手动操作建议。', examples: ['整理成 md 文件', '帮我改这个文件'], guard_layers: ['通道意图识别', 'Agent 工具过滤', 'Prompt 权限提示'], affected_objects: ['write', 'edit', 'bash', 'agent_workspace'], default_enabled: true },
    { id: 'wechat_group_config', label: '修改微信群配置/人设', summary: '限制普通成员通过群聊修改机器人配置。', blocked_behavior: '修改人设、群配置、管理员、运行状态。', allowed_behavior: '询问当前配置含义、请求说明。', examples: ['修改人设', '把这个群设成自由回复'], guard_layers: ['通道意图识别', 'Prompt 权限提示', '配置 API 保护'], affected_objects: ['wechat_group_* 配置', '人设 prompt'], default_enabled: true },
    { id: 'scheduler_write', label: '新增/修改定时任务', summary: '限制普通成员创建或变更持久化定时任务。', blocked_behavior: '创建、更新、删除定时任务或提醒。', allowed_behavior: '查询任务说明、让机器人解释如何手动设置。', examples: ['每天九点提醒我', '删除这个定时任务'], guard_layers: ['通道意图识别', 'Agent 工具过滤', 'Prompt 权限提示'], affected_objects: ['scheduler 工具', '任务存储'], default_enabled: true },
    { id: 'sticker_manage', label: '管理表情包/素材库', summary: '限制普通成员修改群素材库。', blocked_behavior: '收藏、禁用、改写表情包或素材库元数据。', allowed_behavior: '搜索和发送已启用表情包。', examples: ['禁用这个表情', '把这张图收进素材库'], guard_layers: ['通道意图识别', '微信群工具过滤', 'Prompt 权限提示'], affected_objects: ['wechat_group_stickers', '素材目录'], default_enabled: true },
];

function getGroupsAdminPermissionDefinitions(requiredPermissions = {}, permissionDefinitions = []) {
    const source = Array.isArray(permissionDefinitions) && permissionDefinitions.length
        ? permissionDefinitions
        : WECHAT_GROUP_ADMIN_PERMISSION_FALLBACKS;
    return source.map(item => {
        const id = String(item.id || '');
        const hasSavedState = Object.prototype.hasOwnProperty.call(requiredPermissions || {}, id);
        return {
            ...item,
            id,
            enabled: hasSavedState
                ? !!requiredPermissions[id]
                : item.enabled !== undefined ? !!item.enabled : item.default_enabled !== false,
        };
    }).filter(item => item.id);
}

function buildGroupsAdminPermissionsPanel(requiredPermissions = {}, permissionDefinitions = []) {
    const definitions = getGroupsAdminPermissionDefinitions(requiredPermissions, permissionDefinitions);
    return `<section class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
        <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_admin_permissions_title')}</h4>
        <p class="text-xs text-slate-500 dark:text-slate-400 mt-1 mb-3">${t('groups_admin_permissions_desc')}</p>
        <div class="space-y-2">
            ${definitions.map(item => renderGroupsAdminPermissionRow(item)).join('')}
        </div>
    </section>`;
}

function renderGroupsAdminPermissionRow(item) {
    const id = String(item.id || '');
    const enabled = item.enabled !== false;
    const expanded = groupsAdminState.expandedPermissionIds?.has(id);
    return `<div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
        <div class="flex items-start gap-3">
            <input type="checkbox"
                class="mt-1 accent-primary-500"
                data-groups-admin-permission="${escapeHtml(id)}"
                onchange="updateGroupsAdminPermissionStatus(this)"
                ${enabled ? 'checked' : ''}>
            <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                    <h5 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${escapeHtml(item.label || id)}</h5>
                    <span data-groups-admin-permission-status="${escapeHtml(id)}"
                        class="rounded-full px-2 py-0.5 text-[11px] ${enabled ? 'bg-primary-50 text-primary-600 dark:bg-primary-500/10 dark:text-primary-300' : 'bg-slate-100 text-slate-500 dark:bg-white/5 dark:text-slate-400'}">
                        ${enabled ? t('groups_admin_permission_enabled') : t('groups_admin_permission_disabled')}
                    </span>
                    <code class="text-[11px] text-slate-400 break-all">${escapeHtml(id)}</code>
                </div>
                <p class="mt-1 text-xs text-slate-500 dark:text-slate-400">${escapeHtml(item.summary || '')}</p>
            </div>
            <button type="button" onclick="toggleGroupsAdminPermissionDetails('${escapeHtml(id)}')"
                class="px-2 py-1 rounded-md border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 cursor-pointer transition-colors">
                ${t('groups_admin_permission_details')}
            </button>
        </div>
        ${expanded ? renderGroupsAdminPermissionDetails(item) : ''}
    </div>`;
}

function renderGroupsAdminPermissionDetails(item) {
    return `<dl class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
        ${renderGroupsAdminPermissionDetail('groups_admin_permission_blocked_behavior', item.blocked_behavior)}
        ${renderGroupsAdminPermissionDetail('groups_admin_permission_allowed_behavior', item.allowed_behavior)}
        ${renderGroupsAdminPermissionDetail('groups_admin_permission_examples', item.examples)}
        ${renderGroupsAdminPermissionDetail('groups_admin_permission_guard_layers', item.guard_layers)}
        ${renderGroupsAdminPermissionDetail('groups_admin_permission_affected_objects', item.affected_objects)}
    </dl>`;
}

function renderGroupsAdminPermissionDetail(labelKey, value) {
    const values = Array.isArray(value) ? value : [value];
    const filtered = values.map(item => String(item || '').trim()).filter(Boolean);
    if (!filtered.length) return '';
    return `<div class="rounded-md bg-slate-50 dark:bg-white/5 p-2">
        <dt class="font-medium text-slate-600 dark:text-slate-300">${t(labelKey)}</dt>
        <dd class="mt-1 text-slate-500 dark:text-slate-400 break-words">${filtered.map(item => `<span class="inline-block mr-1 mb-1">${escapeHtml(item)}</span>`).join('')}</dd>
    </div>`;
}

function toggleGroupsAdminPermissionDetails(permissionId) {
    const next = new Set(groupsAdminState.expandedPermissionIds || []);
    if (next.has(permissionId)) next.delete(permissionId);
    else next.add(permissionId);
    groupsAdminState.expandedPermissionIds = next;
    renderGroupsView();
}

function updateGroupsAdminPermissionStatus(el) {
    const id = el?.dataset?.groupsAdminPermission || '';
    const ch = getWechatGroupChannel();
    if (ch) {
        ch.extra = ch.extra || {};
        ch.extra.admin = ch.extra.admin || {};
        ch.extra.admin.required_permissions = ch.extra.admin.required_permissions || {};
        ch.extra.admin.required_permissions[id] = !!el.checked;
    }
    const target = document.querySelector(`[data-groups-admin-permission-status="${id}"]`);
    if (target) {
        target.textContent = el.checked ? t('groups_admin_permission_enabled') : t('groups_admin_permission_disabled');
        target.className = `rounded-full px-2 py-0.5 text-[11px] ${el.checked ? 'bg-primary-50 text-primary-600 dark:bg-primary-500/10 dark:text-primary-300' : 'bg-slate-100 text-slate-500 dark:bg-white/5 dark:text-slate-400'}`;
    }
}

function buildGroupsPersonaPanel(extra) {
    const persona = extra.persona || {};
    const prompt = String(persona.prompt || '');
    const maxLength = Number(persona.max_length || 6000);
    return `<div class="h-full w-full flex flex-col min-h-0">
        ${buildGroupsPanelTitle('fa-user-pen', 'groups_persona_title', 'groups_persona_desc')}
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 flex flex-col flex-1 min-h-0">
            <label class="block text-sm font-medium text-slate-800 dark:text-slate-100 mb-1.5">${t('wechat_group_persona_prompt_label')}</label>
            <textarea id="groups-persona-prompt" rows="16" maxlength="${maxLength}" oninput="updateGroupsPersonaCount()"
                class="flex-1 min-h-[360px] w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors resize-none"
                placeholder="${escapeHtml(t('wechat_group_persona_prompt_placeholder'))}">${escapeHtml(prompt)}</textarea>
            <div class="flex items-center justify-between gap-3 mt-2">
                <p class="text-xs text-slate-500 dark:text-slate-400">${t('wechat_group_persona_boundary')}</p>
                <span class="text-xs text-slate-500 dark:text-slate-400 tabular-nums"><span id="groups-persona-count">${prompt.length}</span>/${maxLength}</span>
            </div>
        </div>
    </div>`;
}

function getGroupsMemoryRooms(extra) {
    const rooms = Array.isArray(extra.rooms) ? extra.rooms : [];
    const selectedIds = Array.isArray(extra.selected_room_ids) ? extra.selected_room_ids.map(String).filter(Boolean) : [];
    const selectedNames = Array.isArray(extra.selected_room_names) ? extra.selected_room_names : [];
    const roomNameById = new Map(rooms.map(room => [String(room.id || ''), String(room.name || '')]));
    return selectedIds.map((id, idx) => ({
        id,
        name: roomNameById.get(id) || selectedNames[idx] || t('groups_room_saved').replace('{n}', String(idx + 1)),
    }));
}

function ensureGroupsMemoryLoaded(extra) {
    const rooms = getGroupsMemoryRooms(extra);
    if (!rooms.length) return;
    const stillSelected = rooms.some(room => room.id === groupsMemoryState.selectedRoomId);
    if (!groupsMemoryState.selectedRoomId || !stillSelected) {
        groupsMemoryState.selectedRoomId = rooms[0].id;
        groupsMemoryState.loadedRoomId = '';
        groupsMemoryState.preview = null;
    }
    if (!groupsMemoryState.loading && groupsMemoryState.loadedRoomId !== groupsMemoryState.selectedRoomId) {
        refreshGroupsMemoryData(groupsMemoryState.selectedRoomId);
    }
}

function ensureGroupsProfilesLoaded(extra) {
    const rooms = getGroupsMemoryRooms(extra);
    if (!rooms.length) {
        groupsProfilesState.roomFilter = '';
        groupsProfilesState.profiles = [];
        groupsProfilesState.members = [];
        groupsProfilesState.total = 0;
        return;
    }
    if (!groupsProfilesState.roomFilter || !rooms.some(room => room.id === groupsProfilesState.roomFilter)) {
        groupsProfilesState.roomFilter = rooms[0].id;
        groupsProfilesState.loadedRoomFilter = null;
        groupsProfilesState.loadedMembersRoom = '';
        groupsProfilesState.selectedSenderId = '';
    }
    const needsLoad = !groupsProfilesState.loading && (
        groupsProfilesState.loadedQuery !== groupsProfilesState.query
        || groupsProfilesState.loadedRoomFilter !== groupsProfilesState.roomFilter
    );
    if (needsLoad) {
        refreshGroupsProfilesData();
    }
}

function buildGroupsProfilesPanel(extra) {
    const rooms = getGroupsMemoryRooms(extra);
    if (!rooms.length) {
        return `<div class="h-full w-full">
            ${buildGroupsPanelTitle('fa-id-card', 'groups_profiles_title', 'groups_profiles_desc')}
            <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-6 text-sm text-slate-500 dark:text-slate-400">
                ${t('groups_memory_no_room')}
            </div>
        </div>`;
    }
    const profiles = groupsProfilesState.profiles || [];
    const profileMemberIds = new Set(profiles.map(profile => String(profile.stable_member_id || profile.sender_id || '')));
    const availableMembers = (groupsProfilesState.members || []).filter(member => {
        const memberId = String(member.stable_member_id || '');
        return memberId && !profileMemberIds.has(memberId);
    });
    const selectedProfile = getGroupsProfilesSelectedProfile();
    return `<div class="h-full w-full flex flex-col min-h-0">
        ${buildGroupsPanelTitle('fa-id-card', 'groups_profiles_title', 'groups_profiles_desc')}
        <div class="flex flex-wrap items-end gap-3 mb-4">
            <label class="block min-w-[220px]">
                <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_profiles_room_filter')}</span>
                <select id="groups-profiles-room-filter" onchange="refreshGroupsProfilesData(true)"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors">
                    ${rooms.map(room => `<option value="${escapeHtml(room.id)}" ${groupsProfilesState.roomFilter === room.id ? 'selected' : ''}>${escapeHtml(room.name || room.id)}</option>`).join('')}
                </select>
            </label>
            <label class="block flex-1 min-w-[260px]">
                <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_profiles_search')}</span>
                <input id="groups-profiles-search" type="text" value="${escapeHtml(groupsProfilesState.query || '')}"
                    onkeydown="if (event.key === 'Enter') refreshGroupsProfilesData(true)"
                    placeholder="${escapeHtml(t('groups_profiles_search_placeholder'))}"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors">
            </label>
            <button type="button" onclick="refreshGroupsProfilesData(true)"
                class="px-3 py-2 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">
                ${t('groups_profiles_search')}
            </button>
            <label class="block min-w-[220px]">
                <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_profiles_create_member')}</span>
                <select id="groups-profiles-create-member"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors">
                    <option value="">${availableMembers.length ? t('groups_profiles_create_member') : t('groups_profiles_no_members')}</option>
                    ${availableMembers.map(member => {
                        const memberId = String(member.stable_member_id || '');
                        const memberName = String(member.sender_nickname || member.profile_nickname || memberId);
                        return `<option value="${escapeHtml(memberId)}" data-member-name="${escapeHtml(memberName)}">${escapeHtml(memberName)}</option>`;
                    }).join('')}
                </select>
            </label>
            <button type="button" onclick="startGroupsProfileCreate()" ${availableMembers.length ? '' : 'disabled'}
                class="px-3 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-xs font-medium cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                ${t('groups_profiles_create')}
            </button>
            <span class="ml-auto text-xs text-slate-500 dark:text-slate-400">${t('groups_profiles_result_count').replace('{count}', String(groupsProfilesState.total || 0))}</span>
        </div>
        <div class="flex-1 min-h-0 grid grid-cols-1 xl:grid-cols-[minmax(320px,0.9fr)_minmax(0,1.4fr)] gap-4">
            <section class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 min-h-0 flex flex-col">
                <div class="flex items-center justify-between gap-3 mb-3">
                    <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_profiles_list_title')}</h4>
                    ${groupsProfilesState.loading ? `<span class="text-xs text-slate-500 dark:text-slate-400"><i class="fas fa-spinner fa-spin mr-1"></i>${t('groups_loading')}</span>` : ''}
                </div>
                <div id="groups-profiles-list" class="flex-1 min-h-[320px] overflow-y-auto space-y-2">
                    ${buildGroupsProfilesList(profiles, selectedProfile?.sender_id || '')}
                </div>
            </section>
            <section id="groups-profiles-detail" class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 min-h-0 overflow-y-auto">
                ${buildGroupsProfilesDetail(selectedProfile)}
            </section>
        </div>
    </div>`;
}

function buildGroupsProfilesList(profiles, selectedSenderId) {
    if (!profiles.length) {
        return `<p class="text-sm text-slate-500 dark:text-slate-400">${t('groups_profiles_no_data')}</p>`;
    }
    return profiles.map(profile => {
        const senderId = profile.sender_id || '';
        const aliases = Array.isArray(profile.aliases) ? profile.aliases : [];
        const nameRecords = Array.isArray(profile.name_records) ? profile.name_records : [];
        const active = senderId === selectedSenderId;
        return `<button type="button" onclick="selectGroupsProfile(this)"
            data-sender-id="${escapeHtml(senderId)}"
            class="w-full text-left rounded-lg border px-3 py-3 cursor-pointer transition-colors ${active ? 'border-primary-300 dark:border-primary-700 bg-primary-50 dark:bg-primary-900/20' : 'border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] hover:bg-slate-50 dark:hover:bg-white/5'}">
            <div class="flex items-start gap-3">
                <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                        <span class="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">${escapeHtml(profile.primary_nickname || senderId)}</span>
                        <span class="text-[11px] text-slate-400 dark:text-slate-500 whitespace-nowrap">${t('groups_profiles_name_records').replace('{count}', String(nameRecords.length))}</span>
                    </div>
                    <div class="mt-1 text-[11px] font-mono text-slate-400 dark:text-slate-500 truncate">${escapeHtml(senderId)}</div>
                    ${aliases.length ? `<div class="mt-2 text-xs text-slate-500 dark:text-slate-400 truncate">${escapeHtml(aliases.join(' / '))}</div>` : ''}
                    <div class="mt-2 flex flex-wrap gap-1">
                        <span class="rounded-full border border-slate-200 dark:border-white/10 px-2 py-0.5 text-[11px] text-slate-500 dark:text-slate-400">${t('groups_profiles_metric_messages')} ${escapeHtml(String(profile.msg_count || 0))}</span>
                        <span class="rounded-full border border-slate-200 dark:border-white/10 px-2 py-0.5 text-[11px] text-slate-500 dark:text-slate-400">${t('groups_profiles_metric_activity')} ${escapeHtml(String(profile.activity_score || 0))}</span>
                    </div>
                </div>
            </div>
        </button>`;
    }).join('');
}

function buildGroupsProfilesDetail(profile) {
    if (!profile) {
        return `<div class="h-full min-h-[320px] flex items-center justify-center text-sm text-slate-500 dark:text-slate-400">${t('groups_profiles_detail_empty')}</div>`;
    }
    const roomSummaries = Array.isArray(profile.room_summaries) ? profile.room_summaries : [];
    const nameRecords = Array.isArray(profile.name_records) ? profile.name_records : [];
    const last_seen_at = profile.last_seen_at || 0;
    const aliases = Array.isArray(profile.aliases) ? profile.aliases : [];
    return `<div class="space-y-4">
        <div>
            <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                    <h4 class="text-base font-semibold text-slate-800 dark:text-slate-100 truncate">${escapeHtml(profile.primary_nickname || profile.sender_id || '')}</h4>
                    <p class="mt-1 font-mono text-xs text-slate-400 dark:text-slate-500 break-all">${escapeHtml(profile.sender_id || '')}</p>
                </div>
                <span class="rounded-full border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] px-2 py-1 text-[11px] text-slate-500 dark:text-slate-400 whitespace-nowrap">${t('groups_profiles_last_seen')} ${escapeHtml(formatGroupsProfileTimestamp(last_seen_at))}</span>
            </div>
            ${aliases.length ? `<div class="mt-3 flex flex-wrap gap-1.5">${aliases.map(alias => `<span class="rounded-full bg-white dark:bg-[#111111] border border-slate-200 dark:border-white/10 px-2 py-0.5 text-xs text-slate-600 dark:text-slate-300">${escapeHtml(alias)}</span>`).join('')}</div>` : ''}
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
                <div class="text-[11px] text-slate-400 dark:text-slate-500">${t('groups_profiles_metric_messages')}</div>
                <div class="mt-1 text-lg font-semibold text-slate-800 dark:text-slate-100">${escapeHtml(String(profile.msg_count || 0))}</div>
            </div>
            <div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
                <div class="text-[11px] text-slate-400 dark:text-slate-500">${t('groups_profiles_metric_activity')}</div>
                <div class="mt-1 text-lg font-semibold text-slate-800 dark:text-slate-100">${escapeHtml(String(profile.activity_score || 0))}</div>
            </div>
            <div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
                <div class="text-[11px] text-slate-400 dark:text-slate-500">${t('groups_profiles_metric_intimacy')}</div>
                <div class="mt-1 text-lg font-semibold text-slate-800 dark:text-slate-100">${escapeHtml(String(profile.intimacy_score || 0))}</div>
            </div>
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-4">
            <h5 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_profiles_summary_title')}</h5>
            <p class="mt-3 text-xs text-slate-500 dark:text-slate-400 whitespace-pre-wrap break-words">${escapeHtml(profile.content || '')}</p>
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-4">
            <div class="flex items-center justify-between gap-3">
                <h5 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_profiles_rooms_title')}</h5>
                <span class="text-[11px] text-slate-400 dark:text-slate-500">${t('groups_profiles_name_records').replace('{count}', String(nameRecords.length))}</span>
            </div>
            <div class="mt-3 space-y-2">
                ${roomSummaries.length ? roomSummaries.map(item => `
                    <div class="rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 px-3 py-2">
                        <div class="flex items-center gap-2">
                            <span class="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">${escapeHtml(item.room_name || t('groups_room_unnamed'))}</span>
                            <span class="ml-auto text-[11px] text-slate-400 dark:text-slate-500 whitespace-nowrap">${escapeHtml(formatGroupsProfileTimestamp(item.last_seen_at || 0))}</span>
                        </div>
                        <div class="mt-1 font-mono text-[11px] text-slate-400 dark:text-slate-500 break-all">${escapeHtml(item.room_id || '')}</div>
                        ${Array.isArray(item.display_names) && item.display_names.length ? `<div class="mt-2 text-xs text-slate-500 dark:text-slate-400">${escapeHtml(item.display_names.join(' / '))}</div>` : ''}
                    </div>
                `).join('') : `<p class="text-sm text-slate-500 dark:text-slate-400">${t('groups_profiles_room_empty')}</p>`}
            </div>
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-4">
            <h5 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">${t('groups_profiles_edit_title')}</h5>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                ${buildGroupsMemoryInput('groups-profiles-detail-sender-id', 'groups_memory_sender_id', profile.stable_member_id || profile.sender_id || '', 'font-mono', true)}
                ${buildGroupsMemoryInput('groups-profiles-detail-nickname', 'groups_memory_sender_name', profile.primary_nickname || '')}
                ${buildGroupsMemoryInput('groups-profiles-detail-aliases', 'groups_memory_aliases', aliases.join(', '))}
                ${buildGroupsMemoryInput('groups-profiles-detail-role', 'groups_memory_role', profile.speak_style || '')}
                ${buildGroupsMemoryInput('groups-profiles-detail-preferences', 'groups_memory_preferences', Array.isArray(profile.interests) ? profile.interests.join(', ') : '')}
                ${buildGroupsMemoryInput('groups-profiles-detail-common-words', 'groups_memory_common_words', Array.isArray(profile.common_words) ? profile.common_words.join(', ') : '')}
            </div>
            <div class="flex justify-end mt-3">
                <button type="button" onclick="saveGroupsProfileDetail()" class="px-3 py-1.5 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-xs font-medium cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    ${t('groups_profiles_save')}
                </button>
            </div>
        </div>
    </div>`;
}

function getGroupsProfilesSelectedProfile() {
    const profiles = groupsProfilesState.profiles || [];
    return profiles.find(item => item.sender_id === groupsProfilesState.selectedSenderId) || profiles[0] || null;
}

function selectGroupsProfile(target) {
    const senderId = typeof target === 'string'
        ? target
        : (target?.dataset?.senderId || '');
    if (!senderId) return;
    groupsProfilesState.selectedSenderId = senderId;
    renderGroupsView();
}

function refreshGroupsProfilesData(fromInputs = false) {
    if (fromInputs) {
        groupsProfilesState.query = (document.getElementById('groups-profiles-search')?.value || '').trim();
        groupsProfilesState.roomFilter = (document.getElementById('groups-profiles-room-filter')?.value || '').trim();
    }
    if (!groupsProfilesState.roomFilter) {
        groupsProfilesState.loading = false;
        groupsProfilesState.profiles = [];
        groupsProfilesState.members = [];
        groupsProfilesState.total = 0;
        renderGroupsView();
        return;
    }
    groupsProfilesState.loading = true;
    renderGroupsView();
    const params = new URLSearchParams();
    if (groupsProfilesState.query) params.set('q', groupsProfilesState.query);
    params.set('stable_room_id', groupsProfilesState.roomFilter);
    params.set('limit', '200');
    const membersRequest = groupsProfilesState.loadedMembersRoom === groupsProfilesState.roomFilter
        ? Promise.resolve({ status: 'success', members: groupsProfilesState.members })
        : fetch(`/api/wechat-group/members?stable_room_id=${encodeURIComponent(groupsProfilesState.roomFilter)}&limit=500`).then(r => r.json());
    Promise.all([
        fetch(`/api/wechat-group/memories/profiles?${params.toString()}`).then(r => r.json()),
        membersRequest,
    ]).then(([profileData, memberData]) => {
            if (profileData.status !== 'success') throw new Error(profileData.message || 'profile load failed');
            if (memberData.status !== 'success') throw new Error(memberData.message || 'member load failed');
            groupsProfilesState.profiles = profileData.profiles || [];
            groupsProfilesState.members = memberData.members || [];
            groupsProfilesState.total = Number(profileData.total || groupsProfilesState.profiles.length);
            groupsProfilesState.loadedQuery = groupsProfilesState.query;
            groupsProfilesState.loadedRoomFilter = groupsProfilesState.roomFilter;
            groupsProfilesState.loadedMembersRoom = groupsProfilesState.roomFilter;
            if (!groupsProfilesState.profiles.some(item => item.sender_id === groupsProfilesState.selectedSenderId)) {
                groupsProfilesState.selectedSenderId = groupsProfilesState.profiles[0]?.sender_id || '';
            }
        })
        .catch(err => {
            groupsProfilesState.profiles = [];
            groupsProfilesState.total = 0;
            groupsProfilesState.selectedSenderId = '';
            showGroupsStatus(err.message || 'groups_load_failed', true);
        })
        .finally(() => {
            groupsProfilesState.loading = false;
            renderGroupsView();
        });
}

function startGroupsProfileCreate() {
    const select = document.getElementById('groups-profiles-create-member');
    const stableMemberId = String(select?.value || '').trim();
    if (!stableMemberId || !stableMemberId.startsWith('wgm_')) {
        showGroupsStatus('groups_profiles_create_member', true);
        return;
    }
    const selectedOption = select.options[select.selectedIndex];
    const nickname = String(selectedOption?.dataset?.memberName || '').trim();
    const draft = {
        stable_room_id: groupsProfilesState.roomFilter,
        room_id: groupsProfilesState.roomFilter,
        stable_member_id: stableMemberId,
        sender_id: stableMemberId,
        primary_nickname: nickname,
        aliases: [],
        interests: [],
        common_words: [],
        speak_style: '',
        msg_count: 0,
        activity_score: 0,
        intimacy_score: 0,
        name_records: [],
        room_summaries: [],
        is_draft: true,
    };
    groupsProfilesState.profiles = [
        draft,
        ...(groupsProfilesState.profiles || []).filter(item => item.sender_id !== stableMemberId),
    ];
    groupsProfilesState.selectedSenderId = stableMemberId;
    renderGroupsView();
}

function saveGroupsProfileDetail() {
    const senderId = (document.getElementById('groups-profiles-detail-sender-id')?.value || '').trim();
    if (!senderId) {
        showGroupsStatus('groups_memory_sender_id', true);
        return;
    }
    const stableMemberId = senderId.startsWith('wgm_') ? senderId : '';
    if (!groupsProfilesState.roomFilter || !stableMemberId) {
        showGroupsStatus('groups_memory_sender_id', true);
        return;
    }
    fetch('/api/wechat-group/memories/profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            stable_room_id: groupsProfilesState.roomFilter || '',
            runtime_room_id: '',
            room_name: '',
            stable_member_id: stableMemberId,
            primary_nickname: document.getElementById('groups-profiles-detail-nickname')?.value || '',
            aliases: document.getElementById('groups-profiles-detail-aliases')?.value || '',
            speak_style: document.getElementById('groups-profiles-detail-role')?.value || '',
            interests: document.getElementById('groups-profiles-detail-preferences')?.value || '',
            common_words: document.getElementById('groups-profiles-detail-common-words')?.value || '',
        }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'save failed');
        groupsProfilesState.selectedSenderId = data.profile?.stable_member_id || stableMemberId;
        showGroupsStatus('groups_memory_profile_saved', false);
        groupsProfilesState.loadedQuery = null;
        groupsProfilesState.loadedRoomFilter = null;
        refreshGroupsProfilesData();
    }).catch(err => showGroupsStatus(err.message || 'channels_save_error', true));
}

function formatGroupsProfileTimestamp(value) {
    const timestamp = Number(value || 0);
    if (!timestamp) return '-';
    const date = new Date(timestamp < 1000000000000 ? timestamp * 1000 : timestamp);
    if (Number.isNaN(date.getTime())) return '-';
    return formatTime(date);
}

function formatGroupsMemoryRunTimestamp(value) {
    if (value === null || value === undefined || value === '') return '';
    const raw = String(value).trim();
    const numeric = Number(raw);
    const date = raw && Number.isFinite(numeric) && /^\d+(\.\d+)?$/.test(raw)
        ? new Date(numeric < 1000000000000 ? numeric * 1000 : numeric)
        : new Date(raw);
    if (Number.isNaN(date.getTime())) return raw;
    const pad = (part) => String(part).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function buildGroupsMemoryPanel(extra) {
    const rooms = getGroupsMemoryRooms(extra);
    if (!rooms.length) {
        return `<div class="h-full w-full">
            ${buildGroupsPanelTitle('fa-brain', 'groups_memory_title', 'groups_memory_desc')}
            <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-6 text-sm text-slate-500 dark:text-slate-400">
                ${t('groups_memory_no_room')}
            </div>
        </div>`;
    }
    const selectedRoomId = groupsMemoryState.selectedRoomId || rooms[0].id;
    return `<div class="h-full w-full flex flex-col min-h-0">
        ${buildGroupsPanelTitle('fa-brain', 'groups_memory_title', 'groups_memory_desc')}
        <div class="flex-1 min-h-0 grid grid-cols-1 xl:grid-cols-[260px_minmax(0,1fr)] gap-4">
            <aside class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-3 overflow-y-auto" id="groups-memory-room-list">
                ${rooms.map(room => {
                    const active = room.id === selectedRoomId;
                    return `<button type="button" onclick="selectGroupsMemoryRoom('${escapeHtml(room.id)}')"
                        class="w-full text-left rounded-lg px-3 py-2 mb-1 cursor-pointer transition-colors ${active ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-300' : 'text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5'}">
                        <span class="block text-sm font-medium truncate">${escapeHtml(room.name || room.id)}</span>
                        <span class="block text-[11px] font-mono text-slate-400 dark:text-slate-500 truncate">${escapeHtml(room.id)}</span>
                    </button>`;
                }).join('')}
            </aside>
            <section class="min-w-0 min-h-0 overflow-y-auto space-y-4">
                ${buildGroupsMemoryTabs()}
                ${groupsMemoryState.activeTab === 'auto'
                    ? buildGroupsMemoryLearningPanel(selectedRoomId, extra)
                    : `<div class="space-y-4">
                        ${buildGroupsMemoryProfilesMovedPanel()}
                        ${buildGroupsMemoryGroupPanel(selectedRoomId)}
                    </div>
                    ${buildGroupsMemoryPreviewPanel(selectedRoomId)}`}
            </section>
        </div>
    </div>`;
}

function buildGroupsMemoryTabs() {
    const tabs = [
        ['manual', 'groups_memory_tab_manual'],
        ['auto', 'groups_memory_tab_auto'],
    ];
    return `<div class="inline-flex rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-1">
        ${tabs.map(([id, labelKey]) => {
            const active = groupsMemoryState.activeTab === id;
            return `<button type="button" onclick="setGroupsMemoryTab('${id}')"
                class="px-3 py-1.5 rounded-md text-xs font-medium cursor-pointer transition-colors ${active ? 'bg-white dark:bg-[#111111] text-primary-600 dark:text-primary-300 shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-100'}">
                ${t(labelKey)}
            </button>`;
        }).join('')}
    </div>`;
}

function setGroupsMemoryTab(tab) {
    groupsMemoryState.activeTab = tab === 'auto' ? 'auto' : 'manual';
    renderGroupsView();
}

function buildGroupsMemoryProfilesMovedPanel() {
    return `<div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
                <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_memory_profiles_title')}</h4>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_memory_profiles_moved_hint')}</p>
            </div>
            <button type="button" onclick="goToGroupsProfilesSection()"
                class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">
                ${t('groups_nav_profiles')}
            </button>
        </div>
    </div>`;
}

function goToGroupsProfilesSection() {
    groupsActiveSection = 'profiles';
    renderGroupsView();
}

function buildGroupsMemoryGroupPanel(roomId) {
    const loading = groupsMemoryState.loading && groupsMemoryState.selectedRoomId === roomId;
    const memories = groupsMemoryState.memories || [];
    const summary = groupsMemoryState.summary || {};
    const search = groupsMemoryState.search || '';
    const listHtml = loading
        ? `<p class="text-xs text-slate-500 dark:text-slate-400"><i class="fas fa-spinner fa-spin mr-1"></i>${t('groups_loading')}</p>`
            : memories.length
            ? memories.map(item => {
                const memoryId = item.memory_id || item.id || '';
                return `<div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
                <p class="text-sm text-slate-700 dark:text-slate-200 whitespace-pre-wrap break-words">${escapeHtml(item.content || '')}</p>
                <div class="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400 dark:text-slate-500">
                    <span class="font-mono">${escapeHtml(item.source_kind || 'manual')}</span>
                    ${memoryId ? `<span class="font-mono break-all">${escapeHtml(memoryId)}</span>` : ''}
                    <button type="button" onclick="disableGroupsGroupMemory('${escapeHtml(memoryId)}')"
                        class="ml-auto px-2 py-1 rounded border border-slate-200 dark:border-white/10 text-slate-500 dark:text-slate-400 hover:text-red-500 hover:border-red-200 dark:hover:border-red-900 cursor-pointer transition-colors">
                        ${t('groups_memory_disable')}
                    </button>
                </div>
            </div>`;
            }).join('')
            : `<p class="text-xs text-slate-500 dark:text-slate-400">${t('groups_memory_empty')}</p>`;
    return `<div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 min-w-0">
        <div class="mb-3 flex items-start justify-between gap-3">
            <div>
                <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_memory_group_title')}</h4>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_memory_group_hint')}</p>
            </div>
            <div class="flex flex-col items-end gap-1 text-[11px] text-slate-500 dark:text-slate-400 flex-shrink-0">
                <span class="rounded-full bg-white dark:bg-[#111111] border border-slate-200 dark:border-white/10 px-2 py-0.5">${t('groups_memory_count_label').replace('{count}', String(summary.group_memory_count || 0))}</span>
                <span class="rounded-full bg-white dark:bg-[#111111] border border-slate-200 dark:border-white/10 px-2 py-0.5">${t('groups_memory_profile_count_label').replace('{count}', String(summary.profile_count || 0))}</span>
            </div>
        </div>
        <div class="mb-3 flex gap-2">
            <input id="groups-memory-search" type="text" value="${escapeHtml(search)}"
                class="flex-1 min-w-0 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors"
                placeholder="${escapeHtml(t('groups_memory_search_placeholder'))}">
            <button type="button" onclick="applyGroupsMemorySearch()"
                class="px-3 py-2 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors">
                ${t('groups_memory_search')}
            </button>
        </div>
        <label class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_memory_content_label')}</label>
        <textarea id="groups-memory-group-content" rows="4"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors resize-y"
            placeholder="${escapeHtml(t('groups_memory_content_placeholder'))}"></textarea>
        <label class="block text-xs font-medium text-slate-600 dark:text-slate-400 mt-3 mb-1.5">${t('groups_memory_summary_label')}</label>
        <input id="groups-memory-group-summary" type="text"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors">
        <div class="flex justify-end mt-3">
            <button id="groups-memory-group-save" type="button" onclick="addGroupsGroupMemory()"
                class="px-3 py-1.5 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-xs font-medium cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                ${t('groups_memory_save')}
            </button>
        </div>
        <div class="mt-4 space-y-2 max-h-64 overflow-y-auto">${listHtml}</div>
    </div>`;
}

function buildGroupsMemoryInput(id, labelKey, value, extraClass, readonly = false) {
    return `<label class="block">
        <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t(labelKey)}</span>
        <input id="${id}" type="text" value="${escapeHtml(value || '')}" ${readonly ? 'readonly' : ''}
            class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors ${extraClass || ''}">
    </label>`;
}

function buildGroupsMemoryPreviewPanel(roomId) {
    const preview = groupsMemoryState.preview;
    const content = preview?.content || '';
    return `<div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
        <div class="mb-3">
            <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_memory_preview_title')}</h4>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_memory_preview_hint')}</p>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-[minmax(220px,0.8fr)_minmax(260px,1fr)_auto] gap-3 items-end">
            ${buildGroupsMemoryInput('groups-memory-preview-sender-id', 'groups_memory_sender_id', '', 'font-mono')}
            <label class="block">
                <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('groups_memory_preview_mentions')}</span>
                <input id="groups-memory-preview-mentioned-ids" type="text"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 font-mono transition-colors">
            </label>
            <button id="groups-memory-preview-run" type="button" onclick="runGroupsMemoryPreview()"
                class="px-3 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-xs font-medium cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                ${t('groups_memory_preview_run')}
            </button>
        </div>
        <label class="block text-xs font-medium text-slate-600 dark:text-slate-400 mt-3 mb-1.5">${t('groups_memory_preview_query')}</label>
        <textarea id="groups-memory-preview-query" rows="2"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors resize-y"></textarea>
        <pre id="groups-memory-preview-content" class="mt-3 max-h-72 overflow-auto rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3 text-xs text-slate-700 dark:text-slate-200 whitespace-pre-wrap break-words">${escapeHtml(content || t('groups_memory_preview_empty'))}</pre>
    </div>`;
}

function buildGroupsMemoryLearningPanel(roomId, extra) {
    const config = extra.memory || {};
    const runs = groupsMemoryState.runs || [];
    const evolutionRuns = groupsMemoryState.profileEvolutionRuns || [];
    const evolutionStatus = groupsMemoryState.profileEvolutionStatus || {};
    const loadingHtml = groupsMemoryState.learningLoading
        ? `<p class="text-xs text-slate-500 dark:text-slate-400"><i class="fas fa-spinner fa-spin mr-1"></i>${t('groups_loading')}</p>`
        : '';
    const evolutionLoadingHtml = groupsMemoryState.profileEvolutionLoading
        ? `<p class="text-xs text-slate-500 dark:text-slate-400"><i class="fas fa-spinner fa-spin mr-1"></i>${t('groups_loading')}</p>`
        : '';
    const runsHtml = runs.length ? runs.map(run => {
        const startedAt = formatGroupsMemoryRunTimestamp(run.started_at);
        return `
            <div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
                <div class="flex flex-wrap items-center gap-2 text-xs">
                    <span class="font-mono text-slate-500 dark:text-slate-400">${escapeHtml(run.run_id || '')}</span>
                    <span class="rounded-full px-2 py-0.5 border border-slate-200 dark:border-white/10 text-slate-500 dark:text-slate-400">${escapeHtml(translateGroupsMemoryRunStatus(run.status))}</span>
                    <span class="ml-auto text-slate-400 dark:text-slate-500">${escapeHtml(startedAt)}</span>
                </div>
                <div class="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                    <span>${t('groups_memory_run_messages')} ${escapeHtml(String(run.batch_message_count || 0))}</span>
                    <span>${t('groups_memory_run_profiles')} ${escapeHtml(String(run.profile_update_count || 0))}</span>
                    <span>${t('groups_memory_run_memories')} ${escapeHtml(String(run.group_memory_upsert_count || 0))}</span>
                    <span>${escapeHtml(run.failed_reason || '')}</span>
                </div>
            </div>
        `;
    }).join('') : `<p class="text-xs text-slate-500 dark:text-slate-400">${t('groups_memory_auto_no_runs')}</p>`;
    const evolutionRunsHtml = evolutionRuns.length ? evolutionRuns.map(run => {
        const startedAt = formatGroupsMemoryRunTimestamp(run.started_at);
        return `
            <div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
                <div class="flex flex-wrap items-center gap-2 text-xs">
                    <button type="button" onclick="loadGroupsProfileEvolutionRun('${escapeJs(run.run_id || '')}')"
                        class="font-mono text-primary-600 dark:text-primary-300 hover:underline cursor-pointer">${escapeHtml(run.run_id || '')}</button>
                    <span class="rounded-full px-2 py-0.5 border border-slate-200 dark:border-white/10 text-slate-500 dark:text-slate-400">${escapeHtml(translateGroupsMemoryRunStatus(run.status))}</span>
                    <span class="ml-auto text-slate-400 dark:text-slate-500">${escapeHtml(startedAt)}</span>
                </div>
                <div class="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                    <span>${t('groups_memory_run_messages')} ${escapeHtml(String(run.batch_message_count || 0))}</span>
                    <span>${t('groups_memory_run_profiles')} ${escapeHtml(String(run.profile_update_count || 0))}</span>
                    <span>Aliases ${escapeHtml(String(run.alias_update_count || 0))}</span>
                    <button type="button" onclick="rollbackGroupsProfileEvolutionRun('${escapeJs(run.run_id || '')}')"
                        class="text-left text-red-500 hover:underline cursor-pointer">${currentLang === 'zh' ? '回滚' : 'Rollback'}</button>
                </div>
            </div>
        `;
    }).join('') : `<p class="text-xs text-slate-500 dark:text-slate-400">${t('groups_memory_auto_no_runs')}</p>`;
    const evolutionDetail = groupsMemoryState.profileEvolutionDetail || null;
    const evolutionDetailHtml = evolutionDetail ? `
        <div class="rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-3">
            <div class="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span class="font-mono">${escapeHtml(evolutionDetail.run?.run_id || '')}</span>
                <span>${escapeHtml(String((evolutionDetail.diffs || []).length))} diffs</span>
            </div>
            <pre class="mt-2 max-h-56 overflow-auto text-[11px] text-slate-600 dark:text-slate-300 whitespace-pre-wrap">${escapeHtml(JSON.stringify(evolutionDetail.diffs || [], null, 2))}</pre>
        </div>
    ` : '';
    return `<div class="space-y-4">
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <div class="mb-4">
                <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('groups_memory_auto_title')}</h4>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t('groups_memory_auto_hint')}</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                ${buildGroupsMemoryCheckbox('groups-memory-knowledge-enabled', 'groups_memory_knowledge_enabled', config.knowledge_enabled !== false)}
                ${buildGroupsMemoryCheckbox('groups-memory-profile-enabled', 'groups_memory_profile_enabled', config.profile_enabled !== false)}
                ${buildGroupsMemoryCheckbox('groups-memory-learning-enabled', 'groups_memory_learning_enabled', !!config.learning_enabled)}
                ${buildGroupsMemoryNumberInput('groups-memory-profile-context-limit', 'groups_memory_profile_context_limit', config.profile_context_limit ?? 2, '1', '1', '20')}
                ${buildGroupsMemoryNumberInput('groups-memory-group-context-limit', 'groups_memory_group_context_limit', config.group_memory_context_limit ?? 5, '1', '1', '20')}
                ${buildGroupsMemoryNumberInput('groups-memory-batch-message-limit', 'groups_memory_learning_batch_limit', config.learning_batch_message_limit ?? 200, '1', '1', '1000')}
                ${buildGroupsMemoryNumberInput('groups-memory-profile-min-messages', 'groups_memory_learning_profile_min_messages', config.learning_profile_min_messages ?? 6, '1', '1', '200')}
                ${buildGroupsMemoryNumberInput('groups-memory-profile-sample-limit', 'groups_memory_learning_profile_sample_limit', config.learning_profile_sample_limit ?? 30, '1', '1', '200')}
                ${buildGroupsMemoryNumberInput('groups-memory-group-memory-min-messages', 'groups_memory_learning_group_memory_min_messages', config.learning_group_memory_min_messages ?? 20, '1', '1', '500')}
                ${buildGroupsMemoryNumberInput('groups-memory-window-minutes', 'groups_memory_learning_group_memory_window_minutes', config.learning_group_memory_window_minutes ?? 120, '1', '1', '10080')}
            </div>
            <div class="mt-4 flex flex-wrap justify-end gap-2">
                <button id="groups-memory-auto-save" type="button" onclick="saveGroupsMemoryAutoConfig()"
                    class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    ${t('groups_memory_auto_save')}
                </button>
                <button id="groups-memory-auto-run" type="button" onclick="runGroupsMemoryLearning()"
                    class="px-3 py-1.5 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-xs font-medium cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    ${t('groups_memory_auto_run')}
                </button>
            </div>
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <div class="mb-4">
                <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${currentLang === 'zh' ? '群画像自主学习' : 'Profile evolution'}</h4>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${currentLang === 'zh' ? '空闲后自动调用 LLM 学习群友别名、角色、常用词和表达风格，按当前群隔离自动合并。' : 'Automatically learns aliases, roles, terms, and style with room-scoped isolation.'}</p>
            </div>
            <div id="groups-memory-profile-evolution-status" class="mb-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                <span>Cursor ${escapeHtml(String(evolutionStatus.last_archive_row_id || 0))}</span>
                <span>Observed ${escapeHtml(String(evolutionStatus.latest_observed_row_id || 0))}</span>
                <span>Running ${escapeHtml(String(!!evolutionStatus.running))}</span>
                <span>${escapeHtml(evolutionStatus.last_failed_reason || '')}</span>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                ${buildGroupsMemoryCheckbox('groups-memory-profile-evolution-enabled', currentLang === 'zh' ? '启用群画像自主学习' : 'Enable profile evolution', !!config.profile_evolution_enabled)}
                ${buildGroupsMemoryNumberInput('groups-memory-profile-evolution-idle-minutes', currentLang === 'zh' ? '空闲分钟' : 'Idle minutes', config.profile_evolution_idle_minutes ?? 10, '1', '1', '1440')}
                ${buildGroupsMemoryNumberInput('groups-memory-profile-evolution-min-messages', currentLang === 'zh' ? '最少新消息数' : 'Min new messages', config.profile_evolution_min_messages ?? 10, '1', '1', '500')}
                ${buildGroupsMemoryNumberInput('groups-memory-profile-evolution-max-interval-minutes', currentLang === 'zh' ? '最大间隔分钟' : 'Max interval minutes', config.profile_evolution_max_interval_minutes ?? 120, '1', '1', '10080')}
                ${buildGroupsMemoryNumberInput('groups-memory-profile-evolution-batch-limit', currentLang === 'zh' ? '每批消息数' : 'Batch messages', config.profile_evolution_batch_message_limit ?? 200, '1', '1', '1000')}
            </div>
            <div class="mt-4 flex flex-wrap justify-end gap-2">
                <button id="groups-memory-profile-evolution-save" type="button" onclick="saveGroupsProfileEvolutionConfig()"
                    class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-white dark:hover:bg-white/5 cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    ${t('groups_memory_auto_save')}
                </button>
                <button id="groups-memory-profile-evolution-run" type="button" onclick="runGroupsProfileEvolution()"
                    class="px-3 py-1.5 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-xs font-medium cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    ${currentLang === 'zh' ? '手动执行画像学习' : 'Run profile learning'}
                </button>
            </div>
        </div>
        ${evolutionLoadingHtml}
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">${currentLang === 'zh' ? '群画像学习记录' : 'Profile evolution runs'}</h4>
            <div id="groups-memory-profile-evolution-runs" class="space-y-2 max-h-80 overflow-y-auto">${evolutionRunsHtml}</div>
            ${evolutionDetailHtml}
        </div>
        ${loadingHtml}
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">${t('groups_memory_auto_runs')}</h4>
            <div class="space-y-2 max-h-80 overflow-y-auto">${runsHtml}</div>
        </div>
    </div>`;
}

function buildGroupsMemoryNumberInput(id, labelKey, value, step, min, max) {
    return `<label class="block">
        <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t(labelKey)}</span>
        <input id="${id}" type="number" step="${step}" min="${min}" max="${max}" value="${escapeHtml(String(value ?? ''))}"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors">
    </label>`;
}

function buildGroupsMemoryCheckbox(id, labelKey, checked) {
    return `<label class="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] px-3 py-2 text-sm text-slate-700 dark:text-slate-200 cursor-pointer">
        <input id="${id}" type="checkbox" ${checked ? 'checked' : ''} class="rounded border-slate-300 text-primary-500 focus:ring-primary-500">
        <span>${t(labelKey)}</span>
    </label>`;
}

function selectGroupsMemoryRoom(roomId) {
    groupsMemoryState.selectedRoomId = roomId;
    groupsMemoryState.loadedRoomId = '';
    groupsMemoryState.preview = null;
    renderGroupsView();
}

function refreshGroupsMemoryData(roomId) {
    if (!roomId) return;
    groupsMemoryState.loading = true;
    groupsMemoryState.selectedRoomId = roomId;
    renderGroupsView();
    const encoded = encodeURIComponent(roomId);
    const query = encodeURIComponent(groupsMemoryState.search || '');
    Promise.all([
        fetch(`/api/wechat-group/memories/summary?stable_room_id=${encoded}&room_id=${encoded}`).then(r => r.json()),
        fetch(`/api/wechat-group/memories/group?stable_room_id=${encoded}&room_id=${encoded}&q=${query}`).then(r => r.json()),
        fetch(`/api/wechat-group/memories/learn/runs?stable_room_id=${encoded}&room_id=${encoded}`).then(r => r.json()),
        fetch(`/api/wechat-group/memories/profile-evolution/status?stable_room_id=${encoded}&room_id=${encoded}`).then(r => r.json()),
        fetch(`/api/wechat-group/memories/profile-evolution/runs?stable_room_id=${encoded}&room_id=${encoded}`).then(r => r.json()),
    ]).then(([summaryData, memoryData, runsData, evolutionStatusData, evolutionRunsData]) => {
        if (summaryData.status !== 'success') throw new Error(summaryData.message || 'groups_error_summary_load_failed');
        if (memoryData.status !== 'success') throw new Error(memoryData.message || 'groups_error_memory_load_failed');
        if (runsData.status !== 'success') throw new Error(runsData.message || 'groups_error_runs_load_failed');
        if (evolutionStatusData.status !== 'success') throw new Error(evolutionStatusData.message || 'groups_error_runs_load_failed');
        if (evolutionRunsData.status !== 'success') throw new Error(evolutionRunsData.message || 'groups_error_runs_load_failed');
        groupsMemoryState.summary = summaryData.summary || {};
        groupsMemoryState.memories = memoryData.memories || [];
        groupsMemoryState.runs = runsData.runs || [];
        groupsMemoryState.profileEvolutionStatus = evolutionStatusData.evolution_status || {};
        groupsMemoryState.profileEvolutionRuns = evolutionRunsData.runs || [];
        groupsMemoryState.loadedRoomId = roomId;
    }).catch(err => {
        showGroupsStatus(err.message || 'groups_load_failed', true);
        groupsMemoryState.memories = [];
        groupsMemoryState.runs = [];
        groupsMemoryState.profileEvolutionStatus = null;
        groupsMemoryState.profileEvolutionRuns = [];
        groupsMemoryState.loadedRoomId = roomId;
    }).finally(() => {
        groupsMemoryState.loading = false;
        renderGroupsView();
    });
}

function applyGroupsMemorySearch() {
    groupsMemoryState.search = (document.getElementById('groups-memory-search')?.value || '').trim();
    groupsMemoryState.loadedRoomId = '';
    refreshGroupsMemoryData(groupsMemoryState.selectedRoomId);
}

function addGroupsGroupMemory() {
    const roomId = groupsMemoryState.selectedRoomId;
    const contentEl = document.getElementById('groups-memory-group-content');
    const summaryEl = document.getElementById('groups-memory-group-summary');
    const btn = document.getElementById('groups-memory-group-save');
    const content = (contentEl?.value || '').trim();
    if (!roomId || !content) {
        showGroupsStatus('groups_memory_content_label', true);
        return;
    }
    if (btn) btn.disabled = true;
    fetch('/api/wechat-group/memories/group', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            stable_room_id: roomId,
            room_id: roomId,
            content,
            source_summary: summaryEl?.value || '',
        }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'groups_error_save_failed');
        if (contentEl) contentEl.value = '';
        if (summaryEl) summaryEl.value = '';
        showGroupsStatus('groups_memory_saved', false);
        groupsMemoryState.loadedRoomId = '';
        refreshGroupsMemoryData(roomId);
    }).catch(err => showGroupsStatus(err.message || 'channels_save_error', true))
      .finally(() => { if (btn) btn.disabled = false; });
}

function disableGroupsGroupMemory(memoryId) {
    const roomId = groupsMemoryState.selectedRoomId;
    if (!roomId || !memoryId) return;
    const confirmed = window.confirm(currentLang === 'zh' ? '确定停用这条群记忆吗？' : 'Disable this group memory?');
    if (!confirmed) return;
    fetch('/api/wechat-group/memories/disable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            memory_type: 'group',
            stable_room_id: roomId,
            room_id: roomId,
            memory_id: memoryId,
        }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'groups_error_disable_failed');
        showGroupsStatus('groups_memory_disabled', false);
        groupsMemoryState.loadedRoomId = '';
        refreshGroupsMemoryData(roomId);
    }).catch(err => showGroupsStatus(err.message || 'channels_save_error', true));
}

function splitGroupsMemoryIds(value) {
    return String(value || '')
        .split(/[,\n]/)
        .map(item => item.trim())
        .filter(Boolean);
}

function runGroupsMemoryPreview() {
    const roomId = groupsMemoryState.selectedRoomId;
    const senderId = (document.getElementById('groups-memory-preview-sender-id')?.value || '').trim();
    if (!roomId || !senderId) {
        showGroupsStatus('groups_memory_sender_id', true);
        return;
    }
    const btn = document.getElementById('groups-memory-preview-run');
    if (btn) btn.disabled = true;
    fetch('/api/wechat-group/memories/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            stable_room_id: roomId,
            room_id: roomId,
            stable_member_id: senderId,
            sender_id: senderId,
            query: document.getElementById('groups-memory-preview-query')?.value || '',
            mentioned_sender_ids: splitGroupsMemoryIds(document.getElementById('groups-memory-preview-mentioned-ids')?.value || ''),
        }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'groups_error_preview_failed');
        groupsMemoryState.preview = data.preview || {};
        const pre = document.getElementById('groups-memory-preview-content');
        if (pre) pre.textContent = groupsMemoryState.preview.content || t('groups_memory_preview_empty');
    }).catch(err => showGroupsStatus(err.message || 'groups_load_failed', true))
      .finally(() => { if (btn) btn.disabled = false; });
}

function getGroupsMemoryNumber(id, fallback) {
    const value = Number(document.getElementById(id)?.value || fallback);
    return Number.isFinite(value) ? value : fallback;
}

function saveGroupsMemoryAutoConfig() {
    const ch = channelsData.find(item => item.name === 'wechat_group');
    if (!ch) return;
    const extra = ch.extra || {};
    const btn = document.getElementById('groups-memory-auto-save');
    if (btn) btn.disabled = true;
    fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'save',
            channel: 'wechat_group',
            config: {
                wechat_group_stable_room_ids: extra.selected_room_ids || [],
                wechat_group_room_ids: extra.runtime_selected_room_ids || extra.selected_room_ids || [],
                wechat_group_names: extra.selected_room_names || [],
                wechat_group_persona_prompt: extra.persona?.prompt || '',
                wechat_group_persona_preset_id: extra.persona?.preset_id || 'custom',
                wechat_group_knowledge_enabled: !!document.getElementById('groups-memory-knowledge-enabled')?.checked,
                wechat_group_profile_enabled: !!document.getElementById('groups-memory-profile-enabled')?.checked,
                wechat_group_learning_enabled: !!document.getElementById('groups-memory-learning-enabled')?.checked,
                wechat_group_profile_context_limit: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-profile-context-limit', 2))),
                wechat_group_group_memory_context_limit: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-group-context-limit', 5))),
                wechat_group_learning_batch_message_limit: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-batch-message-limit', 200))),
                wechat_group_learning_profile_min_messages: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-profile-min-messages', 6))),
                wechat_group_learning_profile_sample_limit: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-profile-sample-limit', 30))),
                wechat_group_learning_group_memory_min_messages: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-group-memory-min-messages', 20))),
                wechat_group_learning_group_memory_window_minutes: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-window-minutes', 120))),
            },
        })
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'groups_error_save_failed');
        showGroupsStatus('groups_memory_auto_saved', false);
        loadGroupsView();
    }).catch(err => showGroupsStatus(err.message || 'channels_save_error', true))
      .finally(() => { if (btn) btn.disabled = false; });
}

function runGroupsMemoryLearning() {
    const roomId = groupsMemoryState.selectedRoomId;
    if (!roomId) return;
    const btn = document.getElementById('groups-memory-auto-run');
    if (btn) btn.disabled = true;
    groupsMemoryState.learningLoading = true;
    fetch('/api/wechat-group/memories/learn/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            stable_room_id: roomId,
            room_id: roomId,
            mode: 'all',
        }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'groups_error_learning_failed');
        showGroupsStatus('groups_memory_auto_ran', false);
        groupsMemoryState.loadedRoomId = '';
        refreshGroupsMemoryData(roomId);
    }).catch(err => showGroupsStatus(err.message || 'groups_load_failed', true))
      .finally(() => {
          groupsMemoryState.learningLoading = false;
          if (btn) btn.disabled = false;
      });
}

function saveGroupsProfileEvolutionConfig() {
    const btn = document.getElementById('groups-memory-profile-evolution-save');
    if (btn) btn.disabled = true;
    fetch('/api/wechat-group/memories/profile-evolution/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            wechat_group_profile_evolution_enabled: !!document.getElementById('groups-memory-profile-evolution-enabled')?.checked,
            wechat_group_profile_evolution_idle_minutes: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-profile-evolution-idle-minutes', 10))),
            wechat_group_profile_evolution_min_messages: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-profile-evolution-min-messages', 10))),
            wechat_group_profile_evolution_max_interval_minutes: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-profile-evolution-max-interval-minutes', 120))),
            wechat_group_profile_evolution_batch_message_limit: Math.max(1, Math.floor(getGroupsMemoryNumber('groups-memory-profile-evolution-batch-limit', 200))),
        }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'groups_error_save_failed');
        showGroupsStatus('groups_memory_auto_saved', false);
        loadGroupsView();
    }).catch(err => showGroupsStatus(err.message || 'channels_save_error', true))
      .finally(() => { if (btn) btn.disabled = false; });
}

function runGroupsProfileEvolution() {
    const roomId = groupsMemoryState.selectedRoomId;
    if (!roomId) return;
    const btn = document.getElementById('groups-memory-profile-evolution-run');
    if (btn) btn.disabled = true;
    groupsMemoryState.profileEvolutionLoading = true;
    fetch('/api/wechat-group/memories/profile-evolution/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stable_room_id: roomId, room_id: roomId }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'groups_error_learning_failed');
        showGroupsStatus('groups_memory_auto_ran', false);
        groupsMemoryState.loadedRoomId = '';
        refreshGroupsMemoryData(roomId);
    }).catch(err => showGroupsStatus(err.message || 'groups_load_failed', true))
      .finally(() => {
          groupsMemoryState.profileEvolutionLoading = false;
          if (btn) btn.disabled = false;
      });
}

function loadGroupsProfileEvolutionRun(runId) {
    const roomId = groupsMemoryState.selectedRoomId;
    if (!roomId || !runId) return;
    const encodedRoom = encodeURIComponent(roomId);
    const encodedRun = encodeURIComponent(runId);
    fetch(`/api/wechat-group/memories/profile-evolution/run?stable_room_id=${encodedRoom}&room_id=${encodedRoom}&run_id=${encodedRun}`)
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') throw new Error(data.message || 'groups_error_runs_load_failed');
            groupsMemoryState.profileEvolutionDetail = { run: data.run || {}, diffs: data.diffs || [] };
            renderGroupsView();
        })
        .catch(err => showGroupsStatus(err.message || 'groups_load_failed', true));
}

function rollbackGroupsProfileEvolutionRun(runId) {
    const roomId = groupsMemoryState.selectedRoomId;
    if (!roomId || !runId) return;
    const confirmed = window.confirm(currentLang === 'zh' ? '确定回滚这次群画像学习吗？' : 'Rollback this profile evolution run?');
    if (!confirmed) return;
    fetch('/api/wechat-group/memories/profile-evolution/rollback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stable_room_id: roomId, room_id: roomId, run_id: runId }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'groups_error_reject_failed');
        showGroupsStatus(currentLang === 'zh' ? '群画像已回滚' : 'Profile evolution rolled back', false);
        groupsMemoryState.profileEvolutionDetail = null;
        groupsMemoryState.loadedRoomId = '';
        refreshGroupsMemoryData(roomId);
    }).catch(err => showGroupsStatus(err.message || 'channels_save_error', true));
}

function legacyApproveGroupsMemory(candidateId) {
    const roomId = groupsMemoryState.selectedRoomId;
    if (!roomId || !candidateId) return;
    fetch('/api/wechat-group/memories/learn/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stable_room_id: roomId, room_id: roomId, candidate_id: candidateId }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'groups_error_approve_failed');
        showGroupsStatus('groups_memory_auto_approved', false);
        groupsMemoryState.loadedRoomId = '';
        refreshGroupsMemoryData(roomId);
    }).catch(err => showGroupsStatus(err.message || 'channels_save_error', true));
}

function legacyRejectGroupsMemory(candidateId) {
    const roomId = groupsMemoryState.selectedRoomId;
    if (!roomId || !candidateId) return;
    const reviewNote = window.prompt(currentLang === 'zh' ? '请输入驳回原因' : 'Review note') || '';
    fetch('/api/wechat-group/memories/learn/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stable_room_id: roomId, room_id: roomId, candidate_id: candidateId, review_note: reviewNote }),
    }).then(r => r.json()).then(data => {
        if (data.status !== 'success') throw new Error(data.message || 'groups_error_reject_failed');
        showGroupsStatus('groups_memory_auto_rejected', false);
        groupsMemoryState.loadedRoomId = '';
        refreshGroupsMemoryData(roomId);
    }).catch(err => showGroupsStatus(err.message || 'channels_save_error', true));
}

function toggleGroupsRoomDropdown() {
    const menu = document.getElementById('groups-room-dropdown-menu');
    if (menu) menu.classList.toggle('hidden');
}

function filterGroupsRooms() {
    const query = (document.getElementById('groups-room-search')?.value || '').trim().toLowerCase();
    let visibleCount = 0;
    document.querySelectorAll('.groups-room-option').forEach(option => {
        const match = !query || String(option.dataset.roomName || '').includes(query);
        option.classList.toggle('hidden', !match);
        if (match) visibleCount += 1;
    });
    const emptyId = 'groups-room-no-match';
    let empty = document.getElementById(emptyId);
    if (!empty) {
        empty = document.createElement('p');
        empty.id = emptyId;
        empty.className = 'px-2 py-4 text-center text-xs text-slate-500 dark:text-slate-400';
        empty.textContent = t('groups_rooms_no_match');
        document.getElementById('groups-room-options')?.appendChild(empty);
    }
    empty.classList.toggle('hidden', visibleCount > 0);
}

function updateGroupsRoomSelectedCount() {
    const ch = channelsData.find(item => item.name === 'wechat_group');
    const extra = ch?.extra || {};
    const checkedRoomIds = Array.from(document.querySelectorAll('[data-groups-room-id]:checked:not(:disabled)'))
        .map(el => el.dataset.groupsRoomId)
        .filter(Boolean);
    const count = resolveGroupsSelectedRoomIdsForSave(extra, checkedRoomIds, true).length;
    const dropdown = document.querySelector('#groups-room-dropdown > button > span');
    if (dropdown) {
        dropdown.textContent = count ? t('groups_rooms_selected_count').replace('{count}', String(count)) : t('groups_rooms_select_placeholder');
    }
}

function removeGroupsSelectedRoom(roomId, btn) {
    const ch = channelsData.find(item => item.name === 'wechat_group');
    const extra = ch?.extra || {};
    const persistedRoomIds = Array.isArray(extra.selected_room_ids) ? extra.selected_room_ids : [];
    const removedRoomId = String(roomId || '');
    const index = persistedRoomIds.findIndex(id => String(id || '') === removedRoomId);
    const matchingInput = Array.from(document.querySelectorAll('[data-groups-room-id]'))
        .find(el => String(el.dataset.groupsRoomId || '') === removedRoomId);
    if (matchingInput) matchingInput.checked = false;
    for (const key of ['selected_room_ids', 'stable_selected_room_ids', 'runtime_selected_room_ids', 'selected_room_names']) {
        if (Array.isArray(extra[key]) && index >= 0 && index < extra[key].length) extra[key].splice(index, 1);
    }
    const chip = btn?.closest('span');
    if (chip) chip.remove();
    const selectedList = document.getElementById('groups-room-selected-list');
    if (selectedList && !selectedList.querySelector('button')) {
        selectedList.innerHTML = `<p class="text-xs text-slate-500 dark:text-slate-400">${t('groups_rooms_none_selected')}</p>`;
    }
    updateGroupsRoomSelectedCount();
}

function updateGroupsPersonaCount() {
    const textarea = document.getElementById('groups-persona-prompt');
    const counter = document.getElementById('groups-persona-count');
    if (textarea && counter) counter.textContent = String(textarea.value.length);
}

function renderActiveChannels() {
    stopWeixinQrPoll();
    stopWeixinStatusPoll();
    const container = document.getElementById('channels-content');
    container.innerHTML = '';
    closeAddChannelPanel();

    const activeChannels = channelsData.filter(ch => ch.active);

    if (activeChannels.length === 0) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center py-20">
                <div class="w-16 h-16 rounded-2xl bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center mb-4">
                    <i class="fas fa-tower-broadcast text-blue-400 text-xl"></i>
                </div>
                <p class="text-slate-500 dark:text-slate-400 font-medium">${t('channels_empty')}</p>
                <p class="text-sm text-slate-400 dark:text-slate-500 mt-1">${t('channels_empty_desc')}</p>
            </div>`;
        return;
    }

    activeChannels.forEach(ch => {
        const label = (typeof ch.label === 'object') ? (ch.label[currentLang] || ch.label.en) : ch.label;
        const card = document.createElement('div');
        card.className = 'bg-white dark:bg-[#1A1A1A] rounded-xl border border-slate-200 dark:border-white/10 p-6';
        card.id = `channel-card-${ch.name}`;

        const fieldsHtml = buildChannelFieldsHtml(ch.name, ch.fields || []);
        const hasFields = (ch.fields || []).length > 0;

        const weixinWaiting = ch.name === 'weixin' && ch.login_status && ch.login_status !== 'logged_in';
        const wecomNeedsCreds = ch.name === 'wecom_bot' && !_wecomBotHasCreds(ch);
        // 飞书 active 卡片渲染带 Tab 的 panel：手动填写 + 扫码重建（覆盖现有配置）
        const isFeishu = ch.name === 'feishu';
        const isWechatGroup = ch.name === 'wechat_group';
        let statusDot, statusText;
        if (weixinWaiting) {
            statusDot = 'bg-amber-400 animate-pulse';
            statusText = ch.login_status === 'scanned'
                ? `<span class="text-xs text-primary-500">${t('weixin_scan_scanned')}</span>`
                : `<span class="text-xs text-amber-500">${t('weixin_scan_waiting')}</span>`;
        } else if (wecomNeedsCreds) {
            statusDot = 'bg-amber-400 animate-pulse';
            statusText = `<span class="text-xs text-amber-500">${t('channels_connecting')}</span>`;
        } else {
            statusDot = 'bg-primary-400';
            statusText = `<span class="text-xs text-primary-500">${t('channels_connected')}</span>`;
        }

        card.innerHTML = `
            <div class="flex items-center gap-4${hasFields || weixinWaiting || wecomNeedsCreds || isFeishu ? ' mb-5' : ''}">
                <div class="w-10 h-10 rounded-xl bg-${ch.color}-50 dark:bg-${ch.color}-900/20 flex items-center justify-center flex-shrink-0">
                    <i class="fas ${ch.icon} text-${ch.color}-500 text-base"></i>
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                        <span class="font-semibold text-slate-800 dark:text-slate-100">${escapeHtml(label)}</span>
                        <span class="w-2 h-2 rounded-full ${statusDot}"></span>
                        ${statusText}
                    </div>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5 font-mono">${escapeHtml(ch.name)}</p>
                </div>
                <button onclick="disconnectChannel('${ch.name}')"
                    class="px-3 py-1.5 rounded-lg text-xs font-medium
                           bg-red-50 dark:bg-red-900/20 text-red-500 dark:text-red-400
                           hover:bg-red-100 dark:hover:bg-red-900/40
                           cursor-pointer transition-colors flex-shrink-0">
                    ${t('channels_disconnect')}
                </button>
            </div>
            ${weixinWaiting ? `<div id="weixin-active-qr" class="flex flex-col items-center py-2">
                <button onclick="showWeixinActiveQr()"
                    class="px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium
                           cursor-pointer transition-colors duration-150">
                    ${t('weixin_scan_title')}
                </button>
            </div>` : ''}
            ${wecomNeedsCreds ? `<div id="wecom-active-auth" class="flex flex-col items-center py-2">
                <p class="text-sm text-slate-500 dark:text-slate-400 mb-3">${t('wecom_scan_desc')}</p>
                <button onclick="startWecomBotAuthInCard()"
                    class="px-5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium
                           cursor-pointer transition-colors duration-150">
                    <i class="fas fa-qrcode mr-2"></i>${t('wecom_scan_btn')}
                </button>
                <div id="wecom-card-scan-status" class="mt-3"></div>
            </div>` : ''}
            ${isFeishu ? buildFeishuPanel(ch, true) : (hasFields ? `<div class="space-y-4">
                ${fieldsHtml}
                <div class="flex items-center justify-end gap-3 pt-1">
                    <span id="ch-status-${ch.name}" class="text-xs text-primary-500 opacity-0 transition-opacity duration-300"></span>
                    <button onclick="saveChannelConfig('${ch.name}')"
                        class="px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium
                               cursor-pointer transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
                        id="ch-save-${ch.name}">${t('channels_save')}</button>
                </div>
            </div>` : '')}
            `;

        container.appendChild(card);
        bindSecretFieldEvents(card);

        if (weixinWaiting) {
            startWeixinActiveStatusPoll();
        }
    });
}

function splitWechatGroupLines(value) {
    return String(value || '')
        .split(/\r?\n/)
        .map(item => item.trim())
        .filter(Boolean);
}

function splitWechatGroupList(value) {
    const seen = new Set();
    return String(value || '')
        .split(/[,，;；\s]+/)
        .map(item => item.trim())
        .filter(Boolean)
        .filter(item => {
            if (seen.has(item)) return false;
            seen.add(item);
            return true;
        });
}

function getWechatGroupDraftPresetId(ch) {
    const prompt = document.getElementById('wechat-group-persona-prompt')?.value || '';
    const presets = ch?.extra?.persona_presets || [];
    const matched = presets.find(preset => String(preset.prompt || '') === prompt);
    return matched ? matched.id : 'custom';
}

function formatFreeReplyRuleScore(rule = {}) {
    const score = rule.score;
    if (score === undefined || score === null || String(score).trim() === '') {
        return '-';
    }
    return String(score);
}

function buildFreeReplyBanterScoreInputs(rule = {}) {
    const levels = [
        { id: 'quiet', labelKey: 'wechat_group_free_reply_level_quiet' },
        { id: 'normal', labelKey: 'wechat_group_free_reply_level_normal' },
        { id: 'active', labelKey: 'wechat_group_free_reply_level_active' },
        { id: 'crazy', labelKey: 'wechat_group_free_reply_level_crazy' },
    ];
    const byLevel = rule.score_by_level || {};
    const defaults = { quiet: 5, normal: 10, active: 18, crazy: 28 };
    return `<div class="free-reply-banter-scores">
        ${levels.map(level => {
            const value = Number(byLevel[level.id] ?? defaults[level.id] ?? 0);
            return `<label class="free-reply-banter-score-item" title="${escapeHtml(t(level.labelKey))}">
                <span>${escapeHtml(t(level.labelKey)).slice(0, 1)}</span>
                <input type="number" min="0" max="100" step="1" value="${value}"
                    data-free-reply-rule-score="${escapeHtml(rule.id || 'banter_opportunity')}"
                    data-free-reply-rule-level="${level.id}"
                    class="free-reply-rule-score-input">
            </label>`;
        }).join('')}
    </div>`;
}

function buildFreeReplyRuleControlCell(rule = {}, type = 'positive') {
    if (type === 'negative') {
        const checked = rule.enabled !== false ? 'checked' : '';
        return `<label class="inline-flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400 cursor-pointer whitespace-nowrap" title="${escapeHtml(t('wechat_group_free_reply_rule_enabled'))}">
            <input type="checkbox" class="accent-primary-500 free-reply-rule-enabled-input"
                data-free-reply-rule-enabled="${escapeHtml(rule.id || '')}" ${checked}>
            <span>${t('wechat_group_free_reply_rule_enabled')}</span>
        </label>`;
    }
    if (rule.score_kind === 'by_level' || rule.id === 'banter_opportunity') {
        return buildFreeReplyBanterScoreInputs(rule);
    }
    const value = Number(rule.score ?? 0);
    return `<input type="number" min="0" max="100" step="1" value="${Number.isFinite(value) ? value : 0}"
        data-free-reply-rule-score="${escapeHtml(rule.id || '')}"
        class="free-reply-rule-score-input free-reply-rule-score-input-single"
        title="${escapeHtml(formatFreeReplyRuleScore(rule))}">`;
}

function buildFreeReplyRulesTable(rules = {}) {
    const rows = [
        ...(Array.isArray(rules.positive) ? rules.positive.map(rule => ({ rule, type: 'positive' })) : []),
        ...(Array.isArray(rules.negative) ? rules.negative.map(rule => ({ rule, type: 'negative' })) : []),
    ];
    if (!rows.length) {
        return `<p class="text-xs text-slate-500 dark:text-slate-400">-</p>`;
    }
    return `<div class="space-y-1.5">
        <p class="text-[11px] text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_rule_score_hint')}</p>
        <div class="overflow-x-auto rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111]">
            <table class="free-reply-rules-table min-w-full text-left text-xs">
                <thead class="bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-400">
                    <tr>
                        <th class="px-2 py-1.5 font-medium whitespace-nowrap w-12">${t('wechat_group_free_reply_rule_type')}</th>
                        <th class="px-2 py-1.5 font-medium">${t('wechat_group_free_reply_rule_description')}</th>
                        <th class="px-2 py-1.5 font-medium whitespace-nowrap text-right w-[9.5rem]">${t('wechat_group_free_reply_rule_score')}</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-200 dark:divide-white/10">
                    ${rows.map(({ rule, type }) => {
                        const isPositive = type === 'positive';
                        const badgeClass = isPositive
                            ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-300'
                            : 'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-300';
                        const typeLabel = isPositive ? t('wechat_group_free_reply_rule_positive') : t('wechat_group_free_reply_rule_negative');
                        const description = rule.label_zh || rule.label || rule.id || '';
                        return `<tr class="align-middle text-slate-600 dark:text-slate-300">
                            <td class="px-2 py-1 whitespace-nowrap"><span class="inline-flex rounded px-1 py-0.5 text-[10px] leading-none ${badgeClass}">${escapeHtml(typeLabel)}</span></td>
                            <td class="px-2 py-1 break-words leading-snug" title="${escapeHtml(rule.id || '')}">
                                <span class="text-slate-700 dark:text-slate-200">${escapeHtml(description)}</span>
                                <span class="block font-mono text-[10px] text-slate-400 dark:text-slate-500 leading-tight">${escapeHtml(rule.id || '')}</span>
                            </td>
                            <td class="px-2 py-1 text-right">${buildFreeReplyRuleControlCell(rule, type)}</td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>
    </div>`;
}

function renderWechatGroupFreeReplySettings(extra = {}) {
    const free = extra.free_reply || {};
    const rooms = Array.isArray(extra.rooms) ? extra.rooms : [];
    const targetRoomIds = new Set((extra.selected_room_ids || []).map(String));
    const stableIdByRuntimeId = new Map(rooms.map(room => [String(room.runtime_room_id || ''), String(room.id || '')]));
    const configuredFreeRoomIds = [
        ...(Array.isArray(free.stable_room_ids) ? free.stable_room_ids : []),
        ...(Array.isArray(free.room_ids) ? free.room_ids : []),
        ...(Array.isArray(free.legacy_room_ids) ? free.legacy_room_ids : []),
    ];
    const freeRoomIds = new Set(configuredFreeRoomIds.map(id => stableIdByRuntimeId.get(String(id)) || String(id)));
    const freeNames = Array.isArray(free.names) ? free.names : [];
    const level = free.activity_level || 'normal';
    const profiles = free.profiles || {};
    const profile = profiles[level] || {};
    const forceKeywords = Array.isArray(free.force_keywords) ? free.force_keywords : [];
    const worker = free.worker || {};
    const last = free.last_decision || {};
    const rules = free.rules || {};
    const roomRows = rooms.length ? rooms.map(room => {
        const id = String(room.id || '');
        const name = String(room.name || id || t('groups_room_unnamed'));
        const selectable = isWechatGroupRoomSelectable(room);
        const checked = selectable && freeRoomIds.has(id) ? 'checked' : '';
        const disabled = selectable ? '' : 'disabled';
        const inAccess = !targetRoomIds.size || targetRoomIds.has(id);
        return `<label class="flex items-start gap-2 rounded-lg px-2 py-2 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 ${selectable ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'}">
            <input type="checkbox" class="mt-1 accent-primary-500" data-wechat-group-free-reply-room-id="${escapeHtml(id)}" ${checked} ${disabled}>
            <span class="min-w-0 flex-1">
                <span class="block text-slate-800 dark:text-slate-100 break-words">${escapeHtml(name)}</span>
                <span class="block text-xs text-slate-400 dark:text-slate-500 font-mono break-all">${escapeHtml(id)}</span>
                <span class="block text-[11px] ${inAccess ? 'text-primary-500' : 'text-amber-500'}">${inAccess ? t('wechat_group_free_reply_room_access') : t('groups_rooms_none_selected')}</span>
            </span>
        </label>`;
    }).join('') : `<p class="rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 px-3 py-2 text-xs text-slate-500 dark:text-slate-400">${t('wechat_group_rooms_empty')}</p>`;
    const lastHtml = Object.keys(last).length ? `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
            <div><span class="text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_threshold')}：</span>${escapeHtml(String(last.score ?? 0))}/${escapeHtml(String(last.threshold ?? 0))}</div>
            <div><span class="text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_level')}：</span>${escapeHtml(translateWechatGroupActivityLevel(last.activity_level || '-'))}</div>
            <div class="md:col-span-2"><span class="text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_decision_reasons')}：</span>${(last.reasons || []).map(item => `<span class="inline-block rounded bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-300 px-1.5 py-0.5 mr-1 mb-1">${escapeHtml(item)}</span>`).join('') || '-'}</div>
            <div class="md:col-span-2"><span class="text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_decision_suppressions')}：</span>${(last.suppressions || []).map(item => `<span class="inline-block rounded bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-300 px-1.5 py-0.5 mr-1 mb-1">${escapeHtml(item)}</span>`).join('') || '-'}</div>
            <div class="md:col-span-2 break-words"><span class="text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_decision_preview')}：</span>${escapeHtml(last.text_preview || '')}</div>
        </div>` : `<p class="text-xs text-slate-500 dark:text-slate-400">${t('wechat_group_free_reply_no_decision')}</p>`;
    const workerHtml = `<div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-slate-600 dark:text-slate-300">
        <span>${t('wechat_group_free_reply_worker_status')}: ${worker.running ? t('wechat_group_free_reply_running') : t('wechat_group_free_reply_stopped')}</span>
        <span>${t('wechat_group_free_reply_worker_queue')}: ${Number(worker.queue_size || 0)}/${Number(worker.queue_limit || free.worker_queue_size || 0)}</span>
        <span>${t('wechat_group_free_reply_worker_approved')}: ${Number(worker.approved_total || 0)}</span>
        <span>${t('wechat_group_free_reply_worker_rejected')}: ${Number(worker.rejected_total || 0)}</span>
        <span>${t('wechat_group_free_reply_worker_dropped')}: ${Number(worker.dropped_total || 0)}</span>
        <span>${t('wechat_group_free_reply_worker_expired')}: ${Number(worker.expired_total || 0)}</span>
        <span>${t('wechat_group_free_reply_worker_active')}: ${Number(worker.active_workers || 0)}</span>
        <span class="break-words">${escapeHtml(worker.last_error || '')}</span>
    </div>`;
    const rulesHtml = buildFreeReplyRulesTable(rules);
    return `<div class="h-full w-full space-y-5">
        ${buildGroupsPanelTitle('fa-comment-dots', 'wechat_group_free_reply_title', 'wechat_group_free_reply_hint')}
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                    <h4 class="text-sm font-medium text-slate-800 dark:text-slate-100">${t('wechat_group_free_reply_enabled')}</h4>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">${t('wechat_group_free_reply_hint')}</p>
                </div>
                <label class="relative inline-flex items-center cursor-pointer flex-shrink-0">
                    <input id="free-reply-enabled" type="checkbox" class="sr-only peer" ${free.enabled ? 'checked' : ''}>
                    <div class="w-10 h-5 bg-slate-300 dark:bg-slate-600 rounded-full peer peer-checked:bg-primary-500 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:h-4 after:w-4 after:rounded-full after:transition-all peer-checked:after:translate-x-5"></div>
                </label>
            </div>
            <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
                ${buildFreeReplyNumberField('free-reply-mute-minutes', 'wechat_group_free_reply_mute_minutes', free.mute_minutes ?? 10, 1, 1440, 1, 'wechat_group_free_reply_mute_minutes_hint')}
                <label class="flex items-center justify-between gap-3 cursor-pointer md:pt-4">
                    <span class="min-w-0">
                        <span class="block text-xs font-medium text-slate-600 dark:text-slate-400">${t('wechat_group_free_reply_mute_mentions')}</span>
                        <span id="free-reply-mute-mentions-enabled-hint" class="block text-xs leading-relaxed text-slate-500 dark:text-slate-400 mt-1.5">${t('wechat_group_free_reply_mute_mentions_hint')}</span>
                    </span>
                    <span class="relative inline-flex items-center flex-shrink-0">
                        <input id="free-reply-mute-mentions-enabled" type="checkbox" class="sr-only peer"
                            aria-describedby="free-reply-mute-mentions-enabled-hint" ${free.mute_mentions_enabled === true ? 'checked' : ''}>
                        <span class="w-10 h-5 bg-slate-300 dark:bg-slate-600 rounded-full peer peer-checked:bg-primary-500 peer-focus:ring-2 peer-focus:ring-primary-400 peer-focus:ring-offset-2 dark:peer-focus:ring-offset-[#111111] transition-colors after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:h-4 after:w-4 after:rounded-full after:transition-all peer-checked:after:translate-x-5"></span>
                    </span>
                </label>
            </div>
        </div>
        <div class="grid grid-cols-1 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)] gap-4">
            <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
                <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">${t('wechat_group_free_reply_groups')}</h4>
                <div class="max-h-56 overflow-y-auto rounded-lg border border-slate-200 dark:border-white/10 bg-white dark:bg-[#111111] p-1.5 space-y-1">${roomRows}</div>
            </div>
            <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
                <label class="block text-sm font-medium text-slate-800 dark:text-slate-100 mb-1.5">${t('wechat_group_free_reply_names_label')}</label>
                <textarea id="free-reply-names" rows="8"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 font-mono transition-colors resize-y"
                    placeholder="${escapeHtml(t('wechat_group_room_names_placeholder'))}">${escapeHtml(freeNames.join('\n'))}</textarea>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-2">${t('groups_rooms_fallback_hint')}</p>
            </div>
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <label class="block text-sm font-medium text-slate-800 dark:text-slate-100 mb-1.5">${t('wechat_group_free_reply_force_keywords')}</label>
            <textarea id="free-reply-force-keywords" rows="3"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 font-mono transition-colors resize-y"
                placeholder="${escapeHtml(t('wechat_group_free_reply_force_keywords'))}">${escapeHtml(forceKeywords.join('\n'))}</textarea>
            <p class="text-xs text-slate-500 dark:text-slate-400 mt-2">${t('wechat_group_free_reply_force_keywords_hint')}</p>
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <label class="block text-sm font-medium text-slate-800 dark:text-slate-100 mb-1.5">${t('wechat_group_free_reply_level')}</label>
            <select id="free-reply-activity-level" onchange="syncFreeReplyProfileFields((getWechatGroupChannel() || {}).extra?.free_reply || {})"
                class="w-full md:w-64 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500">
                ${['quiet', 'normal', 'active', 'crazy'].map(item => `<option value="${item}" ${item === level ? 'selected' : ''}>${escapeHtml(translateWechatGroupActivityLevel(item))}</option>`).join('')}
            </select>
            <div class="free-reply-compact-grid mt-3">
                ${buildFreeReplyNumberField('free-reply-min-score', 'wechat_group_free_reply_threshold', profile.min_score ?? 50, 0, 100, 1)}
                ${buildFreeReplyNumberField('free-reply-min-interval', 'wechat_group_free_reply_interval', profile.min_interval_seconds ?? 10, 0, 3600, 1)}
                ${buildFreeReplyNumberField('free-reply-hourly-limit', 'wechat_group_free_reply_hourly', profile.hourly_limit ?? 0, 0, 999, 1)}
                ${buildFreeReplyNumberField('free-reply-consecutive-limit', 'wechat_group_free_reply_consecutive', profile.consecutive_limit ?? 0, 0, 99, 1)}
                ${buildFreeReplyNumberField('free-reply-queue-ttl', 'wechat_group_free_reply_ttl', free.queue_ttl_seconds ?? 120, 10, 600, 1)}
                ${buildFreeReplyNumberField('free-reply-worker-max-workers', 'wechat_group_free_reply_worker_max_workers', free.worker_max_workers ?? 2, 1, 8, 1)}
                ${buildFreeReplyNumberField('free-reply-worker-queue-size', 'wechat_group_free_reply_worker_queue_size', free.worker_queue_size ?? 100, 1, 1000, 1)}
            </div>
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4 space-y-3">
            <div class="flex items-center justify-between gap-3">
                <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('wechat_group_free_reply_llm_title')}</h4>
                <label class="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300 cursor-pointer">
                    <input id="free-reply-llm-enabled" type="checkbox" class="accent-primary-500" ${free.llm_judge_enabled !== false ? 'checked' : ''}>
                    ${t('wechat_group_free_reply_llm_enabled')}
                </label>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                ${buildFreeReplyNumberField('free-reply-llm-timeout', 'wechat_group_free_reply_llm_timeout', free.llm_judge_timeout_seconds ?? 8, 1, 30, 1)}
                ${buildFreeReplyNumberField('free-reply-llm-confidence', 'wechat_group_free_reply_llm_confidence', free.llm_judge_min_confidence ?? 0.6, 0, 1, 0.05)}
            </div>
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">${t('wechat_group_free_reply_worker_title')}</h4>
            ${workerHtml}
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">${t('wechat_group_free_reply_last_decision')}</h4>
            ${lastHtml}
        </div>
        <div class="rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-4">
            <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-2">${t('wechat_group_free_reply_rules')}</h4>
            ${rulesHtml}
        </div>
    </div>`;
}

function buildFreeReplyNumberField(id, labelKey, value, min, max, step, hintKey = '') {
    const hintId = hintKey ? `${id}-hint` : '';
    return `<label class="free-reply-number-field block">
        <span class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t(labelKey)}</span>
        <input id="${id}" type="number" min="${min}" max="${max}" step="${step}" value="${Number(value)}"
            ${hintId ? `aria-describedby="${hintId}"` : ''}
            class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-white dark:bg-[#111111] text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors">
        ${hintId ? `<span id="${hintId}" class="block text-xs leading-relaxed text-slate-500 dark:text-slate-400 mt-1.5">${t(hintKey)}</span>` : ''}
    </label>`;
}

function syncFreeReplyProfileFields(saved = {}) {
    const free = saved.free_reply ? saved.free_reply : saved;
    const level = document.getElementById('free-reply-activity-level')?.value || free.activity_level || 'normal';
    const defaults = {
        quiet: { min_score: 65, min_interval_seconds: 30, hourly_limit: 0, consecutive_limit: 0 },
        normal: { min_score: 50, min_interval_seconds: 10, hourly_limit: 0, consecutive_limit: 0 },
        active: { min_score: 35, min_interval_seconds: 3, hourly_limit: 0, consecutive_limit: 0 },
        crazy: { min_score: 20, min_interval_seconds: 0, hourly_limit: 0, consecutive_limit: 0 },
    };
    const profile = { ...(defaults[level] || defaults.normal), ...((free.profiles || {})[level] || {}) };
    const fields = {
        'free-reply-min-score': profile.min_score,
        'free-reply-min-interval': profile.min_interval_seconds,
        'free-reply-hourly-limit': profile.hourly_limit,
        'free-reply-consecutive-limit': profile.consecutive_limit,
    };
    Object.entries(fields).forEach(([id, value]) => {
        const input = document.getElementById(id);
        if (input) input.value = Number(value ?? 0);
    });
}

function buildWechatGroupSettingsPanel(ch) {
    const extra = ch.extra || {};
    const rooms = Array.isArray(extra.rooms) ? extra.rooms : [];
    const selectedIds = new Set(extra.selected_room_ids || []);
    const selectedNames = Array.isArray(extra.selected_room_names) ? extra.selected_room_names : [];
    const persona = extra.persona || {};
    const presets = Array.isArray(extra.persona_presets) ? extra.persona_presets : [];
    const activePreset = presets.find(preset => preset.id === persona.preset_id);
    const maxLength = Number(persona.max_length || 6000);
    const roomsHtml = rooms.length ? rooms.map(room => {
        const id = String(room.id || '');
        const name = String(room.name || id);
        const checked = selectedIds.has(id) ? 'checked' : '';
        return `<label class="flex items-start gap-2 rounded-lg px-2 py-2 text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 cursor-pointer">
            <input type="checkbox" class="mt-1 accent-primary-500" data-wechat-group-room-id="${escapeHtml(id)}" ${checked}>
            <span class="min-w-0">
                <span class="block text-slate-800 dark:text-slate-100 break-words">${escapeHtml(name)}</span>
                <span class="block text-xs text-slate-400 dark:text-slate-500 font-mono break-all">${escapeHtml(id)}</span>
            </span>
        </label>`;
    }).join('') : `<p class="rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 px-3 py-2 text-xs text-slate-500 dark:text-slate-400">${t('wechat_group_rooms_empty')}</p>`;
    const presetHtml = presets.map(preset => {
        const active = String(preset.prompt || '') === String(persona.prompt || '');
        return `<button type="button" onclick="applyWechatGroupPersonaPreset('${escapeHtml(preset.id || '')}')"
            class="text-left rounded-lg border px-3 py-2 transition-colors cursor-pointer ${active ? 'border-primary-400 bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-300' : 'border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 text-slate-600 dark:text-slate-300 hover:border-primary-300'}">
            <span class="flex items-center gap-1.5 text-sm font-medium">${escapeHtml(preset.name || preset.id || '')}${preset.badge ? `<span class="text-[10px] px-1.5 py-0.5 rounded bg-white/70 dark:bg-white/10 text-slate-500 dark:text-slate-400">${escapeHtml(preset.badge)}</span>` : ''}</span>
            ${preset.summary ? `<span class="block text-xs text-slate-400 dark:text-slate-500 mt-1 line-clamp-2">${escapeHtml(preset.summary)}</span>` : ''}
        </button>`;
    }).join('');
    return `<div class="mt-5 pt-5 border-t border-slate-200 dark:border-white/10 space-y-5" id="wechat-group-settings-panel">
        ${renderWechatGroupFreeReplySettings(extra)}
        <div class="space-y-3">
            <div class="flex items-center justify-between gap-3">
                <div>
                    <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('wechat_group_rooms_title')}</h4>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">${t('wechat_group_rooms_hint')}</p>
                </div>
                <button type="button" onclick="refreshWechatGroupRooms()"
                    class="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-white/10 text-xs text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-white/5 cursor-pointer transition-colors">
                    <i class="fas fa-rotate-right mr-1"></i>${t('wechat_group_rooms_refresh')}
                </button>
            </div>
            <div class="max-h-44 overflow-y-auto rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 p-1.5 space-y-1">${roomsHtml}</div>
            <div>
                <label class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('wechat_group_room_names_label')}</label>
                <textarea id="wechat-group-room-names" rows="2"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-white/5 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 font-mono transition-colors resize-y"
                    placeholder="${escapeHtml(t('wechat_group_room_names_placeholder'))}">${escapeHtml(selectedNames.join('\n'))}</textarea>
            </div>
        </div>
        <div class="space-y-3">
            <div>
                <h4 class="text-sm font-semibold text-slate-800 dark:text-slate-100">${t('wechat_group_persona_title')}</h4>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">${t('wechat_group_persona_hint')}</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-2" id="wechat-group-persona-presets">${presetHtml}</div>
            <div class="rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 px-3 py-2 text-xs text-slate-500 dark:text-slate-400">
                ${t('wechat_group_persona_active')}: <span class="text-slate-800 dark:text-slate-100">${escapeHtml(activePreset?.name || t('wechat_group_persona_custom'))}</span>
                <span id="wechat-group-persona-dirty" class="ml-2 text-primary-500">${t('wechat_group_persona_clean')}</span>
            </div>
            <div>
                <label class="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">${t('wechat_group_persona_prompt_label')}</label>
                <textarea id="wechat-group-persona-prompt" rows="7" maxlength="${maxLength}"
                    oninput="markWechatGroupPersonaDirty()"
                    class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-white/5 text-sm text-slate-800 dark:text-slate-100 focus:outline-none focus:border-primary-500 transition-colors resize-y"
                    placeholder="${escapeHtml(t('wechat_group_persona_prompt_placeholder'))}">${escapeHtml(persona.prompt || '')}</textarea>
                <p class="text-xs text-slate-500 dark:text-slate-400 mt-1"><span id="wechat-group-persona-count">${String(persona.prompt || '').length}</span>/${maxLength} · ${t('wechat_group_persona_boundary')}</p>
            </div>
        </div>
        <div class="flex items-center justify-end gap-3">
            <span id="ch-status-wechat_group" class="text-xs text-primary-500 opacity-0 transition-opacity duration-300"></span>
            <button type="button" id="ch-save-wechat-group-extra" onclick="saveWechatGroupSettings()"
                class="px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium cursor-pointer transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed">
                ${t('wechat_group_settings_save')}
            </button>
        </div>
    </div>`;
}

function applyWechatGroupPersonaPreset(presetId) {
    const ch = channelsData.find(item => item.name === 'wechat_group');
    const preset = (ch?.extra?.persona_presets || []).find(item => item.id === presetId);
    const textarea = document.getElementById('wechat-group-persona-prompt');
    if (!preset || !textarea) return;
    textarea.value = preset.prompt || '';
    markWechatGroupPersonaDirty();
}

function markWechatGroupPersonaDirty() {
    const ch = channelsData.find(item => item.name === 'wechat_group');
    const textarea = document.getElementById('wechat-group-persona-prompt');
    const counter = document.getElementById('wechat-group-persona-count');
    const dirty = document.getElementById('wechat-group-persona-dirty');
    if (counter && textarea) counter.textContent = String(textarea.value.length);
    if (dirty && ch) {
        const savedPrompt = ch.extra?.persona?.prompt || '';
        dirty.textContent = textarea && textarea.value !== savedPrompt ? t('wechat_group_persona_dirty') : t('wechat_group_persona_clean');
        dirty.classList.toggle('text-amber-500', textarea && textarea.value !== savedPrompt);
        dirty.classList.toggle('text-primary-500', !(textarea && textarea.value !== savedPrompt));
    }
}

function refreshWechatGroupRooms(options = {}) {
    const silent = !!options.silent;
    fetch('/api/wechat_group/qrlogin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'refresh' })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status !== 'success') {
            if (!silent) showChannelStatus('wechat_group', 'wechat_group_rooms_refresh_failed', true);
            return;
        }
        const ch = channelsData.find(item => item.name === 'wechat_group');
        if (ch) {
            // Keep current selection snapshot so a partial refresh payload cannot blank target groups.
            const previousSelection = {
                selected_room_ids: Array.isArray(ch.extra?.selected_room_ids) ? ch.extra.selected_room_ids.slice() : [],
                stable_selected_room_ids: Array.isArray(ch.extra?.stable_selected_room_ids) ? ch.extra.stable_selected_room_ids.slice() : [],
                runtime_selected_room_ids: Array.isArray(ch.extra?.runtime_selected_room_ids) ? ch.extra.runtime_selected_room_ids.slice() : [],
                selected_room_names: Array.isArray(ch.extra?.selected_room_names) ? ch.extra.selected_room_names.slice() : [],
            };
            ch.extra = data.extra || ch.extra || {};
            // Prefer normalized rooms from extra (id = stable_room_id || runtime_room_id).
            // Do NOT overwrite with raw data.rooms: raw Wechaty ids break checkbox matching against wgr_* selections.
            if (Array.isArray(data.extra?.rooms)) {
                ch.extra.rooms = data.extra.rooms;
            } else if (!Array.isArray(ch.extra.rooms) || !ch.extra.rooms.length) {
                ch.extra.rooms = Array.isArray(data.rooms) ? data.rooms : [];
            }
            if (!Array.isArray(ch.extra.selected_room_ids) || !ch.extra.selected_room_ids.length) {
                ch.extra.selected_room_ids = previousSelection.selected_room_ids;
            }
            if (!Array.isArray(ch.extra.stable_selected_room_ids) || !ch.extra.stable_selected_room_ids.length) {
                ch.extra.stable_selected_room_ids = previousSelection.stable_selected_room_ids;
            }
            if (!Array.isArray(ch.extra.runtime_selected_room_ids) || !ch.extra.runtime_selected_room_ids.length) {
                ch.extra.runtime_selected_room_ids = previousSelection.runtime_selected_room_ids;
            }
            if (!Array.isArray(ch.extra.selected_room_names) || !ch.extra.selected_room_names.length) {
                ch.extra.selected_room_names = previousSelection.selected_room_names;
            }
        }
        if (currentView === 'groups') {
            if (!silent) showGroupsStatus('wechat_group_rooms_refreshed', false);
            renderGroupsView();
        } else {
            if (!silent) showChannelStatus('wechat_group', 'wechat_group_rooms_refreshed', false);
            renderActiveChannels();
        }
    })
    .catch(() => {
        if (silent) return;
        if (currentView === 'groups') showGroupsStatus('wechat_group_rooms_refresh_failed', true);
        else showChannelStatus('wechat_group', 'wechat_group_rooms_refresh_failed', true);
    });
}

function saveWechatGroupSettings() {
    const ch = channelsData.find(item => item.name === 'wechat_group');
    if (!ch) return;
    const extra = ch.extra || {};
    const btn = document.getElementById('groups-save-btn') || document.getElementById('ch-save-wechat-group-extra');
    const prompt = document.getElementById('groups-persona-prompt')?.value ?? extra.persona?.prompt ?? '';
    const checkedRoomIds = Array.from(document.querySelectorAll('[data-groups-room-id]:checked:not(:disabled)')).map(el => el.dataset.groupsRoomId).filter(Boolean);
    const roomControlsPresent = !!document.getElementById('groups-room-dropdown');
    const selectedIds = resolveGroupsSelectedRoomIdsForSave(extra, checkedRoomIds, roomControlsPresent);
    const roomNameById = new Map();
    const runtimeRoomIdByStableId = new Map();
    (extra.rooms || []).forEach(room => {
        const optionId = getWechatGroupRoomOptionId(room);
        const name = String(room.name || '');
        const runtimeId = String(room.runtime_room_id || room.id || '').trim();
        [room.stable_room_id, room.id, room.runtime_room_id, optionId].forEach(key => {
            const id = String(key || '').trim();
            if (id && name) roomNameById.set(id, name);
            if (id && runtimeId) runtimeRoomIdByStableId.set(id, runtimeId);
        });
    });
    const persistedRoomIds = Array.isArray(extra.selected_room_ids) ? extra.selected_room_ids.map(String) : [];
    const persistedNameByRoomId = new Map(persistedRoomIds.map((id, idx) => [id, String(extra.selected_room_names?.[idx] || '')]));
    const stableSnapshotIds = Array.isArray(extra.stable_selected_room_ids) && extra.stable_selected_room_ids.length
        ? extra.stable_selected_room_ids.map(String)
        : persistedRoomIds;
    const persistedRuntimeByStableId = new Map(stableSnapshotIds.map((id, idx) => [id, String(extra.runtime_selected_room_ids?.[idx] || '')]));
    const selectedStableRoomIds = selectedIds;
    const selectedRuntimeRoomIds = selectedStableRoomIds
        .map(id => runtimeRoomIdByStableId.get(String(id)) || persistedRuntimeByStableId.get(String(id)) || '')
        .filter(Boolean);
    const selectedNames = roomControlsPresent
        ? selectedIds.map(id => roomNameById.get(String(id)) || persistedNameByRoomId.get(String(id)) || '').filter(Boolean)
        : (extra.selected_room_names || []);
    const basic = extra.basic || {};
    const admin = extra.admin || {};
    const sticker = readGroupsStickerConfig(extra.sticker || {});
    const aliasSyncCooldownMinutes = document.getElementById('groups-alias-sync-cooldown-minutes')
        ? Math.max(1, Number(document.getElementById('groups-alias-sync-cooldown-minutes').value || 1))
        : Number(basic.alias_sync_cooldown_minutes || 1);
    const basicProxy = document.getElementById('groups-basic-proxy')
        ? String(document.getElementById('groups-basic-proxy').value || '').trim()
        : String(basic.proxy || '').trim();
    const githubCommitNotify = readGroupsGithubCommitNotifySettings(extra.github_commit_notify || {});
    const githubCommitNotifyConfig = {
        github_commit_notify_enabled: githubCommitNotify.enabled,
        github_commit_notify_repository: githubCommitNotify.repository,
        github_commit_notify_branches: githubCommitNotify.branches,
        github_commit_notify_stable_room_id: githubCommitNotify.stable_room_id,
        github_commit_notify_max_commits: githubCommitNotify.max_commits,
        github_commit_notify_retry_hours: githubCommitNotify.retry_hours,
        github_commit_notify_delivery_retention_days: githubCommitNotify.delivery_retention_days,
    };
    if (Object.prototype.hasOwnProperty.call(githubCommitNotify, 'webhook_secret')) {
        githubCommitNotifyConfig.github_commit_notify_webhook_secret = githubCommitNotify.webhook_secret;
    }
    const humanization = readWechatGroupHumanizationSettings(extra.humanization || {}, extra.recent_context || {});
    const freeReply = readWechatGroupFreeReplySettings(extra.free_reply || {});
    const voiceInteractionMode = readWechatGroupVoiceInteractionMode(extra.voice_interaction || {});
    const freeReplyStableRoomIds = Array.isArray(freeReply.stable_room_ids) ? freeReply.stable_room_ids : [];
    const freeReplyRuntimeRoomIds = freeReplyStableRoomIds.length
        ? freeReplyStableRoomIds.map(id => runtimeRoomIdByStableId.get(String(id)) || '').filter(Boolean)
        : (Array.isArray(freeReply.legacy_room_ids) ? freeReply.legacy_room_ids : []);
    const image = readWechatGroupImageSettings(extra.image || {});
    if (btn) btn.disabled = true;
    fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'save',
            channel: 'wechat_group',
            config: {
                wechat_group_stable_room_ids: selectedStableRoomIds,
                wechat_group_room_ids: selectedRuntimeRoomIds,
                wechat_group_names: selectedNames,
                wechat_group_admin_members: (admin.members || []),
                wechat_group_blacklist_members: (admin.blacklist_members || []),
                wechat_group_admin_required_permissions: readGroupsAdminRequiredPermissions(admin.required_permissions || {}),
                wechat_group_persona_prompt: prompt,
                wechat_group_persona_preset_id: 'custom',
                wechat_group_alias_sync_cooldown_minutes: aliasSyncCooldownMinutes,
                tools_web_fetch_proxy: basicProxy,
                ...githubCommitNotifyConfig,
                wechat_group_humanized_context_enabled: humanization.enabled,
                wechat_group_context_persist_raw_user_only: humanization.persist_raw_user_only,
                wechat_group_reply_policy_enabled: humanization.reply_policy_enabled,
                wechat_group_recent_context_enabled: humanization.recent_enabled,
                wechat_group_recent_context_limit: humanization.recent_limit,
                wechat_group_recent_context_minutes: humanization.recent_minutes,
                wechat_group_archive_evidence_enabled: humanization.archive_evidence_enabled,
                wechat_group_archive_evidence_limit: humanization.archive_evidence_limit,
                wechat_group_archive_evidence_days: humanization.archive_evidence_days,
                wechat_group_archive_evidence_recent_limit: humanization.archive_evidence_recent_limit,
                wechat_group_local_summary_enabled: humanization.local_summary_enabled,
                wechat_group_local_summary_limit: humanization.local_summary_limit,
                wechat_group_local_summary_hours: humanization.local_summary_hours,
                wechat_group_reference_policy_enabled: humanization.reference_policy_enabled,
                wechat_group_link_policy_enabled: humanization.link_policy_enabled,
                wechat_group_response_cleanup_enabled: humanization.response_cleanup_enabled,
                wechat_group_response_cleanup_max_chars: humanization.response_cleanup_max_chars,
                wechat_group_free_reply_enabled: freeReply.enabled,
                wechat_group_free_reply_stable_room_ids: freeReplyStableRoomIds,
                wechat_group_free_reply_room_ids: freeReplyRuntimeRoomIds,
                wechat_group_free_reply_names: freeReply.names,
                wechat_group_free_reply_activity_level: freeReply.activity_level,
                wechat_group_free_reply_mute_minutes: freeReply.mute_minutes,
                wechat_group_free_reply_mute_mentions_enabled: freeReply.mute_mentions_enabled,
                wechat_group_free_reply_queue_ttl_seconds: freeReply.queue_ttl_seconds,
                wechat_group_free_reply_worker_max_workers: freeReply.worker_max_workers,
                wechat_group_free_reply_worker_queue_size: freeReply.worker_queue_size,
                wechat_group_free_reply_llm_judge_enabled: freeReply.llm_judge_enabled,
                wechat_group_free_reply_llm_judge_timeout_seconds: freeReply.llm_judge_timeout_seconds,
                wechat_group_free_reply_llm_judge_min_confidence: freeReply.llm_judge_min_confidence,
                wechat_group_free_reply_force_keywords: freeReply.force_keywords,
                wechat_group_free_reply_profiles: freeReply.profiles,
                wechat_group_free_reply_rule_scores: freeReply.rule_scores,
                wechat_group_free_reply_rule_enabled: freeReply.rule_enabled,
                wechat_group_voice_interaction_mode: voiceInteractionMode,
                wechat_group_image_understanding_enabled: image.understanding_enabled,
                wechat_group_image_understanding_comment_enabled: image.comment_enabled,
                wechat_group_image_understanding_prompt: image.understanding_prompt,
                wechat_group_image_understanding_cache_minutes: image.cache_minutes,
                wechat_group_free_reply_image_understanding_enabled: image.free_reply_understanding_enabled,
                wechat_group_multimodal_context_enabled: image.multimodal_context_enabled,
                wechat_group_multimodal_image_understanding_context_enabled: image.multimodal_image_understanding_context_enabled,
                wechat_group_multimodal_free_reply_image_context_enabled: image.multimodal_free_reply_image_context_enabled,
                wechat_group_multimodal_same_sender_window_seconds: image.multimodal_same_sender_window_seconds,
                wechat_group_multimodal_unique_image_window_seconds: image.multimodal_unique_image_window_seconds,
                wechat_group_multimodal_quote_sender_window_minutes: image.multimodal_quote_sender_window_minutes,
                wechat_group_multimodal_max_recent_messages: image.multimodal_max_recent_messages,
                wechat_group_image_create_hourly_limit: image.create_hourly_limit,
                image_generation_proxy_enabled: image.generation_proxy_enabled,
                image_generation_proxy_domains: image.generation_proxy_domains,
                wechat_group_video_understanding_enabled: image.video_understanding_enabled,
                wechat_group_forward_preview_enabled: image.forward_preview_enabled,
                wechat_group_quote_context_enabled: image.quote_context_enabled,
                wechat_group_sticker_enabled: sticker.enabled,
                wechat_group_sticker_auto_collect_enabled: sticker.auto_collect_enabled,
                wechat_group_sticker_context_limit: sticker.context_limit,
                wechat_group_sticker_reply_percent: sticker.reply_percent,
                wechat_group_sticker_max_size_mb: sticker.max_size_mb,
                wechat_group_sticker_daily_send_limit: sticker.daily_send_limit,
                wechat_group_sticker_storage_dir: sticker.storage_dir,
                wechat_group_sticker_online_search_enabled: sticker.online_search_enabled,
                wechat_group_sticker_online_provider: sticker.online_provider,
                wechat_group_sticker_online_endpoint: sticker.online_endpoint,
                wechat_group_sticker_online_allowed_domains: sticker.online_allowed_domains,
                wechat_group_sticker_online_allow_gif: sticker.online_allow_gif,
                wechat_group_sticker_online_search_count: sticker.online_search_count,
                wechat_group_sticker_cooldown_seconds: sticker.cooldown_seconds,
            },
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            const applied = Array.isArray(data.applied) ? data.applied : [];
            const freeReplyRuleControlsPresent = !!document.querySelector('[data-free-reply-rule-score], [data-free-reply-rule-enabled]');
            const freeReplyRulesPersisted = applied.includes('wechat_group_free_reply_rule_scores')
                || applied.includes('wechat_group_free_reply_rule_enabled');
            if (currentView === 'groups') {
                if (freeReplyRuleControlsPresent && !freeReplyRulesPersisted) {
                    showGroupsStatus('wechat_group_free_reply_rules_not_persisted', true);
                } else {
                    showGroupsStatus('wechat_group_settings_saved', false);
                }
                loadGroupsView();
            } else {
                showChannelStatus('wechat_group', 'wechat_group_settings_saved', false);
                loadChannelsView();
            }
        } else {
            if (currentView === 'groups') showGroupsStatus('channels_save_error', true);
            else showChannelStatus('wechat_group', 'channels_save_error', true);
        }
    })
    .catch(() => {
        if (currentView === 'groups') showGroupsStatus('channels_save_error', true);
        else showChannelStatus('wechat_group', 'channels_save_error', true);
    })
    .finally(() => { if (btn) btn.disabled = false; });
}

function readGroupsAdminRequiredPermissions(saved = {}) {
    const result = { ...saved };
    document.querySelectorAll('[data-groups-admin-permission]').forEach(el => {
        result[el.dataset.groupsAdminPermission] = !!el.checked;
    });
    return result;
}

function clampNumber(value, min, max, fallback) {
    const n = Number(value);
    if (!Number.isFinite(n)) return fallback;
    return Math.min(Math.max(n, min), max);
}

function readWechatGroupImageSettings(saved = {}) {
    return {
        understanding_enabled: document.getElementById('groups-image-understanding-enabled')
            ? !!document.getElementById('groups-image-understanding-enabled').checked
            : saved.understanding_enabled !== false,
        comment_enabled: document.getElementById('groups-image-comment-enabled')
            ? !!document.getElementById('groups-image-comment-enabled').checked
            : saved.comment_enabled !== false,
        understanding_prompt: document.getElementById('groups-image-understanding-prompt')
            ? String(document.getElementById('groups-image-understanding-prompt').value || '').trim()
            : String(saved.understanding_prompt || '').trim(),
        cache_minutes: clampNumber(document.getElementById('groups-image-cache-minutes')?.value, 1, 120, saved.cache_minutes ?? 30),
        free_reply_understanding_enabled: document.getElementById('groups-image-free-reply-understanding-enabled')
            ? !!document.getElementById('groups-image-free-reply-understanding-enabled').checked
            : saved.free_reply_understanding_enabled === true,
        multimodal_context_enabled: document.getElementById('groups-multimodal-context-enabled')
            ? !!document.getElementById('groups-multimodal-context-enabled').checked
            : saved.multimodal_context_enabled !== false,
        multimodal_image_understanding_context_enabled: document.getElementById('groups-multimodal-image-context-enabled')
            ? !!document.getElementById('groups-multimodal-image-context-enabled').checked
            : saved.multimodal_image_understanding_context_enabled !== false,
        multimodal_free_reply_image_context_enabled: document.getElementById('groups-multimodal-free-reply-image-context-enabled')
            ? !!document.getElementById('groups-multimodal-free-reply-image-context-enabled').checked
            : saved.multimodal_free_reply_image_context_enabled === true,
        multimodal_same_sender_window_seconds: clampNumber(document.getElementById('groups-multimodal-same-sender-window-seconds')?.value, 5, 600, saved.multimodal_same_sender_window_seconds ?? 120),
        multimodal_unique_image_window_seconds: clampNumber(document.getElementById('groups-multimodal-unique-image-window-seconds')?.value, 5, 600, saved.multimodal_unique_image_window_seconds ?? 120),
        multimodal_quote_sender_window_minutes: clampNumber(document.getElementById('groups-multimodal-quote-sender-window-minutes')?.value, 1, 120, saved.multimodal_quote_sender_window_minutes ?? 30),
        multimodal_max_recent_messages: clampNumber(document.getElementById('groups-multimodal-max-recent-messages')?.value, 1, 100, saved.multimodal_max_recent_messages ?? 20),
        create_hourly_limit: clampNumber(document.getElementById('groups-image-create-hourly-limit')?.value, 0, 100, saved.create_hourly_limit ?? 5),
        generation_proxy_enabled: document.getElementById('groups-image-generation-proxy-enabled')
            ? !!document.getElementById('groups-image-generation-proxy-enabled').checked
            : saved.generation_proxy_enabled === true,
        generation_proxy_domains: document.getElementById('groups-image-generation-proxy-domains')
            ? String(document.getElementById('groups-image-generation-proxy-domains').value || '').trim()
            : (Array.isArray(saved.generation_proxy_domains) ? saved.generation_proxy_domains : []),
        video_understanding_enabled: document.getElementById('groups-video-understanding-enabled')
            ? !!document.getElementById('groups-video-understanding-enabled').checked
            : saved.video_understanding_enabled === true,
        forward_preview_enabled: document.getElementById('groups-forward-preview-enabled')
            ? !!document.getElementById('groups-forward-preview-enabled').checked
            : saved.forward_preview_enabled !== false,
        quote_context_enabled: document.getElementById('groups-quote-context-enabled')
            ? !!document.getElementById('groups-quote-context-enabled').checked
            : saved.quote_context_enabled !== false,
    };
}

function readFreeReplyRuleAttr(input, name) {
    if (!input) return '';
    const fromAttr = input.getAttribute(name);
    if (fromAttr != null && String(fromAttr).trim() !== '') {
        return String(fromAttr).trim();
    }
    // Fallback for browsers that only expose camelCase dataset keys.
    const datasetKey = String(name || '')
        .replace(/^data-/, '')
        .split('-')
        .map((part, index) => (index === 0 ? part : part.charAt(0).toUpperCase() + part.slice(1)))
        .join('');
    return String(input.dataset?.[datasetKey] || '').trim();
}

function readWechatGroupFreeReplyRuleScores(saved = {}) {
    const scores = JSON.parse(JSON.stringify(saved.rule_scores || {}));
    // Prefer rules snapshot defaults so partial DOM reads still keep a full map.
    const rules = saved.rules || {};
    (Array.isArray(rules.positive) ? rules.positive : []).forEach(rule => {
        const ruleId = String(rule?.id || '').trim();
        if (!ruleId || ruleId in scores) return;
        if (rule.score_kind === 'by_level' || ruleId === 'banter_opportunity') {
            scores[ruleId] = { ...(rule.score_by_level || {}) };
            return;
        }
        if (typeof rule.score === 'number') {
            scores[ruleId] = rule.score;
        }
    });
    const scoreInputs = document.querySelectorAll('[data-free-reply-rule-score]');
    if (!scoreInputs.length) {
        return scores;
    }
    scoreInputs.forEach(input => {
        const ruleId = readFreeReplyRuleAttr(input, 'data-free-reply-rule-score');
        if (!ruleId) return;
        const level = readFreeReplyRuleAttr(input, 'data-free-reply-rule-level');
        const fallback = level
            ? (scores?.[ruleId] && typeof scores[ruleId] === 'object' ? scores[ruleId][level] : 0)
            : (scores?.[ruleId] ?? 0);
        const value = clampNumber(input.value, 0, 100, fallback);
        if (level) {
            if (!scores[ruleId] || typeof scores[ruleId] !== 'object' || Array.isArray(scores[ruleId])) {
                scores[ruleId] = {};
            }
            scores[ruleId][level] = value;
            return;
        }
        scores[ruleId] = value;
    });
    return scores;
}

function readWechatGroupFreeReplyRuleEnabled(saved = {}) {
    const enabled = JSON.parse(JSON.stringify(saved.rule_enabled || {}));
    const rules = saved.rules || {};
    (Array.isArray(rules.negative) ? rules.negative : []).forEach(rule => {
        const ruleId = String(rule?.id || '').trim();
        if (!ruleId || ruleId in enabled) return;
        enabled[ruleId] = rule.enabled !== false;
    });
    const inputs = document.querySelectorAll('[data-free-reply-rule-enabled]');
    if (!inputs.length) {
        return enabled;
    }
    inputs.forEach(input => {
        const ruleId = readFreeReplyRuleAttr(input, 'data-free-reply-rule-enabled');
        if (!ruleId) return;
        enabled[ruleId] = !!input.checked;
    });
    return enabled;
}

function readWechatGroupFreeReplySettings(saved = {}) {
    const level = document.getElementById('free-reply-activity-level')?.value || saved.activity_level || 'normal';
    const profiles = JSON.parse(JSON.stringify(saved.profiles || {}));
    const roomControlsPresent = !!document.querySelector('[data-wechat-group-free-reply-room-id]');
    const selectedRoomIds = roomControlsPresent
        ? Array.from(document.querySelectorAll('[data-wechat-group-free-reply-room-id]:checked:not(:disabled)')).map(el => el.dataset.wechatGroupFreeReplyRoomId).filter(Boolean)
        : [];
    profiles[level] = {
        min_score: clampNumber(document.getElementById('free-reply-min-score')?.value, 0, 100, profiles[level]?.min_score ?? 50),
        min_interval_seconds: clampNumber(document.getElementById('free-reply-min-interval')?.value, 0, 3600, profiles[level]?.min_interval_seconds ?? 10),
        hourly_limit: clampNumber(document.getElementById('free-reply-hourly-limit')?.value, 0, 999, profiles[level]?.hourly_limit ?? 0),
        consecutive_limit: clampNumber(document.getElementById('free-reply-consecutive-limit')?.value, 0, 99, profiles[level]?.consecutive_limit ?? 0),
    };
    return {
        enabled: document.getElementById('free-reply-enabled') ? !!document.getElementById('free-reply-enabled').checked : !!saved.enabled,
        room_ids: roomControlsPresent
            ? selectedRoomIds
            : (saved.room_ids || []),
        stable_room_ids: roomControlsPresent
            ? selectedRoomIds
            : (Array.isArray(saved.stable_room_ids) ? saved.stable_room_ids : []),
        legacy_room_ids: roomControlsPresent ? [] : (saved.legacy_room_ids || []),
        names: document.getElementById('free-reply-names') ? splitWechatGroupLines(document.getElementById('free-reply-names').value || '') : (saved.names || []),
        force_keywords: document.getElementById('free-reply-force-keywords') ? splitWechatGroupList(document.getElementById('free-reply-force-keywords').value || '') : (saved.force_keywords || []),
        activity_level: ['quiet', 'normal', 'active', 'crazy'].includes(level) ? level : 'normal',
        mute_minutes: clampNumber(document.getElementById('free-reply-mute-minutes')?.value, 1, 1440, saved.mute_minutes ?? 10),
        mute_mentions_enabled: document.getElementById('free-reply-mute-mentions-enabled')
            ? !!document.getElementById('free-reply-mute-mentions-enabled').checked
            : saved.mute_mentions_enabled === true,
        queue_ttl_seconds: clampNumber(document.getElementById('free-reply-queue-ttl')?.value, 10, 600, saved.queue_ttl_seconds ?? 120),
        worker_max_workers: clampNumber(document.getElementById('free-reply-worker-max-workers')?.value, 1, 8, saved.worker_max_workers ?? 2),
        worker_queue_size: clampNumber(document.getElementById('free-reply-worker-queue-size')?.value, 1, 1000, saved.worker_queue_size ?? 100),
        llm_judge_enabled: document.getElementById('free-reply-llm-enabled') ? !!document.getElementById('free-reply-llm-enabled').checked : saved.llm_judge_enabled !== false,
        llm_judge_timeout_seconds: clampNumber(document.getElementById('free-reply-llm-timeout')?.value, 1, 30, saved.llm_judge_timeout_seconds ?? 8),
        llm_judge_min_confidence: clampNumber(document.getElementById('free-reply-llm-confidence')?.value, 0, 1, saved.llm_judge_min_confidence ?? 0.6),
        profiles,
        rule_scores: readWechatGroupFreeReplyRuleScores(saved),
        rule_enabled: readWechatGroupFreeReplyRuleEnabled(saved),
    };
}

function buildChannelFieldsHtml(chName, fields) {
    let html = '';
    fields.forEach(f => {
        const inputId = `ch-${chName}-${f.key}`;
        let inputHtml = '';
        if (f.type === 'bool') {
            const checked = f.value ? 'checked' : '';
            inputHtml = `<label class="relative inline-flex items-center cursor-pointer">
                <input id="${inputId}" type="checkbox" ${checked} class="sr-only peer" data-field="${f.key}" data-ch="${chName}">
                <div class="w-9 h-5 bg-slate-200 dark:bg-slate-700 peer-checked:bg-primary-400 rounded-full
                            after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white
                            after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full"></div>
            </label>`;
        } else if (f.type === 'secret') {
            inputHtml = `<input id="${inputId}" type="text" value="${escapeHtml(String(f.value || ''))}"
                data-field="${f.key}" data-ch="${chName}" data-masked="${f.value ? '1' : ''}"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600
                       bg-slate-50 dark:bg-white/5 text-sm text-slate-800 dark:text-slate-100
                       focus:outline-none focus:border-primary-500 font-mono transition-colors
                       ${f.value ? 'cfg-key-masked' : ''}"
                placeholder="${escapeHtml(f.label)}">`;
        } else {
            const inputType = f.type === 'number' ? 'number' : 'text';
            inputHtml = `<input id="${inputId}" type="${inputType}" value="${escapeHtml(String(f.value ?? f.default ?? ''))}"
                data-field="${f.key}" data-ch="${chName}"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600
                       bg-slate-50 dark:bg-white/5 text-sm text-slate-800 dark:text-slate-100
                       focus:outline-none focus:border-primary-500 font-mono transition-colors"
                placeholder="${escapeHtml(f.label)}">`;
        }
        html += `<div>
            <label class="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">${escapeHtml(f.label)}</label>
            ${inputHtml}
        </div>`;
    });
    return html;
}

function bindSecretFieldEvents(container) {
    container.querySelectorAll('input[data-masked="1"]').forEach(inp => {
        inp.addEventListener('focus', function() {
            if (this.dataset.masked === '1') {
                this.value = '';
                this.dataset.masked = '';
                this.classList.remove('cfg-key-masked');
            }
        });
    });
}

function showChannelStatus(chName, msgKey, isError) {
    const el = document.getElementById(`ch-status-${chName}`);
    if (!el) return;
    el.textContent = t(msgKey);
    el.classList.toggle('text-red-500', !!isError);
    el.classList.toggle('text-primary-500', !isError);
    el.classList.remove('opacity-0');
    setTimeout(() => el.classList.add('opacity-0'), 2500);
}

function saveChannelConfig(chName) {
    const card = document.getElementById(`channel-card-${chName}`);
    if (!card) return;

    const updates = {};
    card.querySelectorAll('input[data-ch="' + chName + '"]').forEach(inp => {
        const key = inp.dataset.field;
        if (inp.type === 'checkbox') {
            updates[key] = inp.checked;
        } else {
            if (inp.dataset.masked === '1') return;
            updates[key] = inp.value;
        }
    });

    const btn = document.getElementById(`ch-save-${chName}`);
    if (btn) btn.disabled = true;

    fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'save', channel: chName, config: updates })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            showChannelStatus(chName, data.restarted ? 'channels_restarted' : 'channels_saved', false);
        } else {
            showChannelStatus(chName, 'channels_save_error', true);
        }
    })
    .catch(() => showChannelStatus(chName, 'channels_save_error', true))
    .finally(() => { if (btn) btn.disabled = false; });
}

function disconnectChannel(chName) {
    const ch = channelsData.find(c => c.name === chName);
    const label = ch ? ((typeof ch.label === 'object') ? (ch.label[currentLang] || ch.label.en) : ch.label) : chName;

    showConfirmDialog({
        title: t('channels_disconnect'),
        message: t('channels_disconnect_confirm'),
        okText: t('channels_disconnect'),
        cancelText: t('channels_cancel'),
        onConfirm: () => {
            fetch('/api/channels', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'disconnect', channel: chName })
            })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    if (ch) ch.active = false;
                    renderActiveChannels();
                }
            })
            .catch(() => {});
        }
    });
}

// --- Add channel panel ---
function openAddChannelPanel() {
    const panel = document.getElementById('channels-add-panel');
    const activeNames = new Set(channelsData.filter(c => c.active).map(c => c.name));
    const available = channelsData.filter(c => !activeNames.has(c.name));

    const content = document.getElementById('channels-content');
    if (activeNames.size === 0 && content) content.classList.add('hidden');

    if (available.length === 0) {
        panel.innerHTML = `<div class="bg-white dark:bg-[#1A1A1A] rounded-xl border border-slate-200 dark:border-white/10 p-6 text-center">
            <p class="text-sm text-slate-500 dark:text-slate-400">${currentLang === 'zh' ? '所有通道均已接入' : 'All channels are already connected'}</p>
            <button onclick="closeAddChannelPanel()" class="mt-3 text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer">${t('channels_cancel')}</button>
        </div>`;
        panel.classList.remove('hidden');
        return;
    }

    const ddOptions = [
        { value: '', label: t('channels_select_placeholder') },
        ...available.map(ch => {
            const label = (typeof ch.label === 'object') ? (ch.label[currentLang] || ch.label.en) : ch.label;
            return { value: ch.name, label: `${label} (${ch.name})` };
        })
    ];

    panel.innerHTML = `
        <div class="bg-white dark:bg-[#1A1A1A] rounded-xl border border-primary-200 dark:border-primary-800 p-6">
            <div class="flex items-center gap-3 mb-5">
                <div class="w-9 h-9 rounded-lg bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center">
                    <i class="fas fa-plus text-primary-500 text-sm"></i>
                </div>
                <h3 class="font-semibold text-slate-800 dark:text-slate-100">${t('channels_add')}</h3>
            </div>
            <div class="mb-4">
                <div id="add-channel-select" class="cfg-dropdown" tabindex="0">
                    <div class="cfg-dropdown-selected">
                        <span class="cfg-dropdown-text">--</span>
                        <i class="fas fa-chevron-down cfg-dropdown-arrow"></i>
                    </div>
                    <div class="cfg-dropdown-menu"></div>
                </div>
            </div>
            <div id="add-channel-fields" class="space-y-4"></div>
            <div id="add-channel-actions" class="hidden flex items-center justify-end gap-3 pt-4">
                <button onclick="closeAddChannelPanel()"
                    class="px-4 py-2 rounded-lg border border-slate-200 dark:border-white/10
                           text-slate-600 dark:text-slate-300 text-sm font-medium
                           hover:bg-slate-50 dark:hover:bg-white/5
                           cursor-pointer transition-colors duration-150">${t('channels_cancel')}</button>
                <button id="add-channel-submit" onclick="submitAddChannel()"
                    class="px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium
                           cursor-pointer transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed">${t('channels_connect_btn')}</button>
            </div>
        </div>`;
    panel.classList.remove('hidden');
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    const ddEl = document.getElementById('add-channel-select');
    initDropdown(ddEl, ddOptions, '', onAddChannelSelect);
}

function closeAddChannelPanel() {
    stopWeixinQrPoll();
    stopFeishuRegisterPoll();
    const panel = document.getElementById('channels-add-panel');
    if (panel) {
        panel.classList.add('hidden');
        panel.innerHTML = '';
    }
    const content = document.getElementById('channels-content');
    if (content) content.classList.remove('hidden');
}

function onAddChannelSelect(chName) {
    stopWeixinQrPoll();
    stopFeishuRegisterPoll();
    const fieldsContainer = document.getElementById('add-channel-fields');
    const actions = document.getElementById('add-channel-actions');

    if (!chName) {
        fieldsContainer.innerHTML = '';
        actions.classList.add('hidden');
        return;
    }

    if (chName === 'weixin' || chName === 'wechat_group') {
        actions.classList.add('hidden');
        fieldsContainer.innerHTML = `
            <div id="weixin-qr-panel" class="flex flex-col items-center py-4">
                <p class="text-sm text-slate-500 dark:text-slate-400 mb-4">${t(chName === 'wechat_group' ? 'wechat_group_scan_loading' : 'weixin_scan_loading')}</p>
            </div>`;
        if (chName === 'wechat_group') {
            startWechatGroupQrLogin();
        } else {
            startWeixinQrLogin();
        }
        return;
    }

    if (chName === 'wecom_bot') {
        actions.classList.add('hidden');
        const ch = channelsData.find(c => c.name === chName);
        fieldsContainer.innerHTML = buildWecomBotPanel(ch);
        return;
    }

    if (chName === 'feishu') {
        actions.classList.add('hidden');
        const ch = channelsData.find(c => c.name === chName);
        fieldsContainer.innerHTML = buildFeishuPanel(ch);
        return;
    }

    const ch = channelsData.find(c => c.name === chName);
    if (!ch) return;

    fieldsContainer.innerHTML = buildChannelFieldsHtml(chName, ch.fields || []);
    bindSecretFieldEvents(fieldsContainer);
    actions.classList.remove('hidden');
}

function submitAddChannel() {
    const ddEl = document.getElementById('add-channel-select');
    const chName = getDropdownValue(ddEl);
    if (!chName) return;

    const fieldsContainer = document.getElementById('add-channel-fields');
    const updates = {};
    fieldsContainer.querySelectorAll('input[data-ch="' + chName + '"]').forEach(inp => {
        const key = inp.dataset.field;
        if (inp.type === 'checkbox') {
            updates[key] = inp.checked;
        } else {
            if (inp.dataset.masked === '1') return;
            updates[key] = inp.value;
        }
    });

    const btn = document.getElementById('add-channel-submit');
    if (btn) { btn.disabled = true; btn.textContent = t('channels_connecting'); }

    fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'connect', channel: chName, config: updates })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            const ch = channelsData.find(c => c.name === chName);
            if (ch) {
                ch.active = true;
                (ch.fields || []).forEach(f => {
                    if (updates[f.key] !== undefined) {
                        f.value = f.type === 'secret' ? ChannelsHandler_maskSecret(updates[f.key]) : updates[f.key];
                    }
                });
            }
            renderActiveChannels();
        } else {
            if (btn) { btn.disabled = false; btn.textContent = t('channels_connect_btn'); }
        }
    })
    .catch(() => {
        if (btn) { btn.disabled = false; btn.textContent = t('channels_connect_btn'); }
    });
}

// =====================================================================
// WeChat QR Login
// =====================================================================
let _weixinQrPollTimer = null;
let _weixinStatusPollTimer = null;

function stopWeixinStatusPoll() {
    if (_weixinStatusPollTimer) {
        clearTimeout(_weixinStatusPollTimer);
        _weixinStatusPollTimer = null;
    }
}

function startWeixinActiveStatusPoll() {
    stopWeixinStatusPoll();
    _weixinStatusPollTimer = setTimeout(() => {
        fetch('/api/channels').then(r => r.json()).then(data => {
            if (data.status !== 'success') return;
            const wx = (data.channels || []).find(c => c.name === 'weixin');
            if (!wx || !wx.active) return;
            if (wx.login_status === 'logged_in') {
                channelsData = data.channels;
                renderActiveChannels();
            } else {
                const ch = channelsData.find(c => c.name === 'weixin');
                if (ch) ch.login_status = wx.login_status;
                startWeixinActiveStatusPoll();
            }
        }).catch(() => { startWeixinActiveStatusPoll(); });
    }, 3000);
}

function showWeixinActiveQr() {
    const container = document.getElementById('weixin-active-qr');
    if (!container) return;
    container.innerHTML = `
        <div id="weixin-qr-panel" class="flex flex-col items-center py-2">
            <p class="text-sm text-slate-500 dark:text-slate-400 mb-4">${t('weixin_scan_loading')}</p>
        </div>`;
    stopWeixinStatusPoll();
    startWeixinQrLogin();
}

function stopWeixinQrPoll() {
    if (_weixinQrPollTimer) {
        clearTimeout(_weixinQrPollTimer);
        _weixinQrPollTimer = null;
    }
}

function startWeixinQrLogin() {
    stopWeixinQrPoll();
    fetch('/api/weixin/qrlogin')
        .then(r => r.json())
        .then(data => {
            const panel = document.getElementById('weixin-qr-panel');
            if (!panel) return;
            if (data.status !== 'success') {
                panel.innerHTML = `<p class="text-sm text-red-500">${t('weixin_scan_fail')}: ${data.message || ''}</p>`;
                return;
            }
            renderWeixinQr(data.qr_image || data.qrcode_url, 'waiting');
            if (data.source === 'channel') {
                startWeixinActiveStatusPoll();
            } else {
                pollWeixinQrStatus();
            }
        })
        .catch(() => {
            const panel = document.getElementById('weixin-qr-panel');
            if (panel) panel.innerHTML = `<p class="text-sm text-red-500">${t('weixin_scan_fail')}</p>`;
        });
}

function renderWeixinQr(qrcodeUrl, status) {
    const panel = document.getElementById('weixin-qr-panel');
    if (!panel) return;

    let statusText = t('weixin_scan_waiting');
    let statusColor = 'text-slate-500 dark:text-slate-400';
    if (status === 'scanned') {
        statusText = t('weixin_scan_scanned');
        statusColor = 'text-primary-500';
    } else if (status === 'expired') {
        statusText = t('weixin_scan_expired');
        statusColor = 'text-amber-500';
    } else if (status === 'confirmed') {
        statusText = t('weixin_scan_success');
        statusColor = 'text-primary-500';
    }

    panel.innerHTML = `
        <div class="flex flex-col items-center">
            <p class="text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">${t('weixin_scan_title')}</p>
            <p class="text-xs text-slate-400 dark:text-slate-500 mb-4">${t('weixin_scan_desc')}</p>
            <div class="bg-white p-3 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700 mb-3">
                <img src="${escapeHtml(qrcodeUrl)}" alt="QR Code" class="w-52 h-52" style="image-rendering: pixelated;"/>
            </div>
            <p class="text-xs ${statusColor} mb-1">${statusText}</p>
            <p class="text-xs text-slate-400 dark:text-slate-500">${t('weixin_qr_tip')}</p>
        </div>`;
}

function pollWeixinQrStatus() {
    _weixinQrPollTimer = setTimeout(() => {
        fetch('/api/weixin/qrlogin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'poll' })
        })
        .then(r => r.json())
        .then(data => {
            const panel = document.getElementById('weixin-qr-panel');
            if (!panel) { stopWeixinQrPoll(); return; }

            if (data.status !== 'success') {
                pollWeixinQrStatus();
                return;
            }

            const qrStatus = data.qr_status;
            if (qrStatus === 'confirmed') {
                renderWeixinQr('', 'confirmed');
                panel.innerHTML = `
                    <div class="flex flex-col items-center py-4">
                        <div class="w-12 h-12 rounded-full bg-primary-50 dark:bg-primary-900/30 flex items-center justify-center mb-3">
                            <i class="fas fa-check text-primary-500 text-lg"></i>
                        </div>
                        <p class="text-sm font-medium text-primary-600 dark:text-primary-400">${t('weixin_scan_success')}</p>
                    </div>`;
                connectWeixinAfterQr();
            } else if (qrStatus === 'expired' && (data.qr_image || data.qrcode_url)) {
                renderWeixinQr(data.qr_image || data.qrcode_url, 'waiting');
                pollWeixinQrStatus();
            } else if (qrStatus === 'scaned') {
                const img = panel.querySelector('img');
                const currentSrc = img ? img.src : '';
                renderWeixinQr(currentSrc, 'scanned');
                pollWeixinQrStatus();
            } else {
                pollWeixinQrStatus();
            }
        })
        .catch(() => {
            pollWeixinQrStatus();
        });
    }, 2000);
}

function connectWeixinAfterQr() {
    fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'connect', channel: 'weixin', config: {} })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            const ch = channelsData.find(c => c.name === 'weixin');
            if (ch) ch.active = true;
            setTimeout(() => renderActiveChannels(), 1500);
        }
    })
    .catch(() => {});
}

function startWechatGroupQrLogin() {
    stopWeixinQrPoll();
    fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'connect', channel: 'wechat_group', config: {} })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status !== 'success') {
            const panel = document.getElementById('weixin-qr-panel');
            if (panel) panel.innerHTML = `<p class="text-sm text-red-500">${t('wechat_group_scan_fail')}: ${data.message || ''}</p>`;
            return;
        }
        pollWechatGroupQrStatus(true);
    })
    .catch(() => {
        const panel = document.getElementById('weixin-qr-panel');
        if (panel) panel.innerHTML = `<p class="text-sm text-red-500">${t('wechat_group_scan_fail')}</p>`;
    });
}

function renderWechatGroupQr(qrcodeUrl, status) {
    const panel = document.getElementById('weixin-qr-panel');
    if (!panel) return;

    let statusText = t('weixin_scan_waiting');
    let statusColor = 'text-slate-500 dark:text-slate-400';
    if (status === 'connected') {
        statusText = t('wechat_group_scan_success');
        statusColor = 'text-primary-500';
    }

    panel.innerHTML = `
        <div class="flex flex-col items-center">
            <p class="text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">${t('wechat_group_scan_title')}</p>
            <p class="text-xs text-slate-400 dark:text-slate-500 mb-4">${t('wechat_group_scan_desc')}</p>
            <div class="bg-white p-3 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700 mb-3">
                <img src="${escapeHtml(qrcodeUrl || '')}" alt="QR Code" class="w-52 h-52" style="image-rendering: pixelated;"/>
            </div>
            <p class="text-xs ${statusColor} mb-1">${statusText}</p>
            <p class="text-xs text-slate-400 dark:text-slate-500">${t('wechat_group_qr_tip')}</p>
        </div>`;
}

function pollWechatGroupQrStatus(immediate) {
    _weixinQrPollTimer = setTimeout(() => {
        fetch('/api/wechat_group/qrlogin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'poll' })
        })
        .then(r => r.json())
        .then(data => {
            const panel = document.getElementById('weixin-qr-panel');
            if (!panel) { stopWeixinQrPoll(); return; }
            if (data.status !== 'success') {
                pollWechatGroupQrStatus(false);
                return;
            }
            if (data.login_status === 'connected' || data.login_status === 'logged_in') {
                renderWechatGroupQr(data.qr_image || data.qrcode_url || '', 'connected');
                setTimeout(() => loadChannelsView(), 1200);
            } else {
                if (data.qr_image || data.qrcode_url) {
                    renderWechatGroupQr(data.qr_image || data.qrcode_url, 'waiting');
                }
                pollWechatGroupQrStatus(false);
            }
        })
        .catch(() => pollWechatGroupQrStatus(false));
    }, immediate ? 0 : 2000);
}

// =====================================================================
// WeCom Bot QR Auth
// =====================================================================
// NOTE: This is the only remaining external script in the Web Console.
// Tencent's WeCom Bot SDK must be loaded from their official CDN — it
// performs runtime origin/signature checks and will not work if
// self-hosted. The SDK is fetched lazily, only when the user opens the
// "WeCom Bot" channel QR-login flow, so the rest of the console works
// fully offline.
const WECOM_BOT_SDK_URL = 'https://wwcdn.weixin.qq.com/node/wework/js/wecom-aibot-sdk@0.1.0.min.js';
const WECOM_BOT_SOURCE = 'lightagent';
let _wecomSdkLoaded = false;

function ensureWecomSdkLoaded() {
    return new Promise((resolve, reject) => {
        if (_wecomSdkLoaded && window.WecomAIBotSDK) { resolve(); return; }
        if (document.querySelector(`script[src="${WECOM_BOT_SDK_URL}"]`)) {
            _wecomSdkLoaded = true; resolve(); return;
        }
        const s = document.createElement('script');
        s.src = WECOM_BOT_SDK_URL;
        s.onload = () => { _wecomSdkLoaded = true; resolve(); };
        s.onerror = () => reject(new Error('Failed to load WecomAIBotSDK'));
        document.head.appendChild(s);
    });
}

function _wecomBotHasCreds(ch) {
    if (!ch || !ch.fields) return false;
    const idField = ch.fields.find(f => f.key === 'wecom_bot_id');
    const secretField = ch.fields.find(f => f.key === 'wecom_bot_secret');
    return !!(idField && idField.value && secretField && secretField.value);
}

function buildWecomBotPanel(ch) {
    const scanLabel = t('wecom_mode_scan');
    const manualLabel = t('wecom_mode_manual');
    const hasCreds = _wecomBotHasCreds(ch);
    const defaultMode = hasCreds ? 'manual' : 'scan';
    return `
        <div id="wecom-bot-panel" data-default-mode="${defaultMode}">
            <div class="flex items-center justify-center gap-1 mb-5 bg-slate-100 dark:bg-white/5 rounded-lg p-1">
                <button id="wecom-tab-scan" onclick="switchWecomBotMode('scan')"
                    class="flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors
                           bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 shadow-sm">
                    ${scanLabel}
                </button>
                <button id="wecom-tab-manual" onclick="switchWecomBotMode('manual')"
                    class="flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors
                           text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
                    ${manualLabel}
                </button>
            </div>
            <div id="wecom-mode-content"></div>
        </div>`;
}

function switchWecomBotMode(mode) {
    const scanTab = document.getElementById('wecom-tab-scan');
    const manualTab = document.getElementById('wecom-tab-manual');
    const content = document.getElementById('wecom-mode-content');
    const actions = document.getElementById('add-channel-actions');
    if (!scanTab || !manualTab || !content) return;

    const activeClasses = 'bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 shadow-sm';
    const inactiveClasses = 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200';

    if (mode === 'scan') {
        scanTab.className = scanTab.className.replace(/text-slate-500[^\s]*/g, '').replace(/hover:\S+/g, '');
        scanTab.className = `flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${activeClasses}`;
        manualTab.className = `flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${inactiveClasses}`;
        actions.classList.add('hidden');
        content.innerHTML = `
            <div class="flex flex-col items-center py-4">
                <p class="text-sm text-slate-600 dark:text-slate-300 mb-2">${t('wecom_scan_desc')}</p>
                <button onclick="startWecomBotAuth()"
                    class="mt-3 px-6 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium
                           cursor-pointer transition-colors duration-150">
                    <i class="fas fa-qrcode mr-2"></i>${t('wecom_scan_btn')}
                </button>
                <div id="wecom-scan-status" class="mt-3"></div>
            </div>`;
    } else {
        manualTab.className = `flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${activeClasses}`;
        scanTab.className = `flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${inactiveClasses}`;
        const ch = channelsData.find(c => c.name === 'wecom_bot');
        content.innerHTML = `<div class="space-y-4">${buildChannelFieldsHtml('wecom_bot', ch ? ch.fields || [] : [])}</div>`;
        bindSecretFieldEvents(content);
        actions.classList.remove('hidden');
    }
}

function startWecomBotAuth() {
    const statusEl = document.getElementById('wecom-scan-status');
    ensureWecomSdkLoaded().then(() => {
        WecomAIBotSDK.openBotInfoAuthWindow({
            source: WECOM_BOT_SOURCE,
            onCreated: function(bot) {
                if (statusEl) {
                    statusEl.innerHTML = `
                        <div class="flex flex-col items-center py-2">
                            <div class="w-10 h-10 rounded-full bg-emerald-50 dark:bg-emerald-900/30 flex items-center justify-center mb-2">
                                <i class="fas fa-check text-emerald-500 text-lg"></i>
                            </div>
                            <p class="text-sm font-medium text-emerald-600 dark:text-emerald-400">${t('wecom_scan_success')}</p>
                        </div>`;
                }
                connectWecomBotAfterAuth(bot.botid, bot.secret);
            },
            onError: function(err) {
                if (statusEl) {
                    statusEl.innerHTML = `<p class="text-sm text-red-500">${t('wecom_scan_fail')}: ${err.message || err.code || ''}</p>`;
                }
            }
        });
    }).catch(err => {
        if (statusEl) {
            statusEl.innerHTML = `<p class="text-sm text-red-500">SDK load failed: ${err.message}</p>`;
        }
    });
}

function connectWecomBotAfterAuth(botId, secret) {
    fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'connect',
            channel: 'wecom_bot',
            config: { wecom_bot_id: botId, wecom_bot_secret: secret }
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            const ch = channelsData.find(c => c.name === 'wecom_bot');
            if (ch) {
                ch.active = true;
                (ch.fields || []).forEach(f => {
                    if (f.key === 'wecom_bot_id') f.value = botId;
                    if (f.key === 'wecom_bot_secret') f.value = ChannelsHandler_maskSecret(secret);
                });
            }
            setTimeout(() => renderActiveChannels(), 1500);
        }
    })
    .catch(() => {});
}

function startWecomBotAuthInCard() {
    const statusEl = document.getElementById('wecom-card-scan-status');
    ensureWecomSdkLoaded().then(() => {
        WecomAIBotSDK.openBotInfoAuthWindow({
            source: WECOM_BOT_SOURCE,
            onCreated: function(bot) {
                if (statusEl) {
                    statusEl.innerHTML = `
                        <div class="flex flex-col items-center py-2">
                            <div class="w-10 h-10 rounded-full bg-emerald-50 dark:bg-emerald-900/30 flex items-center justify-center mb-2">
                                <i class="fas fa-check text-emerald-500 text-lg"></i>
                            </div>
                            <p class="text-sm font-medium text-emerald-600 dark:text-emerald-400">${t('wecom_scan_success')}</p>
                        </div>`;
                }
                connectWecomBotAfterAuth(bot.botid, bot.secret);
            },
            onError: function(err) {
                if (statusEl) {
                    statusEl.innerHTML = `<p class="text-sm text-red-500">${t('wecom_scan_fail')}: ${err.message || err.code || ''}</p>`;
                }
            }
        });
    }).catch(err => {
        if (statusEl) {
            statusEl.innerHTML = `<p class="text-sm text-red-500">SDK load failed: ${err.message}</p>`;
        }
    });
}

// Initialize wecom bot panel with correct default mode when inserted into DOM
document.addEventListener('DOMContentLoaded', function() {
    const observer = new MutationObserver(function() {
        const wecomPanel = document.getElementById('wecom-bot-panel');
        if (wecomPanel && !wecomPanel.dataset.initialized) {
            wecomPanel.dataset.initialized = '1';
            switchWecomBotMode(wecomPanel.dataset.defaultMode || 'scan');
        }
        const feishuPanel = document.getElementById('feishu-panel');
        if (feishuPanel && !feishuPanel.dataset.initialized) {
            feishuPanel.dataset.initialized = '1';
            switchFeishuMode(feishuPanel.dataset.defaultMode || 'scan');
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
});

// =====================================================================
// Feishu One-click App Registration (lark-oapi register_app)
// =====================================================================
let _feishuRegisterPollTimer = null;

function _feishuHasCreds(ch) {
    if (!ch || !ch.fields) return false;
    const idField = ch.fields.find(f => f.key === 'feishu_app_id');
    const secretField = ch.fields.find(f => f.key === 'feishu_app_secret');
    return !!(idField && idField.value && secretField && secretField.value);
}

function buildFeishuPanel(ch, isActive) {
    const scanLabel = t('feishu_mode_scan');
    const manualLabel = t('feishu_mode_manual');
    // 已有凭据时默认进入手动 Tab，方便修改；否则推荐扫码
    const defaultMode = _feishuHasCreds(ch) ? 'manual' : 'scan';
    const activeAttr = isActive ? 'data-active="1"' : '';
    return `
        <div id="feishu-panel" data-default-mode="${defaultMode}" ${activeAttr}>
            <div class="flex items-center justify-center gap-1 mb-5 bg-slate-100 dark:bg-white/5 rounded-lg p-1">
                <button id="feishu-tab-scan" onclick="switchFeishuMode('scan')"
                    class="flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors
                           bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 shadow-sm">
                    ${scanLabel}
                </button>
                <button id="feishu-tab-manual" onclick="switchFeishuMode('manual')"
                    class="flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors
                           text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
                    ${manualLabel}
                </button>
            </div>
            <div id="feishu-mode-content"></div>
        </div>`;
}

function switchFeishuMode(mode) {
    const panel = document.getElementById('feishu-panel');
    const scanTab = document.getElementById('feishu-tab-scan');
    const manualTab = document.getElementById('feishu-tab-manual');
    const content = document.getElementById('feishu-mode-content');
    if (!scanTab || !manualTab || !content) return;

    // 已激活通道卡片中嵌入此 panel 时，没有 add-channel-actions（保存按钮就近渲染）
    const isActive = panel && panel.dataset.active === '1';
    const actions = isActive ? null : document.getElementById('add-channel-actions');

    const activeClasses = 'bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 shadow-sm';
    const inactiveClasses = 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200';

    stopFeishuRegisterPoll();

    if (mode === 'scan') {
        scanTab.className = `flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${activeClasses}`;
        manualTab.className = `flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${inactiveClasses}`;
        if (actions) actions.classList.add('hidden');
        // active 卡片下扫码替换的提示文案，强调"创建新机器人会覆盖现有配置"
        const desc = isActive
            ? t('feishu_scan_replace_desc')
            : t('feishu_scan_desc');
        content.innerHTML = `
            <div id="feishu-scan-panel" class="flex flex-col items-center py-4">
                <p class="text-sm text-slate-600 dark:text-slate-300 mb-3 text-center">${desc}</p>
                <button onclick="startFeishuRegister()"
                    class="mt-2 px-6 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium
                           cursor-pointer transition-colors duration-150">
                    <i class="fas fa-qrcode mr-2"></i>${t('feishu_scan_btn')}
                </button>
                <div id="feishu-scan-status" class="mt-4 w-full"></div>
            </div>`;
    } else {
        manualTab.className = `flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${activeClasses}`;
        scanTab.className = `flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${inactiveClasses}`;
        const ch = channelsData.find(c => c.name === 'feishu');
        const fieldsHtml = buildChannelFieldsHtml('feishu', ch ? ch.fields || [] : []);
        if (isActive) {
            // 已接入卡片：内置保存按钮，复用 saveChannelConfig 走 update 流程
            content.innerHTML = `
                <div class="space-y-4">
                    ${fieldsHtml}
                    <div class="flex items-center justify-end gap-3 pt-1">
                        <span id="ch-status-feishu" class="text-xs text-primary-500 opacity-0 transition-opacity duration-300"></span>
                        <button onclick="saveChannelConfig('feishu')"
                            class="px-4 py-2 rounded-lg bg-primary-500 hover:bg-primary-600 text-white text-sm font-medium
                                   cursor-pointer transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
                            id="ch-save-feishu">${t('channels_save')}</button>
                    </div>
                </div>`;
        } else {
            content.innerHTML = `<div class="space-y-4">${fieldsHtml}</div>`;
            if (actions) actions.classList.remove('hidden');
        }
        bindSecretFieldEvents(content);
    }
}

function stopFeishuRegisterPoll() {
    if (_feishuRegisterPollTimer) {
        clearTimeout(_feishuRegisterPollTimer);
        _feishuRegisterPollTimer = null;
    }
}

function startFeishuRegister(targetStatusId) {
    const statusId = targetStatusId || 'feishu-scan-status';
    const statusEl = document.getElementById(statusId);
    if (statusEl) {
        statusEl.innerHTML = `<p class="text-sm text-slate-500 dark:text-slate-400 text-center">${t('feishu_scan_loading')}</p>`;
    }
    stopFeishuRegisterPoll();
    fetch('/api/feishu/register')
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') {
                renderFeishuRegisterError(statusId, data.message || t('feishu_scan_fail'));
                return;
            }
            renderFeishuQr(statusId, data.qr_image, data.qrcode_url);
            pollFeishuRegisterStatus(statusId);
        })
        .catch(err => {
            renderFeishuRegisterError(statusId, err.message || t('feishu_scan_fail'));
        });
}

function renderFeishuQr(statusId, qrImage, qrUrl) {
    const statusEl = document.getElementById(statusId);
    if (!statusEl) return;
    const imgHtml = qrImage
        ? `<img src="${qrImage}" alt="QR" class="w-44 h-44 rounded-lg border border-slate-200 dark:border-white/10 bg-white p-2"/>`
        : `<div class="w-44 h-44 rounded-lg border border-dashed border-slate-300 flex items-center justify-center text-xs text-slate-400">QR</div>`;
    statusEl.innerHTML = `
        <div class="flex flex-col items-center gap-3">
            ${imgHtml}
            <p class="text-xs text-amber-500">${t('feishu_scan_waiting')}</p>
            <p class="text-xs text-slate-400 dark:text-slate-500">${t('feishu_scan_tip')}</p>
            ${qrUrl ? `<a href="${qrUrl}" target="_blank" rel="noopener"
                class="text-xs text-blue-500 hover:text-blue-600 underline">${t('feishu_scan_open_link')}</a>` : ''}
        </div>`;
}

function renderFeishuRegisterError(statusId, message) {
    const statusEl = document.getElementById(statusId);
    if (!statusEl) return;
    statusEl.innerHTML = `
        <div class="flex flex-col items-center gap-2 py-2">
            <p class="text-sm text-red-500 text-center">${message}</p>
            <button onclick="startFeishuRegister('${statusId}')"
                class="mt-1 px-4 py-1.5 rounded-md text-xs font-medium
                       bg-slate-100 dark:bg-white/10 text-slate-700 dark:text-slate-200
                       hover:bg-slate-200 dark:hover:bg-white/20 cursor-pointer">
                <i class="fas fa-rotate-right mr-1"></i>${t('feishu_scan_retry')}
            </button>
        </div>`;
}

function pollFeishuRegisterStatus(statusId) {
    stopFeishuRegisterPoll();
    _feishuRegisterPollTimer = setTimeout(() => {
        fetch('/api/feishu/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'poll' })
        })
        .then(r => r.json())
        .then(data => {
            if (data.status !== 'success') {
                renderFeishuRegisterError(statusId, data.message || t('feishu_scan_fail'));
                return;
            }
            const rs = data.register_status;
            if (rs === 'done') {
                const statusEl = document.getElementById(statusId);
                if (statusEl) {
                    statusEl.innerHTML = `
                        <div class="flex flex-col items-center py-2">
                            <div class="w-10 h-10 rounded-full bg-emerald-50 dark:bg-emerald-900/30 flex items-center justify-center mb-2">
                                <i class="fas fa-check text-emerald-500 text-lg"></i>
                            </div>
                            <p class="text-sm font-medium text-emerald-600 dark:text-emerald-400">${t('feishu_scan_success')}</p>
                        </div>`;
                }
                connectFeishuAfterRegister(data.app_id, data.app_secret);
            } else if (rs === 'expired') {
                renderFeishuRegisterError(statusId, t('feishu_scan_expired'));
            } else if (rs === 'denied') {
                renderFeishuRegisterError(statusId, t('feishu_scan_denied'));
            } else if (rs === 'error') {
                renderFeishuRegisterError(statusId, data.message || t('feishu_scan_fail'));
            } else {
                pollFeishuRegisterStatus(statusId);
            }
        })
        .catch(() => {
            pollFeishuRegisterStatus(statusId);
        });
    }, 2000);
}

function connectFeishuAfterRegister(appId, appSecret) {
    fetch('/api/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            action: 'connect',
            channel: 'feishu',
            config: { feishu_app_id: appId, feishu_app_secret: appSecret }
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            const ch = channelsData.find(c => c.name === 'feishu');
            if (ch) {
                ch.active = true;
                (ch.fields || []).forEach(f => {
                    if (f.key === 'feishu_app_id') f.value = appId;
                    if (f.key === 'feishu_app_secret') f.value = ChannelsHandler_maskSecret(appSecret);
                });
            }
            setTimeout(() => renderActiveChannels(), 1500);
        }
    })
    .catch(() => {});
}

// =====================================================================
// Scheduler View
// =====================================================================
let tasksLoaded = false;
function refreshTasksView() {
    const btn = document.getElementById('task-refresh-btn');
    const icon = btn.querySelector('i');
    
    // Add spin animation
    icon.classList.add('fa-spin');
    btn.disabled = true;
    
    tasksLoaded = false;
    const listEl = document.getElementById('tasks-list');
    listEl.innerHTML = '';
    
    loadTasksView();
    
    // Restore button after animation ends
    setTimeout(() => {
        icon.classList.remove('fa-spin');
        btn.disabled = false;
    }, 500);
}
function loadTasksView() {
    if (tasksLoaded) return;
    fetch('/api/scheduler').then(r => r.json()).then(data => {
        if (data.status !== 'success') return;
        const emptyEl = document.getElementById('tasks-empty');
        const listEl = document.getElementById('tasks-list');
        const allTasks = data.tasks || [];
        // Backend already sorted by enabled and next_run_at, no need to re-sort on frontend
        if (allTasks.length === 0) {
            emptyEl.querySelector('p').textContent = currentLang === 'zh' ? '暂无定时任务' : 'No scheduled tasks';
            emptyEl.classList.remove('hidden');
            listEl.classList.add('hidden');
            tasksLoaded = true;
            return;
        }
        emptyEl.classList.add('hidden');
        listEl.classList.remove('hidden');
        listEl.innerHTML = '';

        allTasks.forEach(task => {
            const isEnabled = task.enabled !== false;
            const card = document.createElement('div');
            card.className = 'bg-white dark:bg-[#1A1A1A] rounded-xl border border-slate-200 dark:border-white/10 p-4';
            card.dataset.taskId = task.id;
            if (!isEnabled) card.classList.add('opacity-50');
            const schedule = task.schedule || {};
            let typeLabel = '';
            if (schedule.type === 'cron') {
                typeLabel = `<span class="text-xs font-mono text-slate-400">${escapeHtml(schedule.expression || '')}</span>`;
            } else if (schedule.type === 'interval') {
                const seconds = schedule.seconds || 0;
                const hours = Math.floor(seconds / 3600);
                const mins = Math.floor((seconds % 3600) / 60);
                const secs = seconds % 60;
                let intervalText = [];
                if (hours > 0) intervalText.push(`${hours}h`);
                if (mins > 0) intervalText.push(`${mins}m`);
                if (secs > 0 || intervalText.length === 0) intervalText.push(`${secs}s`);
                typeLabel = `<span class="text-xs text-slate-400">${intervalText.join(' ')}</span>`;
            } else {
                typeLabel = `<span class="text-xs text-slate-400">${escapeHtml(schedule.type || 'once')}</span>`;
            }
            let nextRun = '--';
            if (task.next_run_at) {
                const d = new Date(task.next_run_at);
                if (!isNaN(d.getTime())) nextRun = d.toLocaleString();
            }
            const action = task.action || {};
            const taskContent = action.content || action.task_description || '';
            const taskTarget = action.receiver_name || '--';
            const deliveryStatus = task.delivery_status || action.delivery_status || '';
            const deliveryStatusText = deliveryStatus === 'waiting_identity_binding'
                ? (currentLang === 'zh' ? '需要重新绑定' : 'Rebind required')
                : '';
            const toggleId = 'toggle-' + task.id;
            card.innerHTML = `
                <div class="flex items-center gap-2 mb-2">
                    <span class="w-2 h-2 rounded-full ${isEnabled ? 'bg-primary-400' : 'bg-slate-300 dark:bg-slate-600'}"></span>
                    <span class="font-medium text-sm text-slate-700 dark:text-slate-200">${escapeHtml(task.name || task.id || '--')}</span>
                    <div class="flex-1"></div>
                    ${typeLabel}
                </div>
                <p class="text-xs text-slate-500 dark:text-slate-400 mb-2 line-clamp-2">${escapeHtml(taskContent)}</p>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400 dark:text-slate-500">
                    <span><i class="fas fa-clock mr-1"></i>${currentLang === 'zh' ? '下次执行' : 'Next run'}: ${nextRun}</span>
                    <span class="min-w-0"><i class="fas fa-users mr-1"></i>${currentLang === 'zh' ? '目标' : 'Target'}: <span class="break-words">${escapeHtml(taskTarget)}</span></span>
                    ${deliveryStatusText ? `<span class="text-amber-600 dark:text-amber-300"><i class="fas fa-link-slash mr-1"></i>${escapeHtml(deliveryStatusText)}</span>` : ''}
                    <div class="flex-1"></div>
                    <label class="relative inline-flex items-center cursor-pointer" for="${toggleId}">
                        <input type="checkbox" id="${toggleId}" class="sr-only peer" ${isEnabled ? 'checked' : ''}>
                        <div class="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary-500 dark:bg-slate-600 dark:peer-checked:bg-primary-500"></div>
                    </label>
                </div>`;
            const checkbox = card.querySelector('#' + toggleId);
            checkbox.addEventListener('change', function() {
                const newEnabled = this.checked;
                fetch('/api/scheduler/toggle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({task_id: task.id, enabled: newEnabled})
                }).then(r => r.json()).then(res => {
                    if (res.status === 'success') {
                        const dot = card.querySelector('.rounded-full.w-2');
                        if (newEnabled) {
                            card.classList.remove('opacity-50');
                            if (dot) { dot.classList.remove('bg-slate-300','dark:bg-slate-600'); dot.classList.add('bg-primary-400'); }
                        } else {
                            card.classList.add('opacity-50');
                            if (dot) { dot.classList.remove('bg-primary-400'); dot.classList.add('bg-slate-300','dark:bg-slate-600'); }
                        }
                    } else {
                        this.checked = !newEnabled;
                    }
                }).catch(() => { this.checked = !newEnabled; });
            });
            // Card click event (excluding toggle switch clicks)
            card.addEventListener('click', function(e) {
                if (!e.target.closest('label') && !e.target.closest('input[type="checkbox"]')) {
                    openTaskEditModal(task);
                }
            });
            card.style.cursor = 'pointer';
            listEl.appendChild(card);
        });
        tasksLoaded = true;
    }).catch(() => {});
}

// =====================================================================
// Logs View
// =====================================================================
let logEventSource = null;

function logLevelClass(line) {
    if (/\[CRITICAL\]/.test(line)) return 'log-line-critical';
    if (/\[ERROR\]/.test(line))    return 'log-line-error';
    if (/\[WARNING\]/.test(line))  return 'log-line-warning';
    if (/\[INFO\]/.test(line))     return 'log-line-info';
    if (/\[DEBUG\]/.test(line))    return 'log-line-debug';
    return '';
}

function getHiddenLevels() {
    const hidden = new Set();
    document.querySelectorAll('.log-filter-cb').forEach(function(cb) {
        if (!cb.checked) hidden.add('log-line-' + cb.dataset.level);
    });
    return hidden;
}

function applyLogFilter() {
    const hidden = getHiddenLevels();
    document.querySelectorAll('#log-output .log-line').forEach(function(span) {
        const level = span.classList[1] || '';
        span.style.display = hidden.has(level) ? 'none' : '';
    });
}

function appendLogLines(output, text) {
    const hidden = getHiddenLevels();
    let lastLevelClass = '';
    const lines = text.split('\n');
    lines.forEach(function(line, i) {
        if (i === lines.length - 1 && line === '') return;
        const span = document.createElement('span');
        const levelClass = logLevelClass(line) || lastLevelClass;
        if (logLevelClass(line)) lastLevelClass = levelClass;
        span.className = 'log-line ' + levelClass;
        span.textContent = line + '\n';
        if (hidden.has(levelClass)) span.style.display = 'none';
        output.appendChild(span);
    });
}

document.addEventListener('change', function(e) {
    if (e.target.classList.contains('log-filter-cb')) applyLogFilter();
});

function startLogStream() {
    if (logEventSource) return;
    const output = document.getElementById('log-output');
    output.innerHTML = '';

    logEventSource = new EventSource('/api/logs');
    logEventSource.onmessage = function(e) {
        let item;
        try { item = JSON.parse(e.data); } catch (_) { return; }

        if (item.type === 'init') {
            output.innerHTML = '';
            appendLogLines(output, item.content || '');
            output.scrollTop = output.scrollHeight;
        } else if (item.type === 'line') {
            appendLogLines(output, item.content);
            output.scrollTop = output.scrollHeight;
        } else if (item.type === 'error') {
            output.textContent = item.message || 'Error loading logs';
        }
    };
    logEventSource.onerror = function() {
        logEventSource.close();
        logEventSource = null;
    };
}

function stopLogStream() {
    if (logEventSource) {
        logEventSource.close();
        logEventSource = null;
    }
}

// =====================================================================
// View Navigation Hook
// =====================================================================
const _origNavigateTo = navigateTo;
navigateTo = function(viewId) {
    // Stop log stream when leaving logs view
    if (currentView === 'logs' && viewId !== 'logs') stopLogStream();

    _origNavigateTo(viewId);

    // Lazy-load view data
    if (viewId === 'config') loadConfigView();
    else if (viewId === 'models') loadModelsView();
    else if (viewId === 'skills') loadSkillsView();
    else if (viewId === 'memory') {
        document.getElementById('memory-panel-viewer').classList.add('hidden');
        document.getElementById('memory-panel-list').classList.remove('hidden');
        switchMemoryTab('files');
    }
    else if (viewId === 'knowledge') loadKnowledgeView();
    else if (viewId === 'channels') loadChannelsView();
    else if (viewId === 'groups') loadGroupsView();
    else if (viewId === 'tasks') loadTasksView();
    else if (viewId === 'logs') startLogStream();
};

// =====================================================================
// Knowledge View
// =====================================================================
let _knowledgeTreeData = [];
let _knowledgeRootFiles = [];
let _knowledgeCurrentFile = null;
let _knowledgeGraphLoaded = false;
const KNOWLEDGE_IMPORT_MAX_FILES = 100;
const KNOWLEDGE_IMPORT_MAX_FILE_SIZE = 10 * 1024 * 1024;
const KNOWLEDGE_IMPORT_MAX_TOTAL_SIZE = 200 * 1024 * 1024;

function loadKnowledgeView(targetPath) {
    // Reset to docs tab
    switchKnowledgeTab('docs');
    _knowledgeGraphLoaded = false;
    _knowledgeCurrentFile = null;

    fetch('/api/knowledge/list').then(r => r.json()).then(data => {
        if (data.status !== 'success') return;
        initKnowledgeImportDropZone();

        const emptyEl = document.getElementById('knowledge-empty');
        const docsPanel = document.getElementById('knowledge-panel-docs');
        const statsEl = document.getElementById('knowledge-stats');

        const tree = data.tree || [];
        const rootFiles = data.root_files || [];
        _knowledgeTreeData = tree;
        _knowledgeRootFiles = rootFiles;
        const stats = data.stats || {};
        const totalPages = stats.pages || 0;
        const sizeStr = stats.size < 1024 ? stats.size + ' B' : (stats.size / 1024).toFixed(1) + ' KB';

        statsEl.textContent = totalPages + ' pages · ' + sizeStr;

        if (totalPages === 0 && tree.length === 0 && rootFiles.length === 0) {
            emptyEl.querySelector('p').textContent = t('knowledge_empty_hint');
            const guideEl = document.getElementById('knowledge-empty-guide');
            if (guideEl) guideEl.classList.remove('hidden');
            emptyEl.classList.remove('hidden');
            docsPanel.classList.add('hidden');
            return;
        }
        emptyEl.classList.add('hidden');
        docsPanel.classList.remove('hidden');

        renderKnowledgeTree(tree, rootFiles);

        // Prefer opening the just created/imported file; ensure its group is
        // expanded so the active item is visible in the tree.
        const targetTitle = targetPath ? _findKnowledgeFileTitle(targetPath) : null;
        if (targetTitle !== null) {
            _expandKnowledgeGroupFor(targetPath);
            openKnowledgeFile(targetPath, targetTitle);
            return;
        }

        // Auto-select the first file (desktop only)
        if (window.innerWidth >= 768) {
            const firstFile = rootFiles.length > 0 ? rootFiles[0] : null;
            const firstGroup = !firstFile ? tree.find(g => g.files && g.files.length > 0) : null;
            if (firstFile) {
                openKnowledgeFile(firstFile.name, firstFile.title);
            } else if (firstGroup) {
                const gf = firstGroup.files[0];
                openKnowledgeFile(firstGroup.dir + '/' + gf.name, gf.title);
            }
        } else {
            document.getElementById('knowledge-content-placeholder').classList.add('hidden');
            document.getElementById('knowledge-content-viewer').classList.add('hidden');
        }
    }).catch(() => {});
}

// Find a file's display title by its relative path within the knowledge tree.
// Returns the title, or null when the path is not present.
function _findKnowledgeFileTitle(path) {
    if (!path) return null;
    const rootHit = (_knowledgeRootFiles || []).find(f => f.name === path);
    if (rootHit) return rootHit.title || rootHit.name;
    const walk = (groups, parentPath) => {
        for (const group of groups || []) {
            const groupPath = parentPath ? `${parentPath}/${group.dir}` : group.dir;
            const hit = (group.files || []).find(f => `${groupPath}/${f.name}` === path);
            if (hit) return hit.title || hit.name;
            const childHit = walk(group.children, groupPath);
            if (childHit !== null) return childHit;
        }
        return null;
    };
    return walk(_knowledgeTreeData, '');
}

// Open every ancestor group of the given file path so it is visible.
function _expandKnowledgeGroupFor(path) {
    if (!path || !path.includes('/')) return;
    const target = document.querySelector(`.knowledge-tree-file[data-path="${CSS.escape(path)}"]`);
    let node = target ? target.closest('.knowledge-tree-group') : null;
    while (node) {
        node.classList.add('open');
        node = node.parentElement ? node.parentElement.closest('.knowledge-tree-group') : null;
    }
}

function renderKnowledgeTree(tree, rootFilesOrFilter, filter) {
    const container = document.getElementById('knowledge-tree');
    container.innerHTML = '';
    let rootFiles, lowerFilter;
    if (typeof rootFilesOrFilter === 'string') {
        rootFiles = _knowledgeRootFiles;
        lowerFilter = (rootFilesOrFilter || '').toLowerCase();
    } else {
        rootFiles = rootFilesOrFilter || _knowledgeRootFiles;
        lowerFilter = (filter || '').toLowerCase();
    }
    (rootFiles || []).forEach(f => {
        if (lowerFilter && !f.title.toLowerCase().includes(lowerFilter) && !f.name.toLowerCase().includes(lowerFilter)) return;
        const fbtn = document.createElement('button');
        fbtn.className = 'knowledge-tree-file' + (_knowledgeCurrentFile === f.name ? ' active' : '');
        fbtn.dataset.path = f.name;
        fbtn.innerHTML = `<i class="fas fa-file-lines text-[10px] text-slate-400"></i><span class="truncate">${escapeHtml(f.title)}</span>${_knowledgeFileActions(f.name)}`;
        fbtn.onclick = () => openKnowledgeFile(f.name, f.title);
        container.appendChild(fbtn);
    });
    _renderKnowledgeGroups(container, tree, '', lowerFilter, 0);
}

function _renderKnowledgeGroups(container, groups, parentPath, lowerFilter, depth) {
    const indent = depth * 12;
    groups.forEach(group => {
        const groupPath = parentPath ? parentPath + '/' + group.dir : group.dir;
        const files = (group.files || []).filter(f =>
            !lowerFilter || f.title.toLowerCase().includes(lowerFilter) || f.name.toLowerCase().includes(lowerFilter)
        );
        const children = group.children || [];
        const hasMatchingChildren = lowerFilter ? _hasFilterMatch(children, lowerFilter) : children.length > 0;
        if (files.length === 0 && !hasMatchingChildren && lowerFilter) return;

        const div = document.createElement('div');
        div.className = 'knowledge-tree-group open';

        const fileCount = _countFiles(group);
        const btn = document.createElement('button');
        btn.className = 'knowledge-tree-group-btn';
        btn.style.paddingLeft = (8 + indent) + 'px';
        btn.innerHTML = `<i class="fas fa-chevron-right chevron"></i><i class="fas fa-folder text-amber-400 text-[11px]"></i><span>${escapeHtml(group.dir)}</span><span class="ml-auto text-[10px] text-slate-400">${fileCount}</span>${_knowledgeCategoryActions(groupPath)}`;
        btn.onclick = () => div.classList.toggle('open');
        div.appendChild(btn);

        const items = document.createElement('div');
        items.className = 'knowledge-tree-group-items';
        files.forEach(f => {
            const fbtn = document.createElement('button');
            const fpath = groupPath + '/' + f.name;
            fbtn.className = 'knowledge-tree-file' + (_knowledgeCurrentFile === fpath ? ' active' : '');
            fbtn.dataset.path = fpath;
            fbtn.style.paddingLeft = (24 + indent) + 'px';
            fbtn.innerHTML = `<i class="fas fa-file-lines text-[10px] text-slate-400"></i><span class="truncate">${escapeHtml(f.title)}</span>${_knowledgeFileActions(fpath)}`;
            fbtn.onclick = () => openKnowledgeFile(fpath, f.title);
            items.appendChild(fbtn);
        });
        if (children.length > 0) {
            _renderKnowledgeGroups(items, children, groupPath, lowerFilter, depth + 1);
        }
        div.appendChild(items);
        container.appendChild(div);
    });
}

function _knowledgeActionButton(icon, title, handler) {
    const danger = icon === 'fa-trash' ? ' danger' : '';
    return `<span role="button" tabindex="0" title="${escapeHtml(title)}" onclick="event.stopPropagation();${handler}" class="knowledge-action${danger}"><i class="fas ${icon}"></i></span>`;
}

function _knowledgeFileActions(path) {
    if (path === 'index.md' || path === 'log.md') return '';
    const value = JSON.stringify(path).replace(/"/g, '&quot;');
    return `<span class="knowledge-actions">${_knowledgeActionButton('fa-arrow-right-arrow-left', '移动', `moveKnowledgeDocument(${value})`)}${_knowledgeActionButton('fa-trash', '删除', `deleteKnowledgeDocument(${value})`)}</span>`;
}

function _knowledgeCategoryActions(path) {
    const value = JSON.stringify(path).replace(/"/g, '&quot;');
    return `<span class="knowledge-actions">${_knowledgeActionButton('fa-pen', '重命名', `renameKnowledgeCategory(${value})`)}${_knowledgeActionButton('fa-trash', '删除', `deleteKnowledgeCategory(${value})`)}</span>`;
}

async function dispatchKnowledgeAction(action, payload, openPathResolver) {
    _setKnowledgeStatus(currentLang === 'zh' ? '处理中...' : 'Working...', false, true);
    try {
        const response = await fetch('/api/knowledge/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action, payload}),
        });
        const result = await response.json();
        if (result.status !== 'success') {
            _setKnowledgeStatus(result.message || (currentLang === 'zh' ? '操作失败' : 'Operation failed'), true);
            loadKnowledgeView();
            return null;
        }
        _setKnowledgeStatus(_knowledgeResultMessage(action, result.payload), false);
        // Optionally auto-open the affected file after the tree refreshes.
        const openPath = openPathResolver ? openPathResolver(result.payload) : null;
        loadKnowledgeView(openPath || undefined);
        return result.payload;
    } catch (error) {
        _setKnowledgeStatus(currentLang === 'zh' ? '请求失败，请稍后重试' : 'Request failed, please try again', true);
        return null;
    }
}

function _setKnowledgeStatus(message, isError, persistent) {
    const el = document.getElementById('knowledge-action-status');
    el.textContent = message;
    el.className = `text-xs transition-opacity duration-200 ${isError ? 'text-red-500' : 'text-primary-500'}`;
    el.classList.remove('opacity-0');
    clearTimeout(el._hideTimer);
    if (!persistent) el._hideTimer = setTimeout(() => el.classList.add('opacity-0'), 3500);
}

function _knowledgeResultMessage(action, payload) {
    if (currentLang !== 'zh') {
        return action === 'create_category' ? 'Category created' :
            action === 'create_document' ? 'Document created' :
            action === 'rename_category' ? 'Category renamed' :
            action === 'delete_category' ? 'Category deleted' :
            action === 'import_documents' ? `${payload?.imported || 0} imported · ${payload?.skipped || 0} skipped · ${payload?.failed || 0} failed` :
            action === 'move_documents' ? `${payload?.moved || 0} document moved` :
            `${payload?.deleted || 0} document deleted`;
    }
    return action === 'create_category' ? '分类已创建' :
        action === 'create_document' ? '文档已创建' :
        action === 'rename_category' ? '分类已重命名' :
        action === 'delete_category' ? '分类已删除' :
        action === 'import_documents' ? `导入 ${payload?.imported || 0} 个，跳过 ${payload?.skipped || 0} 个，失败 ${payload?.failed || 0} 个` :
        action === 'move_documents' ? `已移动 ${payload?.moved || 0} 个文档` :
        `已删除 ${payload?.deleted || 0} 个文档`;
}

function _knowledgeCategoryPaths(groups, parent = '') {
    const paths = [];
    for (const group of groups || []) {
        const path = parent ? `${parent}/${group.dir}` : group.dir;
        paths.push(path, ..._knowledgeCategoryPaths(group.children || [], path));
    }
    return paths;
}

function openKnowledgeDialog(options) {
    const overlay = document.getElementById('knowledge-dialog-overlay');
    const card = document.getElementById('knowledge-dialog-card');
    const input = document.getElementById('knowledge-dialog-input');
    const select = document.getElementById('knowledge-dialog-select');
    const textarea = document.getElementById('knowledge-dialog-textarea');
    const documentForm = document.getElementById('knowledge-document-form');
    const documentFilename = document.getElementById('knowledge-document-filename');
    const documentContent = document.getElementById('knowledge-document-content');
    const templateBtn = document.getElementById('knowledge-document-template');
    const documentPathPreview = document.getElementById('knowledge-document-path-preview');
    const submit = document.getElementById('knowledge-dialog-submit');
    const cancel = document.getElementById('knowledge-dialog-cancel');
    document.getElementById('knowledge-dialog-title').textContent = options.title;
    document.getElementById('knowledge-dialog-subtitle').textContent = options.subtitle || '';
    document.getElementById('knowledge-dialog-label').textContent = options.label;
    document.getElementById('knowledge-dialog-hint').textContent = options.hint || '';
    document.getElementById('knowledge-dialog-error').classList.add('hidden');
    document.getElementById('knowledge-dialog-icon').className = `fas ${options.icon || 'fa-folder'} text-emerald-500`;
    card.classList.toggle('knowledge-document-dialog', options.type === 'document');
    input.classList.toggle('hidden', options.type === 'select' || options.type === 'textarea' || options.type === 'document');
    select.classList.toggle('hidden', options.type !== 'select');
    textarea.classList.toggle('hidden', options.type !== 'textarea');
    documentForm.classList.toggle('hidden', options.type !== 'document');
    input.value = options.value || '';
    textarea.value = options.value || '';
    documentFilename.value = options.filename || '';
    documentContent.value = options.content || '';
    document.getElementById('knowledge-document-category-label').textContent = currentLang === 'zh' ? '目标分类' : 'Destination category';
    documentPathPreview.textContent = options.category
        ? `knowledge/${options.category}/`
        : 'knowledge/';
    documentFilename.oninput = null;
    document.getElementById('knowledge-document-filename-label').textContent = currentLang === 'zh' ? '文件名' : 'Filename';
    document.getElementById('knowledge-document-content-label').textContent = currentLang === 'zh' ? 'Markdown 内容' : 'Markdown content';
    templateBtn.textContent = currentLang === 'zh' ? '插入模板' : 'Insert template';
    templateBtn.onclick = () => {
        if (documentContent.value.trim()) return;
        const title = (documentFilename.value || 'untitled').replace(/\.md$/i, '');
        documentContent.value = currentLang === 'zh'
            ? `# ${title}\n\n## 摘要\n\n\n## 关键点\n\n- \n\n## 参考\n\n`
            : `# ${title}\n\n## Summary\n\n\n## Key points\n\n- \n\n## References\n\n`;
        documentContent.focus();
    };
    if (options.type === 'select') {
        // Use the shared custom dropdown component instead of a native
        // <select> so the arrow / menu match the rest of the console.
        const ddOptions = (options.choices || []).map(value => ({ value, label: value }));
        initDropdown(select, ddOptions, (options.choices || [])[0] || '', null);
    }
    submit.textContent = currentLang === 'zh' ? '确定' : 'Confirm';
    cancel.textContent = currentLang === 'zh' ? '取消' : 'Cancel';
    submit.disabled = options.type === 'select' && !(options.choices || []).length;

    const close = () => overlay.classList.add('hidden');
    const submitAction = async () => {
        const rawValue = options.type === 'select' ? getDropdownValue(select) :
            (options.type === 'textarea' ? textarea.value :
            (options.type === 'document' ? {
                filename: documentFilename.value.trim(),
                content: documentContent.value,
            } : input.value));
        const value = options.type === 'textarea' || options.type === 'document' ? rawValue : rawValue.trim();
        const error = options.validate ? options.validate(value) : (!value ? (currentLang === 'zh' ? '此项不能为空' : 'This field is required') : '');
        if (error) {
            const errorEl = document.getElementById('knowledge-dialog-error');
            errorEl.textContent = error;
            errorEl.classList.remove('hidden');
            return;
        }
        submit.disabled = true;
        const ok = await options.onSubmit(value);
        submit.disabled = false;
        if (ok !== null) close();
    };
    submit.onclick = submitAction;
    cancel.onclick = close;
    overlay.onclick = event => { if (event.target === overlay) close(); };
    input.onkeydown = event => { if (event.key === 'Enter') submitAction(); };
    overlay.classList.remove('hidden');
    setTimeout(() => (options.type === 'select' ? select : (options.type === 'textarea' ? textarea : (options.type === 'document' ? documentFilename : input))).focus(), 0);
}

function closeKnowledgeNewMenu() {
    const list = document.getElementById('knowledge-new-menu-list');
    if (list) list.classList.add('hidden');
    document.removeEventListener('click', _knowledgeNewMenuOutside, true);
}

function _knowledgeNewMenuOutside(event) {
    const menu = document.getElementById('knowledge-new-menu');
    if (menu && !menu.contains(event.target)) closeKnowledgeNewMenu();
}

function toggleKnowledgeNewMenu(event) {
    if (event) event.stopPropagation();
    const list = document.getElementById('knowledge-new-menu-list');
    if (!list) return;
    const willOpen = list.classList.contains('hidden');
    list.classList.toggle('hidden');
    if (willOpen) {
        document.addEventListener('click', _knowledgeNewMenuOutside, true);
    } else {
        document.removeEventListener('click', _knowledgeNewMenuOutside, true);
    }
}

function createKnowledgeCategory() {
    openKnowledgeDialog({
        title: currentLang === 'zh' ? '新建分类' : 'New category',
        subtitle: currentLang === 'zh' ? '分类会创建为 knowledge/ 下的目录' : 'Creates a directory under knowledge/',
        label: currentLang === 'zh' ? '分类路径' : 'Category path',
        hint: currentLang === 'zh' ? '支持嵌套路径，例如 research/ai' : 'Nested paths are supported, e.g. research/ai',
        icon: 'fa-folder-plus',
        onSubmit: path => dispatchKnowledgeAction('create_category', {path}),
    });
}

function createKnowledgeDocument() {
    const categories = _knowledgeCategoryPaths(_knowledgeTreeData);
    if (!categories.length) {
        _setKnowledgeStatus(currentLang === 'zh' ? '请先创建分类' : 'Create a category first', true);
        return;
    }
    openKnowledgeDialog({
        title: currentLang === 'zh' ? '新建文档' : 'New document',
        subtitle: currentLang === 'zh' ? '先选择分类，然后输入文件名' : 'Choose a category, then enter a filename',
        label: currentLang === 'zh' ? '目标分类' : 'Destination category',
        type: 'select',
        choices: categories,
        icon: 'fa-file-circle-plus',
        onSubmit: category => {
            openKnowledgeDocumentEditor(category);
            return null;
        },
    });
}

function openKnowledgeDocumentEditor(category) {
    openKnowledgeDialog({
        title: currentLang === 'zh' ? '新建文档' : 'New document',
        subtitle: currentLang === 'zh' ? `保存到 ${category}` : `Save to ${category}`,
        label: '',
        hint: currentLang === 'zh' ? '文件名可省略 .md 后缀；保存后会自动同步索引。' : 'The .md suffix is optional. Index sync runs after saving.',
        type: 'document',
        category,
        filename: '',
        content: '',
        icon: 'fa-file-circle-plus',
        validate: value => {
            if (!value.filename) return currentLang === 'zh' ? '文件名不能为空' : 'Filename is required';
            if (/\.[^.]+$/i.test(value.filename) && !/\.md$/i.test(value.filename)) {
                return currentLang === 'zh' ? '新建文档仅支持 .md 文件名' : 'New documents must be .md files';
            }
            if (!value.content.trim()) return currentLang === 'zh' ? '内容不能为空' : 'Content is required';
            if (new Blob([value.content]).size > KNOWLEDGE_IMPORT_MAX_FILE_SIZE) {
                return currentLang === 'zh' ? '内容不能超过 10MB' : 'Content cannot exceed 10MB';
            }
            return '';
        },
        onSubmit: value => {
            const safeName = value.filename.endsWith('.md') ? value.filename : `${value.filename}.md`;
            return dispatchKnowledgeAction('create_document', {
                path: `${category}/${safeName}`,
                content: value.content,
                overwrite: false,
            }, payload => payload?.path || `${category}/${safeName}`);
        },
    });
}

function selectKnowledgeImportFiles() {
    const input = document.getElementById('knowledge-import-input');
    input.value = '';
    input.onchange = () => {
        if (input.files && input.files.length) openKnowledgeImportDialog(Array.from(input.files));
    };
    input.click();
}

function openKnowledgeImportDialog(files) {
    const validationError = validateKnowledgeImportFiles(files);
    if (validationError) {
        _setKnowledgeStatus(validationError, true);
        return;
    }
    const choices = _knowledgeCategoryPaths(_knowledgeTreeData);
    openKnowledgeDialog({
        title: currentLang === 'zh' ? '导入文档' : 'Import documents',
        subtitle: currentLang === 'zh' ? `已选择 ${files.length} 个文件` : `${files.length} file(s) selected`,
        label: currentLang === 'zh' ? '目标分类' : 'Destination category',
        hint: choices.length ? (currentLang === 'zh' ? '支持 Markdown 和 TXT，TXT 会转成 Markdown 文档' : 'Markdown and TXT are supported. TXT is converted to Markdown.') :
            (currentLang === 'zh' ? '请先创建一个分类' : 'Create a category first'),
        type: 'select',
        choices,
        icon: 'fa-file-arrow-up',
        onSubmit: target => importKnowledgeDocuments(files, target),
    });
}

async function importKnowledgeDocuments(files, targetCategory) {
    const validationError = validateKnowledgeImportFiles(files);
    if (validationError) {
        _setKnowledgeStatus(validationError, true);
        return null;
    }
    const supported = files.filter(file => /\.(md|txt)$/i.test(file.name || ''));
    if (!supported.length) {
        _setKnowledgeStatus(currentLang === 'zh' ? '请选择 .md 或 .txt 文件' : 'Choose .md or .txt files', true);
        return null;
    }
    const formData = new FormData();
    formData.append('target_category', targetCategory);
    formData.append('conflict_strategy', 'rename');
    supported.forEach(file => formData.append('files', file, file.name));
    _setKnowledgeStatus(currentLang === 'zh' ? '正在导入...' : 'Importing...', false, true);
    try {
        const response = await fetch('/api/knowledge/import', { method: 'POST', body: formData });
        const result = await response.json();
        if (result.status !== 'success') {
            _setKnowledgeStatus(result.message || (currentLang === 'zh' ? '导入失败' : 'Import failed'), true);
            loadKnowledgeView();
            return null;
        }
        _setKnowledgeStatus(_knowledgeResultMessage('import_documents', result.payload), false);
        // Auto-open the first successfully imported document.
        const firstImported = (result.payload?.results || []).find(item => item.status === 'imported');
        loadKnowledgeView(firstImported ? firstImported.path : undefined);
        return result.payload;
    } catch (error) {
        _setKnowledgeStatus(currentLang === 'zh' ? '导入请求失败' : 'Import request failed', true);
        return null;
    }
}

function validateKnowledgeImportFiles(files) {
    if (!files || !files.length) return currentLang === 'zh' ? '请选择文件' : 'Choose files';
    if (files.length > KNOWLEDGE_IMPORT_MAX_FILES) {
        return currentLang === 'zh' ? `一次最多导入 ${KNOWLEDGE_IMPORT_MAX_FILES} 个文件` : `Import at most ${KNOWLEDGE_IMPORT_MAX_FILES} files at a time`;
    }
    let total = 0;
    for (const file of files) {
        total += file.size || 0;
        if ((file.size || 0) > KNOWLEDGE_IMPORT_MAX_FILE_SIZE) {
            return currentLang === 'zh' ? `${file.name} 超过 10MB` : `${file.name} exceeds 10MB`;
        }
    }
    if (total > KNOWLEDGE_IMPORT_MAX_TOTAL_SIZE) {
        return currentLang === 'zh' ? '单次导入总大小不能超过 200MB' : 'Total import size cannot exceed 200MB';
    }
    return '';
}

let _knowledgeImportDropReady = false;
function initKnowledgeImportDropZone() {
    if (_knowledgeImportDropReady) return;
    const panel = document.getElementById('knowledge-panel-docs');
    if (!panel) return;
    _knowledgeImportDropReady = true;
    ['dragenter', 'dragover'].forEach(name => {
        panel.addEventListener(name, event => {
            if (!event.dataTransfer || !event.dataTransfer.types.includes('Files')) return;
            event.preventDefault();
            panel.classList.add('knowledge-import-drag-over');
        });
    });
    ['dragleave', 'drop'].forEach(name => {
        panel.addEventListener(name, event => {
            if (event.type === 'drop') {
                event.preventDefault();
                const files = Array.from(event.dataTransfer?.files || []);
                if (files.length) openKnowledgeImportDialog(files);
            }
            panel.classList.remove('knowledge-import-drag-over');
        });
    });
}

function renameKnowledgeCategory(path) {
    openKnowledgeDialog({
        title: currentLang === 'zh' ? '重命名分类' : 'Rename category',
        subtitle: path,
        label: currentLang === 'zh' ? '新的分类路径' : 'New category path',
        value: path,
        icon: 'fa-pen',
        validate: value => value === path ? (currentLang === 'zh' ? '请输入不同的分类路径' : 'Enter a different category path') : '',
        onSubmit: newPath => dispatchKnowledgeAction('rename_category', {path, new_path: newPath}),
    });
}

function deleteKnowledgeCategory(path) {
    showConfirmDialog({
        title: '删除分类',
        message: `确认删除“${path}”及其中全部文档？`,
        okText: t('confirm_yes'),
        cancelText: t('confirm_cancel'),
        onConfirm: () => dispatchKnowledgeAction('delete_category', {path, confirm: true}),
    });
}

function deleteKnowledgeDocument(path) {
    showConfirmDialog({
        title: '删除文档',
        message: `确认删除“${path}”？`,
        okText: t('confirm_yes'),
        cancelText: t('confirm_cancel'),
        onConfirm: () => dispatchKnowledgeAction('delete_documents', {paths: [path]}),
    });
}

function moveKnowledgeDocument(path) {
    const currentCategory = path.includes('/') ? path.split('/').slice(0, -1).join('/') : '';
    const choices = _knowledgeCategoryPaths(_knowledgeTreeData).filter(value => value !== currentCategory);
    openKnowledgeDialog({
        title: currentLang === 'zh' ? '移动文档' : 'Move document',
        subtitle: path,
        label: currentLang === 'zh' ? '目标分类' : 'Destination category',
        hint: choices.length ? '' : (currentLang === 'zh' ? '请先创建其他分类' : 'Create another category first'),
        type: 'select',
        choices,
        icon: 'fa-arrow-right-arrow-left',
        onSubmit: target => dispatchKnowledgeAction('move_documents', {paths: [path], target_category: target}),
    });
}

function _hasFilterMatch(groups, lowerFilter) {
    for (const g of groups) {
        for (const f of (g.files || [])) {
            if (f.title.toLowerCase().includes(lowerFilter) || f.name.toLowerCase().includes(lowerFilter)) return true;
        }
        if (_hasFilterMatch(g.children || [], lowerFilter)) return true;
    }
    return false;
}

function _countFiles(group) {
    let count = (group.files || []).length;
    for (const child of (group.children || [])) {
        count += _countFiles(child);
    }
    return count;
}

function filterKnowledgeTree(query) {
    renderKnowledgeTree(_knowledgeTreeData, _knowledgeRootFiles, query);
}

function resolveKnowledgePath(currentFilePath, relativeHref) {
    // currentFilePath: e.g. "concepts/mcp-protocol.md"
    // relativeHref: e.g. "../entities/openai.md"
    const parts = currentFilePath.split('/');
    parts.pop(); // remove filename, keep directory
    const segments = [...parts, ...relativeHref.split('/')];
    const resolved = [];
    for (const seg of segments) {
        if (seg === '..') resolved.pop();
        else if (seg !== '.' && seg !== '') resolved.push(seg);
    }
    return resolved.join('/');
}

function bindKnowledgeLinks(container, currentFilePath) {
    container.querySelectorAll('a').forEach(a => {
        const href = a.getAttribute('href');
        if (!href || !href.endsWith('.md')) return;
        // Skip absolute URLs
        if (/^https?:\/\//.test(href)) return;

        a.addEventListener('click', (e) => {
            e.preventDefault();
            const resolved = resolveKnowledgePath(currentFilePath, href);
            const linkTitle = a.textContent.trim() || resolved.replace(/\.md$/, '').split('/').pop();
            openKnowledgeFile(resolved, linkTitle);
        });
        a.style.cursor = 'pointer';
        a.classList.add('text-primary-500', 'hover:underline');
    });
}

function bindChatKnowledgeLinks(container) {
    if (!container) return;
    container.querySelectorAll('a').forEach(a => {
        const href = a.getAttribute('href');
        if (!href || !href.endsWith('.md')) return;
        if (/^https?:\/\//.test(href)) return;

        // Determine knowledge path
        let knowledgePath = null;
        if (href.startsWith('knowledge/')) {
            // Full path from workspace root: knowledge/concepts/moe.md
            knowledgePath = href.replace(/^knowledge\//, '');
        } else if (/^[a-z0-9_-]+\/[a-z0-9_.-]+\.md$/i.test(href)) {
            // Looks like category/file.md pattern without knowledge/ prefix
            knowledgePath = href;
        } else if (href.includes('/') && !href.startsWith('/')) {
            // Relative path like ../entities/deepseek.md — extract filename and search
            const filename = href.split('/').pop();
            knowledgePath = '__search__:' + filename;
        }
        if (!knowledgePath) return;

        a.addEventListener('click', (e) => {
            e.preventDefault();
            if (knowledgePath.startsWith('__search__:')) {
                const filename = knowledgePath.replace('__search__:', '');
                // Find the file in cached tree data
                const found = _findKnowledgeFileByName(filename);
                if (found) {
                    navigateTo('knowledge');
                    setTimeout(() => openKnowledgeFile(found.path, found.title), 100);
                }
            } else {
                navigateTo('knowledge');
                const linkTitle = a.textContent.trim() || knowledgePath.replace(/\.md$/, '').split('/').pop();
                setTimeout(() => openKnowledgeFile(knowledgePath, linkTitle), 100);
            }
        });
        a.style.cursor = 'pointer';
        a.classList.add('text-primary-500', 'hover:underline');
    });
}

function _findKnowledgeFileByName(filename) {
    for (const f of _knowledgeRootFiles) {
        if (f.name === filename) return { path: f.name, title: f.title };
    }
    return _searchFileInGroups(_knowledgeTreeData, '', filename);
}

function _searchFileInGroups(groups, parentPath, filename) {
    for (const group of groups) {
        const groupPath = parentPath ? parentPath + '/' + group.dir : group.dir;
        for (const f of (group.files || [])) {
            if (f.name === filename) {
                return { path: groupPath + '/' + f.name, title: f.title };
            }
        }
        const found = _searchFileInGroups(group.children || [], groupPath, filename);
        if (found) return found;
    }
    return null;
}

function openKnowledgeFile(path, title) {
    _knowledgeCurrentFile = path;
    // Update active state in tree via data-path
    document.querySelectorAll('.knowledge-tree-file').forEach(el => {
        el.classList.toggle('active', el.dataset.path === path);
    });

    // Immediately hide placeholder
    document.getElementById('knowledge-content-placeholder').classList.add('hidden');

    fetch(`/api/knowledge/read?path=${encodeURIComponent(path)}`).then(r => r.json()).then(data => {
        if (data.status !== 'success') return;
        const viewer = document.getElementById('knowledge-content-viewer');
        document.getElementById('knowledge-viewer-title').textContent = title;
        document.getElementById('knowledge-viewer-path').textContent = path;
        const bodyEl = document.getElementById('knowledge-viewer-body');
        bodyEl.innerHTML = renderMarkdown(data.content || '');
        viewer.classList.remove('hidden');
        applyHighlighting(viewer);
        bindKnowledgeLinks(bodyEl, path);

        // Mobile: hide sidebar, show content
        if (window.innerWidth < 768) {
            document.getElementById('knowledge-sidebar').classList.add('hidden');
        }
    }).catch(() => {});
}

function knowledgeMobileBack() {
    document.getElementById('knowledge-sidebar').classList.remove('hidden');
    document.getElementById('knowledge-content-viewer').classList.add('hidden');
}

function switchKnowledgeTab(tab) {
    document.querySelectorAll('.knowledge-tab').forEach(el => el.classList.remove('active'));
    document.getElementById('knowledge-tab-' + tab).classList.add('active');

    const docsPanel = document.getElementById('knowledge-panel-docs');
    const graphPanel = document.getElementById('knowledge-panel-graph');

    if (tab === 'docs') {
        docsPanel.classList.remove('hidden');
        graphPanel.classList.add('hidden');
    } else {
        docsPanel.classList.add('hidden');
        graphPanel.classList.remove('hidden');
        if (!_knowledgeGraphLoaded) {
            loadKnowledgeGraph();
        }
    }
}

let _d3LoadPromise = null;

function ensureD3Loaded() {
    if (window.d3) return Promise.resolve(window.d3);
    if (_d3LoadPromise) return _d3LoadPromise;
    _d3LoadPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'assets/vendor/d3/d3.min.js';
        script.async = true;
        script.onload = () => resolve(window.d3);
        script.onerror = () => reject(new Error('Failed to load d3'));
        document.head.appendChild(script);
    });
    return _d3LoadPromise;
}

function loadKnowledgeGraph() {
    _knowledgeGraphLoaded = true;
    const container = document.getElementById('knowledge-graph-container');
    container.innerHTML = '<div class="flex items-center justify-center h-full text-slate-400 text-sm"><i class="fas fa-spinner fa-spin mr-2"></i>Loading graph...</div>';

    Promise.all([
        ensureD3Loaded(),
        fetch('/api/knowledge/graph').then(r => r.json()),
    ]).then(([, data]) => {
        const nodes = data.nodes || [];
        const links = data.links || [];
        if (nodes.length === 0) {
            container.innerHTML = `<div class="flex flex-col items-center justify-center h-full text-slate-400"><i class="fas fa-diagram-project text-3xl mb-3 opacity-40"></i><p class="text-sm">${t('knowledge_empty_hint')}</p></div>`;
            return;
        }
        container.innerHTML = '';
        renderKnowledgeGraph(container, nodes, links);
    }).catch(() => {
        container.innerHTML = '<div class="flex items-center justify-center h-full text-slate-400 text-sm">Failed to load graph</div>';
    });
}

function renderKnowledgeGraph(container, nodes, links) {
    const width = container.clientWidth;
    const height = container.clientHeight || 600;

    const categories = [...new Set(nodes.map(n => n.category))];
    const colorScale = d3.scaleOrdinal(d3.schemeTableau10).domain(categories);

    // Connection count for sizing
    const connCount = {};
    nodes.forEach(n => connCount[n.id] = 0);
    links.forEach(l => {
        connCount[l.source] = (connCount[l.source] || 0) + 1;
        connCount[l.target] = (connCount[l.target] || 0) + 1;
    });

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g');

    // Zoom with adaptive label visibility
    let currentZoomScale = 1;
    const zoom = d3.zoom()
        .scaleExtent([0.2, 5])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
            currentZoomScale = event.transform.k;
            updateLabelVisibility();
        });
    svg.call(zoom);

    function updateLabelVisibility() {
        if (!label) return;
        if (currentZoomScale < 0.8) {
            label.attr('opacity', 0);
        } else {
            const baseFontSize = Math.min(12, 10 / Math.max(currentZoomScale * 0.7, 0.5));
            label.attr('opacity', 1).attr('font-size', baseFontSize);
        }
    }

    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(90))
        .force('charge', d3.forceManyBody().strength(-180))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('x', d3.forceX(width / 2).strength(0.06))
        .force('y', d3.forceY(height / 2).strength(0.06))
        .force('collision', d3.forceCollide().radius(d => getNodeRadius(d) + 30));

    function getNodeRadius(d) {
        return Math.max(5, Math.min(16, 5 + (connCount[d.id] || 0) * 2));
    }

    const link = g.append('g')
        .selectAll('line')
        .data(links)
        .join('line')
        .attr('stroke', '#94a3b8')
        .attr('stroke-opacity', 0.3)
        .attr('stroke-width', 1);

    const node = g.append('g')
        .selectAll('circle')
        .data(nodes)
        .join('circle')
        .attr('r', d => getNodeRadius(d))
        .attr('fill', d => colorScale(d.category))
        .attr('stroke', '#fff')
        .attr('stroke-width', 1.5)
        .style('cursor', 'pointer')
        .call(d3.drag()
            .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
            .on('end', (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
        );

    const label = g.append('g')
        .selectAll('text')
        .data(nodes)
        .join('text')
        .text(d => d.label.length > 15 ? d.label.slice(0, 14) + '…' : d.label)
        .attr('font-size', 9)
        .attr('dx', d => getNodeRadius(d) + 4)
        .attr('dy', 3)
        .attr('fill', '#64748b')
        .style('pointer-events', 'none');

    // Tooltip
    const tooltip = document.createElement('div');
    tooltip.className = 'knowledge-graph-tooltip';
    container.style.position = 'relative';
    container.appendChild(tooltip);

    node.on('mouseover', (event, d) => {
        tooltip.textContent = d.label + ' (' + d.category + ')';
        tooltip.style.opacity = '1';
        tooltip.style.left = (event.offsetX + 12) + 'px';
        tooltip.style.top = (event.offsetY - 8) + 'px';
        // Highlight connections
        link.attr('stroke-opacity', l => (l.source.id === d.id || l.target.id === d.id) ? 0.8 : 0.1);
        node.attr('opacity', n => n.id === d.id || links.some(l => (l.source.id === d.id && l.target.id === n.id) || (l.target.id === d.id && l.source.id === n.id)) ? 1 : 0.2);
        label.attr('opacity', n => n.id === d.id || links.some(l => (l.source.id === d.id && l.target.id === n.id) || (l.target.id === d.id && l.source.id === n.id)) ? 1 : 0.1);
    }).on('mousemove', (event) => {
        tooltip.style.left = (event.offsetX + 12) + 'px';
        tooltip.style.top = (event.offsetY - 8) + 'px';
    }).on('mouseout', () => {
        tooltip.style.opacity = '0';
        link.attr('stroke-opacity', 0.3);
        node.attr('opacity', 1);
        label.attr('opacity', 1);
    }).on('click', (event, d) => {
        // Switch to docs tab and open the file
        switchKnowledgeTab('docs');
        openKnowledgeFile(d.id, d.label);
    });

    simulation.on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        node.attr('cx', d => d.x).attr('cy', d => d.y);
        label.attr('x', d => d.x).attr('y', d => d.y);
    });

    // Auto fit-to-view when simulation settles
    simulation.on('end', () => {
        const pad = 16;
        let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
        nodes.forEach(n => {
            if (n.x < x0) x0 = n.x;
            if (n.y < y0) y0 = n.y;
            if (n.x > x1) x1 = n.x;
            if (n.y > y1) y1 = n.y;
        });
        const bw = x1 - x0 + pad * 2;
        const bh = y1 - y0 + pad * 2;
        if (bw > 0 && bh > 0) {
            const scale = Math.min(width / bw, height / bh, 4);
            const tx = width / 2 - (x0 + x1) / 2 * scale;
            const ty = height / 2 - (y0 + y1) / 2 * scale;
            svg.transition().duration(500).call(
                zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale)
            );
        }
    });

    // Legend
    const legendDiv = document.createElement('div');
    legendDiv.className = 'knowledge-graph-legend';
    categories.forEach(cat => {
        const item = document.createElement('span');
        item.className = 'knowledge-graph-legend-item';
        item.innerHTML = `<span class="knowledge-graph-legend-dot" style="background:${colorScale(cat)}"></span>${escapeHtml(cat)}`;
        legendDiv.appendChild(item);
    });
    container.appendChild(legendDiv);
}

// =====================================================================
// Authentication
// =====================================================================
function toggleLoginPassword() {
    const input = document.getElementById('login-password');
    const icon = document.querySelector('#login-toggle-pwd i');
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.replace('fa-eye', 'fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.replace('fa-eye-slash', 'fa-eye');
    }
}
window.toggleLoginPassword = toggleLoginPassword;

function showLoginScreen() {
    const overlay = document.getElementById('login-overlay');
    if (!overlay) return;
    overlay.classList.remove('hidden');
    document.getElementById('app').classList.add('hidden');

    const subtitle = document.getElementById('login-subtitle');
    const loginBtn = document.getElementById('login-btn');
    if (currentLang === 'en') {
        subtitle.textContent = 'Enter password to access the console';
        loginBtn.textContent = 'Login';
    } else {
        subtitle.textContent = '请输入密码以访问控制台';
        loginBtn.textContent = '登录';
    }

    const form = document.getElementById('login-form');
    const pwdInput = document.getElementById('login-password');
    pwdInput.focus();

    form.onsubmit = function(e) {
        e.preventDefault();
        const pwd = pwdInput.value;
        if (!pwd) return;
        const btn = document.getElementById('login-btn');
        const errEl = document.getElementById('login-error');
        btn.disabled = true;
        errEl.classList.add('hidden');

        fetch('/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({password: pwd})
        }).then(r => r.json()).then(data => {
            if (data.status === 'success') {
                overlay.classList.add('hidden');
                document.getElementById('app').classList.remove('hidden');
                initApp();
            } else {
                errEl.textContent = currentLang === 'zh' ? '密码错误' : 'Wrong password';
                errEl.classList.remove('hidden');
                pwdInput.value = '';
                pwdInput.focus();
            }
            btn.disabled = false;
        }).catch(() => {
            errEl.textContent = currentLang === 'zh' ? '网络错误，请重试' : 'Network error, please retry';
            errEl.classList.remove('hidden');
            btn.disabled = false;
        });
        return false;
    };
}

// Intercept 401 responses globally to show login screen on session expiry
const _originalFetch = window.fetch;
window.fetch = function(...args) {
    return _originalFetch.apply(this, args).then(response => {
        if (response.status === 401) {
            const url = typeof args[0] === 'string' ? args[0] : (args[0]?.url || '');
            if (!url.startsWith('/auth/')) {
                showLoginScreen();
            }
        }
        return response;
    });
};

function initApp() {
    applyI18n();
    _applyInputTooltips();
    _restoreSessionPanel();

    fetch('/api/knowledge/list').then(r => r.json()).then(data => {
        if (data.status === 'success') {
            _knowledgeTreeData = data.tree || [];
            _knowledgeRootFiles = data.root_files || [];
        }
    }).catch(() => {});

    fetch('/api/version').then(r => r.json()).then(data => {
        APP_VERSION = `v${data.version}`;
        document.getElementById('sidebar-version').textContent = `LightAgent ${APP_VERSION}`;
    }).catch(() => {
        document.getElementById('sidebar-version').textContent = 'LightAgent';
    });
    chatInput.focus();
}

// =====================================================================
// Initialization
// =====================================================================
applyTheme();
applyI18n();

fetch('/auth/check').then(r => r.json()).then(data => {
    if (data.auth_required && !data.authenticated) {
        showLoginScreen();
    } else {
        initApp();
    }
}).catch(() => {
    initApp();
});

requestAnimationFrame(() => {
    document.body.classList.add('transition-colors', 'duration-200');
});

// =====================================================================
// Task Edit Modal
// =====================================================================
let currentEditingTask = null;

function loadTaskChannelOptions(selectedChannelType) {
    const select = document.getElementById('task-edit-channel-type');
    select.innerHTML = '';
    fetch('/api/channels').then(r => r.json()).then(data => {
        if (data.status !== 'success') return;
        const allChannels = data.channels || [];
        // Only include currently active channels, strictly following the channel management page logic
        let channels = allChannels.filter(c => c.active).map(c => {
            const label = (typeof c.label === 'object') ? (c.label[currentLang] || c.label.en || c.name) : (c.label || c.name);
            return { name: c.name, label: label };
        });
        const channelNames = channels.map(c => c.name);
        // Always include the web console channel
        if (!channelNames.includes('web')) {
            channels.unshift({ name: 'web', label: currentLang === 'zh' ? 'Web' : 'Web' });
        }
        // If the currently selected channel is not in the active list (e.g. disabled), append it to preserve selection
        if (selectedChannelType && !channelNames.includes(selectedChannelType) && selectedChannelType !== 'web') {
            const ch = allChannels.find(c => c.name === selectedChannelType);
            const label = ch
                ? ((typeof ch.label === 'object') ? (ch.label[currentLang] || ch.label.en || ch.name) : (ch.label || ch.name))
                : selectedChannelType;
            channels.push({ name: selectedChannelType, label: label });
        }
        channels.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.name;
            opt.textContent = c.label;
            select.appendChild(opt);
        });
        // Set selected value
        if (selectedChannelType) {
            select.value = selectedChannelType;
        }
    }).catch(() => {
        // fallback: at least keep the current selection and web
        select.innerHTML = '';
        const webOpt = document.createElement('option');
        webOpt.value = 'web';
        webOpt.textContent = 'Web';
        select.appendChild(webOpt);
        
        if (selectedChannelType && selectedChannelType !== 'web') {
            const opt = document.createElement('option');
            opt.value = selectedChannelType;
            opt.textContent = selectedChannelType;
            select.appendChild(opt);
        }
        if (selectedChannelType) {
            select.value = selectedChannelType;
        }
        
        // Show error message
        console.error('Failed to load channel options');
    });
}

function openTaskEditModal(task) {
    currentEditingTask = task;
    const overlay = document.getElementById('task-edit-modal-overlay');
    const titleEl = document.querySelector('#task-edit-modal-overlay h3');
    const subtitle = document.getElementById('task-edit-modal-subtitle');
    const deleteBtn = document.getElementById('task-edit-modal-delete');
    const nameInput = document.getElementById('task-edit-name');
    const enabledInput = document.getElementById('task-edit-enabled');
    const scheduleTypeSelect = document.getElementById('task-edit-schedule-type');
    const cronInput = document.getElementById('task-edit-cron-expression');
    const intervalInput = document.getElementById('task-edit-interval-seconds');
    const onceInput = document.getElementById('task-edit-once-time');
    const actionTypeSelect = document.getElementById('task-edit-action-type');
    const receiverInput = document.getElementById('task-edit-receiver');
    const contentInput = document.getElementById('task-edit-content');

    // Set title and subtitle
    titleEl.textContent = t('task_edit_title');
    subtitle.textContent = task.id;
    deleteBtn.classList.remove('hidden');

    // Populate data
    nameInput.value = task.name || '';
    enabledInput.checked = task.enabled !== false;

    const schedule = task.schedule || {};
    scheduleTypeSelect.value = schedule.type || 'cron';

    // Clear all schedule type input values first to avoid stale data
    cronInput.value = '';
    intervalInput.value = '';
    onceInput.value = '';

    if (schedule.type === 'cron') {
        cronInput.value = schedule.expression || '';
    } else if (schedule.type === 'interval') {
        intervalInput.value = schedule.seconds || '';
    } else if (schedule.type === 'once') {
        if (schedule.run_at) {
            // Manually parse ISO time string to avoid cross-browser timezone issues with new Date()
            // run_at format: "YYYY-MM-DDTHH:mm:ss" or "YYYY-MM-DDTHH:mm:ss.ffffff"
            const parts = schedule.run_at.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
            if (parts) {
                const timeInput = document.getElementById('task-edit-once-time');
                timeInput.value = `${parts[1]}-${parts[2]}-${parts[3]}T${parts[4]}:${parts[5]}:${parts[6]}`;
            }
        }
    }

    const action = task.action || {};
    actionTypeSelect.value = action.type || 'send_message';
    receiverInput.value = action.receiver || '';
    contentInput.value = action.content || action.task_description || '';

    // Load channel options and set selected value
    loadTaskChannelOptions(action.channel_type || 'web');

    // Disable channel type selector — channel is read-only when editing.
    // Switching the channel after a task is created is problematic because:
    //   1. The WeChat (weixin/ilink) bot requires a valid context_token that is tied
    //      to a specific user-session on that channel. Changing the channel to weixin
    //      would invalidate the existing token — the new receiver on weixin may not
    //      have an active context_token, causing the scheduled push to silently fail.
    //   2. Other channels (DingTalk, Feishu, etc.) also carry channel-specific fields
    //      (e.g. dingtalk_sender_staff_id) that cannot be trivially re-populated for
    //      a different channel type without user intervention.
    //   3. The receiver identity itself is channel-bound — a weixin user-id means
    //      nothing on a Feishu channel, so changing the channel would orphan the task.
    // For these reasons, the channel type is intentionally frozen once a task exists.
    // Users who need a task on a different channel should create a new task through
    // the chat interface (by asking the bot) rather than editing an existing one.
    document.getElementById('task-edit-channel-type').disabled = true;

    // Update UI
    updateTaskScheduleFields();
    updateTaskActionLabel();

    overlay.classList.remove('hidden');
}

function closeTaskEditModal() {
    document.getElementById('task-edit-modal-overlay').classList.add('hidden');
    currentEditingTask = null;
}

function updateTaskScheduleFields() {
    const scheduleType = document.getElementById('task-edit-schedule-type').value;
    const cronWrap = document.getElementById('task-edit-cron-wrap');
    const intervalWrap = document.getElementById('task-edit-interval-wrap');
    const onceWrap = document.getElementById('task-edit-once-wrap');
    const cronHint = document.getElementById('task-edit-cron-hint');
    const intervalHint = document.getElementById('task-edit-interval-hint');
    
    cronWrap.classList.toggle('hidden', scheduleType !== 'cron');
    intervalWrap.classList.toggle('hidden', scheduleType !== 'interval');
    onceWrap.classList.toggle('hidden', scheduleType !== 'once');
    
    if (cronHint) cronHint.classList.toggle('hidden', scheduleType !== 'cron');
    if (intervalHint) intervalHint.classList.toggle('hidden', scheduleType !== 'interval');
}

function updateTaskActionLabel() {
    const actionType = document.getElementById('task-edit-action-type').value;
    const label = document.getElementById('task-edit-content-label');
    const content = document.getElementById('task-edit-content');
    
    if (actionType === 'send_message') {
        label.textContent = t('task_message_content');
        content.placeholder = t('task_message_content');
    } else {
        label.textContent = t('task_task_description');
        content.placeholder = t('task_task_description');
    }
}

function saveTaskEdit() {
    const nameInput = document.getElementById('task-edit-name');
    const enabledInput = document.getElementById('task-edit-enabled');
    const scheduleTypeSelect = document.getElementById('task-edit-schedule-type');
    const cronInput = document.getElementById('task-edit-cron-expression');
    const intervalInput = document.getElementById('task-edit-interval-seconds');
    const onceInput = document.getElementById('task-edit-once-time');
    const actionTypeSelect = document.getElementById('task-edit-action-type');
    const channelTypeSelect = document.getElementById('task-edit-channel-type');
    const receiverInput = document.getElementById('task-edit-receiver');
    const contentInput = document.getElementById('task-edit-content');
    const statusEl = document.getElementById('task-edit-modal-status');
    const saveBtn = document.getElementById('task-edit-modal-save');
    
    const name = nameInput.value.trim();
    if (!name) {
        statusEl.textContent = currentLang === 'zh' ? '请输入任务名称' : 'Please enter task name';
        statusEl.style.opacity = '1';
        setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
        return;
    }
    
    const scheduleType = scheduleTypeSelect.value;
    const schedule = { type: scheduleType };
    
    if (scheduleType === 'cron') {
        const expr = cronInput.value.trim();
        if (!expr) {
            statusEl.textContent = currentLang === 'zh' ? '请输入 Cron 表达式' : 'Please enter cron expression';
            statusEl.style.opacity = '1';
            setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
            return;
        }
        // Basic cron expression format validation: 5 or 6 fields
        const fields = expr.split(/\s+/);
        if (fields.length < 5 || fields.length > 6) {
            statusEl.textContent = currentLang === 'zh' ? 'Cron 表达式格式错误，应为 5 或 6 个字段（分 时 日 月 周）' : 'Invalid cron expression, expected 5 or 6 fields (min hour day month weekday)';
            statusEl.style.opacity = '1';
            setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
            return;
        }
        schedule.expression = expr;
        // Note: detailed cron expression validity is verified by the backend croniter library; frontend only does basic format validation
    } else if (scheduleType === 'interval') {
        const seconds = parseInt(intervalInput.value);
        if (!seconds || seconds < 60) {
            statusEl.textContent = currentLang === 'zh' ? '间隔秒数最小为 60 秒' : 'Interval must be at least 60 seconds';
            statusEl.style.opacity = '1';
            setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
            return;
        }
        schedule.seconds = seconds;
    } else if (scheduleType === 'once') {
        const time = onceInput.value;
        if (!time) {
            statusEl.textContent = currentLang === 'zh' ? '请选择执行时间' : 'Please select execution time';
            statusEl.style.opacity = '1';
            setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
            return;
        }
        // Validate execution time format
        const selectedTime = new Date(time);
        if (isNaN(selectedTime.getTime())) {
            statusEl.textContent = currentLang === 'zh' ? '执行时间格式错误' : 'Invalid execution time format';
            statusEl.style.opacity = '1';
            setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
            return;
        }
        // Validate that time is in the future for one-time tasks
        if (selectedTime <= new Date()) {
            statusEl.textContent = currentLang === 'zh' ? '执行时间必须在当前时间之后' : 'Execution time must be in the future';
            statusEl.style.opacity = '1';
            setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
            return;
        }
        // datetime-local value with step="1" is already in YYYY-MM-DDTHH:mm:ss format
        // Backend _parse_naive_local treats strings without timezone suffix as local time
        schedule.run_at = time;
    }
    
    const actionType = actionTypeSelect.value;
    const channelType = channelTypeSelect.value;
    const content = contentInput.value.trim();

    if (!content) {
        statusEl.textContent = currentLang === 'zh' ? '请输入内容' : 'Please enter content';
        statusEl.style.opacity = '1';
        setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
        return;
    }
    
    // Build action with only necessary fields to avoid stale data
    const action = {
        type: actionType,
        channel_type: channelType,
        receiver: '',
        receiver_name: '',
        is_group: false,
        notify_session_id: ''
    };
    
    if (actionType === 'send_message') {
        action.content = content;
    } else {
        action.task_description = content;
    }
    
    // Preserve the original receiver info (channel is read-only, so it never changes)
    if (currentEditingTask && currentEditingTask.action) {
        action.receiver = currentEditingTask.action.receiver || '';
        action.receiver_name = currentEditingTask.action.receiver_name || '';
        action.is_group = currentEditingTask.action.is_group || false;
        action.notify_session_id = currentEditingTask.action.notify_session_id || '';
        action.receiver_kind = currentEditingTask.action.receiver_kind || '';
        action.stable_receiver = currentEditingTask.action.stable_receiver || '';
        action.runtime_receiver = currentEditingTask.action.runtime_receiver || '';
        
        // Preserve channel-specific fields (e.g. DingTalk sender_staff_id)
        if (channelType === 'dingtalk' && currentEditingTask.action.dingtalk_sender_staff_id) {
            action.dingtalk_sender_staff_id = currentEditingTask.action.dingtalk_sender_staff_id;
        }
    }
    
    saveBtn.disabled = true;
    
    const payload = {
        task_id: currentEditingTask.id,
        name: name,
        enabled: enabledInput.checked,
        schedule: schedule,
        action: action
    };
    
    fetch('/api/scheduler/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(r => r.json()).then(res => {
        saveBtn.disabled = false;
        if (res.status === 'success') {
            closeTaskEditModal();
            tasksLoaded = false;
            loadTasksView();
        } else {
            statusEl.textContent = res.message || (currentLang === 'zh' ? '保存失败' : 'Save failed');
            statusEl.style.opacity = '1';
            setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
        }
    }).catch(() => {
        saveBtn.disabled = false;
        statusEl.textContent = currentLang === 'zh' ? '网络错误' : 'Network error';
        statusEl.style.opacity = '1';
        setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
    });
}

function deleteTask() {
    if (!currentEditingTask) return;
    
    const taskName = currentEditingTask.name || currentEditingTask.id || '未知任务';
    const taskId = currentEditingTask.id;  // Capture early to avoid closure race condition
    showConfirmDialog({
        title: t('task_delete_confirm_title'),
        message: (currentLang === 'zh' ? `确定要删除任务「${taskName}」吗？` : `Are you sure to delete task "${taskName}"?`),
        onConfirm: () => {
            fetch('/api/scheduler/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: taskId })
            }).then(r => r.json()).then(res => {
                if (res.status === 'success') {
                    closeTaskEditModal();
                    tasksLoaded = false;
                    loadTasksView();
                } else {
                    const statusEl = document.getElementById('task-edit-modal-status');
                    if (statusEl) {
                        statusEl.textContent = res.message || 'Delete failed';
                        statusEl.classList.remove('hidden', 'text-green-500');
                        statusEl.classList.add('text-red-500');
                        setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
                    }
                }
            }).catch(() => {
                const statusEl = document.getElementById('task-edit-modal-status');
                if (statusEl) {
                    statusEl.textContent = 'Network error';
                    statusEl.classList.remove('hidden', 'text-green-500');
                    statusEl.classList.add('text-red-500');
                    setTimeout(() => { statusEl.style.opacity = '0'; }, 3000);
                }
            });
        }
    });
}

document.getElementById('task-edit-schedule-type').addEventListener('change', updateTaskScheduleFields);
document.getElementById('task-edit-action-type').addEventListener('change', updateTaskActionLabel);
document.getElementById('task-edit-modal-cancel').addEventListener('click', closeTaskEditModal);
document.getElementById('task-edit-modal-save').addEventListener('click', saveTaskEdit);
document.getElementById('task-edit-modal-delete').addEventListener('click', deleteTask);
document.getElementById('task-edit-modal-overlay').addEventListener('click', function(e) {
    if (e.target === this) closeTaskEditModal();
});
