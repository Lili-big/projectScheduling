# 契约：第一阶段钻机组路径连续性优化

## 输入契约

本功能不新增 API 入口，继续通过现有求解请求携带：

- `ScenarioInput.schedule_strategy.objective_terms.resource_path_continuity.enabled`
- `ScenarioInput.schedule_strategy.objective_terms.resource_path_continuity.weight`
- 由场景生成得到的 `ScheduleInput.tasks`
- 启用的机械钻资源池与命名资源
- 任务中的桥梁、幅别、结构物、构件类型、工艺和墩号位置字段

### 输入规则

- 当 `resource_path_continuity.enabled = false` 时，本功能不生效。
- 当不存在机械钻机组时，本功能不生效。
- 当任务缺少幅别或墩号位置时，不得强行生成空间候选转移。

## 输出契约

求解结果继续返回 `ScheduleResult`。新增或强化的诊断字段应保持可选，建议挂载在：

- `ScheduleResult.stats.drill_group_refinement`
- `ScheduleResult.objective_breakdown.drill_group_refinement`
- 必要时同步摘要到 `ScheduleResult.stats.continuity_objective`

### 建议诊断字段

```json
{
  "stage1_route_status": "enabled",
  "stage1_route_node_count": 4,
  "stage1_route_candidate_arc_count": 6,
  "stage1_route_rejected_arc_counts": {
    "same_side_window_exceeded": 2,
    "cross_side_gap_exceeded": 3,
    "missing_location": 0
  },
  "stage1_same_side_penalty": 1,
  "stage1_cross_side_penalty": 1,
  "stage1_route_penalty": 2,
  "stage1_route_failure_reason": null
}
```

### 状态枚举

| 字段 | 取值 | 含义 |
|------|------|------|
| `stage1_route_status` | `not_enabled` | `resource_path_continuity` 关闭 |
| `stage1_route_status` | `not_applicable` | 无机械钻机组或节点不足 |
| `stage1_route_status` | `enabled` | 第一阶段空间路径已建模 |
| `stage1_route_status` | `infeasible` | 窗口规则导致无法形成可用路径或求解不可行 |

### 惩罚口径

| 转移类型 | 允许条件 | 惩罚 |
|----------|----------|------|
| 同幅 | 可施工序列距离 `<= 2` | `max(0, 可施工序列距离 - 1)` |
| 跨幅 | 真实墩号差 `<= 1` | `1` |
| 窗口外 | 不允许 | 不生成候选弧 |

## 兼容要求

- 旧结果缺少 `stage1_*` 字段时，前端按未评估处理。
- 不改变 `objective_contributions` 中 `resource_path_continuity` 的目标项 ID。
- 不新增前端可配置目标项。
- 当前资源失败时继续沿用已有 `schedule_source` 和资源建议语义，不用成功标签掩盖失败。
## 2026-07-08 补充：第一阶段最终状态

新增 `drill_group_refinement.status = "stage1_final"`，表示开启资源连续性且机械钻机组第一阶段可行时，系统直接采用第一阶段完整排程作为主结果，未再进入第二阶段 `refined` 排程。

历史状态 `stage2_refined`、`stage2_fallback` 和字段 `stage2_node_count`、`stage2_arc_count` 保留兼容旧结果；新结果中第二阶段节点和弧数量通常为 0。
