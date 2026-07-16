import type { FieldConflict, GirderPlanningReadiness, SourceEvidence, ValidationMessage } from "../../contracts";

export function GirderDiagnostics({
  conflicts,
  evidence,
  readiness,
  diagnostics,
}: {
  conflicts: FieldConflict[];
  evidence: SourceEvidence[];
  readiness: GirderPlanningReadiness | null;
  diagnostics: ValidationMessage[];
}) {
  const messages = readiness?.diagnostics ?? diagnostics;
  return (
    <section className="girder-card">
      <div className="girder-card-heading"><div><h3>完整性与来源核查</h3><p>阻断项必须解决后才能确认或进入联合计算。</p></div>{readiness && <span className={`girder-status ${readiness.status}`}>{readiness.status}</span>}</div>
      <div className="girder-diagnostics">
        {messages.map((item, index) => <div className={`girder-message ${item.level}`} key={`${item.code ?? "message"}-${index}`}><strong>{item.code ?? item.level}</strong><span>{item.message}</span>{item.suggestion && <small>{item.suggestion}</small>}</div>)}
        {!messages.length && <div className="empty-state">尚未执行专项校验。</div>}
      </div>
      <details><summary>字段冲突（{conflicts.length}）</summary>{conflicts.map((item) => <div key={item.conflict_id}>{item.entity_ref} · {item.field_path} · {item.status}</div>)}</details>
      <details><summary>来源证据（{evidence.length}）</summary>{evidence.slice(0, 50).map((item) => <div key={item.evidence_id}>{item.field_path} · {item.authority_domain} · {item.file_name ?? "人工"}:{item.row_or_region ?? "-"}</div>)}</details>
    </section>
  );
}
