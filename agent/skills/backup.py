"""Encrypted, one-time backups for Skill Hub configuration and user data."""

import io
import json
import os
import secrets
import shutil
import struct
import tempfile
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from agent.skills.lifecycle import SkillLifecycleError, _NAME_RE


MAGIC = b"LASKILL2\0"
MAX_BACKUP_BYTES = 100 * 1024 * 1024
MAX_BACKUP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_BACKUP_FILES = 5000
TOKEN_TTL_SECONDS = 10 * 60
_TOKENS = {}
_TOKENS_LOCK = threading.Lock()


def _derive_key(passphrase, salt):
    if not isinstance(passphrase, str) or len(passphrase) < 8:
        raise SkillLifecycleError("备份口令至少需要 8 个字符")
    return Scrypt(salt=salt, length=32, n=2 ** 14, r=8, p=1).derive(passphrase.encode("utf-8"))


def _zip_data(workspace, name):
    output = io.BytesIO()
    manifest = {
        "format_version": 1,
        "skill_name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contents": ["config", "data"],
    }
    file_count = 0
    uncompressed_bytes = 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
        for label, root_name in (("config", "skill-config"), ("data", "skill-data")):
            root = Path(workspace, root_name, name)
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_symlink():
                    raise SkillLifecycleError("技能备份不允许包含符号链接")
                if path.is_file():
                    file_count += 1
                    uncompressed_bytes += path.stat().st_size
                    if file_count > MAX_BACKUP_FILES:
                        raise SkillLifecycleError("技能备份文件数量超过限制")
                    if uncompressed_bytes > MAX_BACKUP_UNCOMPRESSED_BYTES:
                        raise SkillLifecycleError("技能备份未压缩数据超过 100 MiB 限制")
                    archive.write(path, str(Path(label) / path.relative_to(root)))
    payload = output.getvalue()
    if len(payload) > MAX_BACKUP_BYTES:
        raise SkillLifecycleError("技能备份超过 100 MiB 限制")
    return payload


def create_encrypted_backup(workspace, name, passphrase):
    if not _NAME_RE.fullmatch(str(name or "")):
        raise SkillLifecycleError("技能名称无效")
    lock_path = Path(workspace, "skills.lock.json")
    try:
        installed = json.loads(lock_path.read_text(encoding="utf-8")).get("skills", {})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        installed = {}
    if name not in installed:
        raise SkillLifecycleError(f"技能 {name} 尚未通过在线技能库安装")
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    header = json.dumps({
        "format": "laskill-backup",
        "version": 1,
        "skill_name": name,
        "kdf": "scrypt-n16384-r8-p1",
        "cipher": "aes-256-gcm",
        "salt": salt.hex(),
        "nonce": nonce.hex(),
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    prefix = MAGIC + struct.pack(">I", len(header)) + header
    ciphertext = AESGCM(_derive_key(passphrase, salt)).encrypt(nonce, _zip_data(workspace, name), prefix)
    return prefix + ciphertext


def restore_encrypted_backup(workspace, content, passphrase):
    if not isinstance(content, bytes) or len(content) > MAX_BACKUP_BYTES:
        raise SkillLifecycleError("备份文件无效或超过 100 MiB 限制")
    if not content.startswith(MAGIC) or len(content) < len(MAGIC) + 4:
        raise SkillLifecycleError("不是有效的 .laskill-backup 文件")
    header_length = struct.unpack(">I", content[len(MAGIC):len(MAGIC) + 4])[0]
    header_start = len(MAGIC) + 4
    header_end = header_start + header_length
    if header_length > 8192 or header_end >= len(content):
        raise SkillLifecycleError("备份文件头无效")
    try:
        header = json.loads(content[header_start:header_end].decode("utf-8"))
        if (
            header.get("format") != "laskill-backup"
            or header.get("version") != 1
            or header.get("kdf") != "scrypt-n16384-r8-p1"
            or header.get("cipher") != "aes-256-gcm"
        ):
            raise ValueError("unsupported backup header")
        name = str(header["skill_name"])
        salt = bytes.fromhex(header["salt"])
        nonce = bytes.fromhex(header["nonce"])
        if len(salt) != 16 or len(nonce) != 12:
            raise ValueError("invalid salt or nonce")
    except Exception as exc:
        raise SkillLifecycleError("备份文件头损坏") from exc
    if not _NAME_RE.fullmatch(name):
        raise SkillLifecycleError("备份中的技能名称无效")
    lock_path = Path(workspace, "skills.lock.json")
    try:
        installed = json.loads(lock_path.read_text(encoding="utf-8")).get("skills", {})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        installed = {}
    if name not in installed:
        raise SkillLifecycleError(f"请先重新安装技能 {name}，再恢复配置和数据")
    try:
        payload = AESGCM(_derive_key(passphrase, salt)).decrypt(
            nonce, content[header_end:], content[:header_end]
        )
    except Exception as exc:
        raise SkillLifecycleError("备份口令错误或文件已被篡改") from exc
    with tempfile.TemporaryDirectory(prefix=f".{name}-restore-", dir=workspace) as stage:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.infolist()
            if len(members) > MAX_BACKUP_FILES:
                raise SkillLifecycleError("备份文件数量超过限制")
            if sum(member.file_size for member in members) > MAX_BACKUP_UNCOMPRESSED_BYTES:
                raise SkillLifecycleError("备份解压数据超过 100 MiB 限制")
            root = Path(stage).resolve()
            for member in members:
                target = (root / member.filename).resolve()
                if root != target and root not in target.parents:
                    raise SkillLifecycleError("备份包含路径穿越")
                mode = member.external_attr >> 16
                if mode and (mode & 0o170000) == 0o120000:
                    raise SkillLifecycleError("备份不允许包含符号链接")
            archive.extractall(root)
        manifest = json.loads(Path(stage, "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("skill_name") != name:
            raise SkillLifecycleError("备份清单与文件头中的技能名称不一致")
        replacements = []
        for label, root_name in (("config", "skill-config"), ("data", "skill-data")):
            source = Path(stage, label)
            target = Path(workspace, root_name, name)
            replacement = Path(stage, f"ready-{label}")
            if source.is_dir():
                shutil.copytree(source, replacement)
            else:
                replacement.mkdir()
            target.parent.mkdir(parents=True, exist_ok=True)
            previous = Path(stage, f"previous-{label}")
            replacements.append((target, replacement, previous))
        committed = []
        try:
            for target, replacement, previous in replacements:
                had_previous = target.exists()
                if had_previous:
                    os.replace(target, previous)
                try:
                    os.replace(replacement, target)
                except Exception:
                    if had_previous and previous.exists():
                        os.replace(previous, target)
                    raise
                committed.append((target, previous, had_previous))
        except Exception:
            for target, previous, had_previous in reversed(committed):
                shutil.rmtree(target, ignore_errors=True)
                if had_previous and previous.exists():
                    os.replace(previous, target)
            raise
    return {"name": name, "restored": ["config", "data"]}


def create_download_token(workspace, name, passphrase):
    content = create_encrypted_backup(workspace, name, passphrase)
    token = secrets.token_urlsafe(32)
    directory = Path(workspace, ".skillhub", "backup-tmp")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{token}.laskill-backup"
    path.write_bytes(content)
    os.chmod(path, 0o600)
    expires_at = time.time() + TOKEN_TTL_SECONDS
    with _TOKENS_LOCK:
        _cleanup_tokens_locked()
        _TOKENS[token] = {"path": str(path), "name": name, "expires_at": expires_at}
    return {"token": token, "filename": f"{name}.laskill-backup", "expires_at": expires_at}


def consume_download_token(token):
    with _TOKENS_LOCK:
        _cleanup_tokens_locked()
        entry = _TOKENS.pop(str(token or ""), None)
    if not entry:
        raise SkillLifecycleError("备份下载令牌无效或已过期")
    path = Path(entry["path"])
    try:
        return entry["name"], path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


def _cleanup_tokens_locked():
    now = time.time()
    for token, entry in list(_TOKENS.items()):
        if entry["expires_at"] <= now:
            Path(entry["path"]).unlink(missing_ok=True)
            _TOKENS.pop(token, None)
