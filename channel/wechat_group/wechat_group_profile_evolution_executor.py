"""Executor for one validated WeChat group profile evolution pass."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from common.log import logger

from channel.wechat_group.wechat_group_archive import WechatGroupArchive
from channel.wechat_group.wechat_group_profile_evolution_merger import (
    WechatGroupProfileEvolutionMerger,
)
from channel.wechat_group.wechat_group_profile_evolution_store import (
    WechatGroupProfileEvolutionStore,
)
from channel.wechat_group.wechat_group_profile_llm_extractor import (
    WechatGroupProfileExtractionError,
    WechatGroupProfileLlmExtractor,
)
from channel.wechat_group.wechat_group_profile_service import WechatGroupProfileService


class WechatGroupProfileEvolutionExecutor:
    def __init__(
        self,
        archive: Optional[WechatGroupArchive] = None,
        evolution_store: Optional[WechatGroupProfileEvolutionStore] = None,
        profile_service: Optional[WechatGroupProfileService] = None,
        extractor: Optional[Any] = None,
        merger: Optional[Any] = None,
        batch_message_limit: int = 200,
    ):
        self.archive = archive or WechatGroupArchive()
        self.evolution_store = evolution_store or WechatGroupProfileEvolutionStore()
        self.profile_service = profile_service or WechatGroupProfileService(
            store=self.evolution_store.profile_store,
        )
        if os.path.abspath(self.profile_service.store.db_path) != os.path.abspath(self.evolution_store.db_path):
            raise ValueError("profile service and evolution store must share one profile database")
        self.extractor = extractor or WechatGroupProfileLlmExtractor()
        self.merger = merger or WechatGroupProfileEvolutionMerger(
            profile_service=self.profile_service,
        )
        self.batch_message_limit = max(int(batch_message_limit or 200), 1)

    def run_once(self, room_id: str, trigger_source: str = "manual") -> Dict[str, Any]:
        room_text = str(room_id or "").strip()
        if not room_text:
            raise ValueError("stable_room_id is required")

        status = self.evolution_store.get_status(room_text)
        if int(status.get("updated_at") or 0) == 0:
            baseline = self.archive.get_max_row_id(room_text)
            status = self.evolution_store.update_status(
                room_text,
                last_archive_row_id=baseline,
                latest_observed_row_id=baseline,
                running=False,
            )
        start_row_id = int(status.get("last_archive_row_id") or 0)
        run_id = self.evolution_store.create_run(room_text, trigger_source, start_row_id)
        self.evolution_store.update_status(room_text, running=True)

        try:
            messages = self.archive.get_messages_after_row_id(
                room_text,
                start_row_id,
                limit=self.batch_message_limit,
            )
            if not messages:
                self._finish_run(run_id, "skipped", start_row_id)
                self.evolution_store.update_status(room_text, running=False)
                return self._result("skipped", run_id, 0, {})

            room_name = self._resolve_room_name(messages)
            projected_messages, existing_profiles, member_by_token, evidence_by_token = self._prepare_batch(
                room_text,
                messages,
            )
            merge_result: Dict[str, int] = {}
            if projected_messages and member_by_token:
                payload = self.extractor.extract(
                    room_id=room_text,
                    room_name=room_name,
                    messages=projected_messages,
                    existing_profiles=existing_profiles,
                )
                merge_result = self.merger.merge(
                    room_id=room_text,
                    run_id=run_id,
                    payload=payload,
                    room_name=room_name,
                    member_by_token=member_by_token,
                    evidence_by_token=evidence_by_token,
                )

            end_row_id = int(messages[-1].get("id") or start_row_id)
            self.evolution_store.finish_run(
                run_id=run_id,
                status="success",
                batch_end_row_id=end_row_id,
                batch_message_count=len(messages),
                analyzed_member_count=len(member_by_token),
                profile_update_count=int(merge_result.get("profile_update_count") or 0),
                alias_update_count=int(merge_result.get("alias_update_count") or 0),
                role_hint_update_count=int(merge_result.get("role_hint_update_count") or 0),
            )
            self.evolution_store.update_status(
                room_text,
                last_archive_row_id=end_row_id,
                last_success_at=int(time.time()),
                running=False,
                last_failed_reason="",
            )
            return self._result("success", run_id, len(messages), merge_result)
        except WechatGroupProfileExtractionError as e:
            logger.warning("[wechat_group] profile evolution LLM extraction failed for room {}: {}".format(room_text, e))
            self._record_failure(room_text, run_id, start_row_id, e)
            raise
        except Exception as e:
            logger.warning("[wechat_group] profile evolution failed for room {}: {}".format(room_text, e))
            self._record_failure(room_text, run_id, start_row_id, e)
            raise

    def _prepare_batch(
        self,
        room_id: str,
        messages: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str], Dict[str, List[str]]]:
        related_members: List[Tuple[str, List[str]]] = []
        member_order: List[str] = []
        bot_runtime_ids = {
            str((item.get("metadata") or {}).get("self_id") or "").strip()
            for item in messages
            if isinstance(item.get("metadata"), dict)
        }
        bot_runtime_ids.discard("")

        for item in messages:
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            runtime_sender_id = str(item.get("runtime_sender_id") or item.get("sender_id") or "").strip()
            raw_subject = str(item.get("stable_member_id") or runtime_sender_id).strip()
            author_member = ""
            if runtime_sender_id not in bot_runtime_ids:
                author_member = self.profile_service.resolve_automatic_member_id(room_id, raw_subject)
            related = []
            if author_member:
                related.append(author_member)
            for raw_mention in metadata.get("at_list") or item.get("at_list") or []:
                mention_id = str(raw_mention or "").strip()
                if not mention_id or mention_id in bot_runtime_ids:
                    continue
                member_id = self.profile_service.resolve_automatic_member_id(room_id, mention_id)
                if member_id and member_id not in related:
                    related.append(member_id)
            for member_id in related:
                if member_id not in member_order:
                    member_order.append(member_id)
            related_members.append((author_member, related))

        token_by_member = {
            member_id: "member_{:03d}".format(index)
            for index, member_id in enumerate(member_order, 1)
        }
        member_by_token = {token: member_id for member_id, token in token_by_member.items()}
        evidence_by_token: Dict[str, List[str]] = {token: [] for token in member_by_token}
        projected_messages = []
        for item, (author_member, related) in zip(messages, related_members):
            if not author_member:
                continue
            message_id = str(item.get("message_id") or "").strip()
            author_token = token_by_member.get(author_member, "")
            if not message_id or not author_token:
                continue
            for member_id in related:
                token = token_by_member.get(member_id, "")
                if token and message_id not in evidence_by_token[token]:
                    evidence_by_token[token].append(message_id)
            projected_messages.append({
                "message_id": message_id,
                "member_token": author_token,
                "mentioned_member_tokens": [
                    token_by_member[member_id]
                    for member_id in related
                    if member_id != author_member and member_id in token_by_member
                ],
                "sender_nickname": str(item.get("sender_nickname") or "").strip(),
                "message_type": str(item.get("message_type") or "text"),
                "text": str(item.get("text") or ""),
            })

        existing_profiles = []
        for member_id in member_order:
            profile = self.profile_service.get_profile(member_id, room_id=room_id)
            if not profile:
                continue
            existing_profiles.append({
                "member_token": token_by_member[member_id],
                "primary_nickname": profile.get("primary_nickname") or "",
                "aliases": list(profile.get("aliases") or []),
                "role_hints": list(profile.get("role_hints") or []),
                "speak_style": profile.get("speak_style") or "",
                "interests": list(profile.get("interests") or []),
                "common_words": list(profile.get("common_words") or []),
            })
        return projected_messages, existing_profiles, member_by_token, evidence_by_token

    def _record_failure(self, room_id: str, run_id: str, start_row_id: int, error: Exception) -> None:
        self.evolution_store.finish_run(
            run_id=run_id,
            status="failed",
            batch_end_row_id=start_row_id,
            batch_message_count=0,
            analyzed_member_count=0,
            profile_update_count=0,
            failed_reason=str(error),
        )
        self.evolution_store.update_status(
            room_id,
            running=False,
            last_failed_at=int(time.time()),
            last_failed_reason=str(error),
        )

    def _finish_run(self, run_id: str, status: str, row_id: int) -> None:
        self.evolution_store.finish_run(
            run_id=run_id,
            status=status,
            batch_end_row_id=row_id,
            batch_message_count=0,
            analyzed_member_count=0,
            profile_update_count=0,
        )

    @staticmethod
    def _result(status: str, run_id: str, message_count: int, counters: Dict[str, int]) -> Dict[str, Any]:
        return {
            "status": status,
            "run_id": run_id,
            "batch_message_count": message_count,
            "profile_update_count": int(counters.get("profile_update_count") or 0),
            "alias_update_count": int(counters.get("alias_update_count") or 0),
            "role_hint_update_count": int(counters.get("role_hint_update_count") or 0),
            "rejected_profile_count": int(counters.get("rejected_profile_count") or 0),
            "rejected_claim_count": int(counters.get("rejected_claim_count") or 0),
        }

    @staticmethod
    def _resolve_room_name(messages) -> str:
        for item in reversed(messages or []):
            room_name = str(item.get("room_name") or "").strip()
            if room_name:
                return room_name
        return ""
