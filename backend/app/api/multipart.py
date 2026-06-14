from __future__ import annotations

from email.parser import BytesParser
from email.policy import default

from fastapi import HTTPException, Request


MultipartFields = dict[str, str]
MultipartFiles = dict[str, dict[str, bytes | str]]


async def parse_multipart_request(request: Request) -> tuple[MultipartFields, MultipartFiles]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(status_code=415, detail="璇蜂娇鐢?multipart/form-data 涓婁紶 Excel 鍜?scenario銆?")

    body = await request.body()
    mime_body = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    message = BytesParser(policy=default).parsebytes(mime_body)
    if not message.is_multipart():
        raise HTTPException(status_code=400, detail="multipart 璇锋眰浣撴牸寮忎笉姝ｇ‘銆?")

    fields: MultipartFields = {}
    files: MultipartFiles = {}
    for part in message.iter_parts():
        params = dict(part.get_params(header="content-disposition", unquote=True) or [])
        name = params.get("name")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = params.get("filename")
        if filename:
            files[name] = {"filename": filename, "content": payload}
        else:
            charset = part.get_content_charset() or "utf-8"
            fields[name] = payload.decode(charset)
    return fields, files
