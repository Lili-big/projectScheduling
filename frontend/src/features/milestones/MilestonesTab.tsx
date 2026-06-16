import { Fragment } from "react";

import { PanelTitle } from "../../components/common/PanelTitle";
import type { MilestoneConstraint, ProjectBridge, ScenarioInput, WorkPointType } from "../../types/scheduler";

const workPointTypeLabels: Record<WorkPointType, string> = {
  bridge: "桥梁工点",
  road: "路基工点",
  tunnel: "隧道工点",
};

type MilestoneRow = {
  bridge: ProjectBridge;
  milestone: MilestoneConstraint;
  milestoneIndex: number;
};

export function MilestonesTab({
  scenario,
  onUpdateMilestone,
  scopeLabelForMilestone,
}: {
  scenario: ScenarioInput;
  onUpdateMilestone: (index: number, patch: Partial<MilestoneConstraint>) => void;
  scopeLabelForMilestone: (milestone: MilestoneConstraint, scenario: ScenarioInput) => string;
}) {
  const rows = milestoneRowsByBridge(scenario);

  return (
    <section className="panel full">
      <PanelTitle title="关键里程碑节点约束" subtitle="按桥梁/工点维护单一完成节点，用于固定工期和资源建议测算" />
      {rows.length ? (
        <div className="table-wrap">
          <table className="milestone-table">
            <thead>
              <tr>
                <th>节点名称</th>
                <th>范围</th>
                <th>事件</th>
                <th>目标日期</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ bridge, milestone, milestoneIndex }) => (
                <Fragment key={bridge.id}>
                  <tr className="milestone-group-row">
                    <td colSpan={4}>
                      <span className="milestone-group-heading">
                        <strong>{bridge.name}</strong>
                        <span>{workPointTypeLabels[bridge.workpoint_type]}</span>
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <input
                        className="milestone-name-input"
                        value={milestone.name}
                        onChange={(event) => onUpdateMilestone(milestoneIndex, { name: event.target.value })}
                      />
                    </td>
                    <td className="milestone-scope-cell">{scopeLabelForMilestone(milestone, scenario)}</td>
                    <td>
                      <span className="text-pill">{milestone.target_event === "start" ? "开始" : "完成"}</span>
                    </td>
                    <td>
                      <input
                        type="date"
                        value={milestone.target_date}
                        onChange={(event) => onUpdateMilestone(milestoneIndex, { target_date: event.target.value })}
                      />
                    </td>
                  </tr>
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty compact">暂无桥梁/工点里程碑</div>
      )}
    </section>
  );
}

function milestoneRowsByBridge(scenario: ScenarioInput): MilestoneRow[] {
  return [...scenario.project.bridges]
    .sort((left, right) => left.order - right.order || left.name.localeCompare(right.name))
    .flatMap((bridge) => {
      const milestoneIndex = scenario.milestones.findIndex(
        (milestone) => milestone.scope_type === "bridge" && milestone.scope_id === bridge.id,
      );
      if (milestoneIndex < 0) return [];
      return [{ bridge, milestone: scenario.milestones[milestoneIndex], milestoneIndex }];
    });
}
