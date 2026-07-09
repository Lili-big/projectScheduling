# 契约：resource_path_continuity 候选路径无窗口化

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

## 输入契约

本功能不新增 API 入口，继续通过现有求解请求携带：

- `ScenarioInput.schedule_strategy.objective_terms.resource_path_continuity.enabled`
- `ScenarioInput.schedule_strategy.objective_terms.resource_path_continuity.weight`
- 由场景生成得到的 `ScheduleInput.tasks`
- 启用的机械钻资源池与命名资源
- 任务中的桥梁、幅别、结构物、构件类型、工艺和墩号位置字段

### 输入规则

- 当 `resource_path_continuity.enabled = false` 时，资源路径候选诊断不生效；机械钻按结构物聚合和组内连续施工仍作为基础建模规则生效。
- 当不存在机械钻机组时，本功能不生效。
- 当任务缺少幅别或墩号位置时，不得强行生成空间候选转移。
- 当两个节点不属于同桥梁、同资源组、同构件类型、同施工工艺时，不得生成候选转移。

## 输出契约

求解结果继续返回 `ScheduleResult`。诊断字段保持可选，优先挂载在：

- `ScheduleResult.stats.drill_group_refinement`
- `ScheduleResult.objective_breakdown.drill_group_refinement`
- `ScheduleResult.stats.continuity_objective`

### 建议诊断字段

```json
{
  "stage1_route_status": "enabled",
  "stage1_route_candidate_mode": "unbounded",
  "stage1_route_node_count": 4,
  "stage1_route_candidate_arc_count": 12,
  "stage1_route_rejected_arc_counts": {
    "same_side_window_exceeded": 0,
    "cross_side_gap_exceeded": 0,
    "missing_location": 0,
    "scope_mismatch": 0
  },
  "stage1_same_side_penalty": 0,
  "stage1_cross_side_penalty": 0,
  "stage1_route_penalty": 0,
  "stage1_route_failure_reason": null
}
```

### 状态枚举

| 字段 | 取值 | 含义 |
|------|------|------|
| `stage1_route_status` | `not_enabled` | `resource_path_continuity` 关闭 |
| `stage1_route_status` | `not_applicable` | 无机械钻机组或节点不足 |
| `stage1_route_status` | `enabled` | 第一阶段路径已建模 |
| `stage1_route_status` | `infeasible` | 真实 CP-SAT 约束、资源、前后置或里程碑导致不可行 |

### 顺序罚分口径

| 转移类型 | 候选条件 | 顺序罚分 |
|----------|----------|------|
| 同幅 | 同范围、位置可识别、不同节点 | `0` |
| 跨幅 | 同范围、位置可识别、不同节点 | `0` |
| 缺少位置 | 不允许 | 不生成候选弧 |
| 范围不一致 | 不允许 | 不生成候选弧 |

### 兼容要求

- 不改变 `objective_contributions` 中 `resource_path_continuity` 的目标项 ID。
- `resource_path_continuity` 对资源路径顺序的加权贡献应为 0 或未建模语义。
- 不新增前端可配置目标项。
- 旧结果缺少 `stage1_route_candidate_mode` 时，前端不得报错。
- 旧字段 `same_side_window_exceeded` 和 `cross_side_gap_exceeded` 可保留，但本功能生效时不得因距离超限增加。
- 不再返回 `stage1_route_window_infeasible` 作为仅由窗口过滤导致的失败原因。
