# 功能规格：移除同类资源工作量均衡目标

**功能目录/分支**：`009-remove-resource-workload-balance`

**创建日期**：2026-07-06

**状态**：草稿，待用户确认后进入实现

**输入**：用户指出目标函数配置中“同类资源工作量均衡”不应再作为目标函数指标。

## 来源与评审上下文

- **来源文档**：`AGENTS.md`、`agent.md`、`README.md`、`docs/精排目标函数算法需求文档_v4.0.md`、`docs/固定资源满足分支详细排程算法文档_v1.6.md`、`specs/007-objective-metric-config/`、`specs/008-objective-model-gating/`。
- **评审结论**：该请求直接改变目标函数项，属于算法和前后端契约变更，按仓库规则走独立 Spec Kit。范围收窄为移除 `resource_workload_balance`，不回退 007/008 中其他目标项。
- **使用的 Demo/代码事实**：
  - `backend/app/models.py` 当前把 `resource_workload_balance` 放入 `ObjectiveTermId`、默认权重和 `OBJECTIVE_METRIC_DEFINITIONS`。
  - `backend/app/solver.py` 当前用 `resource_workload_balance_enabled` 控制 `workload_balance_terms`，并在 `model.Minimize(...)` 中按权重计入目标函数。
  - `backend/app/solver.py` 当前在 `objective_breakdown`、`objective_contributions` 和资源组织诊断中输出同类资源工作量均衡相关字段。
  - `frontend/src/app/App.tsx` 和 `frontend/src/types/scheduler.ts` 当前把该项作为可配置目标项展示，并在旧结果拆解中合成贡献。
- **不在范围内**：
  - 不移除“未配置资源普通工程均衡”目标。
  - 不调整 `resource_idle`、`resource_path_continuity`、`resource_slot_balance`、`target_relaxation` 等其他目标项。
  - 不改变资源互斥、命名资源分配、同结构同工艺、工作面并行、里程碑等硬约束。
  - 不删除资源工作量原始诊断数据；只是不再将其解释为目标函数贡献。
  - 不修改 `README.md`，不提交 git。

## Clarifications

### Session 2026-07-06

- Q: 移除到什么程度？ -> A: 从目标函数、可配置目标项、默认权重、贡献拆解中移除；保留资源工作量原始诊断。
- Q: 历史请求仍带 `resource_workload_balance` 怎么办？ -> A: 作为废弃目标兼容忽略，不让旧场景因该字段报错。

## 用户场景与测试

### 用户故事 1 - 目标函数不再优化同类资源工作量差异（优先级：P1）

作为排程用户，我在运行“固定资源条件下推算最短工期”或综合精排时，不希望求解器为了让同类资源工作天数接近而牺牲更重要的控制节点、总工期、资源空闲或路径连续性。

**优先级理由**：这是本次变更的核心价值，直接影响 CP-SAT 目标函数和结果解释。

**独立测试**：使用包含多台同类资源的场景求解，确认返回结果的 `objective_weights`、`objective_terms_used`、`objective_contributions` 均不包含 `resource_workload_balance`，且加权目标不含该贡献。

**验收场景**：

1. **假设** 默认目标函数配置已加载，**当** 用户打开模拟求解目标函数配置，**则** 不再看到“同类资源工作量均衡”这一行。
2. **假设** 求解场景中存在多台同类资源且工作量不均，**当** 求解器构建目标函数，**则** 不创建 `workload_balance_terms`，也不把工作量差异乘权重加入 `model.Minimize(...)`。

---

### 用户故事 2 - 历史配置兼容但不生效（优先级：P2）

作为使用历史 Excel 导入数据或旧场景配置的用户，我希望旧请求中仍带 `resource_workload_balance` 时系统不要失败，但该字段不再产生目标函数影响。

**优先级理由**：Excel 生成数据和本地配置可能仍缓存旧目标项，兼容处理可以避免用户已有案例突然 422 或无法求解。

**独立测试**：构造请求中包含 `objective_terms.resource_workload_balance` 的场景，确认后端接受并过滤该字段，结果中没有该目标贡献。

**验收场景**：

1. **假设** 旧场景请求包含 `resource_workload_balance: { enabled: true, weight: 100 }`，**当** 后端解析 `ScheduleStrategyConfig`，**则** 该字段被当作废弃目标忽略。
2. **假设** 旧结果对象仍有 `resource_workload_balance_penalty`，**当** 前端展示目标贡献，**则** 不从旧字段重新合成“同类资源工作量均衡”贡献项。

---

### 用户故事 3 - 资源工作量仍可诊断但不称为目标（优先级：P3）

作为排程复核人员，我仍希望查看每台资源承担了多少工作、同类资源工作量差异是多少，但这些信息应被理解为诊断数据，而不是求解器正在优化的目标。

**优先级理由**：避免把目标项移除后连基础复核数据也丢失，降低结果解释风险。

**独立测试**：求解后检查 `resource_organization_analysis.resource_types` 仍包含 `active_days`、`min_workload_days`、`max_workload_days`、`workload_range_days` 等原始统计，同时目标贡献中无 `resource_workload_balance`。

**验收场景**：

1. **假设** 求解结果包含资源组织诊断，**当** 用户查看资源详情，**则** 可以看到资源活跃天数和工作量范围等原始统计。
2. **假设** 同类资源工作量差异较大，**当** 用户查看目标贡献，**则** 不显示“同类资源工作量均衡”的权重、原始罚分或加权贡献。

### 边界与异常场景

- 当所有其他目标项都被关闭时，仍需沿用现有“至少一个目标项启用”的校验，不允许靠废弃的 `resource_workload_balance` 通过校验。
- 当旧配置只启用 `resource_workload_balance` 时，过滤后应触发现有“至少一个目标项启用”校验，而不是悄悄恢复该目标。
- 当结果来自旧缓存并包含 `resource_workload_balance_penalty` 时，前端只可保留原始字段兼容读取，不得把它展示成当前目标函数贡献。
- 当 `resource_idle` 启用时，求解器仍可为了计算空闲天数建立资源工作量辅助变量，但这些变量不得形成工作量均衡目标项。

## 需求

### 功能需求

- **FR-001**：系统必须从当前可配置目标项集合中移除 `resource_workload_balance`，包括后端 `ObjectiveTermId`、默认权重、目标指标定义、前端类型定义和目标项展示定义。
- **FR-002**：系统必须把 `resource_workload_balance` 作为废弃目标项兼容处理；旧请求传入该字段时应忽略该字段，不得让它进入有效目标项集合。
- **FR-003**：求解器不得在 CP-SAT 目标函数中创建或累加同类资源工作量均衡罚分；`model.Minimize(...)` 不得包含 `workload_balance_terms * resource_workload_balance_weight`。
- **FR-004**：`objective_modeling_gates`、`objective_terms_used`、`objective_weights` 和 `objective_contributions` 不得再输出 `resource_workload_balance` 作为当前目标项。
- **FR-005**：结果拆解中的旧字段 `resource_workload_balance_penalty` 和 `resource_balance_weight` 不得再作为当前目标函数贡献来源；如保留旧字段，只能用于兼容或诊断。
- **FR-006**：前端目标函数配置表不得显示“同类资源工作量均衡”，旧结果拆解 fallback 也不得重新合成该目标项。
- **FR-007**：资源组织诊断应保留每台资源和同类资源分组的原始工作量统计；聚合状态如果依赖已移除目标，应显示为未评价或诊断态，而不是目标已启用。
- **FR-008**：后端测试必须覆盖默认目标项集合、废弃字段兼容、求解结果贡献缺失和只启用废弃字段时的失败校验。
- **FR-009**：前端类型和展示必须与后端目标项集合一致，避免 UI 中出现后端已废弃的目标项。

### 关键实体

- **目标函数指标定义**：由目标项 ID、名称、分组、默认权重、来源、适用分支和旧字段映射组成；本变更删除 `resource_workload_balance`。
- **目标函数配置**：用户或默认场景传入的 `objective_terms`；本变更将 `resource_workload_balance` 归入废弃输入。
- **目标贡献拆解**：求解后返回的 `objective_contributions`；本变更要求该列表不再包含 `resource_workload_balance`。
- **资源组织诊断**：求解后返回的资源活跃天数、空闲、路径连续性和工作量统计；本变更只改变其目标解释，不删除原始统计。

## 成功标准

### 可衡量结果

- **SC-001**：目标函数配置表中“同类资源工作量均衡”出现次数为 0。
- **SC-002**：默认 `objective_terms`、`OBJECTIVE_METRIC_DEFINITIONS`、前端 `objectiveTermDefinitions` 中均不包含 `resource_workload_balance`。
- **SC-003**：典型 Excel 导入场景求解结果中，`objective_contributions[*].term_id` 不包含 `resource_workload_balance`。
- **SC-004**：旧请求中带 `resource_workload_balance` 时，如果还有其他有效目标项，后端可继续求解且忽略该废弃字段。
- **SC-005**：只启用 `resource_workload_balance` 的旧请求不能作为有效目标配置通过，必须触发现有“至少一个目标项启用”的校验。
- **SC-006**：后端相关测试和前端构建验证通过。

## 默认假设

- 本次需求只移除同类资源工作量均衡这个目标项，不代表资源工作量统计没有业务价值。
- 目标项移除后，资源路径连续性、资源空闲和资源槽位均衡仍继续承担资源组织类优化。
- 历史结果中的旧字段可能仍存在，但当前结果解释以 `objective_contributions` 为准。
