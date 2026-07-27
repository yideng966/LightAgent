# 微信群自由回复评分与发送链路修复记录

日期：2026-07-03

## 背景

用户反馈自由回复评分经常为 0，并指出应参考 `D:\JiangShuai\SourceCode\BaiLongmaPro` 中的评分逻辑。同时从日志观察到部分消息得分达到阈值后，似乎没有继续请求最终 LLM 并发送到微信群。

## 根因

1. 本项目自由回复本地评分规则过窄，只覆盖少量“谁能/帮我/怎么/如何”等关键词，未覆盖“哪里/啥意思/能不能/看看”等常见群聊口语问法。
2. 原始 XML / 表情 / 图片 payload 仍按普通文本评分，可能因为 XML 头部 `?` 被误判为群问题。
3. 自由回复 worker 的 LLM 复核通过后再次调用通用群聊 `_compose_context()`，但普通群聊非 @ 文本会被 `ChatChannel` 的触发规则拦截，导致无法进入最终回复队列。
4. Web 控制台切换自由回复活跃档位时没有同步刷新档位参数输入框，容易把 normal 档阈值保存到 active 档。

## 参考逻辑

参考文件：

- `D:\JiangShuai\SourceCode\BaiLongmaPro\src\social\wechat-ambient-reply.js`
- `D:\JiangShuai\SourceCode\BaiLongmaPro\src\social\wechaty-duty-group.js`

采用的思路：

- 评分分为正向原因和抑制原因。
- 群聊口语问题、能力请求、记忆/上下文请求分别加分。
- 近期上下文存在时，短问题可补充 unanswered 类加分。
- 原始媒体 payload 不应作为普通文本问题触发。
- 自由接话命中后必须绕过普通 @ 触发门槛，进入最终回复链路。

## 实际改动

- `channel/wechat_group/wechat_group_free_reply.py`
  - 扩展中文口语问题、能力请求、记忆上下文和梗/吐槽规则。
  - 新增 XML / 表情 / 图片等原始 payload 抑制。
  - 使用 `recent_messages` 为问题补充 `unanswered_question` 加分。

- `channel/wechat_group/wechat_group_channel.py`
  - 自由回复评分前读取当前群最近消息。
  - worker 复核通过后构造上下文时传入 `wechat_group_force_reply=True`。

- `channel/chat_channel.py`
  - 群聊文本触发判断支持 `wechat_group_force_reply`，仅用于已通过自由回复判定的上下文。

- `channel/web/static/js/console.js`
  - 切换自由回复档位时同步刷新当前档位参数输入框。

- `tests/test_wechat_group_free_reply.py`
  - 覆盖“哪里的用户名”在 active 档结合近期上下文触发。
  - 覆盖 XML payload 被抑制且不误判为群问题。

- `tests/test_wechat_group_channel.py`
  - 覆盖 worker LLM 复核通过后绕过普通群聊非 @ 过滤并进入 `produce()`。

- `tests/test_wechat_group_web.py`
  - 覆盖前端存在自由回复档位参数同步逻辑。

## 验证结果

已通过：

```powershell
python -m unittest tests.test_wechat_group_free_reply tests.test_wechat_group_free_reply_judge tests.test_wechat_group_free_reply_worker tests.test_wechat_group_channel tests.test_wechat_group_web
```

```powershell
node --check D:\JiangShuai\SourceCode\CowAgent\channel\web\static\js\console.js
```

```powershell
python -m py_compile channel\chat_channel.py channel\wechat_group\wechat_group_free_reply.py channel\wechat_group\wechat_group_channel.py tests\test_wechat_group_free_reply.py tests\test_wechat_group_channel.py tests\test_wechat_group_web.py
```

## 剩余事项

- 尚未执行真实微信群手动验收。建议启动 CowAgent 后在已开启自由回复的测试群发送：
  - “哪里的用户名”
  - “这是啥意思”
  - 一条表情或图片消息
  - 一条明确 @ 机器人消息
- 预期结果：
  - 普通口语问题在存在近期上下文时进入自由回复 LLM 复核。
  - XML / 表情 / 图片原始 payload 不因 `?` 误触发。
  - 自由回复通过后能发送到原群且不 mention 发言人。
  - @ 必回链路不受影响。
