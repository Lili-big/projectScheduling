import { PanelTitle } from "../../components/common/PanelTitle";
import type { MilestoneConstraint, ScenarioInput } from "../../types/scheduler";

export function MilestonesTab({
  scenario,
  onUpdateMilestone,
  scopeLabelForMilestone,
}: {
  scenario: ScenarioInput;
  onUpdateMilestone: (index: number, patch: Partial<MilestoneConstraint>) => void;
  scopeLabelForMilestone: (milestone: MilestoneConstraint, scenario: ScenarioInput) => string;
}) {
  return (
    <section className="panel full">
      <PanelTitle title="关键里程碑节点约束" subtitle="固定资源最短工期允许突破目标并给出偏差；固定工期最少资源会把强制目标作为不可突破工期" />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>节点</th>
              <th>等级</th>
              <th>约束</th>
              <th>范围</th>
              <th>事件</th>
              <th>目标日期</th>
              <th>罚分/天</th>
            </tr>
          </thead>
          <tbody>
            {scenario.milestones.map((milestone, index) => (
              <tr key={milestone.id}>
                <td>
                  <input
                    className="wide-input"
                    value={milestone.name}
                    onChange={(event) => onUpdateMilestone(index, { name: event.target.value })}
                  />
                </td>
                <td>
                  <select value={milestone.level} onChange={(event) => onUpdateMilestone(index, { level: event.target.value as MilestoneConstraint["level"] })}>
                    <option value="contract">合同</option>
                    <option value="control">强控</option>
                    <option value="internal">内部</option>
                  </select>
                </td>
                <td>
                  <select value={milestone.mode} onChange={(event) => onUpdateMilestone(index, { mode: event.target.value as MilestoneConstraint["mode"] })}>
                    <option value="hard">强制目标</option>
                    <option value="soft">提醒目标</option>
                  </select>
                </td>
                <td>{scopeLabelForMilestone(milestone, scenario)}</td>
                <td>
                  <select
                    value={milestone.target_event}
                    onChange={(event) => onUpdateMilestone(index, { target_event: event.target.value as MilestoneConstraint["target_event"] })}
                  >
                    <option value="finish">完成</option>
                    <option value="start">开始</option>
                  </select>
                </td>
                <td>
                  <input
                    type="date"
                    value={milestone.target_date}
                    onChange={(event) => onUpdateMilestone(index, { target_date: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min={0}
                    value={milestone.penalty_per_day}
                    disabled={milestone.mode === "hard"}
                    onChange={(event) => onUpdateMilestone(index, { penalty_per_day: Number(event.target.value) })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
