import io
import json
import unittest


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
        self.headers = {}

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class WechatGroupStickerOnlineTest(unittest.TestCase):
    def test_clean_meme_query_removes_mention_and_command_words(self):
        from channel.wechat_group.wechat_group_sticker_online import clean_meme_query

        self.assertEqual("开心", clean_meme_query("@机器人 来个开心表情包"))
        self.assertEqual("吃瓜", clean_meme_query("搜一张吃瓜gif"))

    def test_safe_query_blocks_sensitive_terms(self):
        from channel.wechat_group.wechat_group_sticker_online import is_safe_meme_query

        self.assertFalse(is_safe_meme_query("token 表情包"))
        self.assertFalse(is_safe_meme_query("银行卡 梗图"))
        self.assertTrue(is_safe_meme_query("开心吃瓜"))

    def test_public_image_url_rejects_private_or_non_https_urls(self):
        from channel.wechat_group.wechat_group_sticker_online import normalize_public_image_url

        self.assertEqual("", normalize_public_image_url("http://biaoqing.gtimg.com/a.png", https_only=True))
        self.assertEqual("", normalize_public_image_url("https://127.0.0.1/a.png", https_only=True))
        self.assertEqual("", normalize_public_image_url("https://192.168.1.2/a.png", https_only=True))
        self.assertEqual("", normalize_public_image_url("file:///tmp/a.png", https_only=True))
        self.assertEqual(
            "https://biaoqing.gtimg.com/a.png",
            normalize_public_image_url(" https://biaoqing.gtimg.com/a.png ", https_only=True),
        )

    def test_allowed_meme_url_honors_domain_and_gif_config(self):
        from channel.wechat_group.wechat_group_sticker_online import is_allowed_meme_url

        config = {"allowed_domains": ["biaoqing.gtimg.com"], "allow_gif": False}

        self.assertTrue(is_allowed_meme_url("https://biaoqing.gtimg.com/a.png", config))
        self.assertFalse(is_allowed_meme_url("https://evil.example.com/a.png", config))
        self.assertFalse(is_allowed_meme_url("https://biaoqing.gtimg.com/a.gif", config))

    def test_diversify_meme_items_is_stable_for_same_seed(self):
        from channel.wechat_group.wechat_group_sticker_online import diversify_meme_items

        items = [
            {"url": "https://biaoqing.gtimg.com/a.png", "width": 240, "height": 240, "size": 100},
            {"url": "https://biaoqing.gtimg.com/b.png", "width": 240, "height": 240, "size": 100},
            {"url": "https://biaoqing.gtimg.com/c.gif", "width": 240, "height": 240, "size": 100},
        ]

        first = diversify_meme_items(items, "开心", seed="room:a")
        second = diversify_meme_items(items, "开心", seed="room:a")
        third = diversify_meme_items(items, "开心", seed="room:b")

        self.assertEqual([item["url"] for item in first], [item["url"] for item in second])
        self.assertNotEqual([item["url"] for item in first], [item["url"] for item in third])

    def test_search_online_memes_parses_xiaoapi_response(self):
        from channel.wechat_group.wechat_group_sticker_online import search_online_memes

        requests = []

        def opener(request, timeout=0):
            requests.append((request.full_url, timeout, dict(request.header_items())))
            return FakeResponse({
                "data": [
                    {
                        "img_url": "https://biaoqing.gtimg.com/happy.gif",
                        "img_width": 240,
                        "img_height": 180,
                        "img_size": 1234,
                    },
                    {
                        "img_url": "https://evil.example.com/blocked.png",
                        "img_width": 240,
                        "img_height": 180,
                        "img_size": 1234,
                    },
                ]
            })

        result = search_online_memes(
            "来个开心表情包",
            count=5,
            seed="room:sender",
            config={
                "enabled": True,
                "provider": "xiaoapi",
                "endpoint": "https://api.suol.cc/v1/meme.php",
                "allowed_domains": ["biaoqing.gtimg.com"],
                "allow_gif": True,
            },
            opener=opener,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("开心", result["query"])
        self.assertEqual(1, result["count"])
        self.assertEqual("https://biaoqing.gtimg.com/happy.gif", result["items"][0]["url"])
        self.assertIn("msg=%E5%BC%80%E5%BF%83", requests[0][0])
        self.assertIn("num=5", requests[0][0])
        self.assertGreater(requests[0][1], 0)

    def test_search_online_memes_rejects_private_or_unapproved_endpoint(self):
        from channel.wechat_group.wechat_group_sticker_online import search_online_memes

        def opener(request, timeout=0):
            raise AssertionError("unsafe endpoint should not be requested")

        private_result = search_online_memes(
            "开心",
            config={
                "enabled": True,
                "provider": "xiaoapi",
                "endpoint": "https://127.0.0.1/v1/meme.php",
                "allowed_domains": ["biaoqing.gtimg.com"],
                "allow_gif": True,
            },
            opener=opener,
        )
        unapproved_result = search_online_memes(
            "开心",
            config={
                "enabled": True,
                "provider": "xiaoapi",
                "endpoint": "https://evil.example.com/v1/meme.php",
                "allowed_domains": ["biaoqing.gtimg.com"],
                "allow_gif": True,
            },
            opener=opener,
        )

        self.assertFalse(private_result["ok"])
        self.assertEqual("meme endpoint is not allowed", private_result["error"])
        self.assertFalse(unapproved_result["ok"])
        self.assertEqual("meme endpoint is not allowed", unapproved_result["error"])

    def test_search_online_memes_reports_invalid_json(self):
        from channel.wechat_group.wechat_group_sticker_online import search_online_memes

        def opener(request, timeout=0):
            return FakeResponse(io.BytesIO(b"not-json").read())

        result = search_online_memes(
            "开心",
            config={
                "enabled": True,
                "provider": "xiaoapi",
                "endpoint": "https://api.suol.cc/v1/meme.php",
                "allowed_domains": ["biaoqing.gtimg.com"],
                "allow_gif": True,
            },
            opener=opener,
        )

        self.assertFalse(result["ok"])
        self.assertEqual("invalid meme api response", result["error"])


if __name__ == "__main__":
    unittest.main()
