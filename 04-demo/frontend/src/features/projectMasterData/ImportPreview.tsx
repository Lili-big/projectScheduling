import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import type { ProjectMasterImportBatch, ProjectMasterVersionDetail } from "../../contracts/projectMaster";
import { groupProjectMasterDiffs, projectMasterIssueLocation } from "../../domain/projectMaster";

export function ImportPreview({
  batch,
  version,
  busy,
  onConfirm,
  onCancel,
}: {
  batch: ProjectMasterImportBatch;
  version: ProjectMasterVersionDetail | null;
  busy: boolean;
  onConfirm: (warningCodes: string[]) => Promise<void>;
  onCancel: () => Promise<void>;
}) {
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());
  const diffs = useMemo(() => groupProjectMasterDiffs(version?.diff_entries ?? []), [version]);
  const canConfirm = batch.status === "ready" && version && version.warning_codes.every((code) => acknowledged.has(code));
  return (
    <section className="project-master-import-preview panel full">
      <header>
        <div>
          {batch.status === "blocked" ? <XCircle size={20} /> : <CheckCircle2 size={20} />}
          <span><strong>{batch.file_name}</strong><small>批次 {batch.batch_id}</small></span>
        </div>
        <b data-status={batch.status}>{statusLabel(batch.status)}</b>
      </header>
      <div className="project-master-counts">
        <span>工点 <b>{batch.counts.workpoints}</b></span>
        <span>结构物 <b>{batch.counts.structures}</b></span>
        <span>构件 <b>{batch.counts.components}</b></span>
        <span>错误 <b>{batch.counts.errors}</b></span>
        <span>告警 <b>{batch.counts.warnings}</b></span>
      </div>
      {batch.issues.length > 0 && (
        <div className="project-master-issues">
          {batch.issues.map((issue) => (
            <div data-severity={issue.severity} key={issue.issue_id}>
              <AlertTriangle size={15} />
              <span><strong>{issue.message}</strong><small>{projectMasterIssueLocation(issue)} · {issue.issue_code}</small></span>
            </div>
          ))}
        </div>
      )}
      {version && (
        <div className="project-master-diffs">
          <strong>相对当前确认版本的差异</strong>
          <span>新增 {diffs.added.length}</span><span>修改 {diffs.modified.length}</span><span>删除 {diffs.deleted.length}</span>
        </div>
      )}
      {version?.warning_codes.map((code) => (
        <label className="project-master-warning-ack" key={code}>
          <input
            type="checkbox"
            checked={acknowledged.has(code)}
            onChange={(event) => setAcknowledged((current) => {
              const next = new Set(current);
              if (event.target.checked) next.add(code); else next.delete(code);
              return next;
            })}
          />
          已知悉告警 {code}
        </label>
      ))}
      <footer>
        {batch.status === "ready" && <button type="button" onClick={onCancel} disabled={busy}>取消本次导入</button>}
        <button className="primary" type="button" disabled={!canConfirm || busy} onClick={() => onConfirm([...acknowledged])}>
          {busy ? "正在处理…" : "确认并设为当前版本"}
        </button>
      </footer>
    </section>
  );
}

function statusLabel(status: ProjectMasterImportBatch["status"]): string {
  return ({ ready: "待确认", blocked: "导入阻断", unchanged: "内容未变化", confirmed: "已确认", cancelled: "已取消", failed: "处理失败" } as Record<string, string>)[status] || "处理中";
}
