"""Compatibility adapter for profile evolution data in the unified profile store."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from channel.wechat_group.wechat_group_profile_store import WechatGroupProfileStore


class WechatGroupProfileEvolutionStore:
    """Keeps the existing evolution API while using the unified profile database."""

    def __init__(self, db_path: Optional[str] = None, profile_store: Optional[WechatGroupProfileStore] = None):
        self.profile_store = profile_store or WechatGroupProfileStore(db_path)
        self.db_path = self.profile_store.db_path

    def create_run(self, room_id: str, trigger_source: str, batch_start_row_id: int) -> str:
        return self.profile_store.create_run(
            room_id,
            trigger_source,
            batch_start_row_id,
            pipeline="evolution",
        )

    def finish_run(
        self,
        run_id: str,
        status: str,
        batch_end_row_id: int,
        batch_message_count: int,
        analyzed_member_count: int,
        profile_update_count: int,
        alias_update_count: int = 0,
        role_hint_update_count: int = 0,
        failed_reason: str = "",
    ) -> None:
        self.profile_store.finish_run(
            run_id,
            status=status,
            batch_end_row_id=batch_end_row_id,
            batch_message_count=batch_message_count,
            analyzed_member_count=analyzed_member_count,
            profile_update_count=profile_update_count,
            alias_update_count=alias_update_count,
            role_hint_update_count=role_hint_update_count,
            failed_reason=failed_reason,
        )

    def list_runs(self, room_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self.profile_store.list_runs(room_id, limit=limit, pipeline="evolution")

    def get_run(self, room_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        return self.profile_store.get_run(room_id, run_id)

    def record_diff(
        self,
        run_id: str,
        room_id: str,
        sender_id: str,
        before: Dict[str, Any],
        after: Dict[str, Any],
        evidence_message_ids: Optional[List[str]] = None,
    ) -> None:
        self.profile_store.record_revision(
            run_id,
            room_id,
            sender_id,
            before,
            after,
            evidence_message_ids=evidence_message_ids,
            reason="llm_evolution",
        )

    def list_diffs(
        self,
        room_id: str,
        sender_id: str = "",
        run_id: str = "",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self.profile_store.list_revisions(
            room_id,
            stable_member_id=sender_id,
            run_id=run_id,
            limit=limit,
        )

    def get_status(self, room_id: str) -> Dict[str, Any]:
        return self.profile_store.get_learning_state(room_id, pipeline="evolution")

    def update_status(self, room_id: str, **fields) -> Dict[str, Any]:
        return self.profile_store.update_learning_state(room_id, pipeline="evolution", **fields)

    def rollback_run(self, room_id: str, run_id: str) -> Dict[str, Any]:
        return self.profile_store.rollback_run(room_id, run_id)
