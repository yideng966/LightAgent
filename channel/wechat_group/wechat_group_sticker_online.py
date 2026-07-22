"""Online meme search helpers for WeChat group stickers."""

from __future__ import annotations

import hashlib
import json
import random
import re
from typing import Callable, Dict, List, Optional
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from common.log import logger
from config import conf

SAFE_QUERY_BLOCK_RE = re.compile(
    r"(裸|色情|成人视频|黄色|三级片|露点|血腥|恐怖袭击|自杀|身份证|银行卡|密码|token|api\s*key)",
    re.IGNORECASE,
)
IMAGE_EXT_RE = re.compile(r"\.(?:png|jpe?g|gif|webp)(?:[?#].*)?$", re.IGNORECASE)
IMAGE_HINT_QUERY_RE = re.compile(
    r"[?&](?:(?:format|type|mime|image|img|pic|photo|thumb)=|[^=&#]*(?:image|img|pic|photo|thumb)[^=&#]*=)",
    re.IGNORECASE,
)
IMAGE_FILE_EXT_RE = re.compile(r"\.(?:png|jpe?g|gif|webp)$", re.IGNORECASE)
DEFAULT_ENDPOINT = "https://api.suol.cc/v1/meme.php"
ALLOWED_XIAOAPI_ENDPOINTS = ["https://api.suol.cc/v1/meme.php"]
DEFAULT_ALLOWED_DOMAINS = ["biaoqing.gtimg.com", "tugelepic.mse.sogou.com"]
DEFAULT_EXTENSIONLESS_IMAGE_HOSTS = ["biaoqing.gtimg.com", "tugelepic.mse.sogou.com"]


def get_online_sticker_config() -> Dict:
    return {
        "enabled": conf().get("wechat_group_sticker_online_search_enabled", True),
        "provider": str(conf().get("wechat_group_sticker_online_provider", "xiaoapi") or "xiaoapi"),
        "endpoint": str(conf().get("wechat_group_sticker_online_endpoint", DEFAULT_ENDPOINT) or DEFAULT_ENDPOINT),
        "allowed_domains": conf().get(
            "wechat_group_sticker_online_allowed_domains",
            DEFAULT_ALLOWED_DOMAINS,
        ) or DEFAULT_ALLOWED_DOMAINS,
        "allow_gif": conf().get("wechat_group_sticker_online_allow_gif", True),
        "search_count": conf().get("wechat_group_sticker_online_search_count", 10),
    }


def clean_meme_query(value: str = "") -> str:
    text = str(value or "")
    text = re.sub(r"^[@＠][^\s\u2005\u2006\u2007\u2008\u2009\u200a，,：:、]{1,40}", "", text)
    text = re.sub(
        r"(?:发|发送|来|整|给|给我|找|搜|搜索|搞|要|一个|一张|个|张|点|一下|吧|啊|呀|哈)",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?:表情包|表情|梗图|斗图|gif|GIF|动图|图片|图)",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", text).strip()[:40]


def is_safe_meme_query(query: str = "") -> bool:
    return not SAFE_QUERY_BLOCK_RE.search(str(query or ""))


def normalize_public_image_url(value: str = "", https_only: bool = False, max_length: int = 900) -> str:
    raw = str(value or "").strip().replace("&amp;", "&")
    raw = re.sub(r"[\r\n\t ]+", "", raw)
    if not raw or len(raw) > max_length or re.search(r"[\s<>\"'`]", raw):
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return ""
    if https_only and parsed.scheme != "https":
        return ""
    if _is_private_or_local_host(parsed.hostname or ""):
        return ""
    return urlunparse(parsed)


def is_allowed_meme_url(url: str = "", config: Optional[Dict] = None) -> bool:
    cfg = config or get_online_sticker_config()
    normalized = normalize_public_image_url(url, https_only=True)
    if not normalized:
        return False
    parsed = urlparse(normalized)
    host = _normalize_domain(parsed.hostname or "")
    domains = _normalize_domains(cfg.get("allowed_domains") or DEFAULT_ALLOWED_DOMAINS)
    if domains and not any(_host_matches_domain(host, domain) for domain in domains):
        return False
    if cfg.get("allow_gif") is False and re.search(r"\.gif(?:[?#].*)?$", normalized, re.IGNORECASE):
        return False
    return _is_likely_public_image_url(normalized, domains)


def score_meme_item(item: Dict, query: str = "") -> int:
    url = str(item.get("url") or item.get("img_url") or "")
    width = _to_int(item.get("width") or item.get("img_width"), 0)
    height = _to_int(item.get("height") or item.get("img_height"), 0)
    size = _to_int(item.get("size") or item.get("img_size"), 0)
    score = 0
    if re.search(r"\.gif(?:[?#].*)?$", url, re.IGNORECASE):
        score += 3
    if width >= 120 and height >= 120:
        score += 2
    if 0 < width <= 600 and 0 < height <= 600:
        score += 1
    if 0 < size <= 2 * 1024 * 1024:
        score += 1
    if re.search(r"biaoqing\.gtimg\.com", url, re.IGNORECASE):
        score += 2
    if re.search(r"tugelepic\.mse\.sogou\.com", url, re.IGNORECASE):
        score += 1
    if query and query in url:
        score += 1
    return score


def diversify_meme_items(items: List[Dict], query: str = "", seed: str = "") -> List[Dict]:
    if not items:
        return []
    scored = [dict(item, _score=score_meme_item(item, query)) for item in items]
    max_score = max(item.get("_score", 0) for item in scored)
    pool = [item for item in scored if item.get("_score", 0) >= max_score - 2]
    chosen = pool if len(pool) >= 3 else scored
    salt = seed or str(random.random())
    ranked = []
    for index, item in enumerate(chosen):
        rank = hashlib.sha1(f"{salt}:{item.get('url', '')}:{index}".encode("utf-8")).hexdigest()
        ranked.append((rank, item))
    ranked.sort(key=lambda row: row[0])
    return [_strip_internal_score(item) for _, item in ranked]


def search_online_memes(
    query: str = "",
    provider: str = "xiaoapi",
    count: Optional[int] = None,
    page: int = 1,
    seed: str = "",
    config: Optional[Dict] = None,
    opener: Optional[Callable] = None,
) -> Dict:
    cfg = config or get_online_sticker_config()
    if cfg.get("enabled") is False:
        return {"ok": False, "tool": "meme_search", "error": "meme search disabled"}
    provider = provider or str(cfg.get("provider") or "xiaoapi")
    if provider != "xiaoapi":
        return {"ok": False, "tool": "meme_search", "error": f"unsupported provider: {provider}"}
    clean = clean_meme_query(query) or "表情包"
    if not is_safe_meme_query(clean):
        return {
            "ok": False,
            "tool": "meme_search",
            "error": "query blocked by meme safety filter",
            "query": clean,
        }
    limit = min(max(_to_int(count if count is not None else cfg.get("search_count"), 10), 1), 40)
    endpoint = normalize_meme_endpoint(cfg.get("endpoint") or DEFAULT_ENDPOINT, provider=provider)
    if not endpoint:
        return {
            "ok": False,
            "tool": "meme_search",
            "provider": provider,
            "query": clean,
            "error": "meme endpoint is not allowed",
        }
    request_url = _build_xiaoapi_url(endpoint, clean, page, limit)
    request = Request(
        request_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "LightAgent/WechatGroupMemeSearch",
        },
    )
    opener = opener or urlopen
    try:
        with opener(request, timeout=12) as response:
            status = int(getattr(response, "status", 200) or 200)
            text = response.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(text)
        except Exception:
            return {
                "ok": False,
                "tool": "meme_search",
                "status": status,
                "error": "invalid meme api response",
                "preview": text[:300],
            }
        if status < 200 or status >= 300:
            return {
                "ok": False,
                "tool": "meme_search",
                "status": status,
                "error": "invalid meme api response",
                "preview": text[:300],
            }
        raw_items = payload.get("data") if isinstance(payload, dict) else []
        if not isinstance(raw_items, list):
            raw_items = []
        items = []
        for row in raw_items:
            if not isinstance(row, dict):
                continue
            image_url = normalize_public_image_url(row.get("img_url") or row.get("url") or "", https_only=True)
            item = {
                "url": image_url,
                "width": _to_int(row.get("img_width") or row.get("width"), 0),
                "height": _to_int(row.get("img_height") or row.get("height"), 0),
                "size": _to_int(row.get("img_size") or row.get("size"), 0),
                "type": "gif" if re.search(r"\.gif(?:[?#].*)?$", image_url, re.IGNORECASE) else "image",
                "source": "xiaoapi",
            }
            if image_url and is_allowed_meme_url(image_url, cfg):
                items.append(item)
        diversified = diversify_meme_items(items, clean, seed or f"{clean}:{random.random()}")[:limit]
        return {
            "ok": True,
            "tool": "meme_search",
            "provider": "xiaoapi",
            "query": clean,
            "endpoint": request_url,
            "randomized": True,
            "count": len(diversified),
            "items": diversified,
        }
    except Exception as e:
        logger.warning("[wechat_group] online meme search failed: {}".format(e))
        return {
            "ok": False,
            "tool": "meme_search",
            "provider": "xiaoapi",
            "query": clean,
            "error": str(e),
        }


def public_image_file_name_for_url(value: str = "", fallback_base_name: str = "online-sticker") -> str:
    normalized = normalize_public_image_url(value)
    parsed = urlparse(normalized) if normalized else None
    base_name = fallback_base_name
    if parsed:
        base_name = parsed.path.rstrip("/").split("/")[-1] or fallback_base_name
    base_name = re.sub(r"[\\/:*?\"<>|\s]+", "_", base_name).strip("._")[:120] or fallback_base_name
    if IMAGE_FILE_EXT_RE.search(base_name):
        return base_name
    ext = "jpg"
    if parsed:
        query = parsed.query.lower()
        if "gif" in query:
            ext = "gif"
        elif "webp" in query:
            ext = "webp"
        elif "png" in query:
            ext = "png"
    return f"{base_name}.{ext}"


def normalize_meme_endpoint(value: str = "", provider: str = "xiaoapi") -> str:
    if provider != "xiaoapi":
        return ""
    normalized = normalize_public_image_url(value or DEFAULT_ENDPOINT, https_only=True)
    if not normalized:
        return ""
    allowed = {
        normalize_public_image_url(endpoint, https_only=True).rstrip("/")
        for endpoint in ALLOWED_XIAOAPI_ENDPOINTS
    }
    return normalized if normalized.rstrip("/") in allowed else ""


def _build_xiaoapi_url(endpoint: str, query: str, page: int, limit: int) -> str:
    parsed = urlparse(endpoint)
    params = urlencode({
        "msg": query,
        "page": str(max(_to_int(page, 1), 1)),
        "num": str(limit),
    })
    separator = "&" if parsed.query else "?"
    return f"{endpoint}{separator}{params}"


def _is_likely_public_image_url(value: str, allowed_domains: List[str]) -> bool:
    if IMAGE_EXT_RE.search(value) or IMAGE_HINT_QUERY_RE.search(value):
        return True
    parsed = urlparse(value)
    host = _normalize_domain(parsed.hostname or "")
    trusted = _normalize_domains(DEFAULT_EXTENSIONLESS_IMAGE_HOSTS + list(allowed_domains or []))
    return any(_host_matches_domain(host, domain) for domain in trusted)


def _is_private_or_local_host(host: str) -> bool:
    value = _normalize_domain(host)
    if not value:
        return True
    if value == "localhost" or value.endswith(".localhost"):
        return True
    if value.startswith(("127.", "0.0.0.0", "10.", "192.168.", "169.254.")):
        return True
    if re.match(r"^172\.(?:1[6-9]|2\d|3[0-1])\.", value):
        return True
    if value in ("::1", "[::1]"):
        return True
    return False


def _host_matches_domain(host: str, domain: str) -> bool:
    return bool(host and domain and (host == domain or host.endswith(f".{domain}")))


def _normalize_domain(value: str) -> str:
    return str(value or "").strip().lower().strip(".")


def _normalize_domains(values) -> List[str]:
    if not isinstance(values, list):
        return []
    domains = []
    for value in values:
        domain = _normalize_domain(value)
        if domain and domain not in domains:
            domains.append(domain)
    return domains[:20]


def _strip_internal_score(item: Dict) -> Dict:
    result = dict(item)
    result.pop("_score", None)
    return result


def _to_int(value, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback
