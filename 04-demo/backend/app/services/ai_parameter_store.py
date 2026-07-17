from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from ..contracts import (
    AiParameterCandidateAddition,
    AiParameterConflictGroup,
    AiParameterSuggestion,
    AiParameterSuggestionStoreEntry,
    AiParameterUploadedMaterialSummary,
)


class AiParameterStoreExpiredError(KeyError):
    pass


class AiParameterStore:
    def __init__(self) -> None:
        self._entries: dict[str, AiParameterSuggestionStoreEntry] = {}

    def put(
        self,
        *,
        run_id: str,
        scenario_id: str,
        suggestions: list[AiParameterSuggestion],
        conflict_groups: list[AiParameterConflictGroup],
        candidate_additions: list[AiParameterCandidateAddition],
        material_summaries: list[AiParameterUploadedMaterialSummary],
    ) -> AiParameterSuggestionStoreEntry:
        now = datetime.now(timezone.utc)
        entry = AiParameterSuggestionStoreEntry(
            run_id=run_id,
            created_at=now,
            expires_at=now + timedelta(minutes=_ttl_minutes()),
            scenario_id=scenario_id,
            suggestions=suggestions,
            conflict_groups=conflict_groups,
            candidate_additions=candidate_additions,
            material_summaries=material_summaries,
        )
        self._entries[run_id] = entry
        return entry

    def get(self, run_id: str) -> AiParameterSuggestionStoreEntry:
        entry = self._entries.get(run_id)
        if entry is None:
            raise AiParameterStoreExpiredError(run_id)
        if entry.expires_at <= datetime.now(timezone.utc):
            entry.application_status = "expired"
            self._entries.pop(run_id, None)
            raise AiParameterStoreExpiredError(run_id)
        return entry

    def mark_applied(self, run_id: str, *, partial: bool) -> None:
        entry = self.get(run_id)
        entry.application_status = "partially_applied" if partial else "applied"

    def expire(self, run_id: str) -> None:
        self._entries.pop(run_id, None)

    def clear(self) -> None:
        self._entries.clear()


default_ai_parameter_store = AiParameterStore()


def _ttl_minutes() -> int:
    raw = os.getenv("AI_PARAMETER_ASSISTANT_STORE_TTL_MINUTES", "60")
    try:
        return max(1, int(raw))
    except ValueError:
        return 60
