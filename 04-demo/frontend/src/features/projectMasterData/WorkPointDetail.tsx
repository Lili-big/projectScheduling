import type { ProjectMasterSource, ProjectMasterWorkpoint } from "../../contracts/projectMaster";
import { projectMasterSideLabels, projectMasterWorkpointTypeLabels } from "../../domain/projectMaster";

export function WorkPointDetail({ workpoint, loading }: { workpoint: ProjectMasterWorkpoint | null; loading: boolean }) {
  if (loading) return <section className="project-master-detail project-master-empty">正在读取工点结构…</section>;
  if (!workpoint) return <section className="project-master-detail project-master-empty">从左侧选择一个工点查看结构物与构件参数</section>;
  return (
    <section className="project-master-detail" aria-label="工点明细">
      <div className="project-master-detail-heading">
        <div>
          <span>{projectMasterWorkpointTypeLabels[workpoint.workpoint_type]}</span>
          <h3>{workpoint.workpoint_name}</h3>
          <p>{workpoint.workpoint_id} · {workpoint.alignment_code || "未填写线路编码"}</p>
        </div>
        <b className={workpoint.schedule_support === "bridge_supported" ? "supported" : "unsupported"}>
          {workpoint.schedule_support === "bridge_supported" ? "支持桥梁排程" : "当前不参与排程"}
        </b>
      </div>
      <dl className="project-master-basic-grid">
        <div><dt>起点里程</dt><dd>{formatMileage(workpoint.start_mileage_m)}</dd></div>
        <div><dt>终点里程</dt><dd>{formatMileage(workpoint.end_mileage_m)}</dd></div>
        <div><dt>结构物数量</dt><dd>{workpoint.structures.length}</dd></div>
        <div><dt>来源</dt><dd><Source source={workpoint.source} /></dd></div>
      </dl>
      <div className="project-master-structure-list">
        {workpoint.structures.map((structure) => (
          <article key={structure.structure_id}>
            <header>
              <div>
                <b>{projectMasterSideLabels[structure.side]}</b>
                <strong>{structure.structure_name}</strong>
                <small>{structure.structure_id}</small>
              </div>
              <span>{structure.structure_type} · {structure.section_name || structure.section_code || "未分工区"}</span>
            </header>
            {structure.parameters.length > 0 && (
              <div className="project-master-parameter-grid">
                {structure.parameters.map((parameter) => (
                  <div key={parameter.parameter_code}>
                    <span>{parameter.parameter_code}</span>
                    <strong>{String(parameter.value)}{parameter.unit || ""}</strong>
                  </div>
                ))}
              </div>
            )}
            <div className="project-master-components">
              {structure.components.map((component) => (
                <div key={component.component_id}>
                  <span><strong>{component.component_name}</strong><small>{component.component_type}</small></span>
                  <b>{component.quantity} {component.unit}</b>
                  <Source source={component.source} />
                </div>
              ))}
              {structure.components.length === 0 && <em>该结构物没有独立构件行</em>}
            </div>
            <footer><Source source={structure.source} /></footer>
          </article>
        ))}
      </div>
    </section>
  );
}

function Source({ source }: { source?: ProjectMasterSource | null }) {
  return source ? <small>{source.sheet_name} · 第 {source.row_no} 行{source.column_name ? ` · ${source.column_name}` : ""}</small> : <small>无来源记录</small>;
}

function formatMileage(value?: number | null): string {
  return value == null ? "—" : `${value.toLocaleString()} m`;
}
