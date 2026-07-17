# 数据模型：AI 方案严格固定资源单次求解

## 1. 方案业务状态 `ResourceAssistantPlanOutcomeStatus`

枚举值：

- `met`：存在可行排程且已满足全部可评估强制目标。
- `not_met`：已证明当前完整目标模型最优，但仍存在目标延期。
- `unconfirmed`：未证明最优且当前结果延期、求解限时内未得到排程，或缺少目标依据。
- `infeasible`：资源覆盖错误或求解器证明物理不可行。

### 状态转换矩阵

| solver_status | 有排程 | 有目标 | 目标延期 | 证明最优 | plan_status |
|---|---:|---:|---:|---:|---|
| `OPTIMAL` | 是 | 是 | 否 | 是 | `met` |
| `FEASIBLE` | 是 | 是 | 否 | 否 | `met` |
| `OPTIMAL` | 是 | 是 | 是 | 是 | `not_met` |
| `FEASIBLE` | 是 | 是 | 是 | 否 | `unconfirmed` |
| `OPTIMAL` / `FEASIBLE` | 是 | 否 | 不适用 | 任意 | `unconfirmed` |
| `UNKNOWN` | 否 | 任意 | 未知 | 否 | `unconfirmed` |
| `INFEASIBLE` | 否 | 任意 | 不适用 | 是 | `infeasible` |
| 资源覆盖错误 | 否 | 任意 | 不适用 | 预校验 | `infeasible` |

`MODEL_INVALID`、非法输入或运行环境缺失不进入该矩阵，按技术失败处理。

## 2. `ResourceAssistantPlanResult` 增量字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `plan_status` | `ResourceAssistantPlanOutcomeStatus \| null` | 有业务求解结果时必填；技术失败可为空 |
| `solver_status` | `string \| null` | 与 `result.status` 一致；技术失败可为空 |
| `input_resource_quantities` | `dict<string, int>` | 本次严格采用的资源数量；非负整数 |
| `resource_expansion_attempted` | `boolean` | AI 路径固定为 `false` |

现有字段 `generated`、`result`、`metrics`、`diagnostics`、`generated_at`、`input_fingerprint` 保持兼容。

## 3. `TargetAchievement` 扩展语义

继续存放于 `ScheduleResult.stats.target_achievement` 和 `objective_breakdown.target_achievement`：

| 字段 | 类型 | 规则 |
|---|---|---|
| `target_status` | 四种业务状态 | AI 路径与 `plan_status` 一致 |
| `solver_status` | string | 原始求解器状态 |
| `business_success` | boolean | 仅 `met` 为 `true` |
| `target_present` | boolean | 是否存在强制里程碑或固定工期依据 |
| `has_schedule` | boolean | 是否有可查看任务排程 |
| `optimality_proven` | boolean | 仅 `OPTIMAL` 为 `true` |
| `hard_milestone_late_days` | int | 所有强制里程碑延期天数合计，非负 |
| `fixed_duration_overrun_days` | int | 固定工期超期天数，非负 |
| `failure_reasons` | string[] | 如 `hard_milestone_late`、`fixed_duration_overrun`、`target_missing`、`time_budget_exhausted`、`missing_compatible_resource` |
| `time_budget_seconds` | number | 本次唯一求解预算 |
| `time_budget_exhausted` | boolean | 是否耗尽预算 |
| `evaluated_at_source` | string | AI 路径固定为 `ai_strict_fixed_resources` |

## 4. 严格固定资源输入快照

`input_resource_quantities` 按资源类型记录本次数量。验证关系：

- 每个值必须等于当前 `ResourceAssistantPlan.resource_pools` 中同类型有效数量。
- `generated.schedule_input.resources` 中同类型命名资源数量不得超过快照值。
- 有工作量且启用的资源按快照展开；工作量为 0、禁用或未映射资源保持为 0。
- 不读取 `max_quantity` 作为本次排程数量。

## 5. 生命周期与失效

```text
方案生成/用户调整
  -> plan_status=null，旧结果失效
  -> 求解中
  -> met | not_met | unconfirmed | infeasible
  -> 再次调整或项目变化
  -> plan_status=null，结果和推荐失效
```

工作流 `solve_status` 继续表达待求解、求解中、失败等页面过程；不得替代 `plan_status`。

## 6. 推荐候选集

```text
eligible_results = [result for result in plan_results if result.plan_status == "met"]
```

- 候选集非空：沿用现有确定性评分和边际收益规则。
- 候选集为空：`recommended_scenario_id=null`，返回无满足目标说明。
- `not_met`、`unconfirmed` 和 `infeasible` 可进入对比展示，不进入推荐评分。
