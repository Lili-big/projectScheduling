from __future__ import annotations

from collections.abc import Iterable

from ..models import ValidationMessage


def diagnostic(
    *,
    level: str,
    code: str,
    message: str,
    entity_refs: Iterable[str] = (),
    suggestion: str | None = None,
) -> ValidationMessage:
    refs = list(dict.fromkeys(ref for ref in entity_refs if ref))
    return ValidationMessage(
        level=level,
        code=code,
        message=message,
        subject_id=refs[0] if refs else None,
        entity_refs=refs,
        suggestion=suggestion,
    )


def blocked(code: str, message: str, *entity_refs: str, suggestion: str | None = None) -> ValidationMessage:
    return diagnostic(level="error", code=code, message=message, entity_refs=entity_refs, suggestion=suggestion)


def warning(code: str, message: str, *entity_refs: str, suggestion: str | None = None) -> ValidationMessage:
    return diagnostic(level="warning", code=code, message=message, entity_refs=entity_refs, suggestion=suggestion)


def info(code: str, message: str, *entity_refs: str) -> ValidationMessage:
    return diagnostic(level="info", code=code, message=message, entity_refs=entity_refs)
