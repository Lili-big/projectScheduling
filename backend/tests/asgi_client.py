from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlsplit


def request(
    app: Any,
    method: str,
    path: str,
    payload: Any | None = None,
    *,
    raw_body: bytes | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    parsed = urlsplit(path)
    body = raw_body if raw_body is not None else (
        b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )
    headers = [(b"host", b"testserver")]
    if payload is not None and raw_body is None:
        headers.append((b"content-type", b"application/json"))
        headers.append((b"content-length", str(len(body)).encode("ascii")))
    for key, value in (extra_headers or {}).items():
        headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))
    if body and not any(key == b"content-length" for key, _ in headers):
        headers.append((b"content-length", str(len(body)).encode("ascii")))
    messages: list[dict[str, Any]] = []
    delivered = False

    async def receive() -> dict[str, Any]:
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": parsed.path,
        "raw_path": parsed.path.encode("utf-8"),
        "query_string": parsed.query.encode("utf-8"),
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    asyncio.run(app(scope, receive, send))
    start = next(message for message in messages if message["type"] == "http.response.start")
    response_headers = {key.decode("latin-1"): value.decode("latin-1") for key, value in start.get("headers", [])}
    response_body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return int(start["status"]), response_headers, response_body


def json_request(app: Any, method: str, path: str, payload: Any | None = None) -> tuple[int, Any]:
    status, _, body = request(app, method, path, payload)
    return status, json.loads(body.decode("utf-8"))
