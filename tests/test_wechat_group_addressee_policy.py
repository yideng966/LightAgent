import unittest

from channel.wechat_group.wechat_group_free_reply_judge import build_free_reply_judge_prompt
from channel.wechat_group.wechat_group_reply_policy import build_wechat_group_addressee_policy_block


class _FakeWechatGroupMessage:
    is_at = True
    is_quote_self = False
    actual_user_id = "wxid_alice"
    actual_user_nickname = "Alice"
    to_user_id = "wxid_bot"
    to_user_nickname = "LightBot"
    at_list = ["wxid_bot", "wxid_bob"]


class WechatGroupAddresseePolicyTest(unittest.TestCase):
    def test_addressee_policy_lists_non_bot_mentions_and_delegation_boundary(self):
        block = build_wechat_group_addressee_policy_block(_FakeWechatGroupMessage(), "direct_reply")

        self.assertIn("<wechat-group-addressee-policy>", block)
        self.assertIn("sender_id: wxid_alice", block)
        self.assertIn("mentioned_member_ids: wxid_bob", block)
        self.assertIn("不要替被请求的群友答应、拒绝或执行", block)
        self.assertIn("他/她/这个人", block)
        self.assertNotIn("mentioned_member_ids: wxid_bot", block)

    def test_free_reply_judge_suppresses_member_directed_requests(self):
        prompt = build_free_reply_judge_prompt({
            "room_name": "测试群",
            "sender_name": "Alice",
            "text": "Bob 帮我把这个发一下",
            "local_decision": {
                "score": 55,
                "threshold": 50,
                "reasons": ["group_question"],
                "suppressions": [],
            },
        })

        self.assertIn("A 对 B", prompt)
        self.assertIn("should_reply=false", prompt)
        self.assertIn("请求群友", prompt)


if __name__ == "__main__":
    unittest.main()
