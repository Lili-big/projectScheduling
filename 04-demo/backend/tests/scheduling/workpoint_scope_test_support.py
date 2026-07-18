from __future__ import annotations

from datetime import date, timedelta

from app.contracts import (
    ComponentModel,
    MilestoneConstraint,
    ProcessTemplate,
    ProjectBridge,
    ProjectModel,
    ResourcePool,
    ScenarioInput,
    StructureModel,
    WorkSection,
)


WORKPOINT_A = "WP-A"
WORKPOINT_B = "WP-B"
RESOURCE_TYPE = "cap_team"


def two_workpoint_scenario(
    resource_pool: ResourcePool,
    *,
    target_days: int | None = None,
) -> ScenarioInput:
    start = date(2026, 1, 1)
    milestones = []
    if target_days is not None:
        milestones = [
            MilestoneConstraint(
                id="M-hard",
                name="固定工期目标",
                mode="hard",
                scope_type="project",
                target_event="finish",
                target_date=start + timedelta(days=target_days - 1),
            )
        ]
    return ScenarioInput(
        scenario_id="workpoint-resource-scope",
        scenario_name="工点级资源作用域测试",
        project_data_version_id="project-data-v1",
        project=ProjectModel(
            project_id="P-scope",
            project_name="工点级资源作用域测试",
            start_date=start,
            bridges=[_bridge(WORKPOINT_A, 1), _bridge(WORKPOINT_B, 2)],
        ),
        process_library=[
            ProcessTemplate(
                id="cap-scope-test",
                component_type="cap",
                process_name="承台施工",
                duration_method="fixed_days",
                quantity_source="count",
                productivity_value=5,
                productivity_unit="天/个",
                resource_type=RESOURCE_TYPE,
                is_default=True,
            )
        ],
        logic_rules=[],
        resource_pools=[resource_pool],
        milestones=milestones,
        time_limit_seconds=5,
    )


def _bridge(workpoint_id: str, order: int) -> ProjectBridge:
    return ProjectBridge(
        id=workpoint_id,
        name=f"工点 {order}",
        order=order,
        work_sections=[
            WorkSection(
                id=f"WS-{order}",
                name=f"工区 {order}",
                order=order,
                structures=[
                    StructureModel(
                        id=f"S-{order}",
                        name=f"{order}#墩",
                        structure_type="pier",
                        order=order,
                        components=[
                            ComponentModel(
                                id=f"C-{order}",
                                name=f"{order}#承台",
                                component_type="cap",
                                quantity=1,
                                quantity_label="1个",
                            )
                        ],
                    )
                ],
            )
        ],
    )
