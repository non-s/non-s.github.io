#!/usr/bin/env python3
"""Smoke-test public production GitHub Pages URLs."""

from __future__ import annotations

import argparse
import html.parser
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Iterable

DEFAULT_URLS = (
    "https://non-s.github.io/",
    "https://non-s.github.io/.well-known/security.txt",
    "https://non-s.github.io/TakStud/",
    "https://non-s.github.io/MathQuest-/",
    "https://non-s.github.io/MathQuest-/teacher.html",
    "https://non-s.github.io/CHAMADA-/",
    "https://non-s.github.io/Non-s/",
    "https://non-s.github.io/Portfolio/",
    "https://non-s.github.io/Uplift/",
    "https://non-s.github.io/CLI-P2P/",
)


@dataclass(frozen=True)
class SmokeResponse:
    url: str
    status: int
    body: bytes
    content_type: str
    elapsed_ms: int


@dataclass(frozen=True)
class SmokeResult:
    url: str
    kind: str
    status: int
    elapsed_ms: int
    bytes_read: int
    content_type: str


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() not in {"a", "img", "link", "script", "source"}:
            return
        for name, value in attrs:
            if name.lower() in {"href", "src"} and value:
                self.links.append(value)


def fetch_url(url: str, timeout: float) -> SmokeResponse:
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": "Codex-production-smoke/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return SmokeResponse(
            url=url,
            status=int(response.status),
            body=body,
            content_type=response.headers.get("content-type", ""),
            elapsed_ms=elapsed_ms,
        )


def normalize_url(base_url: str, link: str) -> str | None:
    parsed = urllib.parse.urlparse(link)
    if parsed.scheme in {"mailto", "tel", "javascript", "data", "blob"}:
        return None
    absolute = urllib.parse.urljoin(base_url, link)
    parsed_absolute = urllib.parse.urlparse(absolute)
    if parsed_absolute.scheme not in {"http", "https"}:
        return None
    if parsed_absolute.netloc != "non-s.github.io":
        return None
    return urllib.parse.urlunparse(
        (
            parsed_absolute.scheme,
            parsed_absolute.netloc,
            parsed_absolute.path,
            "",
            "",
            "",
        )
    )


def discover_same_host_links(base_url: str, body: bytes) -> list[str]:
    parser = LinkParser()
    parser.feed(body.decode("utf-8", errors="ignore"))
    discovered: list[str] = []
    for link in parser.links:
        normalized = normalize_url(base_url, link.strip())
        if normalized:
            discovered.append(normalized)
    return discovered


def looks_like_pages_404(body: bytes) -> bool:
    text = body.decode("utf-8", errors="ignore")
    return "<title>404</title>" in text or "There isn't a GitHub Pages site here" in text


def run_smoke(
    seed_urls: Iterable[str] = DEFAULT_URLS,
    *,
    timeout: float = 20,
    max_assets: int = 80,
    fetcher: Callable[[str, float], SmokeResponse] = fetch_url,
) -> tuple[list[SmokeResult], list[str]]:
    seed_list = list(seed_urls)
    targets: dict[str, str] = {url: "page" for url in seed_list}
    results: list[SmokeResult] = []
    failures: list[str] = []
    fetched: set[str] = set()

    cursor = 0
    while cursor < len(targets):
        url = list(targets.keys())[cursor]
        kind = targets[url]
        cursor += 1
        if url in fetched:
            continue
        fetched.add(url)

        try:
            response = fetcher(url, timeout)
        except urllib.error.HTTPError as exc:
            failures.append(f"{url} returned HTTP {exc.code}")
            continue
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            failures.append(f"{url} failed: {exc}")
            continue

        results.append(
            SmokeResult(
                url=response.url,
                kind=kind,
                status=response.status,
                elapsed_ms=response.elapsed_ms,
                bytes_read=len(response.body),
                content_type=response.content_type,
            )
        )

        if response.status >= 400:
            failures.append(f"{url} returned HTTP {response.status}")
        if kind == "page":
            if len(response.body) < 200:
                failures.append(f"{url} returned a suspiciously small page")
            if looks_like_pages_404(response.body):
                failures.append(f"{url} looks like a GitHub Pages 404")
            for discovered in discover_same_host_links(url, response.body):
                if len(targets) >= len(seed_list) + max_assets:
                    break
                targets.setdefault(discovered, "asset")

    return results, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", action="append", dest="urls", help="Seed URL to check; can be repeated")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--max-assets", type=int, default=80)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    results, failures = run_smoke(args.urls or DEFAULT_URLS, timeout=args.timeout, max_assets=args.max_assets)
    payload = {
        "ok": not failures,
        "checked": len(results),
        "max_ms": max((item.elapsed_ms for item in results), default=0),
        "avg_ms": round(sum(item.elapsed_ms for item in results) / len(results)) if results else 0,
        "failures": failures,
        "results": [asdict(item) for item in results],
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif failures:
        print("PRODUCTION_SMOKE_FAILED")
        for failure in failures:
            print(f"- {failure}")
    else:
        summary = f"checked={payload['checked']} maxMs={payload['max_ms']} avgMs={payload['avg_ms']}"
        print(f"PRODUCTION_SMOKE_OK {summary}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
