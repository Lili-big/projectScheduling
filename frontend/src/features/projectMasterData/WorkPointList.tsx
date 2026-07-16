import { Search } from "lucide-react";
import type { ProjectMasterWorkpoint, ProjectMasterWorkpointType } from "../../contracts/projectMaster";
import { projectMasterWorkpointTypeLabels } from "../../domain/projectMaster";

export function WorkPointList({
  items,
  total,
  selectedId,
  keyword,
  workpointType,
  loading,
  onKeywordChange,
  onTypeChange,
  onSelect,
}: {
  items: ProjectMasterWorkpoint[];
  total: number;
  selectedId?: string | null;
  keyword: string;
  workpointType: ProjectMasterWorkpointType | "";
  loading: boolean;
  onKeywordChange: (value: string) => void;
  onTypeChange: (value: ProjectMasterWorkpointType | "") => void;
  onSelect: (item: ProjectMasterWorkpoint) => void;
}) {
  return (
    <section className="project-master-list" aria-label="工点列表">
      <div className="project-master-filter-row">
        <label>
          <Search size={15} />
          <input value={keyword} placeholder="搜索工点名称或 ID" onChange={(event) => onKeywordChange(event.target.value)} />
        </label>
        <select value={workpointType} onChange={(event) => onTypeChange(event.target.value as ProjectMasterWorkpointType | "")}>
          <option value="">全部类型</option>
          {Object.entries(projectMasterWorkpointTypeLabels).map(([value, label]) => (
            <option value={value} key={value}>{label}</option>
          ))}
        </select>
      </div>
      <div className="project-master-list-summary">{loading ? "正在加载…" : `共 ${total} 个工点`}</div>
      <div className="project-master-list-items">
        {items.map((item) => (
          <button
            type="button"
            className={selectedId === item.workpoint_id ? "active" : ""}
            onClick={() => onSelect(item)}
            key={item.workpoint_id}
          >
            <span>
              <strong>{item.workpoint_name}</strong>
              <em>{item.workpoint_id}</em>
            </span>
            <span>
              <b>{projectMasterWorkpointTypeLabels[item.workpoint_type]}</b>
              <small>{item.schedule_support === "bridge_supported" ? "支持桥梁排程" : "暂不参与排程"}</small>
            </span>
          </button>
        ))}
        {!loading && items.length === 0 && <div className="project-master-empty-small">没有符合条件的工点</div>}
      </div>
    </section>
  );
}
