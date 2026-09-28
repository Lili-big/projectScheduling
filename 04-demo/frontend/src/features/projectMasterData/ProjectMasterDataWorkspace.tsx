import { Database, Download, Loader2, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  cancelProjectMasterImport,
  confirmProjectMasterVersion,
  downloadProjectMasterTemplate,
  exportProjectMasterVersion,
  getProjectMasterVersion,
  getProjectMasterWorkpoint,
  importProjectMasterWorkbook,
  listProjectMasterVersions,
  listProjectMasterWorkpoints,
  saveBlob,
} from "../../api/projectMasterApi";
import type {
  ProjectMasterImportBatch,
  ProjectMasterVersionDetail,
  ProjectMasterVersionSummary,
  ProjectMasterWorkpoint,
  ProjectMasterWorkpointType,
} from "../../contracts/projectMaster";
import { ImportPreview } from "./ImportPreview";
import { PavementMasterBrowser } from "./PavementMasterTable";
import { VersionHistory } from "./VersionHistory";
import { WorkPointDetail } from "./WorkPointDetail";
import { WorkPointList } from "./WorkPointList";
import "./styles.css";

export function ProjectMasterDataWorkspace({
  projectId,
  engineeringDomain = "bridge",
  activeVersionId,
  onVersionConfirmed,
}: {
  projectId: string;
  engineeringDomain?: "bridge" | "pavement";
  activeVersionId?: string | null;
  onVersionConfirmed: (versionId: string) => void;
}) {
  const [versions, setVersions] = useState<ProjectMasterVersionSummary[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(activeVersionId ?? null);
  const [batch, setBatch] = useState<ProjectMasterImportBatch | null>(null);
  const [draftVersion, setDraftVersion] = useState<ProjectMasterVersionDetail | null>(null);
  const [workpoints, setWorkpoints] = useState<ProjectMasterWorkpoint[]>([]);
  const [selectedWorkpoint, setSelectedWorkpoint] = useState<ProjectMasterWorkpoint | null>(null);
  const [keyword, setKeyword] = useState("");
  const [workpointType, setWorkpointType] = useState<ProjectMasterWorkpointType | "">("");
  const [total, setTotal] = useState(0);
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedPavementSection, setExpandedPavementSection] = useState<string | null | undefined>(undefined);

  const loadVersions = useCallback(async () => {
    const page = await listProjectMasterVersions(projectId);
    setVersions(page.items);
    setSelectedVersionId((current) => current || activeVersionId || page.items.find((item) => item.status === "confirmed")?.version_id || page.items[0]?.version_id || null);
  }, [activeVersionId, projectId]);

  useEffect(() => {
    void loadVersions().catch((reason) => setError(errorText(reason)));
  }, [loadVersions]);

  useEffect(() => {
    if (engineeringDomain === "pavement") return;
    if (!selectedVersionId) {
      setWorkpoints([]);
      setTotal(0);
      return;
    }
    const timeout = window.setTimeout(() => {
      setDetailBusy(true);
      void listProjectMasterWorkpoints(selectedVersionId, { keyword, workpointType: workpointType || undefined })
        .then((page) => {
          setWorkpoints(page.items);
          setTotal(page.total);
          setSelectedWorkpoint((current) => current && page.items.some((item) => item.workpoint_id === current.workpoint_id) ? current : null);
        })
        .catch((reason) => setError(errorText(reason)))
        .finally(() => setDetailBusy(false));
    }, 200);
    return () => window.clearTimeout(timeout);
  }, [engineeringDomain, keyword, selectedVersionId, workpointType]);

  async function importWorkbook(file: File) {
    setBusy(true);
    setError(null);
    try {
      const current = versions.find((item) => item.status === "confirmed");
      const nextBatch = await importProjectMasterWorkbook(projectId, file, current?.version_id);
      setBatch(nextBatch);
      if (nextBatch.created_version_id) {
        const detail = await getProjectMasterVersion(nextBatch.created_version_id);
        setDraftVersion(detail);
        setSelectedVersionId(detail.version_id);
      } else {
        setDraftVersion(null);
      }
      await loadVersions();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function confirmDraft(warningCodes: string[]) {
    if (!draftVersion) return;
    setBusy(true);
    setError(null);
    try {
      const current = versions.find((item) => item.status === "confirmed");
      const confirmed = await confirmProjectMasterVersion(draftVersion.version_id, current?.version_id ?? null, warningCodes);
      setBatch((value) => value ? { ...value, status: "confirmed" } : value);
      setDraftVersion(confirmed);
      setSelectedVersionId(confirmed.version_id);
      onVersionConfirmed(confirmed.version_id);
      await loadVersions();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function cancelDraft() {
    if (!batch) return;
    setBusy(true);
    try {
      setBatch(await cancelProjectMasterImport(batch.batch_id, "本地计划工程师", "放弃本次草稿"));
      setDraftVersion(null);
      await loadVersions();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  }

  async function selectWorkpoint(item: ProjectMasterWorkpoint) {
    if (!selectedVersionId) return;
    setDetailBusy(true);
    try {
      setSelectedWorkpoint(await getProjectMasterWorkpoint(selectedVersionId, item.workpoint_id));
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setDetailBusy(false);
    }
  }

  async function downloadTemplate() {
    try { saveBlob(await downloadProjectMasterTemplate(engineeringDomain), "项目主数据导入模板.xlsx"); }
    catch (reason) { setError(errorText(reason)); }
  }

  async function exportVersion(version: ProjectMasterVersionSummary) {
    try { saveBlob(await exportProjectMasterVersion(version.version_id), `项目主数据-v${version.version_no}.xlsx`); }
    catch (reason) { setError(errorText(reason)); }
  }

  return (
    <div className="project-master-workspace" aria-label="项目主数据">
      <section className="panel full project-master-hero">
        <div>
          <span className="project-master-hero-icon"><Database size={22} /></span>
          <div><h2>项目主数据</h2>{engineeringDomain !== "pavement" && <p>统一维护工点、结构物、构件与参数。</p>}</div>
        </div>
        <div className="project-master-actions">
          <button type="button" onClick={downloadTemplate}><Download size={16} />下载 Excel 模板</button>
          <label className="primary">
            {busy ? <Loader2 className="spin" size={16} /> : <Upload size={16} />}
            {busy ? "正在处理" : "导入完整快照"}
            <input type="file" accept=".xlsx,.xlsm" disabled={busy} onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void importWorkbook(file);
              event.currentTarget.value = "";
            }} />
          </label>
        </div>
      </section>
      {error && <div className="project-master-error">{error}</div>}
      {batch && <ImportPreview batch={batch} version={draftVersion} busy={busy} onConfirm={confirmDraft} onCancel={cancelDraft} />}
      {selectedVersionId ? (
        engineeringDomain === "pavement" ? <PavementMasterBrowser key={selectedVersionId} versionId={selectedVersionId}
          editable={versions.some(v => v.version_id === selectedVersionId && v.status === "confirmed")}
          expandedSectionId={expandedPavementSection} onExpand={setExpandedPavementSection}
          onVersionSaved={async versionId => {
            setSelectedVersionId(versionId); setError(null); onVersionConfirmed(versionId);
            try { await loadVersions(); } catch (reason) { setError(`结构层已保存，版本列表读取失败：${errorText(reason)}`); }
          }} /> : (
        <div className="project-master-browser panel full">
          <WorkPointList
            items={workpoints}
            total={total}
            selectedId={selectedWorkpoint?.workpoint_id}
            keyword={keyword}
            workpointType={workpointType}
            loading={detailBusy}
            onKeywordChange={setKeyword}
            onTypeChange={setWorkpointType}
            onSelect={(item) => void selectWorkpoint(item)}
          />
          <WorkPointDetail workpoint={selectedWorkpoint} loading={detailBusy && Boolean(selectedWorkpoint)} />
        </div>
        )
      ) : (
        <section className="panel full project-master-first-empty">
          <Database size={32} /><h3>尚未建立项目主数据</h3><p>{engineeringDomain === "pavement" ? "先下载路面模板，填写施工段、幅别和实际结构层后导入完整快照。" : "先下载模板，按“一个物理工点 + 工点下结构物”填写后导入完整快照。"}</p>
        </section>
      )}
      {engineeringDomain !== "pavement" && <VersionHistory versions={versions} engineeringDomain={engineeringDomain} selectedId={selectedVersionId} onSelect={(version) => { setSelectedVersionId(version.version_id); setSelectedWorkpoint(null); }} onExport={(version) => void exportVersion(version)} />}
    </div>
  );
}

function errorText(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}
