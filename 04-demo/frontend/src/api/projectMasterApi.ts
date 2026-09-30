import { withPavementMaster } from "../domain/pavement";
import type { SavePavementHandoverRequest } from "../contracts/projectMaster";
import type { PavementProgressView, SavePavementProgressRequest } from "../contracts/projectMaster";

export function getPavementProgress(projectId: string): Promise<PavementProgressView> {
  return apiGet(`/api/projects/${encodeURIComponent(projectId)}/pavement-progress`);
}
export function savePavementProgress(projectId: string, payload: SavePavementProgressRequest): Promise<PavementProgressView> {
  return apiPut(`/api/projects/${encodeURIComponent(projectId)}/pavement-progress`, payload);
}

export function savePavementHandover(versionId: string, sectionId: string, values: SavePavementHandoverRequest): Promise<ProjectMasterVersionDetail> {
  return apiPut(`/api/project-master/versions/${encodeURIComponent(versionId)}/pavement-sections/${encodeURIComponent(sectionId)}/handover`, values);
}
import type { ScenarioInput } from "../contracts";
import { apiGet, apiGetBlob, apiPost, apiPostFormData, apiPut } from "./client";
import type {
  ProjectMasterImportBatch,
  CreatePavementLayerDraftRequest,
  PavementLayerEdit,
  ProjectMasterVersionDetail,
  ProjectMasterVersionPage,
  ProjectMasterVersionSummary,
  ProjectMasterWorkpoint,
  ProjectMasterWorkpointPage,
  TaskViewDisplayMapResponse,
} from "../contracts/projectMaster";
import type { GirderWorkPoint } from "../contracts";

export function downloadProjectMasterTemplate(engineeringDomain: "bridge" | "pavement" = "bridge"): Promise<Blob> {
  return apiGetBlob(`/api/project-master/template?engineering_domain=${engineeringDomain}`);
}

export function importProjectMasterWorkbook(
  projectId: string,
  file: File,
  expectedCurrentVersionId?: string | null,
  createdBy = "本地计划工程师",
): Promise<ProjectMasterImportBatch> {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("created_by", createdBy);
  if (expectedCurrentVersionId) form.append("expected_current_version_id", expectedCurrentVersionId);
  return apiPostFormData(`/api/projects/${encodeURIComponent(projectId)}/project-master/imports`, form);
}

export function getProjectMasterImport(batchId: string): Promise<ProjectMasterImportBatch> {
  return apiGet(`/api/project-master/imports/${encodeURIComponent(batchId)}`);
}

export function cancelProjectMasterImport(
  batchId: string,
  cancelledBy = "本地计划工程师",
  cancelReason?: string,
): Promise<ProjectMasterImportBatch> {
  return apiPost(`/api/project-master/imports/${encodeURIComponent(batchId)}`, {
    cancelled_by: cancelledBy,
    cancel_reason: cancelReason || null,
  });
}

export function listProjectMasterVersions(projectId: string, page = 1, pageSize = 50): Promise<ProjectMasterVersionPage> {
  return apiGet(`/api/projects/${encodeURIComponent(projectId)}/project-master/versions?page=${page}&page_size=${pageSize}`);
}

export function getCurrentProjectMasterVersion(projectId: string): Promise<ProjectMasterVersionSummary> {
  return apiGet(`/api/projects/${encodeURIComponent(projectId)}/project-master/versions/current`);
}

export function getProjectMasterVersion(versionId: string): Promise<ProjectMasterVersionDetail> {
  return apiGet(`/api/project-master/versions/${encodeURIComponent(versionId)}`);
}

export function createPavementLayerDraft(versionId: string, payload: CreatePavementLayerDraftRequest): Promise<ProjectMasterImportBatch> {
  return apiPost(`/api/project-master/versions/${encodeURIComponent(versionId)}/pavement-layer-drafts`, payload);
}

export function initializePavementLayers(versionId: string): Promise<ProjectMasterVersionDetail> {
  return apiPost(`/api/project-master/versions/${encodeURIComponent(versionId)}/pavement-layers/initialize`, { created_by: "本地计划工程师" });
}

export function savePavementSectionLayers(versionId: string, sectionId: string, layers: PavementLayerEdit[]): Promise<ProjectMasterVersionDetail> {
  return apiPut(`/api/project-master/versions/${encodeURIComponent(versionId)}/pavement-sections/${encodeURIComponent(sectionId)}/layers`, { layers, created_by: "本地计划工程师" });
}

export function confirmProjectMasterVersion(
  versionId: string,
  expectedCurrentVersionId: string | null,
  acknowledgeWarningCodes: string[],
  confirmedBy = "本地计划工程师",
): Promise<ProjectMasterVersionDetail> {
  return apiPost(`/api/project-master/versions/${encodeURIComponent(versionId)}/confirm`, {
    confirmed_by: confirmedBy,
    expected_current_version_id: expectedCurrentVersionId,
    acknowledge_warning_codes: acknowledgeWarningCodes,
  });
}

export function listProjectMasterWorkpoints(
  versionId: string,
  options: { page?: number; pageSize?: number; workpointType?: string; keyword?: string } = {},
): Promise<ProjectMasterWorkpointPage> {
  const query = new URLSearchParams({
    page: String(options.page ?? 1),
    page_size: String(options.pageSize ?? 50),
  });
  if (options.workpointType) query.set("workpoint_type", options.workpointType);
  if (options.keyword) query.set("keyword", options.keyword);
  return apiGet(`/api/project-master/versions/${encodeURIComponent(versionId)}/workpoints?${query}`);
}

export function getProjectMasterWorkpoint(versionId: string, workpointId: string): Promise<ProjectMasterWorkpoint> {
  return apiGet(
    `/api/project-master/versions/${encodeURIComponent(versionId)}/workpoints/${encodeURIComponent(workpointId)}`,
  );
}

export function getProjectMasterTaskViewDisplayMap(
  versionId: string,
  workpointIds: string[],
): Promise<TaskViewDisplayMapResponse> {
  return apiPost(
    `/api/project-master/versions/${encodeURIComponent(versionId)}/task-view-display-map`,
    { workpoint_ids: workpointIds },
  );
}

export function exportProjectMasterVersion(versionId: string): Promise<Blob> {
  return apiGetBlob(`/api/project-master/versions/${encodeURIComponent(versionId)}/export`);
}

export function listProjectMasterGirderWorkpoints(versionId: string): Promise<GirderWorkPoint[]> {
  return apiGet(`/api/project-master/versions/${encodeURIComponent(versionId)}/girder-workpoints`);
}

export async function waitForProjectMasterImport(
  batchId: string,
  intervalMs = 800,
  maxAttempts = 60,
): Promise<ProjectMasterImportBatch> {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const batch = await getProjectMasterImport(batchId);
    if (!["uploaded", "validating"].includes(batch.status)) return batch;
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }
  throw new Error("导入处理超时，请稍后在版本历史中查看。")
}

export function saveBlob(blob: Blob, fileName: string): void {
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(href);
}


export async function getPavementProject(input: ScenarioInput, versionId: string): Promise<ScenarioInput> {
  const workpoints: ProjectMasterWorkpoint[] = [];
  for (let page = 1; ; page++) {
    const data = await listProjectMasterWorkpoints(versionId, { page, pageSize: 200 });
    if (data.items.some(w => w.workpoint_type !== "pavement")) throw new Error("当前版本包含非路面工点，请使用纯路面主数据范围。");
    workpoints.push(...await Promise.all(data.items.map(w => getProjectMasterWorkpoint(versionId, w.workpoint_id))));
    if (workpoints.length >= data.total) break;
  }
  return withPavementMaster(input, workpoints, versionId);
}
