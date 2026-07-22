import unittest

from channel.wechat_group.wechat_group_profile_llm_extractor import (
    WechatGroupProfileExtractionError,
    WechatGroupProfileLlmExtractor,
)


LONG_WECHAT_IMAGE_TRANSPORT_XML = """<?xml version="1.0"?>
<msg><img aeskey="{}" cdnthumburl="masked" hevc_mid_size="31347" /></msg>
""".format("a" * 240)


class FakeModel:
    def __init__(self, response):
        self.response = response
        self.prompt = ""

    def reply_text(self, prompt):
        self.prompt = prompt
        return self.response


class FakeCallModel:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def call(self, request):
        self.requests.append(request)
        return self.response


class WechatGroupProfileLlmExtractorTest(unittest.TestCase):
    def test_prompt_and_result_use_only_opaque_member_tokens(self):
        model = FakeModel(
            '{"profiles":[{"member_token":"member_001","aliases":[{"value":"Alice Lead","confidence":0.91,"evidence_message_ids":["m1"]}]}]}'
        )
        extractor = WechatGroupProfileLlmExtractor(model=model)

        result = extractor.extract(
            room_id="wgr_secret",
            room_name="Group A",
            messages=[{
                "message_id": "m1",
                "member_token": "member_001",
                "sender_nickname": "Alice",
                "message_type": "text",
                "text": "Alice Lead will coordinate release",
                "sender_id": "runtime-secret",
                "stable_member_id": "wgm_secret",
                "media_path": "D:/private/image.jpg",
            }],
            existing_profiles=[{
                "member_token": "member_001",
                "primary_nickname": "Alice",
                "stable_member_id": "wgm_secret",
                "content": "stable_member_id: wgm_secret",
            }],
        )

        self.assertEqual("member_001", result["profiles"][0]["member_token"])
        self.assertNotIn("sender_id", result["profiles"][0])
        for secret in ("wgr_secret", "wgm_secret", "runtime-secret", "D:/private/image.jpg"):
            self.assertNotIn(secret, model.prompt)
        self.assertIn("Alice(member_001)", model.prompt)

    def test_extractor_rejects_legacy_sender_id_output(self):
        extractor = WechatGroupProfileLlmExtractor(
            model=FakeModel('{"profiles":[{"sender_id":"wxid_alice","confidence":0.9}]}')
        )

        result = extractor.extract(
            room_id="wgr_a",
            room_name="Group A",
            messages=[],
            existing_profiles=[],
        )

        self.assertEqual([], result["profiles"])

    def test_extractor_rejects_invalid_json(self):
        extractor = WechatGroupProfileLlmExtractor(model=FakeModel("not json"))

        with self.assertRaises(ValueError):
            extractor.extract("wgr_a", "Group A", [], [])

    def test_extractor_projects_image_transport_xml_to_placeholder(self):
        model = FakeModel('{"profiles":[]}')
        extractor = WechatGroupProfileLlmExtractor(model=model)

        extractor.extract(
            room_id="wgr_a",
            room_name="Group A",
            messages=[{
                "message_id": "image-1",
                "member_token": "member_001",
                "sender_nickname": "Alice",
                "message_type": "text",
                "text": LONG_WECHAT_IMAGE_TRANSPORT_XML,
            }],
            existing_profiles=[],
        )

        self.assertIn("Alice(member_001): [image]", model.prompt)
        for fragment in ("<?xml", "<img", "hevc_mid_size", "aeskey", "cdnthumburl"):
            self.assertNotIn(fragment, model.prompt)

    def test_extractor_drops_claims_without_evidence(self):
        extractor = WechatGroupProfileLlmExtractor(
            model=FakeModel(
                '{"profiles":[{"member_token":"member_001",'
                '"aliases":[{"value":"Alice Lead","confidence":0.91}],'
                '"interests":["release"],"common_terms":["ship"]}]}'
            )
        )

        result = extractor.extract("wgr_a", "Group A", [], [])

        profile = result["profiles"][0]
        self.assertEqual([], profile["aliases"])
        self.assertEqual([], profile["interests"])
        self.assertEqual([], profile["common_terms"])

    def test_extractor_supports_agent_llm_model_call_request(self):
        extractor = WechatGroupProfileLlmExtractor(
            model=FakeCallModel('{"profiles":[{"member_token":"member_001"}]}')
        )

        result = extractor.extract(
            "wgr_a",
            "Group A",
            [{"message_id": "m1", "member_token": "member_001", "text": "hello"}],
            [],
        )

        self.assertEqual("member_001", result["profiles"][0]["member_token"])
        self.assertEqual("wechat-group-profile-evolution", extractor.model.requests[0].metadata["source"])

    def test_extractor_classifies_model_error_before_json_parse(self):
        extractor = WechatGroupProfileLlmExtractor(
            model=FakeCallModel({
                "error": True,
                "message": "Inference is temporarily unavailable",
                "status_code": 503,
            })
        )

        with self.assertRaises(WechatGroupProfileExtractionError) as cm:
            extractor.extract("wgr_a", "Group A", [], [])

        self.assertTrue(cm.exception.transient)
        self.assertEqual(503, cm.exception.status_code)
        self.assertIn("LLM provider temporarily unavailable", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
