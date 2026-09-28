import { pavementLayers, emptyPavementSettings, pavementDependencyRows, setPavementDependencyRule, pavementHandover } from "../../domain/pavement";
import { useState } from "react";
import type { PavementSettings, PavementProcessType, PavementDependencyRule } from "../../contracts";
import { Loader2, Save } from "lucide-react";
import { PanelTitle } from "../../components/common/PanelTitle";
import { buildLogicRuleRows, deferredScheduleLogicItems } from "../../domain/logic";
import type { LogicRule, RelationshipType, ScenarioInput, UpperStructureLogicRule } from "../../contracts";

export function LogicTab({
  scenario,
  onUpdateLogic,
  onUpdateUpperStructureLogic,
  onSaveLocalConfig,
  savingLocalConfig,
  localConfigDirty,
  onUpdatePavementSettings,
}: {
  scenario: ScenarioInput;
  onUpdateLogic: (index: number, patch: Partial<LogicRule>) => void;
  onUpdateUpperStructureLogic: (ruleId: string, patch: Partial<UpperStructureLogicRule>) => void;
  onSaveLocalConfig: () => void;
  savingLocalConfig: boolean;
  localConfigDirty: boolean;
  onUpdatePavementSettings?: (settings: PavementSettings) => void;
}) {
  if (scenario.engineering_domain === "pavement") return <PavementLogic scenario={scenario} onChange={onUpdatePavementSettings} onSave={onSaveLocalConfig} saving={savingLocalConfig} />;
  const { rows, summary } = buildLogicRuleRows(scenario);

  const relationshipSelect = (
    value: RelationshipType,
    onChange: (value: RelationshipType) => void,
  ) => (
    <select className="logic-relation-select" value={value} onChange={(event) => onChange(event.target.value as RelationshipType)}>
      <option value="FS">FS</option>
      <option value="SS">SS</option>
      <option value="FF">FF</option>
      <option value="SF">SF</option>
    </select>
  );
  const lagInput = (value: number, onChange: (value: number) => void) => (
    <div className="logic-lag-control">
      <input
        type="number"
        min={0}
        value={value}
        onChange={(event) => onChange(Math.max(0, Number(event.target.value) || 0))}
      />
      <span className="unit">自然日</span>
    </div>
  );
  const finishGapInput = (value: number, onChange: (value: number) => void) => (
    <div className="logic-lag-control">
      <input
        type="number"
        min={0}
        value={value}
        onChange={(event) => onChange(Math.max(0, Number(event.target.value) || 0))}
      />
      <span className="unit">天内</span>
    </div>
  );

  return (
    <section className="panel full logic-panel">
      <PanelTitle
        title="工艺逻辑约束"
        subtitle="维护任务之间谁先谁后；时间关系和等待时间会进入排程求解"
        action={
          <button
            className="secondary"
            type="button"
            onClick={onSaveLocalConfig}
            disabled={savingLocalConfig || !localConfigDirty}
            title="保存到后端本地 JSON 配置文件"
            aria-label="保存工艺逻辑"
          >
            {savingLocalConfig ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
            保存
          </button>
        }
      />
      <div className="logic-content unified">
        <div className="logic-section-title">
          <div>
            <h3>规则配置</h3>
            <span>
              {summary.activeRuleCount} 条规则 / {summary.matchedRuleCount} 条当前适用 / {summary.unmatchedRuleCount} 条暂未适用
            </span>
          </div>
          <span className="text-pill">修改后重新生成任务视图</span>
        </div>
        <div className="table-wrap logic-unified">
          <table className="logic-unified-table">
            <thead>
              <tr>
                <th>规则名称</th>
                <th>适用结构物</th>
                <th>前置工序</th>
                <th>匹配规则</th>
                <th>逻辑关系</th>
                <th>时间间隔</th>
                <th>同步/窗口</th>
                <th>使用范围</th>
                <th>规则说明</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <div className="logic-rule-heading">
                      <span className={`logic-source-badge ${row.source}`}>{row.sourceLabel}</span>
                      <div className="rule-name">{row.name}</div>
                    </div>
                  </td>
                  <td>{row.successorLabel}</td>
                  <td>{row.predecessorLabel}</td>
                  <td>
                    <span className="logic-mode-pill readonly">{row.matchModeLabel}</span>
                  </td>
                  <td>
                    {row.readOnly ? (
                      <span className="logic-mode-pill readonly">硬约束</span>
                    ) : relationshipSelect(row.relationship, (relationship) =>
                      row.source === "lower" && row.lowerRuleIndex !== undefined
                        ? onUpdateLogic(row.lowerRuleIndex, { relationship })
                        : onUpdateUpperStructureLogic(row.id, { relationship }),
                    )}
                  </td>
                  <td>
                    {row.readOnly ? (
                      <span className="logic-mode-pill readonly">不可编辑</span>
                    ) : lagInput(row.lagDays, (lag_days) =>
                      row.source === "lower" && row.lowerRuleIndex !== undefined
                        ? onUpdateLogic(row.lowerRuleIndex, { lag_days })
                        : onUpdateUpperStructureLogic(row.id, { lag_days }),
                    )}
                  </td>
                  <td>
                    {row.source === "upper" && !row.readOnly && row.maxFinishGapDays !== undefined && row.maxFinishGapDays !== null
                      ? finishGapInput(row.maxFinishGapDays, (max_finish_gap_days) =>
                          onUpdateUpperStructureLogic(row.id, { max_finish_gap_days }),
                        )
                      : <span className="logic-mode-pill readonly">{row.constraintLabel ?? "无"}</span>}
                  </td>
                  <td>
                    <span className={`logic-match ${row.matchedCount > 0 ? "active" : "muted"}`}>{row.matchedText}</span>
                  </td>
                  <td className="note-cell">
                    <span>{row.note}</span>
                    {row.generation && <span className="logic-note-extra">{row.generation}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="logic-deferred">
          <div>
            <strong>当前暂不生成任务</strong>
            <span>以下工艺已有模板或结构参数，但当前任务图不会生成对应现场任务。</span>
          </div>
          <div className="logic-deferred-list">
            {deferredScheduleLogicItems.map((item) => (
              <div className="logic-deferred-item" key={item.name}>
                <span>{item.name}</span>
                <p>{item.reason}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}


type PavementLogicProps = { scenario: ScenarioInput; onChange?: (s: PavementSettings) => void; onSave: () => void; saving: boolean };

const pavementRelationshipLabels = { FS: "FS 完成→开始", SS: "SS 开始→开始", FF: "FF 完成→完成", SF: "SF 开始→完成" };

function PavementLogic(props: PavementLogicProps) {
  const { scenario, onChange, onSave, saving } = props;
  const [scope, setScope] = useState("");
  const settings = scenario.pavement_settings ?? emptyPavementSettings();
  const rules = settings.dependency_rules ?? [];
  const layers = pavementLayers(scenario);
  const activeRows = pavementDependencyRows(scenario);
  const relationKey = (row: typeof activeRows[number]) => `${row.structure_id}|${row.predecessor_key}|${row.successor_key}`;
  const activeKeys = new Set(activeRows.map(relationKey));
  const allRows = [
    ...activeRows.map(row => ({ ...row, active: true })),
    ...pavementDependencyRows(scenario, true).filter(row => !activeKeys.has(relationKey(row))).map(row => ({ ...row, active: false })),
  ];
  const sections = [...new Map([...layers.map(l => [l.structure.id, l.section.name] as const),
    ...allRows.map(row => [row.structure_id, row.section_name] as const)]).entries()];
  const selectedScope = sections.some(([id]) => id === scope) ? scope : "";
  const groups = new Map<string, typeof allRows>();
  for (const row of allRows) {
    const key = `${row.predecessor_key}|${row.successor_key}`;
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  const rows = selectedScope ? allRows.filter(r => r.structure_id === selectedScope) : [...groups.values()].map(group => {
    const applicable = group.filter(row => row.active);
    const defaults = applicable.length ? applicable : group;
    const first = defaults[0];
    const global = rules.find(r => !r.structure_id && r.predecessor_key === first.predecessor_key && r.successor_key === first.successor_key);
    const sameWait = defaults.every(r => r.default_lag_days === first.default_lag_days);
    return { ...first, relationship: global?.relationship ?? "FS" as const,
      lag_days: global ? global.lag_days : sameWait ? first.default_lag_days : null,
      source: global ? "project" as const : "conditions" as const, active: applicable.length > 0 };
  });
  const unmatched = rules.filter(rule => !allRows.some(row => (!rule.structure_id || row.structure_id === rule.structure_id)
    && row.predecessor_key === rule.predecessor_key && row.successor_key === rule.successor_key));
  const scopedRule = (row: typeof rows[number]): PavementDependencyRule => ({
    structure_id: selectedScope || null, predecessor_key: row.predecessor_key, successor_key: row.successor_key,
    relationship: row.relationship, lag_days: row.lag_days,
  });
  return <section className="panel full pavement-logic-panel">
    <PanelTitle title="施工工序链" subtitle="N为技术间歇（自然日）；分段调整优先于统一配置" action={<button disabled={saving} onClick={onSave}>{saving ? "正在保存…" : "保存配置"}</button>} />
    <div className="pavement-relation-scope"><label>配置范围 <select aria-label="工序关系配置范围" value={selectedScope} onChange={e => setScope(e.target.value)}>
      <option value="">统一工艺关系</option>{sections.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
    </select></label></div>
    {rows.length ? <div className="table-wrap"><table className="pavement-relation-table" aria-label="工序前置关系">
      <thead><tr><th>前置工序</th><th>后续工序</th><th>关系类型</th><th>技术间歇（天）</th><th>关系表达</th><th>配置来源</th><th>应用状态</th><th>调整</th></tr></thead>
      <tbody>{rows.map(row => {
        const rule = scopedRule(row);
        const condition = selectedScope && row.predecessor_id.startsWith("pavement:")
          ? settings.layer_conditions.find(c => `pavement:${c.component_id}` === row.predecessor_id) : null;
        const own = rules.some(r => (r.structure_id ?? null) === rule.structure_id && r.predecessor_key === row.predecessor_key && r.successor_key === row.successor_key);
        const update = (patch: Partial<PavementDependencyRule>) => onChange?.(setPavementDependencyRule(settings, { ...rule, ...patch }));
        return <tr key={`${row.predecessor_key}|${row.successor_key}`}>
          <th scope="row">{row.predecessor_name}{condition && <details className="pavement-relation-date"><summary>{condition.accepted_available_date ? `验收可用：${condition.accepted_available_date}` : "可选验收日期"}</summary>
            <input type="date" disabled={saving} aria-label={`${row.predecessor_name}验收可用日期`} value={condition.accepted_available_date ?? ""} onChange={e => onChange?.({...settings, layer_conditions:settings.layer_conditions.map(c => c.component_id === condition.component_id ? {...c,accepted_available_date:e.target.value || null} : c)})} />
          </details>}</th><td>→ {row.successor_name}</td>
          <td><select disabled={saving} aria-label={`${row.predecessor_name}到${row.successor_name}关系类型`} value={row.relationship} onChange={e => update({ relationship: e.target.value as PavementDependencyRule["relationship"] })}>
            {Object.entries(pavementRelationshipLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></td>
          <td><input disabled={saving} type="number" min="0" step="1" aria-label={`${row.predecessor_name}到${row.successor_name}技术间歇`} value={row.lag_days ?? ""} placeholder="待确认" onChange={e => {
            const value = e.target.value === "" ? null : Number(e.target.value);
            if (value === null || (Number.isInteger(value) && value >= 0)) update({ lag_days: value });
          }} /></td>
          <td className="pavement-relation-expression">{row.relationship}+{row.lag_days ?? "N"}{row.lag_days == null ? "（待确认）" : "天"}</td>
          <td>{row.source === "section" ? "分段调整" : row.source === "project" ? "统一配置" : "原有条件"}</td>
          <td>{row.active ? "当前适用" : "工序停用，暂不参与排程"}</td>
          <td><button disabled={saving || !own} onClick={() => onChange?.(setPavementDependencyRule(settings, rule, true))}>恢复继承</button></td>
        </tr>;
      })}</tbody>
    </table></div> : <p>{layers.length ? "当前只有一道启用工序，无前置关系。" : "请先在项目主数据中启用结构层。"}</p>}
    {!!unmatched.length && <div className="pavement-unmatched-relations" role="status">未匹配的关系配置（结构层或工序链已调整）：
      {unmatched.map((rule, i) => <div key={i}>{rule.structure_id ? sections.find(([id]) => id === rule.structure_id)?.[1] ?? "原施工段" : "统一配置"} · {rule.relationship}+{rule.lag_days ?? "N"}
        <button disabled={saving} onClick={() => onChange?.(setPavementDependencyRule(settings, rule, true))}>移除</button></div>)}
    </div>}
    <p className="pavement-relation-note">路床移交约束本段全部工序：指定日期后可开工，已移交按计划开始日；待移交段在其他施工段全部完成后附条件安排。层间养生在FS+N中维护。</p>
    {selectedScope && <p>当前施工段：{pavementHandover(scenario.project.bridges.flatMap(w => w.work_sections).flatMap(s => s.structures).find(s => s.id === selectedScope)?.properties ?? {}).label}</p>}
    <details className="pavement-logic-configuration"><summary>其他配置：跨段施工顺序</summary>
      {layers.length > 0 ? <PavementLogicConfiguration {...props} /> : <p>配置实际结构层后可维护。</p>}
    </details>
  </section>;
}

function PavementLogicConfiguration({ scenario, onChange }: PavementLogicProps) {
  const settings = scenario.pavement_settings ?? emptyPavementSettings();
  return <div className="pavement-logic-config-content">
    <h3>指定跨段施工顺序（可选）</h3><p>默认由排程选择跨段顺序。只有现场已有固定要求时填写下面的结构层ID顺序。</p>
    <form className="pavement-fixed-sequence-form" onSubmit={e => { e.preventDefault(); const f=new FormData(e.currentTarget); onChange?.({...settings,fixed_sequences:[...settings.fixed_sequences,{process_type:String(f.get("type")) as PavementProcessType,component_ids:String(f.get("ids")).split(/[,，]/).map(x=>x.trim()).filter(Boolean)}]}); e.currentTarget.reset(); }}>
      <select name="type"><option value="granular_base">碎石</option><option value="cement_stabilized_base">水稳</option><option value="asphalt_course">沥青</option></select><input name="ids" required placeholder="层ID按顺序，以逗号分隔" /><button>添加固定顺序</button>
    </form><ul>{settings.fixed_sequences.map((s,i)=><li key={i}>{s.component_ids.join(" → ")} <button onClick={()=>onChange?.({...settings,fixed_sequences:settings.fixed_sequences.filter((_,j)=>i!==j)})}>移除</button></li>)}</ul>
  </div>;
}
