# 接口契约：AI 第二阶段仅优化资源空闲

## 1. 接口范围

保持现有接口不变：

- `POST /api/ai-resource-assistant/solve-plan`
- `POST /api/ai-resource-assistant/batch-solve`
- `POST /api/ai-resource-assistant/compare-results`
- `POST /api/ai-resource-assistant/generate-recommendation`

请求继续提交当前 `scenario` 和 `resource_plan`，不新增第二阶段权重、连续性开关或时限字段。

## 2. 响应结构兼容

`ResourceAssistantPlanResult.optimization_stages` 结构不变：

```json
{
  "optimization_stages": {
    "primary": {
      "attempted": true,
      "solver_status": "OPTIMAL",
      "max_target_delay_days": 0,
      "makespan_days": 579,
      "optimality_proven": true,
      "elapsed_seconds": 18.6,
      "configured_budget_seconds": 60.0
    },
    "secondary": {
      "attempted": true,
      "solver_status": "FEASIBLE",
      "resource_idle_days": 980,
      "continuity_penalty": 460,
      "optimality_proven": false,
      "elapsed_seconds": 10.8,
      "configured_budget_seconds": 40.9,
      "skipped_reason": null,
      "validation_failure_reason": null
    },
    "selected_stage": "secondary",
    "fallback_reason": null,
    "total_budget_seconds": 60.0,
    "total_elapsed_seconds": 29.4
  }
}
```

## 3. 字段语义调整

- `secondary.resource_idle_days`：第二阶段唯一优化指标。
- `secondary.continuity_penalty`：最终排程的连续性诊断，可为空或非负，不参与第二阶段目标和结果选择。
- `secondary.optimality_proven`：表示累计资源空闲目标是否证明最优，不代表连续性诊断最优。
- `validation_failure_reason=no_secondary_improvement`：表示累计资源空闲没有严格小于第一阶段。
- `selected_stage=secondary`：必须满足工期上限、固定资源、任务完整性和累计资源空闲严格下降。

## 4. 典型状态

### 空闲下降、连续性变差

- 第一阶段空闲 120 天，连续性诊断 20；
- 第二阶段空闲 100 天，连续性诊断 35；
- 工期边界均满足；
- `selected_stage=secondary`，连续性变化只显示诊断。

### 空闲相同、连续性改善

- 第一阶段空闲 120 天，连续性诊断 20；
- 第二阶段空闲 120 天，连续性诊断 10；
- `selected_stage=primary`；
- `validation_failure_reason=no_secondary_improvement`。

### 第一阶段空闲为 0

- `secondary.attempted=false`；
- `selected_stage=primary`；
- `secondary.skipped_reason=idle_already_zero`，说明累计资源空闲已为 0、无改善空间。

### 第二阶段工期越界或无排程

- 沿用现有 `primary_bounds_exceeded`、`secondary_no_schedule` 或 `model_error`；
- 完整返回第一阶段排程。

## 5. 页面说明

- 主说明：“单方案两阶段共享 60 秒预算：先锁定最大延期与总工期，再用剩余时间减少资源内部空闲。”
- 阶段成功：“资源空闲已改善，尚未证明最优”或“资源空闲已改善并证明最优”。
- 连续性区域：“根据最终排程计算，仅供施工组织诊断，不参与第二阶段求解和方案推荐。”

## 6. 兼容要求

- 历史结果缺少阶段字段时继续按既有状态展示。
- 历史结果包含连续性罚分时继续显示，不重新解释或重写数据。
- 旧客户端忽略语义变化后仍可解析响应。
- `secondary.skipped_reason` 只增加 `idle_already_zero` 枚举值，不删除历史值。
- 不修改状态码、请求校验和错误响应结构。
