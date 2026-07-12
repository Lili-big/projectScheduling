# 数据模型：三方案资源策略基线与 LLM 校验

## 1. ResourceWorkloadState（服务内部值对象）

| 字段 | 类型 | 含义 |
|---|---|---|
| `resource_type` | string | 资源类型唯一标识 |
| `status` | enum | `ACTIVE`、`UNUSED_OR_UNMAPPED`、`DISABLED`、`UNLIMITED`、`DATA_INVALID` |
| `matched_task_count` | integer | 匹配任务数量 |
| `total_required_days` | integer | 累计资源需求工期 |
| `current_quantity` | integer/null | 当前资源数量 |
| `max_quantity` | integer/null | 原始上限；空值表示无显式上限 |
| `diagnostic_reason` | string | 状态判定依据 |

### 校验规则

- `matched_task_count = 0` 或 `total_required_days = 0` 时不得为 `ACTIVE`。
- `enabled = false` 时为 `DISABLED`，三版数量均为 0。
- 映射缺失或关键数据不合法时为 `UNUSED_OR_UNMAPPED` 或 `DATA_INVALID`，不得生成正数。
- `UNLIMITED` 表示存在有效工作量但无显式上限，仍受其他规则约束。

## 2. DeterministicPlanBaseline（服务内部值对象）

| 字段 | 类型 | 含义 |
|---|---|---|
| `profile` | enum | `economy`、`balanced`、`crash` |
| `resource_quantities` | map<string, integer> | 全部已知资源类型的基线数量 |
| `calculation_reasons` | map<string, string> | 每类资源计算依据 |
| `organization_strategy` | string | 本地回退策略说明 |

### 校验规则

- 三个方案必须齐全且标识唯一。
- 零工作量、禁用或异常资源为 0。
- 对有效资源满足 `economy <= balanced <= crash`。
- 数量必须为非负整数且不超过原始 `max_quantity`。

## 3. PlanValidationIssue（服务内部值对象）

| 字段 | 类型 | 含义 |
|---|---|---|
| `code` | string | 稳定错误代码，如 `ZERO_WORKLOAD_NONZERO` |
| `profile` | string/null | 关联方案 |
| `resource_type` | string/null | 关联资源类型 |
| `actual` | unknown | 草案实际值 |
| `expected` | string | 期望边界摘要 |

## 4. LLM 方案对象（现有共享对象）

继续使用现有字段：`profile`、`positioning`、`resource_quantities`、`organization_strategy`、`generation_rationale`、`applicable_scenarios`、`expected_risks`。本功能不新增响应字段。

## 状态流转

```text
任务需求 -> 资源工作量状态 -> 确定性三方案基线
                              -> LLM 草案 -> 合法 -> 现有方案响应
                                         -> 非法 -> 一次纠错重试
                                                  -> 合法 -> 现有方案响应
                                                  -> 非法/异常 -> 基线回退
```
