from __future__ import annotations

from datetime import timedelta

from ..models import LatestFinishControl, PassageReleaseResult, ProjectDataVersion, RouteRun, ValidationMessage


def calculate_latest_finish_controls(
    project_version: ProjectDataVersion,
    route_runs: list[RouteRun],
    passage_releases: list[PassageReleaseResult],
) -> tuple[list[LatestFinishControl], list[ValidationMessage]]:
    controls: list[LatestFinishControl] = []
    diagnostics: list[ValidationMessage] = []
    route_finish = max((item.finish_date for item in route_runs), default=None)
    if route_finish is None:
        return controls, diagnostics
    for release in passage_releases:
        workpoint = next((item for item in project_version.workpoints if item.workpoint_id == release.workpoint_id), None)
        if workpoint is None:
            continue
        latest = release.passable_date or route_finish
        for ref in workpoint.linked_condition_refs:
            controls.append(
                LatestFinishControl(
                    entity_ref=f"{ref.ref_type}:{ref.entity_id}",
                    controlled_by=workpoint.workpoint_id,
                    latest_finish_date=latest,
                    mode="soft",
                    priority=1,
                )
            )
        if workpoint.workpoint_type in {"roadbed", "tunnel"} and not workpoint.linked_condition_refs:
            controls.append(
                LatestFinishControl(
                    entity_ref=workpoint.workpoint_id,
                    controlled_by="route_passage",
                    latest_finish_date=latest - timedelta(days=1),
                    mode="soft",
                    priority=1,
                )
            )
    return controls, diagnostics
