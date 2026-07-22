"""Context assembly for WeChat group memory injection."""

from __future__ import annotations

from typing import Dict, List, Optional

from channel.wechat_group.wechat_group_knowledge_service import WechatGroupKnowledgeService
from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService
from config import conf


class WechatGroupContextService:
    def __init__(
        self,
        profile_service: Optional[WechatGroupProfileService] = None,
        knowledge_service: Optional[WechatGroupKnowledgeService] = None,
    ):
        self.profile_service = profile_service or WechatGroupProfileService()
        self.knowledge_service = knowledge_service or WechatGroupKnowledgeService()

    def preview_context(
        self,
        room_id: str,
        sender_id: str,
        query: str,
        mentioned_sender_ids: List[str],
        bot_sender_id: str = "",
    ) -> Dict:
        group_memories = []
        speaker_profile = None
        mentioned_profiles = []
        filtered_reasons = []

        knowledge_enabled = bool(conf().get(
            "wechat_group_knowledge_enabled",
            conf().get("wechat_group_memory_enabled", True),
        ))
        profile_enabled = bool(conf().get(
            "wechat_group_profile_enabled",
            conf().get("wechat_group_member_memory_enabled", True),
        ))

        if knowledge_enabled:
            group_memories = self.knowledge_service.search_group_memories(
                room_id,
                query=query,
                limit=int(conf().get("wechat_group_group_memory_context_limit", 5) or 5),
            )
        else:
            filtered_reasons.append("group knowledge disabled")

        if profile_enabled:
            resolved = self.profile_service.resolve_profiles_for_prompt(
                room_id=room_id,
                sender_id=sender_id,
                mentioned_sender_ids=mentioned_sender_ids or [],
                query=query,
                bot_sender_id=bot_sender_id,
            )
            speaker_profile = resolved.get("speaker_profile")
            mentioned_profiles = resolved.get("mentioned_profiles") or []
            limit = int(conf().get("wechat_group_profile_context_limit", 2) or 2)
            mentioned_profiles = mentioned_profiles[:limit]
        else:
            filtered_reasons.append("profile disabled")

        content = self._render_prompt_block(
            sender_id=sender_id,
            group_memories=group_memories,
            speaker_profile=speaker_profile,
            mentioned_profiles=mentioned_profiles,
        )
        return {
            "content": content,
            "group_memories": group_memories,
            "speaker_profile": speaker_profile,
            "mentioned_profiles": mentioned_profiles,
            "filtered_reasons": filtered_reasons,
        }

    def build_prompt_block(
        self,
        room_id: str,
        sender_id: str,
        query: str,
        mentioned_sender_ids: List[str],
        bot_sender_id: str = "",
    ) -> str:
        preview = self.preview_context(
            room_id=room_id,
            sender_id=sender_id,
            query=query,
            mentioned_sender_ids=mentioned_sender_ids,
            bot_sender_id=bot_sender_id,
        )
        return preview["content"]

    @staticmethod
    def _render_prompt_block(
        sender_id: str,
        group_memories: Optional[List[Dict]],
        speaker_profile: Optional[Dict],
        mentioned_profiles: Optional[List[Dict]],
    ) -> str:
        sections = []
        for item in group_memories or []:
            sections.append("[group_memory]\n{}".format(str(item.get("content") or "").strip()))
        if speaker_profile or mentioned_profiles:
            sections.append(
                "[naming_policy]\n"
                "When referring to any listed WeChat group member in the reply, "
                "use reply_name as the preferred display name. If reply_name is "
                "unavailable, use primary_nickname. Do not use sender_id as a name."
            )
        if speaker_profile:
            speaker_member_id = str(
                speaker_profile.get("stable_member_id") or speaker_profile.get("sender_id") or sender_id or ""
            ).strip()
            sections.append(
                '[speaker_profile sender_id="{}"]\n{}'.format(
                    speaker_member_id,
                    str(speaker_profile.get("content") or "").strip(),
                )
            )
        for profile in mentioned_profiles or []:
            mentioned_id = str(profile.get("sender_id") or "").strip()
            if not mentioned_id:
                continue
            sections.append(
                '[mentioned_profile sender_id="{}"]\n{}'.format(
                    mentioned_id,
                    str(profile.get("content") or "").strip(),
                )
            )
        if not sections:
            return ""
        return "<wechat-group-memory>\n{}\n</wechat-group-memory>".format("\n\n".join(sections))
