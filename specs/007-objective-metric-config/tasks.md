# 任务清单：精排目标指标前端全量展示与配置

**输入**：来自 `/specs/007-objective-metric-config/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/objective-metric-config-contract.md`

**测试要求**：本功能涉及目标函数配置、CP-SAT 目标贡献、前后端共享字段和页面展示，必须包含后端测试、前端构建和可复现验证。

**组织方式**：任务按用户故事分组，确保每个故事都可独立实现和验证。

## Phase 1：准备（共享基础）

**目标**：确认当前工作树和影响范围，避免覆盖既有改动。

- [X] T001 检查当前 git 状态，确认既有 `backend/app/scenario.py` 和 `backend/app/solver.py` 未提交改动的归属，实施时不得回退无关改动。
- [X] T002 阅读并复核 `specs/007-objective-metric-config/spec.md`、`plan.md`、`data-model.md`、`contracts/objective-metric-config-contract.md`，确认目标项与诊断项边界。
- [X] T003 [P] 复核 `backend/app/models.py` 中 `ObjectiveTermId`、`DEFAULT_OBJECTIVE_TERM_WEIGHTS`、`effective_objective_weights()` 和配置校验。
- [X] T004 [P] 复核 `backend/app/solver.py` 中 `solve_control_priority_schedule()` 的 `model.Minimize(...)`、`weighted_objective` 和现有 `objective_breakdown` 字段。
- [X] T005 [P] 复核 `frontend/src/app/App.tsx` 和 `frontend/src/types/scheduler.ts` 中目标配置表、默认配置和结果展示入口。

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立目标指标目录、配置契约和统一贡献模型；本阶段完成前不得开始页面故事实现。

- [X] T006 [P] 在 `backend/tests/test_scheduler.py` 或新的后端测试文件中增加目标项目录测试，覆盖新增项 `target_relaxation`、`resource_slot_balance`、`unconfigured_normal_balance`。
- [X] T007 [P] 在 `backend/tests/test_scheduler.py` 或新的后端测试文件中增加旧配置兼容测试，覆盖缺失新增目标项时自动补齐默认值。
- [X] T008 在 `backend/app/models.py` 扩展 `ObjectiveTermId` 和 `DEFAULT_OBJECTIVE_TERM_WEIGHTS`，纳入 `target_relaxation`、`resource_slot_balance`、`unconfigured_normal_balance`。
- [X] T009 在 `backend/app/models.py` 建立目标指标目录结构，包含标签、分组、说明、默认权重、可配置性、来源、适用分支和旧字段映射。
- [X] T010 在 `backend/app/models.py` 更新 `default_objective_terms()`、`effective_objective_weights()`、`objective_terms_used()` 和配置校验，保持旧配置自动补齐。
- [X] T011 在 `backend/app/solver.py` 增加统一目标贡献构造辅助逻辑，输出 `term_id`、原始罚分、配置权重、有效权重、加权贡献、启用状态、适用分支和说明。
- [X] T012 在 `frontend/src/types/scheduler.ts` 扩展 `ObjectiveTermId`、目标贡献类型和只读诊断类型，避免前端继续以宽泛字典处理核心目标贡献。

**检查点**：目标目录、配置补齐和贡献数据结构已存在，用户故事可开始实现。

---

## Phase 3：用户故事 1 - 排程人员配置完整目标项（优先级：P1）

**目标**：求解前展示全部后端可配置目标项，并允许用户配置。

**独立测试**：打开精排页面，目标函数配置表显示全部可配置项；修改任一新增项权重后，请求配置和后端有效权重一致。

### 用户故事 1 的测试

- [X] T013 [P] [US1] 在后端测试中增加新增目标项权重生效测试，验证 `unconfigured_normal_balance`、`target_relaxation`、`resource_slot_balance` 的有效权重进入结果回显。
- [X] T014 [P] [US1] 在前端类型或构建验证范围内覆盖新增 `ObjectiveTermId`，确保目标配置表没有遗漏目录项。

### 用户故事 1 的实现

- [X] T015 [US1] 在 `backend/app/solver.py` 将 `unconfigured_normal_balance` 从固定 `UNCONFIGURED_NORMAL_BALANCE_WEIGHT` 切换为目标配置有效权重，默认值保持 10。
- [X] T016 [US1] 在 `backend/app/solver.py` 将 `target_relaxation` 的贡献与权重从 `control_node_late` 中独立暴露，保持旧默认行为等价。
- [X] T017 [US1] 在 `backend/app/solver.py` 将 `resource_slot_balance` 独立暴露为目标项贡献；如实现仍与路径连续性共享表达式，必须明确有效权重来源。
- [X] T018 [US1] 在 `frontend/src/app/App.tsx` 调整 `objectiveTermDefinitions` 或目录消费逻辑，展示全部可配置目标项和业务说明。
- [X] T019 [US1] 在 `frontend/src/app/App.tsx` 更新 `defaultObjectiveTermsConfig()`、`withDefaultScheduleStrategy()` 和目标项更新逻辑，保证新增项可启用、停用和调整权重。
- [X] T020 [US1] 在 `frontend/src/app/App.tsx` 调整目标配置区的计数、分组和禁用最后一项规则，覆盖全部可配置目标项。

**检查点**：用户故事 1 可独立运行和验证。

---

## Phase 4：用户故事 2 - 结果页解释目标贡献（优先级：P1）

**目标**：求解后展示每个目标项的原始罚分、有效权重和加权贡献。

**独立测试**：运行一次控制优先或综合精排，结果页贡献表能与 `weighted_objective` 对齐。

### 用户故事 2 的测试

- [X] T021 [P] [US2] 在后端测试中增加 `objective_contributions` 求和测试，验证贡献加总等于 `weighted_objective`。
- [X] T022 [P] [US2] 在后端测试中增加最佳努力分支样例，验证 `target_relaxation` 在目标放松分支显示为 active 并输出贡献。

### 用户故事 2 的实现

- [X] T023 [US2] 在 `backend/app/solver.py` 把统一贡献列表写入 `objective_breakdown.objective_contributions`，并保留现有兼容字段。
- [X] T024 [US2] 在 `backend/app/solver.py` 确保 `weighted_objective` 由统一贡献列表对齐计算，避免散字段重复计算漂移。
- [X] T025 [US2] 在 `frontend/src/app/App.tsx` 增加结果页目标贡献展示，显示目标项、原始罚分、有效权重、加权贡献、启用状态和分支适用性。
- [X] T026 [US2] 在 `frontend/src/app/App.tsx` 为旧结果增加回退展示，缺少 `objective_contributions` 时从旧 `objective_breakdown` 字段汇总并标记为旧字段。

**检查点**：用户故事 2 可独立运行和验证。

---

## Phase 5：用户故事 3 - 兼容旧场景与旧结果（优先级：P2）

**目标**：旧场景、旧请求和旧结果在新增目标项后仍能使用。

**独立测试**：使用只包含旧 7 项的场景求解并打开旧结果，系统不报错且默认行为等价。

### 用户故事 3 的测试

- [X] T027 [P] [US3] 在后端测试中增加未知目标项、非法权重和全禁用配置的错误断言。
- [X] T028 [P] [US3] 在前端构建或轻量验证中覆盖旧配置缺失新增目标项的 `withDefaultScheduleStrategy()` 行为。

### 用户故事 3 的实现

- [X] T029 [US3] 在 `backend/app/models.py` 保持废弃目标项兼容策略，并确保新增目标项缺失时自动补齐默认配置。
- [X] T030 [US3] 在 `frontend/src/app/App.tsx` 确保加载旧场景时补齐新增目标项，不覆盖已有用户配置。
- [X] T031 [US3] 在 `frontend/src/app/App.tsx` 确保目标配置变化会清空或标记过期已生成结果、已求解结果和方案对比。
- [X] T032 [US3] 在 `netlify/functions/` 相关演示接口或样例响应中补齐新增字段兼容，确保前端页面不因缺字段报错。

**检查点**：用户故事 3 可独立运行和验证。

---

## Phase 6：用户故事 4 - 区分可配置目标与只读诊断（优先级：P2）

**目标**：诊断指标结果可见，但不进入权重配置。

**独立测试**：结果页展示连续性、跳跃、换向、普通工程均衡等诊断项；目标配置表不提供这些诊断项的权重输入。

### 用户故事 4 的测试

- [X] T033 [P] [US4] 在前端验证中覆盖诊断指标只读展示，确认 `continuity_score`、`jump_pier_count`、`direction_reversal_count` 等不出现在可配置目标项中。
- [X] T034 [P] [US4] 在后端测试中确认诊断字段仍从 `stats.continuity_metrics` 和 `stats.normal_balance_metrics` 输出，不改变其业务含义。

### 用户故事 4 的实现

- [X] T035 [US4] 在 `backend/app/solver.py` 或目标目录中明确诊断项来源，避免诊断项混入 `objective_terms_used`。
- [X] T036 [US4] 在 `frontend/src/app/App.tsx` 增加只读诊断展示或完善现有诊断区，标明诊断来源和不可配置状态。
- [X] T037 [US4] 在 `frontend/src/types/scheduler.ts` 对诊断指标解析做类型补充，减少结果展示中的裸 `Record<string, unknown>` 使用。

**检查点**：全部用户故事均可独立运行和验证。

---

## Phase 7：收尾与横切事项

**目标**：完成文档、验证和门禁收口。

- [X] T038 [P] 更新 `docs/精排目标函数算法需求文档_v4.0.md`，区分硬约束、可配置目标项、派生目标项和只读诊断项，并保持文档版本号一致。
- [X] T039 运行后端测试，至少覆盖目标配置、贡献求和、旧配置兼容和非法配置。
- [X] T040 运行前端构建，确认类型和页面编译通过。
- [X] T041 按 `specs/007-objective-metric-config/quickstart.md` 执行可复现验证流程，并记录未覆盖风险。
- [X] T042 复核 `AGENTS.md` 和 Spec Kit 门禁，确认未跳过用户确认、未改动无关文件、未把诊断项误写为目标项。

---

## 依赖与执行顺序

### 阶段依赖

- Phase 1 无依赖，可立即开始。
- Phase 2 依赖 Phase 1，阻塞所有用户故事。
- Phase 3 和 Phase 4 都是 P1，依赖 Phase 2；建议先完成 US1 配置闭环，再完成 US2 结果解释。
- Phase 5 和 Phase 6 依赖 Phase 2，可在 US1/US2 主链稳定后并行推进。
- Phase 7 依赖目标用户故事完成。

### 用户故事依赖

- **US1**：依赖 Phase 2，提供配置入口。
- **US2**：依赖 Phase 2，可与 US1 并行开发后集成，但结果展示最终需要消费 US1 的完整目录。
- **US3**：依赖 Phase 2，兼容逻辑需与 US1/US2 的字段一致。
- **US4**：依赖 Phase 2，诊断项边界需与后端目标目录一致。

### 单个故事内部顺序

- 测试任务先于实现任务。
- 后端模型先于求解器目标函数接入。
- 后端贡献契约先于前端结果展示。
- 前端类型先于页面展示。
- 文档更新在实现和验证后收口。

### 并行机会

- T003、T004、T005 可并行。
- T006、T007、T012 可并行。
- US1 中 T013、T014 可并行；T018、T019、T020 同在 `frontend/src/app/App.tsx`，需顺序处理。
- US2 中 T021、T022 可并行；T023、T024 同在 `backend/app/solver.py`，需顺序处理。
- US3 中 T027、T028 可并行。
- US4 中 T033、T034 可并行。

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，让用户能看到和配置全部后端目标项。
3. 完成 US2，让用户能用结果贡献解释本次求解。
4. 运行最小后端测试和前端构建。

### 完整交付

1. 在 MVP 基础上完成 US3 兼容旧场景。
2. 完成 US4 只读诊断展示。
3. 更新目标函数文档。
4. 执行 quickstart 验证流程。

## 备注

- `[P]` 表示不同文件且无依赖冲突，可并行。
- 本任务清单生成后，需要用户确认和 `$speckit-analyze` 结果通过后才能进入实现。

