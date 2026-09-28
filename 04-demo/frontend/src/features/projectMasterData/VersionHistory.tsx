import type { ProjectMasterVersionSummary } from "../../contracts/projectMaster";

export function VersionHistory({
  versions,
  engineeringDomain = "bridge",
  selectedId,
  onSelect,
  onExport,
}: {
  versions: ProjectMasterVersionSummary[];
  engineeringDomain?: "bridge" | "pavement";
  selectedId?: string | null;
  onSelect: (version: ProjectMasterVersionSummary) => void;
  onExport: (version: ProjectMasterVersionSummary) => void;
}) {
  return (
    <section className="project-master-versions panel full">
      <header><strong>版本历史</strong><span>{engineeringDomain === "pavement" ? "修改保存为新版本，历史版本保留" : "确认版本不可修改，可切换查看和导出"}</span></header>
      <div>
        {versions.map((version) => (
          <article className={selectedId === version.version_id ? "active" : ""} key={version.version_id}>
            <button type="button" onClick={() => onSelect(version)}>
              <span><strong>V{version.version_no}</strong><b data-status={version.status}>{version.status === "confirmed" ? "当前" : version.status === "draft" ? "草稿" : "已替代"}</b></span>
              <span>{new Date(version.created_at).toLocaleString()} · {version.created_by}</span>
              <small>{engineeringDomain === "pavement" ? `${version.counts.structures} 施工段 / ${version.counts.components} 结构层` : `${version.counts.workpoints} 工点 / ${version.counts.structures} 结构物 / ${version.counts.components} 构件`}</small>
            </button>
            <button type="button" onClick={() => onExport(version)}>导出</button>
          </article>
        ))}
        {versions.length === 0 && <div className="project-master-empty-small">尚无主数据版本</div>}
      </div>
    </section>
  );
}
