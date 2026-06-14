import { PanelTitle } from "../../components/common/PanelTitle";
import { componentLabels } from "../../domain/labels";
import { buildUpperLowerLogicConstraints } from "../../domain/logic";
import type { LogicRule, RelationshipType, ScenarioInput, UpperStructureLogicRule } from "../../types/scheduler";

export function LogicTab({
  scenario,
  onUpdateLogic,
  onUpdateUpperStructureLogic,
}: {
  scenario: ScenarioInput;
  onUpdateLogic: (index: number, patch: Partial<LogicRule>) => void;
  onUpdateUpperStructureLogic: (ruleId: string, patch: Partial<UpperStructureLogicRule>) => void;
}) {
  const upperLowerConstraints = buildUpperLowerLogicConstraints(scenario);

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

  return (
    <section className="panel full logic-panel">
      <PanelTitle title="工艺逻辑约束" subtitle="下部结构规则与桥梁上部结构派生约束使用同一套关系和间隔配置" />
      <div className="logic-content unified">
        <div className="logic-section-title">
          <div>
            <h3>规则配置</h3>
            <span>{scenario.logic_rules.length} 条下部规则 / {upperLowerConstraints.length} 条桥梁上部规则</span>
          </div>
          <span className="text-pill">关系与间隔进入排程求解</span>
        </div>
        <div className="table-wrap logic-unified">
          <table className="logic-unified-table">
            <thead>
              <tr>
                <th>规则</th>
                <th>当前 / 后续</th>
                <th>前置来源</th>
                <th>策略 / 生成</th>
                <th>关系</th>
                <th>间隔</th>
                <th>当前匹配</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              {scenario.logic_rules.map((rule, index) => (
                <tr key={rule.id}>
                  <td>
                    <div className="logic-rule-heading">
                      <span className="logic-source-badge lower">下部结构</span>
                      <div className="rule-name">{logicRuleDisplayName(rule)}</div>
                    </div>
                    <code className="muted-code">{rule.id}</code>
                  </td>
                  <td>{componentLabels[rule.to_component]}</td>
                  <td>{rule.predecessor_candidates.map((item) => componentLabels[item]).join(" / ")}</td>
                  <td>
                    <select
                      value={rule.predecessor_strategy}
                      onChange={(event) => onUpdateLogic(index, { predecessor_strategy: event.target.value as LogicRule["predecessor_strategy"] })}
                    >
                      <option value="first_available">优先回退</option>
                      <option value="all">全部满足</option>
                    </select>
                  </td>
                  <td>{relationshipSelect(rule.relationship, (relationship) => onUpdateLogic(index, { relationship }))}</td>
                  <td>{lagInput(rule.lag_days, (lag_days) => onUpdateLogic(index, { lag_days }))}</td>
                  <td><span className="logic-match muted">默认规则</span></td>
                  <td className="note-cell">{rule.note}</td>
                </tr>
              ))}
              {upperLowerConstraints.map((constraint) => (
                <tr key={constraint.id}>
                  <td>
                    <div className="logic-rule-heading">
                      <span className="logic-source-badge upper">桥梁上部</span>
                      <div className="rule-name">{constraint.name}</div>
                    </div>
                    <code className="muted-code">{constraint.id}</code>
                  </td>
                  <td>{constraint.upperTarget}</td>
                  <td>{constraint.lowerPredecessor}</td>
                  <td className="note-cell">{constraint.generation}</td>
                  <td>
                    {relationshipSelect(
                      constraint.relationship,
                      (relationship) => onUpdateUpperStructureLogic(constraint.id, { relationship }),
                    )}
                  </td>
                  <td>
                    {lagInput(
                      constraint.lagDays,
                      (lag_days) => onUpdateUpperStructureLogic(constraint.id, { lag_days }),
                    )}
                  </td>
                  <td><span className="logic-match">{constraint.matchedText}</span></td>
                  <td className="note-cell">{constraint.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function logicRuleDisplayName(rule: LogicRule): string {
  if (rule.note) {
    return rule.note.replace(/。$/, "");
  }
  const predecessors = rule.predecessor_candidates.map((item) => componentLabels[item]).join("、");
  return `${componentLabels[rule.to_component]}在${predecessors}之后施工`;
}
