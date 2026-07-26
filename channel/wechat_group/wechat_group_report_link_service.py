"""Safe link extraction and enrichment for WeChat group reports."""

from __future__ import annotations

import html
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

from agent.tools.utils.url_safety import validate_url_strict
from common.log import logger


_URL_PATTERN = re.compile(
    r"(?<![\w@])https?://[^\s<>\"'`，。；：！？、】【（）]+",
    re.IGNORECASE,
)
_TRAILING_URL_PUNCTUATION = ".,;:!?)]}，。；：！？、】【）"
_MAX_RESPONSE_BYTES = 1024 * 1024
_MAX_REDIRECTS = 5
_FETCH_WORKERS = 4
_FETCH_TIMEOUT = (3, 8)


def extract_http_urls(text: Any) -> List[str]:
    """Extract URL candidates in message order without accepting other schemes."""
    found: List[str] = []
    for match in _URL_PATTERN.finditer(str(text or "")):
        value = match.group(0).rstrip(_TRAILING_URL_PUNCTUATION)
        if value:
            found.append(value)
    return found


def normalize_http_url(value: Any) -> str:
    """Return a deterministic HTTP(S) URL key or an empty string for invalid input."""
    text = str(value or "").strip()
    if not text or len(text) > 8192:
        return ""
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    if scheme not in {"http", "https"} or not host:
        return ""
    try:
        port = parsed.port
    except ValueError:
        return ""
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def link_domain(url: Any) -> str:
    try:
        return str(urlsplit(str(url or "")).hostname or "")
    except ValueError:
        return ""


class _TextExtractor(HTMLParser):
    """Small dependency-free extractor with a bounded text buffer."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: List[str] = []
        self._title_parts: List[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: D401
        self._in_title = tag.lower() == "title"

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if not data:
            return
        if self._in_title:
            self._title_parts.append(data)
        self._parts.append(data)

    @property
    def title(self) -> str:
        return _compact_text(" ".join(self._title_parts), 240)

    @property
    def text(self) -> str:
        return _compact_text(" ".join(self._parts), 6000)


def _compact_text(value: Any, limit: int) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


class WechatGroupReportLinkService:
    """Fetch report links under a mandatory strict SSRF policy."""

    def __init__(
        self,
        summary_provider: Optional[Callable[[str, str, str], str]] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.summary_provider = summary_provider
        self._session = session
        self._session_lock = threading.Lock()

    def enrich_links(self, links: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch every normalized URL while preserving source order.

        A failed item remains in the report with an explicit state. There is
        intentionally no result-count cap: a large group can produce a long
        report, but it must not silently drop valid links.
        """
        rows = [dict(item or {}) for item in links or []]
        if not rows:
            return []
        results: List[Optional[Dict[str, Any]]] = [None] * len(rows)
        with ThreadPoolExecutor(max_workers=_FETCH_WORKERS, thread_name_prefix="wg-report-link") as executor:
            futures = {
                executor.submit(self._enrich_one, row): index
                for index, row in enumerate(rows)
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    results[index] = future.result()
                except Exception as exc:  # Defensive isolation per link.
                    logger.warning("[wechat_group_report] link enrichment failed: %s", exc)
                    fallback = dict(rows[index])
                    fallback.update({"fetch_status": "failed", "summary": "链接抓取失败"})
                    results[index] = fallback
        return [item for item in results if item is not None]

    def _enrich_one(self, item: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(item)
        url = normalize_http_url(result.get("url"))
        if not url:
            result.update({"fetch_status": "blocked", "summary": "链接地址无效"})
            return result
        result["url"] = url
        result["domain"] = link_domain(url)
        try:
            status, final_url, title, body = self._fetch_public_page(url)
        except ValueError:
            result.update({"fetch_status": "blocked", "summary": "链接因安全策略被拒绝"})
            return result
        except requests.Timeout:
            result.update({"fetch_status": "timeout", "summary": "链接抓取超时"})
            return result
        except requests.RequestException:
            result.update({"fetch_status": "failed", "summary": "链接抓取失败"})
            return result
        except Exception as exc:
            logger.debug("[wechat_group_report] unexpected link fetch error: %s", exc)
            result.update({"fetch_status": "failed", "summary": "链接抓取失败"})
            return result

        result["url"] = final_url
        result["domain"] = link_domain(final_url)
        if status in {401, 403}:
            result.update({"fetch_status": "login_required", "summary": "链接需要登录后访问"})
            return result
        if status >= 400:
            result.update({"fetch_status": "failed", "summary": f"链接返回 HTTP {status}"})
            return result
        if not body:
            result.update({"fetch_status": "empty", "summary": "链接正文为空或不可解析"})
            return result
        summary = self._summarize(title, body, final_url)
        result.update({
            "fetch_status": "ok",
            "page_title": title,
            "summary": summary or title or "已安全抓取链接正文",
        })
        return result

    def _fetch_public_page(self, initial_url: str):
        current_url = initial_url
        for _ in range(_MAX_REDIRECTS + 1):
            validate_url_strict(current_url)
            response = self._get_session().get(
                current_url,
                allow_redirects=False,
                timeout=_FETCH_TIMEOUT,
                headers={
                    "User-Agent": "LightAgent-WechatGroupReport/1.0",
                    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8,*/*;q=0.1",
                },
                stream=True,
            )
            try:
                if response.is_redirect or response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        return response.status_code, current_url, "", ""
                    current_url = normalize_http_url(urljoin(current_url, location))
                    if not current_url:
                        raise ValueError("redirect URL is invalid")
                    continue
                content_type = str(response.headers.get("Content-Type") or "").lower()
                chunks = []
                total = 0
                for chunk in response.iter_content(chunk_size=16384):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > _MAX_RESPONSE_BYTES:
                        break
                    chunks.append(chunk)
                raw = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                text = raw.decode(encoding, errors="replace")
                if "html" in content_type or "xhtml" in content_type or not content_type:
                    parser = _TextExtractor()
                    parser.feed(text)
                    return response.status_code, current_url, parser.title, parser.text
                if content_type.startswith("text/"):
                    return response.status_code, current_url, "", _compact_text(text, 6000)
                return response.status_code, current_url, "", ""
            finally:
                response.close()
        raise ValueError("too many redirects")

    def _get_session(self) -> requests.Session:
        if self._session is not None:
            return self._session
        with self._session_lock:
            if self._session is None:
                self._session = requests.Session()
        return self._session

    def _summarize(self, title: str, body: str, url: str) -> str:
        if self.summary_provider is None:
            return title or _compact_text(body, 180)
        try:
            value = self.summary_provider(title, body, url)
            return _compact_text(value, 260)
        except Exception as exc:
            logger.debug("[wechat_group_report] link summary fallback: %s", exc)
            return title or _compact_text(body, 180)
