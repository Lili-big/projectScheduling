# 契约：桩基钻机墩组两阶段精排

## 请求契约

本功能不新增固定资源求解入口，不要求前端新增请求字段。现有固定资源、最少资源候选精排和最佳努力精排继续使用当前 `ScenarioInput` / `ScheduleInput` / `ScheduleStrategyConfig`。

请求兼容规则：

- 资源路径连续性目标关闭时，两阶段路径精排相关软目标不建模。
- `ResourcePool.same_structure_parallel_limit` 不再作为机械桩基墩组聚合或两阶段精排触发条件。
- 旋挖钻、冲击钻、回旋钻机械桩基墩组默认执行组内同一台命名资源负责；人工挖孔桩不执行该规则。
- 资源池配置仍可通过资源数量、资源启用状态、兼容类型和其他既有规则影响求解，但不得阻止机械桩基墩组进入第一阶段精排。
- 不新增用户可编辑的路径精修开关或权重。

## 结果任务契约

最终结果中的 `ScheduleResult.tasks` 必须保持原任务粒度。

兼容要求：

- 不返回虚拟墩组任务。
- 原任务 `id`、`name`、`structure_id`、`structure_name`、`component_type`、`process_name`、`quantity`、`quantity_label` 保持兼容。
- 被聚合的原任务继承同一机械钻机墩组的 `assigned_resource_id`、`assigned_resource_name` 和 `assigned_resource_type`。
- 展开后的 `start_offset`、`end_offset`、`start_date`、`finish_date` 必须可用于现有甘特图、资源分配和里程碑结果计算。

## 结果来源契约

结果来源必须能区分以下情况：

| 来源状态 | 含义 |
| --- | --- |
| `stage2_refined` | 粗排和细排均成功，主结果使用细排展开结果 |
| `stage2_fallback` | 粗排成功但细排失败或超时，主结果使用粗排展开结果 |
| `coarse_only` | 资源路径连续性关闭或不适用，未运行细排路径排序 |
| `not_applicable` | 场景中没有符合条件的机械钻机墩组 |

具体字段名可在实现中复用现有 `schedule_source`、`performance_path` 或新增诊断字段，但前端和测试必须能判断以上语义。

固定资源主链路的结果来源还必须能区分：

| 来源状态 | 含义 |
| --- | --- |
| `current_resources_control_priority_balanced` 或等价新值 | 当前资源直接进入命名资源精排并成功 |
| `current_resources_refinement_failed` 或等价新值 | 第一阶段命名资源精排不可行或超时，当前资源主结果保持失败语义 |
| `current_resources_capacity_shortest` | 仅作为资源建议测算或内部诊断辅助出现，不作为当前资源失败后的兜底展示结果 |

主链路不得再把池级最短工期排序作为成功精排前的必跑产物。

## 诊断契约

结果应在现有诊断结构中提供两阶段精排信息。建议字段：

```json
{
  "drill_group_refinement": {
    "status": "stage2_refined",
    "coarse_group_count": 30,
    "coarse_child_task_count": 60,
    "stage2_node_count": 30,
    "stage2_arc_count": 180,
    "baseline_candidate_arc_count": 900,
    "arc_reduction_ratio": 0.8,
    "adjacent_resource_switch_penalty": 2,
    "hole_jump_penalty": 1,
    "makespan_tolerance": 0,
    "fallback_reason": null
  }
}
```

兼容规则：

- 前端可以先只展示现有连续性指标，但必须能安全忽略新增字段。
- 后端测试必须验证新增诊断存在且数值与场景规模一致。
- 关闭资源路径连续性时，`status` 应表达未启用或未评价，路径节点和路径弧数量不得伪装为已评价成功。

## 错误和回退契约

- 第一阶段粗排不可行或超时：返回当前资源失败结果，并尝试进入资源建议分支；不得回退展示池级最短工期或当前资源最佳努力结果。
- 细排不可行或超时：返回粗排展开结果，并写明 `stage2_fallback` 和回退原因。
- 没有符合条件的机械钻机墩组：不改变现有精排结果，诊断为 `not_applicable`。
- 人工挖孔：不进入机械钻机墩组聚合，也不受组内单资源规则限制。
- 机械钻机资源池未配置 `same_structure_parallel_limit`、配置为 0 或配置为大于 1：仍可进入机械桩基墩组聚合，并由显式墩组约束保证组内同一命名资源负责。
