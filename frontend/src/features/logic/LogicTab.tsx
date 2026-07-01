import { Loader2, Save } from "lucide-react";
import { PanelTitle } from "../../components/common/PanelTitle";
import { buildLogicRuleRows, deferredScheduleLogicItems } from "../../domain/logic";
import type { LogicRule, RelationshipType, ScenarioInput, UpperStructureLogicRule } from "../../types/scheduler";

export function LogicTab({
  scenario,
  onUpdateLogic,
  onUpdateUpperStructureLogic,
  onSaveLocalConfig,
  savingLocalConfig,
  localConfigDirty,
}: {
  scenario: ScenarioInput;
  onUpdateLogic: (index: number, patch: Partial<LogicRule>) => void;
  onUpdateUpperStructureLogic: (ruleId: string, patch: Partial<UpperStructureLogicRule>) => void;
  onSaveLocalConfig: () => void;
  savingLocalConfig: boolean;
  localConfigDirty: boolean;
}) {
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
