from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


WorkpointType = Literal[
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
    schedule_support: Literal["bridge_supported", "not_supported"] = "not_supported"
    remark: str | None = None
    structures: list[ProjectMasterStructure] = Field(default_factory=list)
    source: SourceEvidence | None = None


class ProjectMasterSnapshot(BaseModel):
    workpoints: list[ProjectMasterWorkpoint] = Field(default_factory=list)


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
    object_kind: Literal["workpoint", "structure", "component", "parameter"]
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


__all__ = [name for name in globals() if not name.startswith("_")]
