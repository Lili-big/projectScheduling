# 数据模型：统一目标函数求解与资源分支重构

本功能遵循“如非必要，勿增实体”。以下对象优先作为现有 `ScheduleResult.stats`、`objective_breakdown`、资源池和分支结果中的嵌入式字段或内部数据结构表达，不新增持久化业务实体。

## 既有对象影响

### `ScenarioInput`

**角色**：用户当前编辑的项目、资源、工艺、逻辑规则、里程碑和求解策略入口。

**本期影响**：

- 继续使用 `ResourcePool.quantity` 作为当前默认资源数量。
- 继续使用 `ResourcePool.max_quantity` 作为可增配上限。
- 继续使用现有里程碑和固定工期输入作为目标达成判定来源。
- 不新增持久化场景实体。

**校验规则**：

- 资源搜索下界不得低于当前默认资源数量。
- 资源搜索上界不得超过最大资源数量。
- 若最大资源数量小于当前默认资源数量，按现有资源配置合法化规则处理，不生成非法搜索区间。

### `ScheduleInput`

**角色**：CP-SAT 求解器的标准输入。

**本期影响**：

- 需要支持将硬里程碑目标作为目标函数项建模，而不是默认作为阻断式硬约束。
- 需要支持在当前资源、最大资源和候选资源之间复用同一生成逻辑。
- 需要接受剩余时间预算，避免每个内部阶段独立 15 秒。

**校验规则**：

- 同结构同工艺规则仍作为施工组织硬规则传入求解器。
- 固定工期目标不应再被解释为“无可展示排程”的唯一原因。

### `ScheduleResult`

**角色**：单次 CP-SAT 排程结果和用户可见结果的载体。

**本期影响**：

- 保留 `solver_status`、`scheduled_tasks`、`resource_allocations`、`objective_breakdown`、`stats` 等既有结构。
- 在 `stats.target_achievement` 中新增统一目标达成字段。
- `objective_breakdown` 需要体现硬里程碑晚点目标项的权重、原始天数和加权贡献。

**校验规则**：

- `OPTIMAL` 或 `FEASIBLE` 且目标达成指标为 0 时，业务状态才可为成功。
- `OPTIMAL` 或 `FEASIBLE` 但硬里程碑晚点或固定工期超期时，业务状态为失败且结果应可查看。
- `UNKNOWN`、超时或预算耗尽不得标记为无解。

## 嵌入对象：目标达成结果

### `TargetAchievement`

**角色**：统一描述排程结果是否达成业务目标。

**建议字段**：

| 字段 | 类型 | 含义 |
|------|------|------|
| `business_success` | boolean | 是否达成业务目标 |
| `target_status` | string | 目标达成状态枚举 |
| `solver_status` | string | CP-SAT 原始状态 |
| `hard_milestone_late_days` | number | 硬里程碑累计晚点天数 |
| `fixed_duration_overrun_days` | number | 固定工期超期天数 |
| `failure_reasons` | string[] | 业务失败或未确认原因 |
| `time_budget_seconds` | number | 单次用户动作总预算 |
| `time_budget_exhausted` | boolean | 是否耗尽预算 |
| `evaluated_at_source` | string | 当前资源、最大资源或候选资源来源 |

**`target_status` 建议值**：

- `met`：目标达成。
- `current_resources_target_failed`：当前默认资源可排程但未达成目标。
- `candidate_resources_target_met`：候选资源复排后目标达成。
- `candidate_resources_target_failed`：候选资源复排后仍未达成目标。
- `max_resources_target_failed`：最大资源硬里程碑和固定工期窗口快速预检未达成目标。
- `physical_infeasible`：施工硬规则或资源配置导致无可展示排程。
- `unconfirmed`：限时内无法确认。

**状态转换**：

```text
CP-SAT 物理可行结果
  -> 晚点/超期均为 0 -> met
  -> 当前资源晚点或超期 -> current_resources_target_failed
  -> 最大资源晚点或超期 -> max_resources_target_failed
  -> 候选资源晚点或超期 -> candidate_resources_target_failed

CP-SAT 无物理可行排程
  -> physical_infeasible

CP-SAT UNKNOWN 或总预算耗尽
  -> unconfirmed
```

**校验规则**：

- `business_success = true` 时，`hard_milestone_late_days` 和 `fixed_duration_overrun_days` 必须为 0。
- `target_status = max_resources_target_failed` 时，不得继续输出超过 `max_quantity` 的资源推荐。
- `target_status = unconfirmed` 时，不得展示“无解”或“最大资源不满足”的确定性结论。

## 嵌入对象：资源搜索范围

### `ResourceSearchRange`

**角色**：描述新增资源分支或固定工期求资源的搜索边界。

**建议字段**：

| 字段 | 类型 | 含义 |
|------|------|------|
| `resource_type` | string | 资源类型 |
| `current_quantity` | number | 当前默认投入数量 |
| `max_quantity` | number | 最大可增配数量 |
| `lower_bound` | number | 实际搜索下界 |
| `upper_bound` | number | 实际搜索上界 |

**校验规则**：

- `lower_bound >= current_quantity`。
- `upper_bound <= max_quantity`。
- `lower_bound <= upper_bound`，否则资源搜索分支应返回合法化诊断。

## 嵌入对象：资源候选结果

### `ResourceCandidateOutcome`

**角色**：描述推荐资源数量及其复排验证结果。

**建议字段**：

| 字段 | 类型 | 含义 |
|------|------|------|
| `candidate_quantities` | object | 推荐资源数量 |
| `added_quantities` | object | 相对当前默认资源的增量 |
| `search_range` | `ResourceSearchRange[]` | 搜索边界 |
| `verification_result_source` | string | 候选资源复排结果来源 |
| `target_achievement` | `TargetAchievement` | 候选资源复排后的目标达成结果 |

**校验规则**：

- 候选资源必须代入完整目标函数复排后才可作为返回结果。
- 候选资源数量不得小于当前默认资源数量，不得超过最大资源数量。
- 候选资源复排未达成目标时，不能标记为推荐成功，只能作为失败候选或诊断。

## 目标函数配置影响

### `ObjectiveTermConfig`

**角色**：现有目标函数项配置。

**本期影响**：

- 权重上限需要支持 `10000000000`。
- 硬里程碑晚点目标项默认权重为 `10000000000`。
- 固定工期超期可复用现有目标项或作为目标达成判定指标输出；若实现阶段需要新增目标项，必须在 analyze 中列明原因和兼容影响。

**校验规则**：

- 缺失目标项按本期默认值补齐。
- 旧配置权重仍需兼容，不得因上限调整破坏旧请求。
- 目标贡献输出必须能区分原始晚点/超期天数和加权贡献。

## 施工组织规则

### 同结构同工艺规则

**角色**：当前桩基机械钻机资源组织硬规则。

**适用范围**：

- 旋挖钻。
- 冲击钻。
- 回旋钻。

**校验规则**：

- 不因硬里程碑目标化或固定工期目标化而放松。
- 不默认扩展到模板、人工班组或其他未确认资源类型。
- 相关测试应覆盖“业务成功结果仍不违反该规则”。
