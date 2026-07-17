# 任务清单：统一目标函数求解与资源分支重构

**输入**：来自 `/specs/018-unified-target-solve/` 的设计文档

**前置条件**：`spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/unified-target-solve-contract.md`、`quickstart.md`

**测试要求**：本功能涉及排程算法、资源模型、工期计算、CP-SAT 目标函数、前后端共享字段和跨模块行为，必须包含后端测试、前端构建验证和可复现场景验证。

**组织方式**：任务按用户故事分组，确保每个故事都能独立实现和验证；用户确认本任务清单和 `$speckit-analyze` 结果前，不进入实现。

## Phase 1：准备

**目标**：确认当前代码入口、旧字段和真实文件路径，避免覆盖无关改动。

- [X] T001 核对当前 git 状态和 018 规格产物范围，确认实现只涉及 `.specify/feature.json`、`specs/018-unified-target-solve/`、`backend/app/models.py`、`backend/app/solver.py`、`backend/app/scenario.py`、`backend/tests/test_scheduler.py`、`frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx`、`netlify/demo-functions/api.mts` 和必要 `docs/` 文件
- [X] T002 [P] 梳理当前固定资源、固定工期、候选资源、硬里程碑和容量模型入口，重点阅读 `backend/app/scenario.py`、`backend/app/solver.py`、`backend/app/models.py`
- [X] T003 [P] 梳理当前前端结果类型、结果来源标签和精排/粗排展示文案，重点阅读 `frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx`
- [X] T004 [P] 梳理当前 Netlify 演示接口是否暴露冲突求解口径，重点阅读 `netlify/demo-functions/api.mts`

---

## Phase 2：基础能力（阻塞所有用户故事）

**目标**：建立统一目标函数、目标达成判定、资源范围和 15 秒总预算的共享基础。

- [X] T005 在 `backend/app/models.py` 将目标函数权重上限和默认硬里程碑晚点权重调整为支持 `10000000000`
- [X] T006 在 `backend/app/models.py` 增加或复用目标达成结果、失败原因、资源候选结果和搜索范围的嵌入式结果字段定义，不新增持久化业务实体
- [X] T007 在 `backend/app/scenario.py` 实现共享的目标达成判定 helper，统一计算 `business_success`、`target_status`、`hard_milestone_late_days`、`fixed_duration_overrun_days` 和 `failure_reasons`
- [X] T008 在 `backend/app/scenario.py` 实现共享的资源数量应用和搜索范围 helper，保证候选资源不低于 `quantity` 且不超过 `max_quantity`
- [X] T009 在 `backend/app/scenario.py` 实现单次用户求解动作的 15 秒总预算上下文，并让后续内部求解只使用剩余预算
- [X] T010 在 `backend/app/solver.py` 接入剩余预算参数，确保 CP-SAT 内部调用不再各自默认独占 15 秒
- [X] T011 在 `frontend/src/types/scheduler.ts` 增加目标达成、失败原因、资源候选和资源搜索范围的前端类型定义，并兼容缺失字段的旧结果

**检查点**：公共字段、资源范围、时间预算和目标达成 helper 就绪后，才能进入用户故事实现。

---

## Phase 3：用户故事 2 - 硬里程碑和固定工期按目标达成结果判定（P1）

**目标**：硬里程碑晚点进入目标函数，固定工期超期进入业务判定，求解器可行性与业务成功状态分离。

**独立测试**：使用硬里程碑晚点、固定工期超期、两者同时存在、`UNKNOWN` 或超时四类场景验证输出。

### 用户故事 2 的测试

- [X] T012 [US2] 在 `backend/tests/test_scheduler.py` 增加硬里程碑作为目标项时输出 `control_node_late` 权重 `10000000000`、原始晚点天数和加权贡献的测试
- [X] T013 [US2] 在 `backend/tests/test_scheduler.py` 增加固定工期超期时返回 `fixed_duration_overrun_days > 0` 且 `business_success = false` 的测试
- [X] T014 [US2] 在 `backend/tests/test_scheduler.py` 增加 `UNKNOWN` 或预算耗尽时返回 `target_status = unconfirmed` 且不标记无解的测试

### 用户故事 2 的实现

- [X] T015 [US2] 在 `backend/app/solver.py` 将硬里程碑晚点从默认阻断式硬约束改为完整目标函数中的晚点目标项，同时保留施工硬规则
- [X] T016 [US2] 在 `backend/app/solver.py` 输出硬里程碑晚点目标项的 `raw_value`、`unit`、`weight` 和 `weighted_value`
- [X] T017 [US2] 在 `backend/app/scenario.py` 基于目标日期或固定工期目标计算 `fixed_duration_overrun_days`
- [X] T018 [US2] 在 `backend/app/scenario.py` 和 `backend/app/solver.py` 将 `UNKNOWN`、超时和预算耗尽统一映射为 `unconfirmed`，不得输出无解或最大资源不足结论
- [X] T019 [US2] 在 `frontend/src/app/App.tsx` 分开展示硬里程碑晚点天数、固定工期超期天数、求解器状态和业务目标状态
- [X] T020 [US2] 在 `frontend/src/types/scheduler.ts` 确保旧结果缺少固定工期超期字段时前端展示为未评估或兼容状态，而不是强行展示为 0

**检查点**：用户故事 2 完成后，CP-SAT `OPTIMAL`/`FEASIBLE` 不再自动等同于业务成功，晚点和超期均可解释。

---

## Phase 4：用户故事 1 - 固定资源下得到可解释的成功或失败结论（P1）

**目标**：固定资源求工期先用当前默认资源运行完整目标函数，并区分业务成功、当前资源目标失败和物理无可行排程。

**独立测试**：使用当前资源成功、当前资源可排程但目标失败、当前资源物理无可行排程三类场景，验证结果状态、晚点/超期指标、任务排程保留和前端展示。

### 用户故事 1 的测试

- [X] T021 [US1] 在 `backend/tests/test_scheduler.py` 增加当前默认资源达成目标时返回 `business_success = true` 且晚点/超期为 0 的测试
- [X] T022 [US1] 在 `backend/tests/test_scheduler.py` 增加当前默认资源可排程但硬里程碑晚点时保留 `scheduled_tasks` 并返回 `current_resources_target_failed` 的测试
- [X] T023 [US1] 在 `backend/tests/test_scheduler.py` 增加施工硬规则或资源配置导致无物理可行排程时返回 `physical_infeasible` 的测试

### 用户故事 1 的实现

- [X] T024 [US1] 在 `backend/app/scenario.py` 将固定资源入口改为先使用当前 `ResourcePool.quantity` 运行完整目标函数求解
- [X] T025 [US1] 在 `backend/app/scenario.py` 将 CP-SAT 可行但业务目标失败的结果包装为当前资源失败结果，并保留排程任务和资源分配
- [X] T026 [US1] 在 `backend/app/scenario.py` 将 CP-SAT 物理无可行结果包装为 `physical_infeasible`，避免伪装成业务目标失败排程
- [X] T027 [US1] 在 `backend/app/scenario.py` 为固定资源结果补齐 `stats.target_achievement` 和目标函数贡献透传
- [X] T028 [US1] 在 `frontend/src/app/App.tsx` 展示固定资源业务成功、当前资源失败和物理无可行排程三类状态
- [X] T029 [US1] 在 `frontend/src/app/App.tsx` 弱化或替换固定资源结果中的精排/粗排主分类文案，改为目标函数排程和目标达成判定口径

**检查点**：用户故事 1 完成后，固定资源入口可独立返回当前资源成功、当前资源失败和物理无可行三类结果。

---

## Phase 5：用户故事 3 - 当前资源失败后进入新增资源分支（P1）

**目标**：当前资源目标失败后，在当前默认资源和最大资源之间搜索候选资源，并将候选资源代入完整目标函数复排验证。

**独立测试**：使用当前资源失败但最大资源可达成、候选资源达成、候选资源仍失败三类场景验证主结果和候选结果。

### 用户故事 3 的测试

- [X] T030 [US3] 在 `backend/tests/test_scheduler.py` 增加当前资源失败后进入新增资源分支且搜索范围在 `quantity` 到 `max_quantity` 之间的测试
- [X] T031 [US3] 在 `backend/tests/test_scheduler.py` 增加候选资源必须经过完整目标函数复排后才能返回 `candidate_resources_target_met` 的测试
- [X] T032 [US3] 在 `backend/tests/test_scheduler.py` 增加候选资源复排仍未达成目标时不得标记为推荐成功的测试

### 用户故事 3 的实现

- [X] T033 [US3] 在 `backend/app/scenario.py` 重构 `_fixed_resource_recommendation`，让新增资源分支复用共享资源范围和完整目标函数求解 helper
- [X] T034 [US3] 在 `backend/app/scenario.py` 重构 `_minimum_resource_candidate_result`，让候选资源复排复用统一目标达成判定
- [X] T035 [US3] 在 `backend/app/scenario.py` 输出 `recommended_resources.candidate_quantities`、`added_quantities`、`search_range`、`verification_result_source` 和候选 `target_achievement`
- [X] T036 [US3] 在 `backend/app/solver.py` 评估并删除、旁路或降级 `_solve_capacity_model` 在新增资源分支和 `solve_min_resources_schedule` 固定工期资源搜索中的作用；若保留，必须输出保留原因诊断供 analyze 和用户确认
- [X] T037 [US3] 在 `frontend/src/types/scheduler.ts` 增加候选资源结果、搜索范围和候选目标达成字段类型
- [X] T038 [US3] 在 `frontend/src/app/App.tsx` 同时展示当前资源失败结果和新增资源候选结果，避免候选结果覆盖当前资源失败结论

**检查点**：用户故事 3 完成后，当前资源失败结果和推荐资源候选结果可并存且可比较。

---

## Phase 6：用户故事 4 - 固定工期下用最大资源硬里程碑快速预检（P2）

**目标**：固定工期求资源先用最大资源运行硬里程碑和固定工期窗口快速预检，最大资源快速预检达成后才搜索候选资源，最大资源未达成或未确认时返回对应提示。

**独立测试**：使用最大资源达成、最大资源不满足、最大资源预检 `UNKNOWN` 或预算耗尽三类场景验证。

### 用户故事 4 的测试

- [X] T039 [US4] 在 `backend/tests/test_scheduler.py` 增加固定工期入口最大资源硬里程碑快速预检达成后继续搜索候选资源的测试
- [X] T040 [US4] 在 `backend/tests/test_scheduler.py` 增加最大资源硬里程碑快速预检不可行时返回 `max_resources_target_failed` 的测试
- [X] T041 [US4] 在 `backend/tests/test_scheduler.py` 增加最大资源预检 `UNKNOWN` 或预算耗尽时返回 `unconfirmed` 且不提示资源上限不足的测试

### 用户故事 4 的实现

- [X] T042 [US4] 在 `backend/app/solver.py` 重构 `solve_min_resources_schedule`，先用最大资源数量运行硬里程碑和固定工期窗口快速预检
- [X] T043 [US4] 在 `backend/app/solver.py` 将最大资源预检达成后的候选资源搜索范围限定为当前默认数量到最大数量之间
- [X] T044 [US4] 在 `backend/app/solver.py` 和 `backend/app/scenario.py` 输出 `max_resources_target_failed` 与 `unconfirmed` 的不同失败原因和可解释指标
- [X] T045 [US4] 在 `backend/app/solver.py` 确保最大资源预检、候选资源搜索和候选复排共享同一 15 秒总预算
- [X] T046 [US4] 在 `frontend/src/app/App.tsx` 展示固定工期最大资源不满足目标和限时内无法确认两类状态
- [X] T047 [US4] 在 `netlify/demo-functions/api.mts` 对固定工期资源求解结果进行字段对齐；如无法提供完整能力，则隐藏冲突结论或显示能力受限

**检查点**：用户故事 4 完成后，固定工期入口不再用非完整目标预检误判最大资源可行性。

---

## Phase 7：用户故事 5 - 保留桩基机械钻机同结构同工艺规则（P2）

**目标**：旋挖钻、冲击钻、回旋钻的同结构同工艺规则继续作为施工组织硬规则，不被硬里程碑或固定工期目标化牺牲，也不扩展到未确认资源类型。

**独立测试**：使用机械钻机和非机械钻机各一类场景验证规则保留和范围不扩展。

### 用户故事 5 的测试

- [X] T048 [US5] 在 `backend/tests/test_scheduler.py` 增加旋挖钻、冲击钻或回旋钻在目标函数排程中仍遵守同结构同工艺规则的测试
- [X] T049 [US5] 在 `backend/tests/test_scheduler.py` 增加模板、人工班组或其他未确认资源类型不会被凭空扩展同结构同工艺限制的测试

### 用户故事 5 的实现

- [X] T050 [US5] 在 `backend/app/solver.py` 确保 `_add_named_same_structure_resource_rules` 和容量/候选路径中的同结构同工艺规则不被目标函数放松
- [X] T051 [US5] 在 `backend/app/scenario.py` 确保当前资源、最大资源和候选资源生成时保留机械钻机 `same_structure_resource_binding` 语义
- [X] T052 [US5] 在 `frontend/src/app/App.tsx` 保留同结构同工艺诊断展示，但不得把该规则作为可被目标函数牺牲的软目标文案

**检查点**：用户故事 5 完成后，业务成功结果仍不违反当前机械钻机同结构同工艺规则。

---

## Phase 8：收尾与横切事项

**目标**：完成文档、兼容、构建和回归验证。

- [X] T053 [P] 更新 `docs/精排目标函数算法需求文档_v4.0.md`，记录硬里程碑目标函数化、权重 `10000000000`、目标贡献和业务判定口径
- [X] T054 [P] 更新 `docs/固定资源满足分支详细排程算法文档_v1.6.md`，记录当前资源失败保留、推荐资源候选复排和容量模型去留结论
- [X] T055 [P] 更新 `docs/资源配置页面需求文档_v1.0.md`，记录资源默认数量、最大数量、搜索范围和最大资源不满足提示口径
- [X] T056 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q` 并修复 `backend/tests/test_scheduler.py` 覆盖的回归问题
- [X] T057 运行 `npm --prefix frontend run build` 并修复 `frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx` 或 `netlify/demo-functions/api.mts` 的类型/构建问题
- [X] T058 按 `specs/018-unified-target-solve/quickstart.md` 验证固定资源、固定工期、候选资源、未确认、旧结果兼容和同结构同工艺场景
- [X] T059 检查 `specs/018-unified-target-solve/plan.md`、`specs/018-unified-target-solve/tasks.md` 与 Constitution 门禁，确认没有新增持久化实体、新依赖、README 修改或未经确认的业务规则扩展

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1 准备**：无依赖，可立即开始。
- **Phase 2 基础能力**：依赖 Phase 1 完成，阻塞所有用户故事。
- **Phase 3、4、5（P1）**：依赖 Phase 2 完成；先完成 US2 的目标达成基础能力，再完成 US1 和 US3 的分支结果。
- **Phase 6、7（P2）**：依赖 Phase 2 完成；可在 P1 稳定后并行推进。
- **Phase 8 收尾**：依赖目标用户故事完成。

### 用户故事依赖

- **US2 目标达成判定**：依赖 Phase 2；是 US1、US3、US4 的共享语义基础。
- **US1 固定资源结果**：依赖 Phase 2 和 US2 的目标达成判定；不依赖 US3，但 US3 会消费 US1 的当前资源失败状态。
- **US3 新增资源分支**：依赖 Phase 2、US2 和 US1 的当前资源失败状态。
- **US4 固定工期最大资源快速预检**：依赖 Phase 2 和 US2 的目标达成判定，可与 US3 部分并行。
- **US5 同结构同工艺规则**：依赖 Phase 2，可与 US4 并行，但必须在最终回归前完成。

### 单个故事内部顺序

- 测试任务先于实现任务。
- 后端模型和求解器基础先于场景编排。
- 场景编排先于前端展示。
- 前端类型先于前端页面接入。
- 每个故事完成并独立验证后，再进入下一个优先级故事的集成验证。

---

## 并行示例

### 用户故事 2

```text
Task: "T012 在 backend/tests/test_scheduler.py 增加硬里程碑目标项测试"
Task: "T019 在 frontend/src/app/App.tsx 分开展示目标状态和业务状态"
```

注意：同一文件内的测试任务不标记 `[P]`，避免并行编辑冲突。

### 用户故事 3

```text
Task: "T033 在 backend/app/scenario.py 重构 _fixed_resource_recommendation"
Task: "T037 在 frontend/src/types/scheduler.ts 增加候选资源结果类型"
```

### 用户故事 4

```text
Task: "T042 在 backend/app/solver.py 重构 solve_min_resources_schedule"
Task: "T046 在 frontend/src/app/App.tsx 展示最大资源不满足目标和限时内无法确认状态"
Task: "T047 在 netlify/demo-functions/api.mts 对固定工期资源求解结果进行字段对齐或降级"
```

---

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US2 的目标达成判定与硬里程碑目标函数化基础。
3. 完成 US1，使固定资源入口能返回可解释成功/失败结果。
4. 完成 US3，使当前资源失败后能返回推荐资源候选。
5. 停下验证 P1 主链路，再进入 US4 和 US5。

### 增量交付

1. 后端先保证统一目标达成字段和业务判定正确。
2. 前端再切换展示口径，减少“后端已改、前端误读”的窗口。
3. Netlify 演示接口最后对齐或明确降级。
4. 每个用户故事完成后执行对应后端测试和必要前端构建验证。

### 风险控制

- 容量模型去留必须在 T036 中同时覆盖新增资源分支和固定工期资源搜索；若保留，需要在 `$speckit-analyze` 和最终交付说明中列出原因、影响范围和后续删除条件。
- `UNKNOWN` 和预算耗尽不得被任何分支解释为无解或最大资源不满足。
- 不新增持久化业务实体；如实现阶段必须新增字段或结构，需在 analyze 结果中作为用户确认项列出。

