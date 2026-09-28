import type { ReactNode } from "react";
import type { ScheduleResult, PavementLiveStatus, GeneratedScheduleInput } from "../../contracts";
import { pavementResultPresentation } from "./presenter";
import { PavementSolveProgress, type PavementProgress } from "./PavementSolveProgress";
import { PavementPlanTimeline } from "./PavementPlanTimeline";
import { PavementCrewRoute } from "./PavementCrewRoute";
import { PavementResourceTimeline } from "./PavementResourceTimeline";

export function ScheduleResultsWorkspace({ children }: { children: ReactNode }) {
  return <div className="results-grid" data-resource-pool-results="pool-id">{children}</div>;
}

export function PavementScheduleResults({ result, generated, liveStatus, progress }: { result: ScheduleResult; generated?: GeneratedScheduleInput; liveStatus?: PavementLiveStatus; progress?: PavementProgress }) {
  const display = pavementResultPresentation(result, liveStatus);
  const summary = display.hasPlan ? result.pavement_summary : null;
  const scope = display.handoverScope;
  const idle = result.pavement_idle_optimization;
  const taskName = (id: string) => result.tasks.find(t => t.id === id)?.name ?? id;
  return <section className="panel full pavement-results"><h2>路面排程结果 · {display.noSchedulableSection ? "暂无可开工施工段" : display.status}</h2>
    {display.optimizationText && <p className="pavement-objective"><b>{display.optimizationText}</b></p>}
    <PavementSolveProgress status={liveStatus} progress={progress} hasPlan={display.hasPlan} improvementCount={progress?.goal === "idle" ? (liveStatus === "running" && !idle ? 0 : idle?.improvement_count) : result.pavement_optimization?.improvement_count} />
    {display.summaryText && <p className="pavement-result-summary" role="status">{display.summaryText}</p>}
    {display.hasPlan && <section className="pavement-date-summary" aria-label="排程起止日期">
      <div className="pavement-date-grid">{display.dateRanges.map(range => <div className="pavement-date-card" key={range.key}>
        <h3>{range.label}</h3>
        {range.taskCount ? <dl>
          <div><dt>开始日期</dt><dd>{range.startDate ? <time dateTime={range.startDate}>{range.startDate}</time> : "—"}</dd></div>
          <div><dt>完成日期</dt><dd>{range.finishDate ? <time dateTime={range.finishDate}>{range.finishDate}</time> : "—"}</dd></div>
        </dl> : <p className="pv-note">{range.key === "overall" ? "暂无排程日期" : "未纳入本次排程"}</p>}
      </div>)}</div>
      <p className="pv-note">按当前方案中对应工序的最早开工日、最晚施工完成日汇总。</p>
    </section>}
    {idle && <p className="pv-note">必要转场 {idle.baseline_transfer_days} → {idle.final_transfer_days} 机组·天。窝工只统计机组首次开工至最后完工之间扣除作业和必要转场的空档，不含首作业前、末作业后；合计改善不代表每套机组都单独改善。</p>}
    {!!scope?.blocked_sections.length && <details open><summary>受阻施工段（未排程）</summary><table aria-label="受阻施工段"><thead><tr><th>施工段</th><th>受阻原因</th></tr></thead><tbody>{scope.blocked_sections.map(s => <tr key={s.structure_id}><th scope="row">{s.section_name}</th><td>{s.reason}</td></tr>)}</tbody></table></details>}
    {!!display.pendingSections.length && <>
      <h3>移交日期未定 · 请关注最晚需移交日</h3>
      <p className="pavement-handover-note">{display.handoverNotice}</p>
      <div className="table-wrap"><table aria-label="待移交施工段日期"><thead><tr><th>施工段</th><th>待移交原因</th>{display.hasPlan && <><th>本方案最晚需移交日</th><th>预计施工完成日期</th></>}</tr></thead>
        <tbody>{display.pendingSections.map(s => <tr key={s.structure_id}><th scope="row">{s.section_name}</th><td>{s.reason}</td>{display.hasPlan && <><td>{s.required_handover_date ?? "—"}</td><td>{s.estimated_finish_date ?? "—"}</td></>}</tr>)}</tbody>
      </table></div>
    </>}
    {summary && <>{display.legacy ? <><p role="status">历史结果使用旧交付口径，请重新求解。</p><p>施工末日 {display.constructionFinish} · 原交付可用日期 {display.readyDate}</p></> : <p>{display.finishLabel} <b>{display.constructionFinish}</b> · 工期 {display.elapsedDays} 天</p>}
      <p className="pv-note">{summary.resource_assumptions.join(" ")}</p>
      <PavementPlanTimeline result={result} generated={generated} pendingIds={display.pendingSections.map(s => s.structure_id)} />
      <PavementResourceTimeline result={result} generated={generated} />
      <PavementCrewRoute result={result} generated={generated} />
      {display.legacy && <><h3>历史分段交付</h3><ul>{summary.readiness.map(r=><li key={r.id}>{taskName(r.terminal_task_id)}完成并满足等待及验收条件：{r.ready_date}</li>)}</ul></>}
      <details><summary>输入来源</summary><p>主数据版本：{summary.project_data_version_id ?? "演示输入"}</p><p>输入指纹：{summary.input_fingerprint}</p></details>
    </>}
    {idle && <details><summary>本轮窝工优化耗时</summary><p>建模 {idle.model_build_seconds.toFixed(2)} 秒 · 优化 {idle.cp_sat_seconds.toFixed(2)} 秒 · 合计 {idle.total_seconds.toFixed(2)} 秒</p>
      <p>计算预算 {idle.time_budget_seconds} 秒 · 搜索线程 {idle.search_workers ?? "未启动"} · 内置 LNS {idle.lns_enabled == null ? "未启动" : idle.lns_enabled ? "启用" : "未启用"} · 合法改善 {idle.improvement_count} 次</p>
    </details>}
    {result.pavement_optimization && <details><summary>{idle ? "第一阶段工期求解耗时" : "计算耗时"}</summary><p>
      初步计划 {result.pavement_optimization.initial_plan_seconds.toFixed(2)} 秒 ·
      建模 {result.pavement_optimization.model_build_seconds.toFixed(2)} 秒 ·
      优化 {result.pavement_optimization.cp_sat_seconds.toFixed(2)} 秒 ·
      合计 {result.pavement_optimization.total_seconds.toFixed(2)} 秒
    </p>{result.pavement_optimization.time_budget_seconds != null && <p>
      计算预算 {result.pavement_optimization.time_budget_seconds} 秒 · 搜索线程 {result.pavement_optimization.search_workers ?? "未启动"} ·
      内置 LNS {result.pavement_optimization.lns_enabled == null ? "未启动" : result.pavement_optimization.lns_enabled ? "启用" : "未启用"} ·
      合法改善 {result.pavement_optimization.improvement_count ?? 0} 次
    </p>}</details>}
    {!summary && !display.noSchedulableSection && <p>本次未获得可展示的可行计划，请查看诊断。</p>}
  </section>;
}
