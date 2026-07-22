"""Stable identity resolution for WeChat group runtime ids."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
import re
import threading
import time
from typing import Any, Dict
from uuid import uuid4

from channel.wechat_group.wechat_group_identity_store import WechatGroupIdentityStore


_IDENTITY_RESOLUTION_LOCK = threading.RLock()


def _synchronized_resolution(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        with _IDENTITY_RESOLUTION_LOCK:
            return func(*args, **kwargs)

    return wrapped


@dataclass
class IdentityResolution:
    stable_id: str
    runtime_id: str
    status: str
    confidence: str
    requires_confirmation: bool
    display_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class WechatGroupIdentityService:
    def __init__(self, store: WechatGroupIdentityStore | None = None):
        self.store = store or WechatGroupIdentityStore()

    @_synchronized_resolution
    def resolve_account(
        self,
        runtime_self_id: str,
        self_name: str = "",
        sidecar_memory_path: str = "",
        metadata: Dict[str, Any] | None = None,
    ) -> IdentityResolution:
        runtime_id = str(runtime_self_id or "").strip()
        memory_path = str(sidecar_memory_path or "").strip()
        identity_metadata = dict(metadata or {})
        wechat_id = _strong_wechat_id(identity_metadata, runtime_id)
        strong_candidates = self.store.list_account_candidates_by_wechat_id(wechat_id) if wechat_id else []
        if len(strong_candidates) == 1:
            account = strong_candidates[0]
            stable_account_id = str(account.get("stable_account_id") or "")
            account = self.store.upsert_account(
                stable_account_id,
                display_name=self_name or account.get("display_name", ""),
                status="confirmed",
                confidence="wechat_id",
                sidecar_memory_path=memory_path or account.get("sidecar_memory_path", ""),
                metadata=_merged_metadata(account, identity_metadata, wechat_id),
                confirmed_at=int(time.time()),
            )
            self.store.activate_account_alias(
                stable_account_id,
                runtime_id,
                self_name=self_name,
                sidecar_memory_path=memory_path,
                reason="automatic wechat id recovery",
                metadata=_merged_metadata({}, identity_metadata, wechat_id),
            )
            return _resolution(
                stable_id=stable_account_id,
                runtime_id=runtime_id,
                row=account,
                display_name=account.get("display_name") or self_name,
                requires_confirmation=False,
            )

        alias = self.store.find_account_alias(runtime_id, memory_path)
        if alias:
            account = self.store.get_account(alias["stable_account_id"])
            account = self.store.upsert_account(
                alias["stable_account_id"],
                display_name=self_name or account.get("display_name", ""),
                status="confirmed",
                confidence="runtime",
                sidecar_memory_path=memory_path or account.get("sidecar_memory_path", ""),
                metadata=_merged_metadata(account, identity_metadata, wechat_id),
                confirmed_at=int(time.time()),
            )
            self.store.activate_account_alias(
                alias["stable_account_id"],
                runtime_id,
                self_name=self_name,
                sidecar_memory_path=memory_path,
                reason="automatic runtime alias recovery",
                metadata=_merged_metadata(alias, identity_metadata, wechat_id),
            )
            return _resolution(
                stable_id=alias["stable_account_id"],
                runtime_id=runtime_id,
                row=account,
                display_name=account.get("display_name") or alias.get("self_name") or self_name,
                requires_confirmation=False,
            )

        profile_candidates = self.store.list_account_candidates_by_profile(memory_path, self_name)
        if len(profile_candidates) == 1:
            account = profile_candidates[0]
            stable_account_id = str(account.get("stable_account_id") or "")
            account = self.store.upsert_account(
                stable_account_id,
                display_name=self_name or account.get("display_name", ""),
                status="confirmed",
                confidence="profile",
                sidecar_memory_path=memory_path,
                metadata=_merged_metadata(account, identity_metadata, wechat_id),
                confirmed_at=int(time.time()),
            )
            self.store.activate_account_alias(
                stable_account_id,
                runtime_id,
                self_name=self_name,
                sidecar_memory_path=memory_path,
                reason="automatic sidecar profile recovery",
                metadata=_merged_metadata({}, identity_metadata, wechat_id),
            )
            return _resolution(
                stable_id=stable_account_id,
                runtime_id=runtime_id,
                row=account,
                display_name=account.get("display_name") or self_name,
                requires_confirmation=False,
            )

        stable_account_id = _new_id("wga")
        account = self.store.upsert_account(
            stable_account_id,
            display_name=self_name,
            status="confirmed",
            confidence="auto_new",
            sidecar_memory_path=memory_path,
            metadata=_merged_metadata({}, identity_metadata, wechat_id),
            confirmed_at=int(time.time()),
        )
        self.store.activate_account_alias(
            stable_account_id,
            runtime_id,
            self_name=self_name,
            sidecar_memory_path=memory_path,
            reason="automatic new account",
            metadata=_merged_metadata({}, identity_metadata, wechat_id),
        )
        return _resolution(
            stable_id=stable_account_id,
            runtime_id=runtime_id,
            row=account,
            display_name=self_name,
            requires_confirmation=False,
        )

    @_synchronized_resolution
    def resolve_room(
        self,
        stable_account_id: str,
        runtime_room_id: str,
        room_name: str = "",
        self_runtime_id: str = "",
        metadata: Dict[str, Any] | None = None,
        allow_name_recovery: bool = True,
    ) -> IdentityResolution:
        account_id = str(stable_account_id or "").strip()
        runtime_id = str(runtime_room_id or "").strip()
        canonical_name = str(room_name or "").strip()
        identity_metadata = dict(metadata or {})
        account = self.store.get_account(account_id)
        if not account or account.get("status") != "confirmed":
            raise ValueError("stable account is not confirmed")
        alias = self.store.find_room_alias(account_id, runtime_id)
        trusted_alias = False
        if alias:
            trusted_alias = int(alias.get("is_active") or 0) == 1
            if not trusted_alias:
                trusted_alias = any(
                    str(item.get("runtime_room_id") or "") == runtime_id
                    for item in self.store.list_confirmed_room_aliases(
                        account_id,
                        alias.get("stable_room_id", ""),
                    )
                )
        if alias and trusted_alias:
            room = self.store.get_room(alias["stable_room_id"])
            room = self.store.upsert_room(
                alias["stable_room_id"],
                account_id,
                canonical_name=canonical_name or room.get("canonical_name", ""),
                status="confirmed",
                confidence="runtime",
                metadata=_merged_metadata(room, identity_metadata),
                confirmed_at=int(time.time()),
            )
            self.store.activate_room_alias(
                account_id,
                alias["stable_room_id"],
                runtime_id,
                room_name=canonical_name,
                self_runtime_id=self_runtime_id,
                source_kind="runtime",
                reason="automatic runtime alias recovery",
                metadata=identity_metadata,
            )
            return _resolution(
                stable_id=alias["stable_room_id"],
                runtime_id=runtime_id,
                row=room,
                display_name=room.get("canonical_name") or alias.get("room_name") or room_name,
                requires_confirmation=False,
            )

        current_name_is_ambiguous = bool(canonical_name and not allow_name_recovery)
        candidates = (
            self.store.list_room_candidates_by_name(account_id, canonical_name)
            if canonical_name and allow_name_recovery
            else []
        )
        if len(candidates) == 1:
            candidate = candidates[0]
            room = self.store.upsert_room(
                candidate["stable_room_id"],
                account_id,
                canonical_name=canonical_name,
                status="confirmed",
                confidence="room_name",
                metadata=_merged_metadata(candidate, identity_metadata),
                confirmed_at=int(time.time()),
            )
            self.store.activate_room_alias(
                account_id,
                candidate["stable_room_id"],
                runtime_id,
                room_name=room_name,
                self_runtime_id=self_runtime_id,
                source_kind="auto_room_name",
                reason="automatic trusted room name recovery",
                metadata={"recovery_reason": "same_account_room_name", **identity_metadata},
            )
            return _resolution(
                stable_id=candidate["stable_room_id"],
                runtime_id=runtime_id,
                row=room,
                display_name=candidate.get("canonical_name") or room_name,
                requires_confirmation=False,
            )

        stable_room_id = _new_id("wgr")
        room = self.store.upsert_room(
            stable_room_id,
            account_id,
            canonical_name=canonical_name,
            status="confirmed",
            confidence="auto_isolated" if candidates or current_name_is_ambiguous else "auto_new",
            metadata={
                **identity_metadata,
                **(
                    {"isolation_reason": "ambiguous_room_name"}
                    if candidates or current_name_is_ambiguous
                    else {}
                ),
            },
            confirmed_at=int(time.time()),
        )
        self.store.activate_room_alias(
            account_id,
            stable_room_id,
            runtime_id,
            room_name=room_name,
            self_runtime_id=self_runtime_id,
            source_kind="runtime",
            reason="automatic new room",
            metadata=identity_metadata,
        )
        return _resolution(
            stable_id=stable_room_id,
            runtime_id=runtime_id,
            row=room,
            display_name=room_name,
            requires_confirmation=False,
        )

    @_synchronized_resolution
    def resolve_member(
        self,
        stable_room_id: str,
        runtime_sender_id: str,
        display_name: str = "",
        room_alias: str = "",
        metadata: Dict[str, Any] | None = None,
    ) -> IdentityResolution:
        room = self.store.get_room(stable_room_id)
        if not room or room.get("status") != "confirmed":
            raise ValueError("stable room is not confirmed")
        account_id = str(room.get("stable_account_id") or "")
        account = self.store.get_account(account_id)
        if not account or account.get("status") != "confirmed":
            raise ValueError("stable account is not confirmed")
        runtime_id = str(runtime_sender_id or "").strip()
        identity_metadata = dict(metadata or {})
        wechat_id = _strong_wechat_id(identity_metadata, runtime_id)
        alias = self.store.find_member_alias(account_id, stable_room_id, runtime_id)

        strong_candidates = self.store.list_member_candidates_by_wechat_id(
            account_id,
            stable_room_id,
            wechat_id,
        ) if wechat_id else []
        ambiguous_wechat_id = bool(wechat_id and len(strong_candidates) > 1)
        if len(strong_candidates) == 1:
            member = strong_candidates[0]
            stable_member_id = str(member.get("stable_member_id") or "")
            member = self.store.upsert_member(
                stable_member_id,
                stable_room_id,
                account_id,
                display_name=display_name or room_alias or member.get("display_name", ""),
                status="confirmed",
                confidence="wechat_id",
                metadata=_merged_metadata(member, identity_metadata, wechat_id),
                confirmed_at=int(time.time()),
            )
            self.store.activate_member_alias(
                account_id,
                stable_room_id,
                stable_member_id,
                runtime_id,
                display_name=display_name,
                room_alias=room_alias,
                source_kind="auto_wechat_id",
                reason="automatic wechat id recovery",
                metadata=_merged_metadata({}, identity_metadata, wechat_id),
            )
            return _resolution(
                stable_id=stable_member_id,
                runtime_id=runtime_id,
                row=member,
                display_name=member.get("display_name") or display_name or room_alias,
                requires_confirmation=False,
            )

        active_alias_member = {}
        if alias and int(alias.get("is_active") or 0) == 1:
            active_alias_member = self.store.get_member(alias["stable_member_id"])
        active_alias_metadata = _metadata(active_alias_member)
        active_alias_wechat_id = _strong_wechat_id(active_alias_metadata, runtime_id)
        reuse_ambiguous_isolation = bool(
            ambiguous_wechat_id
            and active_alias_member.get("status") == "confirmed"
            and active_alias_metadata.get("isolation_reason") == "ambiguous_wechat_id"
            and active_alias_wechat_id.casefold() == wechat_id.casefold()
        )
        if active_alias_member and (not ambiguous_wechat_id or reuse_ambiguous_isolation):
            member = active_alias_member
            confidence = "auto_isolated" if reuse_ambiguous_isolation else ("wechat_id" if wechat_id else "runtime")
            member = self.store.upsert_member(
                alias["stable_member_id"],
                stable_room_id,
                account_id,
                display_name=display_name or room_alias or member.get("display_name", ""),
                status="confirmed",
                confidence=confidence,
                metadata=_merged_metadata(member, identity_metadata, wechat_id),
                confirmed_at=int(time.time()),
            )
            self.store.activate_member_alias(
                account_id,
                stable_room_id,
                alias["stable_member_id"],
                runtime_id,
                display_name=display_name,
                room_alias=room_alias,
                source_kind="auto_isolated" if reuse_ambiguous_isolation else "runtime",
                reason=(
                    "automatic ambiguous isolation recovery"
                    if reuse_ambiguous_isolation
                    else "automatic runtime alias recovery"
                ),
                metadata=_merged_metadata(alias, identity_metadata, wechat_id),
            )
            return _resolution(
                stable_id=alias["stable_member_id"],
                runtime_id=runtime_id,
                row=member,
                display_name=member.get("display_name") or alias.get("display_name") or display_name,
                requires_confirmation=False,
            )

        stable_member_id = _new_id("wgm")
        isolation_reason = "ambiguous_wechat_id" if ambiguous_wechat_id else "missing_wechat_id"
        member = self.store.upsert_member(
            stable_member_id,
            stable_room_id,
            account_id,
            display_name=display_name or room_alias,
            status="confirmed",
            confidence="auto_isolated" if ambiguous_wechat_id or not wechat_id else "wechat_id",
            metadata={
                **identity_metadata,
                **({"isolation_reason": isolation_reason} if not wechat_id or strong_candidates else {}),
            },
            confirmed_at=int(time.time()),
        )
        self.store.activate_member_alias(
            account_id,
            stable_room_id,
            stable_member_id,
            runtime_id,
            display_name=display_name,
            room_alias=room_alias,
            source_kind="auto_isolated" if ambiguous_wechat_id or not wechat_id else "auto_new",
            reason="automatic new member",
            metadata=_merged_metadata({}, identity_metadata, wechat_id),
        )
        return _resolution(
            stable_id=stable_member_id,
            runtime_id=runtime_id,
            row=member,
            display_name=display_name or room_alias,
            requires_confirmation=False,
        )

    def confirm_account_binding(
        self,
        stable_account_id: str,
        runtime_self_id: str,
        actor: str = "",
        reason: str = "",
    ) -> IdentityResolution:
        account = self.store.get_account(stable_account_id)
        if not account:
            raise ValueError("stable account does not exist")
        account = self.store.upsert_account(
            stable_account_id,
            display_name=account.get("display_name", ""),
            status="confirmed",
            confidence="manual",
            sidecar_memory_path=account.get("sidecar_memory_path", ""),
            metadata=_metadata(account),
            confirmed_at=int(time.time()),
        )
        self.store.activate_account_alias(
            stable_account_id,
            runtime_self_id,
            sidecar_memory_path=account.get("sidecar_memory_path", ""),
            actor=actor,
            reason=reason,
        )
        return _resolution(
            stable_id=stable_account_id,
            runtime_id=runtime_self_id,
            row=account,
            display_name=account.get("display_name", ""),
            requires_confirmation=False,
        )

    def confirm_room_binding(
        self,
        stable_room_id: str,
        runtime_room_id: str,
        actor: str = "",
        reason: str = "",
    ) -> IdentityResolution:
        room = self.store.get_room(stable_room_id)
        if not room:
            raise ValueError("stable room does not exist")
        account_id = str(room.get("stable_account_id") or "")
        account = self.store.get_account(account_id)
        if not account or account.get("status") != "confirmed":
            raise ValueError("stable account is not confirmed")
        room = self.store.upsert_room(
            stable_room_id,
            account_id,
            canonical_name=room.get("canonical_name", ""),
            status="confirmed",
            confidence="manual",
            metadata=_metadata(room),
            confirmed_at=int(time.time()),
        )
        self.store.activate_room_alias(
            account_id,
            stable_room_id,
            runtime_room_id,
            room_name=room.get("canonical_name", ""),
            source_kind="manual",
            actor=actor,
            reason=reason,
        )
        return _resolution(
            stable_id=stable_room_id,
            runtime_id=runtime_room_id,
            row=room,
            display_name=room.get("canonical_name", ""),
            requires_confirmation=False,
        )

    def confirm_member_binding(
        self,
        stable_room_id: str,
        stable_member_id: str,
        runtime_sender_id: str,
        actor: str = "",
        reason: str = "",
    ) -> IdentityResolution:
        room = self.store.get_room(stable_room_id)
        if not room:
            raise ValueError("stable room does not exist")
        if room.get("status") != "confirmed":
            raise ValueError("stable room is not confirmed")
        account_id = str(room.get("stable_account_id") or "")
        member = self.store.get_member(stable_member_id)
        if not member:
            raise ValueError("stable member does not exist")
        if (
            str(member.get("stable_room_id") or "") != str(stable_room_id or "")
            or str(member.get("stable_account_id") or "") != account_id
        ):
            raise ValueError("stable member does not belong to stable room")
        member = self.store.upsert_member(
            stable_member_id,
            stable_room_id,
            account_id,
            display_name=member.get("display_name", ""),
            status="confirmed",
            confidence="manual",
            metadata=_metadata(member),
            confirmed_at=int(time.time()),
        )
        self.store.activate_member_alias(
            account_id,
            stable_room_id,
            stable_member_id,
            runtime_sender_id,
            source_kind="manual",
            actor=actor,
            reason=reason,
        )
        return _resolution(
            stable_id=stable_member_id,
            runtime_id=runtime_sender_id,
            row=member,
            display_name=member.get("display_name", ""),
            requires_confirmation=False,
        )

    def get_active_runtime_room_id(self, stable_room_id: str) -> str:
        room = self.store.get_room(stable_room_id)
        if not room:
            return ""
        return self.store.get_active_runtime_room_id(room.get("stable_account_id", ""), stable_room_id)

    def get_active_runtime_sender_id(self, stable_room_id: str, stable_member_id: str) -> str:
        room = self.store.get_room(stable_room_id)
        if not room:
            return ""
        return self.store.get_active_runtime_sender_id(room.get("stable_account_id", ""), stable_room_id, stable_member_id)

    def resolve_runtime_member_in_stable_room(self, stable_room_id: str, runtime_sender_id: str) -> str:
        room_id = str(stable_room_id or "").strip()
        runtime_id = str(runtime_sender_id or "").strip()
        if not room_id or not runtime_id:
            return ""
        room = self.store.get_room(room_id)
        if not room or room.get("status") != "confirmed":
            return ""
        alias = self.store.find_member_alias(
            room.get("stable_account_id", ""),
            room_id,
            runtime_id,
        )
        if not alias or int(alias.get("is_active") or 0) != 1:
            return ""
        member_id = str(alias.get("stable_member_id") or "")
        member = self.store.get_member(member_id)
        if not member or str(member.get("stable_room_id") or "") != room_id:
            return ""
        return self.resolve_canonical_member_id(room_id, member_id)

    def resolve_canonical_member_id(self, stable_room_id: str, stable_member_id: str) -> str:
        room_id = str(stable_room_id or "").strip()
        current = str(stable_member_id or "").strip()
        if not room_id or not current:
            return ""
        seen = set()
        for _ in range(20):
            if current in seen:
                raise ValueError("member redirect cycle detected")
            seen.add(current)
            member = self.store.get_member(current)
            if not member or str(member.get("stable_room_id") or "") != room_id:
                return ""
            redirect = self.store.get_member_redirect(room_id, current)
            target = str(redirect.get("canonical_stable_member_id") or "").strip()
            if not target:
                return current
            current = target
        raise ValueError("member redirect chain is too deep")

    def confirm_member_redirect(
        self,
        stable_room_id: str,
        old_stable_member_id: str,
        canonical_stable_member_id: str,
        actor: str = "",
        reason: str = "",
    ) -> str:
        canonical = self.resolve_canonical_member_id(stable_room_id, canonical_stable_member_id)
        if not canonical:
            raise ValueError("canonical stable member does not belong to stable room")
        if self.resolve_canonical_member_id(stable_room_id, old_stable_member_id) == canonical:
            return canonical
        self.store.upsert_member_redirect(
            stable_room_id,
            old_stable_member_id,
            canonical,
            actor=actor,
            reason=reason,
        )
        return canonical

    def list_confirmed_room_scope_ids(self, stable_room_id: str) -> list[str]:
        room_id = str(stable_room_id or "").strip()
        room = self.store.get_room(room_id)
        if not room or room.get("status") != "confirmed":
            return [room_id] if room_id else []
        account = self.store.get_account(room.get("stable_account_id", ""))
        if not account or account.get("status") != "confirmed":
            return [room_id]
        aliases = self.store.list_confirmed_room_aliases(
            room.get("stable_account_id", ""),
            room_id,
        )
        result = [room_id]
        for alias in aliases:
            runtime_room_id = str(alias.get("runtime_room_id") or "").strip()
            if runtime_room_id and runtime_room_id not in result:
                result.append(runtime_room_id)
        return result

    def confirm_historical_room_binding(
        self,
        stable_room_id: str,
        runtime_room_id: str,
        room_name: str = "",
        actor: str = "",
        reason: str = "",
    ) -> IdentityResolution:
        room = self.store.get_room(stable_room_id)
        if not room:
            raise ValueError("stable room does not exist")
        if room.get("status") != "confirmed":
            raise ValueError("stable room is not confirmed")
        account_id = str(room.get("stable_account_id") or "")
        account = self.store.get_account(account_id)
        if not account or account.get("status") != "confirmed":
            raise ValueError("stable account is not confirmed")
        alias = self.store.confirm_historical_room_alias(
            account_id,
            stable_room_id,
            runtime_room_id,
            room_name=room_name or room.get("canonical_name", ""),
            actor=actor,
            reason=reason,
        )
        return IdentityResolution(
            stable_id=str(stable_room_id or ""),
            runtime_id=str(runtime_room_id or ""),
            status="confirmed",
            confidence="manual",
            requires_confirmation=False,
            display_name=str(room.get("canonical_name") or alias.get("room_name") or room_name or ""),
            metadata={"historical_alias": True, **_metadata(alias)},
        )

    def resolve_legacy_room_id(self, runtime_room_id: str) -> str:
        aliases = self.store.list_room_aliases_by_runtime(str(runtime_room_id or "").strip())
        stable_room_ids = {str(item.get("stable_room_id") or "") for item in aliases if item.get("stable_room_id")}
        return next(iter(stable_room_ids)) if len(stable_room_ids) == 1 else ""

    def resolve_legacy_member_id(self, runtime_room_id: str, runtime_sender_id: str) -> str:
        runtime_room = str(runtime_room_id or "").strip()
        runtime_sender = str(runtime_sender_id or "").strip()
        room_aliases = self.store.list_room_aliases_by_runtime(runtime_room)
        stable_rooms = {
            (str(item.get("stable_account_id") or ""), str(item.get("stable_room_id") or ""))
            for item in room_aliases
            if item.get("stable_room_id")
        }
        if len(stable_rooms) == 1:
            stable_account_id, stable_room_id = next(iter(stable_rooms))
            alias = self.store.find_member_alias(
                stable_account_id,
                stable_room_id,
                runtime_sender,
            )
            return str(alias.get("stable_member_id") or "") if alias else ""
        if stable_rooms:
            return ""
        aliases = self.store.list_member_aliases_by_runtime(runtime_room, runtime_sender)
        stable_member_ids = {str(item.get("stable_member_id") or "") for item in aliases if item.get("stable_member_id")}
        return next(iter(stable_member_ids)) if len(stable_member_ids) == 1 else ""

    def list_binding_candidates(self, entity_type: str, filters: Dict[str, Any] | None = None) -> list:
        kind = str(entity_type or "").strip().lower()
        filters = filters or {}
        stable_room_id = str(filters.get("stable_room_id") or "").strip()
        if kind in ("", "room", "rooms"):
            return [self._room_candidate(row) for row in self.store.list_room_binding_candidates(stable_room_id)]
        if kind in ("member", "members"):
            return [self._member_candidate(row) for row in self.store.list_member_binding_candidates(stable_room_id)]
        if kind == "all":
            return (
                [self._room_candidate(row) for row in self.store.list_room_binding_candidates(stable_room_id)]
                + [self._member_candidate(row) for row in self.store.list_member_binding_candidates(stable_room_id)]
            )
        return []

    @staticmethod
    def _room_candidate(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "entity_type": "room",
            "stable_account_id": str(row.get("stable_account_id") or ""),
            "stable_room_id": str(row.get("stable_room_id") or ""),
            "runtime_room_id": str(row.get("runtime_room_id") or ""),
            "room_name": str(row.get("room_name") or row.get("canonical_name") or ""),
            "binding_status": "suspected" if int(row.get("is_active") or 0) == 0 else str(row.get("status") or ""),
            "confidence": str(row.get("confidence") or "candidate"),
            "source_kind": str(row.get("source_kind") or ""),
            "requires_confirmation": True,
        }

    @staticmethod
    def _member_candidate(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "entity_type": "member",
            "stable_account_id": str(row.get("stable_account_id") or ""),
            "stable_room_id": str(row.get("stable_room_id") or ""),
            "stable_member_id": str(row.get("stable_member_id") or ""),
            "runtime_sender_id": str(row.get("runtime_sender_id") or ""),
            "runtime_room_id": str(row.get("runtime_room_id") or ""),
            "display_name": str(row.get("display_name") or row.get("room_alias") or ""),
            "binding_status": "suspected" if int(row.get("is_active") or 0) == 0 else str(row.get("status") or ""),
            "confidence": str(row.get("confidence") or "candidate"),
            "source_kind": str(row.get("source_kind") or ""),
            "requires_confirmation": True,
        }


def _resolution(
    stable_id: str,
    runtime_id: str,
    row: Dict[str, Any],
    display_name: str = "",
    requires_confirmation: bool = False,
) -> IdentityResolution:
    return IdentityResolution(
        stable_id=stable_id,
        runtime_id=runtime_id,
        status=str(row.get("status") or "legacy_imported"),
        confidence=str(row.get("confidence") or "candidate"),
        requires_confirmation=requires_confirmation,
        display_name=str(display_name or ""),
        metadata=_metadata(row),
    )


def _metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    value = row.get("metadata") if row else {}
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        import json

        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _merged_metadata(
    row: Dict[str, Any] | None,
    incoming: Dict[str, Any] | None,
    wechat_id: str = "",
) -> Dict[str, Any]:
    merged = dict(_metadata(row or {}))
    merged.update(dict(incoming or {}))
    if wechat_id:
        merged["wechat_id"] = wechat_id
    return merged


def _strong_wechat_id(metadata: Dict[str, Any] | None, runtime_id: str = "") -> str:
    payload = metadata or {}
    runtime_key = str(runtime_id or "").strip().casefold()
    for key in ("wechat_id", "weixin", "wxid"):
        value = str(payload.get(key) or "").strip()
        normalized = value.casefold()
        if not value or normalized == runtime_key:
            continue
        if value.startswith("@") or re.fullmatch(r"[0-9a-f]{24,}", value, flags=re.IGNORECASE):
            continue
        return value
    return ""


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
