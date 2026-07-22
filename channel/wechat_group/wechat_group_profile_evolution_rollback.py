"""Rollback service for unified WeChat group profile evolution runs."""

from __future__ import annotations

from typing import Any, Dict, Optional

from channel.wechat_group.wechat_group_profile_evolution_store import (
    WechatGroupProfileEvolutionStore,
)


class WechatGroupProfileEvolutionRollbackService:
    def __init__(
        self,
        evolution_store: Optional[WechatGroupProfileEvolutionStore] = None,
        profile_service=None,
    ):
        self.evolution_store = evolution_store or WechatGroupProfileEvolutionStore()

    def rollback_run(self, room_id: str, run_id: str) -> Dict[str, Any]:
        room_text = str(room_id or "").strip()
        run_text = str(run_id or "").strip()
        if not room_text:
            raise ValueError("stable_room_id is required")
        if not run_text:
            raise ValueError("run_id is required")
        return self.evolution_store.rollback_run(room_text, run_text)
