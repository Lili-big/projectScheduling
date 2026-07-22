# 数据模型：统一固定资源与最少资源求解

## 原则

- 不新增持久化实体、数据库表或 `ScenarioInput` 字段。
- 顶层 API 请求/响应继续使用现有 Pydantic 与 TypeScript 类型。
- 056 新语义通过现有 `ScheduleResult.stats`、`ScheduleResult.objective_breakdown` 和 AI `ResourceAssistantPlanResult` 字段表达。
- `stats` 是运行诊断权威，`objective_breakdown` 为结果展示保留同名兼容摘要；共享字段的值必须一致。

## 1. FixedResourceSolveContext（运行时）

simulation/AI 共用 application 包装的输入上下文；权威 solver 内核仍只接收 `ScheduleInput` 和可选固定工期目标。不持久化，不要求新建公开 Pydantic 模型。

| 字段 | 类型 | 来源 | 规则 |
|---|---|---|---|
| `generated` | `GeneratedScheduleInput` | Scenario generation | 已完成 `ALL/WORKPOINT` 裁剪和资源展开 |
| `entrypoint` | `simulation | ai | minimum_resource_detail` | 调用方 | 只影响来源包装，不改变算法 |
| `time_limit_seconds` | `float` | `ScenarioInput` / `ScheduleInput` | 最小 0.1 秒；一次调用使用完整预算 |
| `fixed_duration_target_days` | `int?` | 强制里程碑或同范围 fallback | 仅最少资源详细验证可能显式传入 |
| `candidate_resource_counts` | `map<resource_pool_id,int>?` | 全局搜索 | 仅 `minimum_resource_detail` 存在 |

### 验证

- generation 含 `error` 时不进入内核。
- `generated.schedule_input.resources` 是唯一资源数量事实；内核不得读取 `max_quantity` 补足或另行生成资源。
- `solve_scope` 已由 054 校验；内核不得改变或跨范围查找。

## 2. UnifiedFixedResourceMetadata（现有扩展字典）

同时写入 `ScheduleResult.stats` 与 `objective_breakdown` 的新结果元数据。

| 字段 | 类型 | 允许值/说明 |
|---|---|---|
| `solve_mode` | string | `unified_fixed_resource` |
| `schedule_source` | string | `unified_fixed_resources`、`ai_strict_fixed_resources` 或 `minimum_resources_fixed_detail` |
| `solver_call_count` | integer | 固定为 `1` |
| `resource_expansion_attempted` | boolean | 固定为 `false` |
| `performance_path` | string | `unified_fixed_resource_single_stage` |
| `optimization_stages.primary.attempted` | boolean | `true` |
| `optimization_stages.secondary.attempted` | boolean | `false` |
| `optimization_stages.secondary.skipped_reason` | string | `not_applicable` |
| `alternative_output_status` | string | `not_applicable` |
| `resource_recommendation_status` | string | 固定资源入口为 `not_applicable`；最少资源详细入口由候选验证状态决定 |
| `max_target_delay_days` | integer | 强制里程碑延期与固定工期超期的最大值，非负 |
| `objective_priority` | string[] | 固定为 `max_target_delay_days`, `makespan_days` |

### 兼容

- 现有 `baseline_makespan_days`、`capacity_precheck_status`、`balanced_reoptimization_status`、`unbalanced_reoptimization_status`、`reoptimization_attempts` 等键如继续返回，新结果值分别为 `null`、`not_run`、`not_run`、`not_run`、`[]`。
- 历史结果保留旧值；读取端按 `schedule_source`/`performance_path` 区分，不改写。
- `ScenarioSolveResult.alternative_results` 对新固定资源结果始终为空数组。

## 3. TargetAchievement（现有扩展字典）

固定资源和最少资源详细排程的统一业务结论。

| 字段 | 类型 | 规则 |
|---|---|---|
| `business_success` | boolean | 仅 `target_status == met` |
| `target_status` | enum | `met | not_met | unconfirmed | infeasible` |
| `solver_status` | string | 原始 `ScheduleResult.status` |
| `selected_schedule_solver_status` | string? | 有阶段包装时与最终排程状态一致 |
| `target_present` | boolean | 当前范围至少有可评估强制目标或固定工期目标 |
| `has_schedule` | boolean | `tasks` 非空且日期/分配可用 |
| `optimality_proven` | boolean | 原始 solver 状态为 `OPTIMAL` |
| `hard_milestone_late_days` | integer | 匹配强制里程碑延期合计，非负 |
| `fixed_duration_overrun_days` | integer | 相对固定工期目标超期天数，非负 |
| `max_target_delay_days` | integer | 单个目标最大延期，非负 |
| `failure_reasons` | string[] | 去重的稳定原因码 |
| `evaluated_at_source` | string | 与入口/候选来源一致 |

### 状态转移矩阵

| solver 状态 | 有排程 | 有目标 | 最大延期 | `target_status` |
|---|---:|---:|---:|---|
| `OPTIMAL` | 是 | 是 | 0 | `met` |
| `FEASIBLE` | 是 | 是 | 0 | `met` |
| `OPTIMAL` | 是 | 是 | >0 | `not_met` |
| `FEASIBLE` | 是 | 是 | >0 | `unconfirmed` |
| `OPTIMAL/FEASIBLE` | 是 | 否 | 任意 | `unconfirmed` |
| `UNKNOWN` | 否或不完整 | 任意 | 任意 | `unconfirmed` |
| `INFEASIBLE/MODEL_INVALID` | 否 | 任意 | 任意 | `infeasible` |

任何有可用排程的 `not_met` 或 `unconfirmed` 结果必须保留 `tasks`、`resource_allocations` 与 `milestone_results`。

## 4. GlobalMinimumResourceCandidate（现有扩展字典）

一次全局数量搜索的输出。

| 字段 | 类型 | 规则 |
|---|---|---|
| `search_status` | solver status | `OPTIMAL | FEASIBLE | UNKNOWN | INFEASIBLE | MODEL_INVALID` |
| `search_lower_bounds` | `map<pool_id,int>` | 模拟入口默认全部为 0 |
| `search_upper_bounds` | `map<pool_id,int>` | 来自各池 `max_quantity` |
| `recommended_resource_counts` | `ResourceCount[]` | 仅有候选时存在，保留稳定池身份/范围 |
| `candidate_total_quantity` | integer | 推荐数量总和 |
| `candidate_makespan_days` | integer? | 全局模型中第二目标值 |
| `resource_count_optimality` | string | `optimal | feasible | unconfirmed | infeasible` |
| `global_search_call_count` | integer | 固定工期入口最多 1 |

### ResourceCount

复用现有资源数量结果结构，至少包含：

- `resource_pool_id`
- `resource_type`
- `scope_mode`
- `workpoint_id`
- `eligible_workpoint_ids`
- `current_quantity`
- `recommended_quantity`
- `max_quantity`

`recommended_quantity` 可小于、等于或大于 `current_quantity`，但必须在 `0..max_quantity` 内。数量 0 表示该池不展开命名资源，不得自动补 1。

## 5. MinimumResourceVerification（现有扩展字典）

连接全局候选与一次详细排程的证据。

| 字段 | 类型 | 规则 |
|---|---|---|
| `candidate_found` | boolean | 全局搜索返回可用数量组合 |
| `candidate_verified` | boolean | 仅详细 `target_status == met` |
| `detail_solve_attempted` | boolean | 仅有候选时为 true |
| `detail_solver_call_count` | integer | 0 或 1 |
| `detail_target_status` | TargetStatus? | 详细排程四态 |
| `detail_solver_status` | string? | 详细排程原始状态 |
| `retry_attempted` | boolean | 固定为 false |
| `retry_reason` | string? | 固定为空 |

### 状态流转

```text
global UNKNOWN      -> unconfirmed, detail_solve_attempted=false
global INFEASIBLE   -> infeasible,  detail_solve_attempted=false
global MODEL_INVALID-> infeasible,  detail_solve_attempted=false
global candidate    -> exactly one unified fixed-resource detail solve
detail met          -> candidate_verified=true
detail other        -> candidate_verified=false, keep candidate and detail result, stop
```

## 6. 前端派生视图

前端不新增持久状态，只从结果派生：

- `fixedObjectiveSummary`：最大目标延期优先、总工期其次、资源组织仅诊断。
- `fixedSolveOutcome`：业务四态、solver 状态、最大延期、总工期、一次调用、未自动增配。
- `minimumResourceOutcome`：全局候选列表、搜索状态、详细状态、是否验证、无重试。
- `legacySolveNotice`：旧 `schedule_source`/多阶段字段存在时显示历史口径，不映射成 056 新结果。

## 7. 不变实体

以下实体仅被读取或复用，本功能不改变其结构和规则：

- `ScenarioInput`、`GeneratedScheduleInput`、`ScheduleInput`
- `TaskInput`、`ResourceInput`、`MilestoneInput`
- `SolveScope`
- `ScenarioSolveResult`、`ScheduleResult`
- `ResourceAssistantSingleSolveRequest/Response`
- 项目主数据、工效/工艺配置、架梁专项模型
