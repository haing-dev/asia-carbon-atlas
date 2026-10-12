"""Inspect source files/pages from CI and write human-readable summaries (used while building adapters).

Usage: python -m pipeline.discover URL [URL ...]   -> work/discover/<n>-<name>.txt
Spreadsheets: sheet names + first rows of each sheet. HTML/JSON: first 300 KB + links/scripts found.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

from pipeline.http import PoliteClient

OUT = Path("work/discover")


def summarize_xlsx(data: bytes, rows: int = 12) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(f"=== SHEET {ws.title!r} max_row={ws.max_row} max_col={ws.max_column}")
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= rows:
                break
            cells = ["" if v is None else str(v)[:60] for v in row]
            while cells and cells[-1] == "":
                cells.pop()
            parts.append(f"r{i}: " + " | ".join(cells))
    return "\n".join(parts)


def summarize_html(text: str) -> str:
    links = sorted(set(re.findall(r'(?:href|src)=["\']([^"\']+)["\']', text)))
    apis = sorted(set(re.findall(r'["\'](https?://[^"\']*(?:api|graphql|json)[^"\']*)["\']', text)))
    return ("LINKS:\n" + "\n".join(links[:400]) + "\n\nAPI-LIKE URLS:\n" + "\n".join(apis[:100])
            + "\n\nBODY (first 300 KB):\n" + text[:300_000])


def main(urls: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(timeout=180)
    for n, url in enumerate(urls):
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[-1])[:80]
        path = OUT / f"{n:02d}-{name}.txt"
        try:
            if "#post=" in url:  # e.g. https://host/api#post={"a":1} (URL-encoded JSON body)
                from urllib.parse import unquote
                target, body = url.split("#post=", 1)
                if not client._allowed(target):
                    raise PermissionError("robots.txt disallows " + target)
                client._wait(target)
                r = client.client.post(target, content=unquote(body), headers={"Content-Type": "application/json", "Accept": "application/json"})
            else:
                r = client.get(url)
            head = (f"URL: {url}\nFINAL: {r.url}\nSTATUS: {r.status_code}\n"
                    f"HEADERS: {dict(r.headers)}\nBYTES: {len(r.content)}\n\n")
            ctype = r.headers.get("content-type", "")
            if "json" in ctype:
                body = r.text[:400_000]
            elif url.endswith((".xlsx", ".xlsm")) or "spreadsheet" in ctype:
                body = summarize_xlsx(r.content)
            else:
                body = summarize_html(r.text)
            path.write_text(head + body, encoding="utf-8")
            print(f"ok {url} -> {path} ({len(r.content)} bytes)")
        except Exception as e:  # noqa: BLE001
            path.write_text(f"URL: {url}\nERROR: {type(e).__name__}: {e}\n", encoding="utf-8")
            print(f"FAILED {url}: {e}")


if __name__ == "__main__":
    main(sys.argv[1:])
