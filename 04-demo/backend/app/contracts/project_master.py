from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from .pavement import PavementHandoverStatus


class SavePavementHandoverRequest(BaseModel):
    status: PavementHandoverStatus
    available_date: date | None = None
    note: str = Field(default="", max_length=1000)
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_handover(self):
        if (self.status == "dated") != (self.available_date is not None):
            raise ValueError("指定日期必须填写移交日期；已移交和待定不填写日期。")
        return self


WorkpointType = Literal[
    "pavement",
    "bridge",
    "roadbed",
    "tunnel",
    "culvert",
    "interchange",
    "service_area",
    "station_yard",
    "access_road",
    "other",
]
StructureSide = Literal["left", "right", "shared", "none"]
RouteSide = Literal["left", "right"]
VersionStatus = Literal["draft", "confirmed", "superseded"]
ImportStatus = Literal[
    "uploaded",
    "validating",
    "blocked",
    "ready",
    "confirmed",
    "cancelled",
    "failed",
    "unchanged",
]
IssueSeverity = Literal["error", "warning"]
ParameterValueType = Literal["text", "number", "integer", "boolean", "date"]


class SourceEvidence(BaseModel):
    batch_id: str | None = None
    sheet_name: str
    row_no: int = Field(ge=1)
    column_name: str | None = None


class ParameterValue(BaseModel):
    parameter_code: str
    value_type: ParameterValueType
    value: Any
    unit: str | None = None
    sort_order: int = Field(default=0, ge=0)
    source: SourceEvidence | None = None


class ProjectMasterComponent(BaseModel):
    component_id: str
    structure_id: str
    component_name: str
    component_type: str
    quantity: float = Field(ge=0)
    unit: str
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0)
    remark: str | None = None
    parameters: list[ParameterValue] = Field(default_factory=list)
    source: SourceEvidence | None = None


class ProjectMasterStructure(BaseModel):
    structure_id: str
    workpoint_id: str
    structure_name: str
    structure_category: str
    structure_type: str
    side: StructureSide
    section_code: str | None = None
    section_name: str | None = None
    control_level: str | None = None
    sort_order: int = Field(default=0, ge=0)
    remark: str | None = None
    parameters: list[ParameterValue] = Field(default_factory=list)
    components: list[ProjectMasterComponent] = Field(default_factory=list)
    source: SourceEvidence | None = None


class ProjectMasterWorkpoint(BaseModel):
    workpoint_id: str
    workpoint_name: str
    workpoint_type: WorkpointType
    alignment_code: str | None = None
    start_mileage_m: float | None = None
    end_mileage_m: float | None = None
    sort_order: int = Field(default=0, ge=0)
    schedule_support: Literal["bridge_supported", "pavement_supported", "not_supported"] = "not_supported"
    remark: str | None = None
    structures: list[ProjectMasterStructure] = Field(default_factory=list)
    source: SourceEvidence | None = None


class TaskViewDisplayMapRequest(BaseModel):
    workpoint_ids: list[str] = Field(default_factory=list, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def reject_oversized_raw_request(cls, value: Any) -> Any:
        if isinstance(value, dict) and isinstance(value.get("workpoint_ids"), list):
            if len(value["workpoint_ids"]) > 500:
                raise ValueError("任务视图显示映射一次最多请求 500 个工点。")
        return value

    @field_validator("workpoint_ids")
    @classmethod
    def normalize_workpoint_ids(cls, values: list[str]) -> list[str]:
        return sorted({value.strip() for value in values if value.strip()})


class TaskViewDisplayWorkSection(BaseModel):
    work_section_id: str
    work_section_name: str | None = None
    side: StructureSide
    sort_order: int = Field(default=0, ge=0)


class TaskViewDisplayWorkpoint(BaseModel):
    workpoint_id: str
    workpoint_name: str
    sort_order: int = Field(default=0, ge=0)
    work_sections: list[TaskViewDisplayWorkSection] = Field(default_factory=list)


class TaskViewDisplayMapResponse(BaseModel):
    project_data_version_id: str
    workpoints: list[TaskViewDisplayWorkpoint] = Field(default_factory=list)


class ProjectMasterRoutePlacement(BaseModel):
    placement_id: str
    workpoint_id: str
    side: RouteSide
    mileage_prefix: str
    start_mileage_m: float | None = None
    end_mileage_m: float | None = None
    spatial_group_id: str
    display_order: int = Field(default=0, ge=0)
    source: SourceEvidence | None = None

    @field_validator("placement_id", "workpoint_id", "spatial_group_id")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("线路落位稳定标识、工点标识和空间对应组不能为空。")
        return value

    @field_validator("mileage_prefix")
    @classmethod
    def normalize_mileage_prefix(cls, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise ValueError("线路落位里程前缀不能为空。")
        return value

    @model_validator(mode="after")
    def validate_mileage_range(self):
        if (self.start_mileage_m is None) != (self.end_mileage_m is None):
            raise ValueError("线路落位起点里程和终点里程必须同时填写。")
        if (
            self.start_mileage_m is not None
            and self.end_mileage_m is not None
            and self.end_mileage_m < self.start_mileage_m
        ):
            raise ValueError("线路落位终点里程不得小于起点里程。")
        return self


class ProjectMasterSnapshot(BaseModel):
    workpoints: list[ProjectMasterWorkpoint] = Field(default_factory=list)
    route_placements: list[ProjectMasterRoutePlacement] = Field(default_factory=list)


class PavementTemplateLayer(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    name: str = Field(min_length=1, max_length=100)
    process_type: Literal["granular_base", "cement_stabilized_base", "asphalt_course"]
    thickness_m: float = Field(gt=0, allow_inf_nan=False)


class CreatePavementLayerDraftRequest(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    section_ids: list[str] = Field(min_length=1, max_length=500)
    layers: list[PavementTemplateLayer] = Field(min_length=1, max_length=30)
    created_by: str = Field(min_length=1, max_length=100)

    @field_validator("section_ids")
    @classmethod
    def validate_sections(cls, values: list[str]) -> list[str]:
        if any(not value for value in values) or len(set(values)) != len(values):
            raise ValueError("施工段标识不能为空或重复。")
        return values


class PavementLayerEdit(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    component_id: str | None = Field(default=None, min_length=1)
    name: str = Field(min_length=1, max_length=100)
    process_type: Literal["granular_base", "cement_stabilized_base", "asphalt_course"]
    thickness_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    density_t_m3: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    enabled: bool = True


class InitializePavementLayersRequest(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    created_by: str = Field(min_length=1, max_length=100)


class SavePavementSectionLayersRequest(InitializePavementLayersRequest):
    layers: list[PavementLayerEdit] = Field(min_length=1, max_length=30)

    @field_validator("layers")
    @classmethod
    def unique_layer_ids(cls, layers: list[PavementLayerEdit]) -> list[PavementLayerEdit]:
        ids = [layer.component_id for layer in layers if layer.component_id is not None]
        if len(set(ids)) != len(ids):
            raise ValueError("同一结构层不能重复填写。")
        return layers


class ProjectMasterCounts(BaseModel):
    workpoints: int = Field(default=0, ge=0)
    structures: int = Field(default=0, ge=0)
    components: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    warnings: int = Field(default=0, ge=0)


class ProjectMasterDiffCounts(BaseModel):
    added: int = Field(default=0, ge=0)
    modified: int = Field(default=0, ge=0)
    deleted: int = Field(default=0, ge=0)


class ProjectMasterImportIssue(BaseModel):
    issue_id: str
    severity: IssueSeverity
    issue_code: str
    sheet_name: str
    row_no: int | None = None
    field_name: str | None = None
    object_kind: str | None = None
    object_id: str | None = None
    message: str
    suggestion: str | None = None


class ProjectMasterDiffEntry(BaseModel):
    diff_id: str | None = None
    object_kind: Literal["workpoint", "route_placement", "structure", "component", "parameter"]
    object_id: str
    change_type: Literal["added", "modified", "deleted", "unchanged"]
    field_name: str | None = None
    before_value: Any = None
    after_value: Any = None
    blocking_reference: bool = False


class ProjectMasterImportBatch(BaseModel):
    batch_id: str
    project_id: str
    status: ImportStatus
    file_name: str
    file_sha256: str
    content_fingerprint: str | None = None
    expected_current_version_id: str | None = None
    created_version_id: str | None = None
    existing_version_id: str | None = None
    cancelled_version_id: str | None = None
    counts: ProjectMasterCounts = Field(default_factory=ProjectMasterCounts)
    diff_counts: ProjectMasterDiffCounts = Field(default_factory=ProjectMasterDiffCounts)
    issues: list[ProjectMasterImportIssue] = Field(default_factory=list)
    created_at: datetime
    created_by: str
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancelled_by: str | None = None
    cancel_reason: str | None = None
    failure_message: str | None = None


class ProjectMasterVersionSummary(BaseModel):
    version_id: str
    project_id: str
    version_no: int = Field(ge=1)
    status: VersionStatus
    content_fingerprint: str
    source_batch_id: str
    base_version_id: str | None = None
    counts: ProjectMasterCounts = Field(default_factory=ProjectMasterCounts)
    created_at: datetime
    created_by: str
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None


class ProjectMasterVersionDetail(ProjectMasterVersionSummary):
    diff_counts: ProjectMasterDiffCounts = Field(default_factory=ProjectMasterDiffCounts)
    diff_entries: list[ProjectMasterDiffEntry] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)


class ProjectMasterPage(BaseModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class ProjectMasterWorkpointPage(ProjectMasterPage):
    items: list[ProjectMasterWorkpoint] = Field(default_factory=list)


class ProjectMasterVersionPage(ProjectMasterPage):
    items: list[ProjectMasterVersionSummary] = Field(default_factory=list)


class ConfirmProjectMasterVersionRequest(BaseModel):
    confirmed_by: str
    expected_current_version_id: str | None = None
    acknowledge_warning_codes: list[str] = Field(default_factory=list)


class CancelProjectMasterImportRequest(BaseModel):
    cancelled_by: str
    cancel_reason: str | None = Field(default=None, max_length=500)


class PavementDailyProgressEntry(BaseModel):
    model_config = {"extra": "forbid"}
    component_id: str = Field(min_length=1)
    progress_date: str
    completed_length_m: float


class PavementProgressCell(PavementDailyProgressEntry):
    completed_length_m: float | None

    @field_validator("progress_date", mode="before")
    @classmethod
    def valid_date(cls, value):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("日期须为 YYYY-MM-DD。")
        date.fromisoformat(value)
        return value

    @field_validator("completed_length_m", mode="before")
    @classmethod
    def valid_length(cls, value):
        if value is None:
            return None
        if type(value) not in (int, float):
            raise ValueError("每日完成长度须为数值。")
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > Decimal("9007199254740.991"):
            raise ValueError("每日完成长度须为可安全表示的非负有限数值。")
        if amount * 1000 != (amount * 1000).to_integral_value():
            raise ValueError("每日完成长度最多填写3位小数。")
        return value


class SavePavementProgressRequest(BaseModel):
    model_config = {"extra": "forbid"}
    expected_master_version_id: str = Field(min_length=1)
    expected_revision: int = Field(ge=0, strict=True)
    cells: list[PavementProgressCell]


class PavementProgressRow(BaseModel):
    component_id: str
    workpoint_id: str
    structure_id: str
    section_name: str
    component_name: str
    side: StructureSide
    section_code: str | None = None
    start_chainage: str | None = None
    end_chainage: str | None = None
    start_mileage_m: float | None = None
    end_mileage_m: float | None = None
    source_version_id: str
    status: Literal["active", "disabled", "removed"]
    design_length_m: float | None = None
    width_m: float | None = None
    thickness_m: float | None = None
    completed_length_m: float = 0
    remaining_length_m: float | None = None
    overrun_length_m: float | None = None


class PavementProgressView(BaseModel):
    project_id: str
    master_version_id: str
    revision: int
    rows: list[PavementProgressRow]
    historical_rows: list[PavementProgressRow]
    entries: list[PavementDailyProgressEntry]


__all__ = [name for name in globals() if not name.startswith("_")]
