# 微信群日志打印优化计划

## 背景

当前 Agent 请求摘要日志包含较多 schema 细节，微信群自由回复链路也缺少“收到什么消息、为何接话或沉默”的直观日志。用户已确认采用短句组合式日志，先展示关键判断信息，不打印完整 prompt、历史消息或工具 schema。

## 目标

- 微信群收到消息时打印群名、发送人、消息类型和截断后的正文预览。
- 未 @ 文本进入自由回复判定后，打印得分、阈值、档位、命中原因和抑制原因。
- 自由回复入队、worker/LLM 复核通过或拒绝时打印简洁结果。
- Agent LLM 请求摘要压缩为一行，保留 system 字数/来源、历史条数/角色/字数、工具数量/名称。

## 修改范围

- `agent/protocol/agent_stream.py`
- `channel/wechat_group/wechat_group_channel.py`
- `channel/wechat_group/wechat_group_free_reply_worker.py`
- `tests/test_agent_stream_logging.py`
- `tests/test_wechat_group_channel.py`
- `CHANGES.md`

## 验证计划

- `python -m unittest tests.test_agent_stream_logging`
- `python -m unittest tests.test_wechat_group_channel`
- `python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- `python -m py_compile agent\protocol\agent_stream.py channel\wechat_group\wechat_group_channel.py channel\wechat_group\wechat_group_free_reply_worker.py`

## 实际改动

- `agent/protocol/agent_stream.py`：LLM 请求摘要由多行改为单行，工具部分只保留数量和前 6 个工具名，不再展开 schema。
- `agent/protocol/agent_stream.py`：Agent turn start 日志改为结构化摘要，只打印真实用户问题预览和微信群增强块规模，不再打印人设、最近群聊 transcript 或群记忆正文。
- `channel/wechat_group/wechat_group_channel.py`：新增微信群入站消息日志，以及自由回复本地判定的入队/跳过日志。
- `channel/wechat_group/wechat_group_free_reply_worker.py`：新增自由回复 LLM 复核通过/拒绝日志。
- `tests/test_agent_stream_logging.py`、`tests/test_wechat_group_channel.py`、`tests/test_wechat_group_free_reply_worker.py`：补充日志回归测试。

## 验证结果

- 通过：`python -m unittest tests.test_agent_stream_logging tests.test_wechat_group_free_reply_worker`
- 通过：`python -m unittest tests.test_wechat_group_message tests.test_wechat_group_channel tests.test_wechat_group_web`
- 通过：`python -m py_compile agent\protocol\agent_stream.py channel\wechat_group\wechat_group_channel.py channel\wechat_group\wechat_group_free_reply_worker.py tests\test_agent_stream_logging.py tests\test_wechat_group_channel.py tests\test_wechat_group_free_reply_worker.py`
- 追加通过：`python -m unittest tests.test_agent_stream_logging`
- 追加通过：`python -m py_compile agent\protocol\agent_stream.py tests\test_agent_stream_logging.py`

## 当前状态

- 已完成代码实现与自动化验证。
- 真实微信群链路仍需在运行环境中手动观察日志输出。
