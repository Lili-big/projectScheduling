# 接口契约：AI 固定资源两阶段求解

## 1. 接口范围

保持现有接口：

- `POST /api/ai-resource-assistant/solve-plan`
- `POST /api/ai-resource-assistant/batch-solve`

请求结构不变，继续提交 `scenario` 与当前 `resource_plan`。不增加阶段权重、阶段时限或连续性参数。

## 2. 向后兼容响应扩展

`ResourceAssistantPlanResult` 新增可选字段：

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
      "configured_budget_seconds": 30.0
    },
    "secondary": {
      "attempted": true,
      "solver_status": "FEASIBLE",
      "resource_idle_days": 980,
      "continuity_penalty": 420,
      "optimality_proven": false,
      "elapsed_seconds": 10.8,
      "configured_budget_seconds": 11.4,
      "skipped_reason": null,
      "validation_failure_reason": null
    },
    "selected_stage": "secondary",
    "fallback_reason": null,
    "total_budget_seconds": 30.0,
    "total_elapsed_seconds": 29.4
  }
}
```

历史响应不包含 `optimization_stages` 时，前端按现有字段解释。

## 3. 现有字段语义

- `solver_status`：被选中最终排程对应阶段的原始求解状态。
- `schedule_outcome_status`：工期三态，依据第一阶段工期证明和最终排程复核。
- `schedule_outcome_reason`：保持现有原因枚举。
- `plan_status`：保持历史四状态兼容字段。
- `input_resource_quantities`：两个阶段共同使用的固定资源快照。
- `resource_expansion_attempted`：固定为 `false`。
- `result.stats.solver_call_count`：第二阶段启动时为 2，否则为 1。
- `result.stats.performance_path`：两阶段路径使用 `ai_strict_fixed_resource_two_stage`。

## 4. 典型状态

### 第一阶段完成，第二阶段改进但未证明最优

- `primary.solver_status=OPTIMAL`
- `secondary.solver_status=FEASIBLE`
- `selected_stage=secondary`
- 工期状态可保持“工期目标已满足”或“已证明工期目标未满足”
- 页面显示“资源组织已改善，尚未证明最优”

### 第二阶段超时无排程

- `secondary.attempted=true`
- `secondary.solver_status=UNKNOWN`
- `selected_stage=primary`
- `fallback_reason=secondary_no_schedule`
- 返回第一阶段完整排程

### 第一阶段耗尽预算

- `primary.solver_status=FEASIBLE` 或 `UNKNOWN`
- `secondary.attempted=false`
- `secondary.skipped_reason=time_budget_exhausted`
- `selected_stage=primary`

### 第二阶段结果越界

- `secondary.validation_failure_reason=primary_bounds_exceeded`
- `selected_stage=primary`
- 第一阶段排程及工期状态不变

## 5. 错误与兼容

- 请求校验、资源覆盖缺失和服务端运行错误继续使用现有状态码及错误结构。
- 第一阶段已有可行排程时，第二阶段模型错误不升级为接口整体失败；通过阶段摘要和诊断回退。
- 第一阶段本身出现模型错误时，沿用现有接口失败或无排程行为。
- 旧前端忽略新增字段后仍可展示三态结果、指标和排程详情。
