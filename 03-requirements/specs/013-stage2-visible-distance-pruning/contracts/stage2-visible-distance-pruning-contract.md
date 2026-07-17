# 契约：第二阶段可见墩距路径剪枝

## 输入契约

沿用现有 `ScheduleInput`。本次不新增字段。

## 行为契约

机械钻资源类型包括：

```text
rotary_drill
circulation_drill
impact_drill
```

第二阶段路径候选弧必须满足：

```text
非机械钻资源：保留全量候选弧
机械钻同幅连接：同幅可见墩距 <= 2
机械钻跨幅连接：跨幅可见墩距 <= 1
不同桥梁/构件类型/工序：不允许直接候选连接
非桥墩或缺失墩号：继续放行
无出入边节点：保留兜底补边
```

## 输出契约

`stats.continuity_objective` 与 `objective_breakdown` 中应继续输出路径建模诊断，并新增跨幅窗口诊断：

```json
{
  "resource_path_sparse_support_window": 2,
  "resource_path_sparse_same_side_window": 2,
  "resource_path_sparse_cross_side_window": 1,
  "resource_path_transition_arc_count": 68
}
```
