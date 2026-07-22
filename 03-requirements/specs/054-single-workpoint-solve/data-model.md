# 数据模型：单工点模拟求解

## 1. SolveScope（求解范围）

请求级、非持久化值对象，描述一次生成或求解覆盖的项目范围。

| 字段 | 类型 | 必填 | 规则 |
|---|---|---:|---|
| `mode` | `ALL \| WORKPOINT` | 是 | `ALL` 表示全项目；`WORKPOINT` 表示单个桥梁工点 |
| `workpoint_id` | `string \| null` | 是 | `WORKPOINT` 时必须是当前已物化项目中的桥梁工点稳定 ID；`ALL` 时必须为 `null` |
| `workpoint_name` | `string \| null` | 是 | `WORKPOINT` 时取项目主数据权威名称；`ALL` 时必须为 `null` |

### 来源与生命周期

- 请求输入只提供可选 `workpoint_id`。
- 后端在项目主数据物化后解析成完整 `SolveScope`，不信任前端提交名称。
- 不写入 `ScenarioInput`、项目主数据、本地配置或方案存储。
- 每个 `GeneratedScheduleInput` 必须携带一个范围对象；旧请求生成 `ALL`。

## 2. ScopedSolveFingerprint（范围化求解指纹）

前端派生值，用于判断生成输入、求解结果和固定工期基准是否仍属于当前请求。

| 组成 | 规则 |
|---|---|
| 规范化场景 | 继续使用现有 `normalizeScenarioForWorkspace` 后的完整 `ScenarioInput` |
| 范围模式 | 空工点选择映射为 `ALL`，非空映射为 `WORKPOINT` |
| 工点 ID | `WORKPOINT` 时纳入稳定 ID；`ALL` 时为 `null` |

该指纹只存在于前端状态，不进入后端持久化。场景或范围任一变化都必须使当前生成输入、求解结果、固定工期基准和比较状态失效。

## 3. GeneratedScheduleInput 范围扩展

现有实体增加：

| 字段 | 类型 | 规则 |
|---|---|---|
| `solve_scope` | `SolveScope` | 必填；是生成预览、主求解和备选结果的范围权威 |

`source_summary` 继续承载数量和来源统计，不复制可被业务判断依赖的第二份范围状态。

## 4. 范围化对象关系

```text
ScenarioInput（不变）
  + request.workpoint_id（临时）
      -> materialized ProjectModel（完整）
      -> SolveScope
      -> GeneratedScheduleInput.solve_scope
           -> ScheduleInput（范围化任务/关系/资源/里程碑）
           -> ScenarioSolveResult.generated.solve_scope
           -> ScenarioAlternativeResult.generated.solve_scope
```

## 5. 状态与转换

### 前端范围状态

```text
ALL（默认）
  --选择桥梁工点--> WORKPOINT(selected_id)
  --选择全部工点--> ALL
  --当前版本删除/改变所选工点--> INVALID_SELECTION
```

- `ALL` 与 `WORKPOINT` 之间切换：立即失效当前生成、求解、基准和比较状态。
- `INVALID_SELECTION`：禁止求解并提示重新选择；后端收到过期 ID 时返回 422。
- `SOLVING`：范围选择不可改变，或迟到响应必须按发起指纹丢弃。

## 6. 范围化集合不变量

- `tasks`：单工点模式下每个 `task.bridge_id == solve_scope.workpoint_id`。
- `precedence_links`：每条关系的前后任务都存在于范围化任务集合。
- `resources`：每个资源均能服务至少一个范围化任务；池 ID、授权集合和共享/独享模式不改写。
- `milestones`：每个里程碑按统一匹配规则至少命中一个范围化任务。
- `diagnostics`：资源错误只针对范围化任务；项目主数据物化诊断仍可保留完整来源信息，但不得改变范围化求解模型。
- `alternative_results`：每个备选结果的 `solve_scope` 必须与主结果相同。

## 7. 比较与保存规则

- 只有 `solve_scope.mode == ALL` 的结果可以进入现有保存集合。
- `compare_scenarios` 只接受全部为 `ALL` 的结果；`WORKPOINT` 或混合范围返回明确错误。
- 本期不定义单工点结果持久化实体、局部结果合并或局部方案审批状态。
