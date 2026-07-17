# 功能规格：移除未配置资源普通工程均衡目标

**功能目录/分支**：`010-remove-unconfigured-normal-balance`

**创建日期**：2026-07-06

**状态**：草稿，待用户确认后进入实现

**输入**：用户要求“在目标函数中移除未配置资源普通工程均衡的指标”。

## 来源与评审上下文

- **来源文档**：`AGENTS.md`、`agent.md`、`docs/精排目标函数算法需求文档_v4.0.md`、`docs/固定资源满足分支详细排程算法文档_v1.6.md`、`specs/004-normal-work-balance/`、`specs/007-objective-metric-config/`、`specs/009-remove-resource-workload-balance/`。
- **评审结论**：该请求改变目标函数和前后端目标项契约，必须走独立 Spec Kit。010 只移除 `unconfigured_normal_balance`，不回退 009 已完成的 `resource_workload_balance` 移除。
- **使用的 Demo/代码事实**：
  - `backend/app/models.py` 当前把 `unconfigured_normal_balance` 放入有效 `ObjectiveTermId`、默认权重和 `OBJECTIVE_METRIC_DEFINITIONS`。
  - `backend/app/solver.py` 当前通过 `_build_unconfigured_normal_balance_terms()` 构建 CP-SAT 目标项，并在 `model.Minimize(...)` 中按 `objective_weights["unconfigured_normal_balance"]` 加权。
  - `backend/app/solver.py` 当前在 `objective_breakdown` 和 `objective_contributions` 输出 `unconfigured_normal_balance` 罚分、权重、评分和贡献。
  - `frontend/src/app/App.tsx` 和 `frontend/src/types/scheduler.ts` 当前把该项作为可配置目标项展示，并在旧结果拆解中合成贡献。
- **不在范围内**：
  - 不恢复或修改 009 中已移除的 `resource_workload_balance`。
  - 不移除 `normal_balance_metrics` 原始诊断统计。
  - 不改变普通工程时间窗口、工作面并行上限、控制链识别、硬约束和资源互斥。
  - 不修改 `README.md`，不提交 git。

## Clarifications

### Session 2026-07-06

- Q: 移除到什么程度？ -> A: 从目标函数、默认权重、前端可配置项、目标贡献和 CP-SAT 加权项中移除；保留普通工程分布诊断。
- Q: 旧配置仍带 `unconfigured_normal_balance` 怎么办？ -> A: 作为废弃目标兼容忽略，不让旧场景因为该字段报错。

## 用户场景与测试

### 用户故事 1 - 未配置资源普通工程均衡不再影响求解（优先级：P1）

作为排程用户，我希望精排只按当前有效目标项优化，不再为了把未配置命名资源的普通工程均匀铺排而改变求解选择。

**优先级理由**：这是本次变更的核心目标，直接影响 CP-SAT 目标函数。

**独立测试**：构造含未配置命名资源普通工程的场景求解，确认目标权重、目标项使用、建模门控和目标贡献均不包含 `unconfigured_normal_balance`。

**验收场景**：

1. **假设** 默认目标函数配置已加载，**当** 用户打开目标函数配置，**则** 不再看到“未配置资源普通工程均衡”。
2. **假设** 场景中存在未配置命名资源的普通工程，**当** 求解器构建目标函数，**则** 不创建或累加 `unconfigured_normal_balance` 罚分项。

---

### 用户故事 2 - 旧场景兼容但不生效（优先级：P2）

作为使用历史配置或 Excel 导入案例的用户，我希望旧请求里仍带 `unconfigured_normal_balance` 时系统不失败，但该字段不再进入当前目标函数。

**优先级理由**：007 曾把该项纳入可配置目标，历史本地配置可能仍包含该字段。

**独立测试**：构造请求包含 `objective_terms.unconfigured_normal_balance`，确认后端过滤该字段；如果还有其他有效目标项可继续求解，如果只剩该废弃目标则触发现有“至少一个目标项启用”校验。

**验收场景**：

1. **假设** 旧请求包含 `unconfigured_normal_balance: { enabled: true, weight: 10 }` 且其他有效目标项启用，**当** 后端解析配置，**则** 该字段被忽略且求解继续。
2. **假设** 旧请求只启用 `unconfigured_normal_balance`，**当** 后端解析配置，**则** 过滤后因没有有效目标项而失败。
3. **假设** 旧结果包含 `unconfigured_normal_balance_penalty` 或 `normal_balance_penalty`，**当** 前端展示目标贡献 fallback，**则** 不从这些旧字段生成当前目标贡献。

---

### 用户故事 3 - 普通工程分布仍可诊断（优先级：P3）

作为排程复核人员，我仍希望看到普通工程是否集中、桶分布如何、评分如何，但这些信息应是只读诊断，不是目标函数指标。

**优先级理由**：移除目标项不能让结果解释失去普通工程分布信息。

**独立测试**：求解后检查 `stats.normal_balance_metrics` 仍输出普通工程数量、已配置/未配置资源数量、桶分布、峰值、低谷和评分；目标贡献中无 `unconfigured_normal_balance`。

**验收场景**：

1. **假设** 存在普通工程任务，**当** 求解结束，**则** `normal_balance_metrics` 仍能用于解释普通工程时间分布。
2. **假设** 普通工程集中在短时间内，**当** 用户查看结果贡献，**则** 不显示“未配置资源普通工程均衡”的权重、原始罚分或加权贡献。

### 边界与异常场景

- 当所有其他有效目标项都关闭时，废弃的 `unconfigured_normal_balance` 不得让配置通过。
- 当旧结果含 `normal_balance_penalty` 时，前端不得把它合成为当前目标贡献；可作为诊断兼容字段读取。
- 当 `normal_balance_metrics` 没有可评价普通工程时，应继续显示未评价或 0 评分，不影响求解状态。
- 该变更不得改变硬约束和普通工程窗口/工作面并行约束。

## 需求

### 功能需求

- **FR-001**：系统必须从有效目标项集合中移除 `unconfigured_normal_balance`，包括后端目标项 ID、默认权重、目标指标定义、前端类型定义和目标项展示定义。
- **FR-002**：系统必须把 `unconfigured_normal_balance` 作为废弃目标输入兼容处理，旧请求传入该字段时过滤掉。
- **FR-003**：求解器不得在 CP-SAT 目标函数中构建或累加 `unconfigured_normal_balance` 目标项；`model.Minimize(...)` 不得包含该项加权贡献。
- **FR-004**：`objective_weights`、`objective_terms_used`、`objective_modeling_gates`、`objective_contributions` 不得输出 `unconfigured_normal_balance` 作为当前目标项。
- **FR-005**：结果拆解中的旧字段 `unconfigured_normal_balance_penalty`、`unconfigured_normal_balance_weight`、`unconfigured_normal_balance_score`、`normal_balance_penalty` 不得再作为当前目标贡献来源；如保留旧字段，只能用于兼容诊断。
- **FR-006**：前端目标函数配置表不得显示“未配置资源普通工程均衡”，旧结果贡献 fallback 不得从 `unconfigured_normal_balance_penalty` 或 `normal_balance_penalty` 合成该目标项。
- **FR-007**：`normal_balance_metrics` 应继续作为只读诊断输出，保留普通工程任务数、已配置/未配置资源任务数、桶分布、峰值/低谷和评分等信息。
- **FR-008**：后端测试必须覆盖默认目标项集合、废弃字段兼容、只启用废弃字段失败、求解结果无目标贡献和诊断保留。
- **FR-009**：前端类型和展示必须与后端目标项集合一致，不得出现后端已废弃的目标项。

### 关键实体

- **目标函数指标定义**：当前可配置并参与贡献解释的目标项集合；本变更删除 `unconfigured_normal_balance`。
- **目标函数配置**：用户或旧场景传入的 `objective_terms`；本变更将 `unconfigured_normal_balance` 作为废弃输入过滤。
- **目标贡献拆解**：求解后返回的 `objective_contributions`；本变更要求该列表不再包含 `unconfigured_normal_balance`。
- **普通工程分布诊断**：`stats.normal_balance_metrics`；本变更保留其只读诊断价值。

## 成功标准

### 可衡量结果

- **SC-001**：目标函数配置表中“未配置资源普通工程均衡”出现次数为 0。
- **SC-002**：默认 `objective_terms`、`OBJECTIVE_METRIC_DEFINITIONS`、前端 `objectiveTermDefinitions` 中均不包含 `unconfigured_normal_balance`。
- **SC-003**：典型 Excel 导入场景求解结果中，`objective_contributions[*].term_id` 不包含 `unconfigured_normal_balance`。
- **SC-004**：旧请求中带 `unconfigured_normal_balance` 时，如果还有其他有效目标项，后端可继续求解且忽略该废弃字段。
- **SC-005**：只启用 `unconfigured_normal_balance` 的旧请求不能作为有效目标配置通过。
- **SC-006**：`stats.normal_balance_metrics` 仍可输出普通工程分布诊断。
- **SC-007**：后端相关测试和前端构建验证通过。

## 默认假设

- 用户要求移除的是目标函数指标，不是删除普通工程分布诊断。
- 010 以 009 之后的目标项集合为基线：`resource_workload_balance` 已废弃，不在本次恢复。
- 历史结果字段可以存在，但当前目标函数解释以 `objective_contributions` 为准。
