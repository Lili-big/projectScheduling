# 任务清单：路面班制工效（单/双班区间）

**输入**：来自当前 `03-requirements/specs/076-pavement-shift-productivity/` 的设计文档

**前置条件**：`plan.md`（必需）、`spec.md`（用户故事必需）、`research.md`、`data-model.md`、`contracts/backend-frontend-contract-changes.md`、`quickstart.md`

**测试要求**：本功能涉及排程算法、工期计算、CP-SAT 约束与前后端共享字段，全部测试写入新建文件（后端 `04-demo/backend/tests/test_pavement_shift.py`、前端 `04-demo/frontend/tests/pavementShift.test.mjs`），既有测试文件零修改（spec FR-005）。

**组织方式**：任务按用户故事分组；US2/US4 的实现由共享基础与 US1 承载，只含验证任务。

## 格式：`[ID] [P?] [Story] 任务描述`

- **[P]**：可并行执行，要求不同文件且无依赖冲突。
- **[Story]**：任务所属用户故事，例如 `US1`。

## Phase 1：共享基础（阻塞前置）

**目标**：契约与工期函数就位；所有故事共用，完成后才可开始 US1。

- [x] T001 [P] 在 `04-demo/backend/app/contracts/pavement.py` 新增 `PavementShiftRegime`（`start_date`/`end_date: date | None`/`shifts: int ∈ [1,2]`，含起止顺序校验），并为 `PavementSettings` 增加 `shift_regimes: list[PavementShiftRegime] = []`
- [x] T002 在 `04-demo/backend/app/contracts/_models.py` 为 `ScheduleInput` 增加 `shift_regimes`（`default_factory=list` + 空列表 `exclude_if`，仿 `readiness_conditions` 风格；依赖 T001）
- [x] T003 [P] 在 `04-demo/frontend/src/contracts/scheduler.ts` 新增 `PavementShiftRegime` 类型并为 `PavementSettings`/`ScheduleInput` 增加对应字段
- [x] T004 新建 `04-demo/backend/app/scheduling/domain/shift_regime.py`：`shifts_for_day`/`task_duration_for_start`/`split_shift_days` 三个纯函数，唯一实现 spec FR-003 公式（浮点累计容差 `1e-9`、最少 1 天、空班制返回 `task.duration_days`；依赖 T001）
- [x] T005 新建 `04-demo/backend/tests/test_pavement_shift.py`：契约校验用例（shifts 越界拒绝、起止顺序拒绝）+ 领域函数数值用例（SC-001 四场景在函数层、浮点容差、最少 1 天、空配置退化等价）；与 T004 同批落地锁定领域口径，其后各故事的求解层测试一律先于对应实现任务执行（依赖 T001/T002/T004）

**检查点**：契约与工期函数可用，领域口径被测试锁定。

## Phase 2：用户故事 1 - 配置双班区间并获得更短工期（P1）

**目标**：计划人员配置班制区间后求解，双班区间内任务日产出 ×2、总工期缩短，页面可配置。

**独立测试**：固定样例分别在无配置/有配置下求解，核对任务偏移与总工期（SC-001）。

### 用户故事 1 的测试

- [x] T006 [P] [US1] `test_pavement_shift.py` 增加生成层用例：`settings.shift_regimes` 快照进入 `generate_pavement_input` 产出的 `ScheduleInput`；起>止、同起点重复、区间重叠分别报 `PAVEMENT_SHIFT_INVALID` 且不进入求解（依赖 T005）
- [x] T007 [P] [US1] `test_pavement_shift.py` 增加求解层用例：小样例配置 `{计划开始日+X 起, 无结束日, 双班}` 后贪心初解与 CP-SAT 终解的工期均按日产出 ×2 计算、双班内开工场景工期 4 天（SC-001 场景 2）、结果通过 `validate_candidate`（依赖 T005）

### 用户故事 1 的实现

- [x] T008 [US1] `04-demo/backend/app/scheduling/generation/pavement.py`：`generate_pavement_input` 把 `settings.shift_regimes` 快照进 `ScheduleInput`，并做区间合法性校验（重叠/倒挂/同起点重复 → `PAVEMENT_SHIFT_INVALID`）（依赖 T001/T002/T006）
- [x] T009 [US1] `04-demo/backend/app/scheduling/solver/strategies/pavement.py`：`validate_pavement_schedule` 复算同一班制校验规则，使直接 `/solve` 载荷受控（依赖 T006）
- [x] T010 [US1] `04-demo/backend/app/scheduling/solver/strategies/pavement_heuristic.py`：`construct_candidate` 与 `validate_candidate` 的工期判定改用 `task_duration_for_start`（`e == s + f(s)`），`horizon` 求和维持基准工期上界不变（依赖 T004）
- [x] T011 [US1] `04-demo/backend/app/scheduling/solver/strategies/pavement.py` 的 `_build_model` 变量工期：按任务预计算 `0..horizon` 工期表，`AddAllowedAssignments` 绑定 start→duration 变量，`ends == starts + dvar`，interval 与 warm-start hint 使用 `dvar`；同步调整 `04-demo/backend/app/scheduling/solver/constraints/pavement.py` 的 interval duration 参数接收变量（依赖 T004/T010）
- [x] T012 [P] [US1] 新建 `04-demo/frontend/tests/pavementShift.test.mjs` 并在 `04-demo/frontend/src/domain/pavement.ts` 实现镜像纯函数（`shiftsForDay`/`taskDurationForStart`/`splitShiftDays`，与后端同公式，用 SC-001 同表数值锁定）（依赖 T003）
- [x] T013 [US1] `04-demo/frontend/src/features/logic/LogicTab.tsx` 增加项目级班制区间编辑器（起/止日期、班次单选、增删行、结束留空=延续），经既有 `onUpdatePavementSettings` 通道写入并走既有保存链路，支持清空恢复默认（依赖 T003/T012）

**检查点**：页面配置班制 → 求解工期缩短，后端定向测试通过。

## Phase 3：用户故事 2 - 跨越班制边界的任务中途加速（P1）

**目标**：跨界任务按分段累计自动提速，无需人工拆分；窝工优化在班制下保持可用。

**独立测试**：SC-001 跨界场景（9-25 开工 7 天 = 单班 6 + 双班 1）与单班内场景（9-01 开工 8 天，全部单班）。

### 用户故事 2 的测试

- [x] T014 [P] [US2] `test_pavement_shift.py` 增加跨界求解用例：跨界场景拆分正确（`split_shift_days` 6+1）、单班内场景不受后段双班影响、层间等待 `wait_days` 仍按自然天（FR-006）、转场天数不变（依赖 T010/T011）
- [x] T015 [US2] `test_pavement_shift.py` 增加窝工共存用例：配置班制后先求解再优化窝工成功（`idle_metrics` 使用实际工期）；修改班制后直接优化窝工报 422 `PAVEMENT_BASELINE_OUTDATED`（指纹失效自动生效，FR-007/FR-010）（依赖 T014）

**检查点**：班制在完整求解与窝工链路可用，跨界数值正确。

## Phase 4：用户故事 3 - 结果中可见班制口径与拆分（P2）

**目标**：任务详情显示单/双班拆分，摘要含班制说明，横道图标注双班区间，旧结果历史提示自动生效。

**独立测试**：求解后检查详情与摘要；修改班制不重解，确认历史提示。

### 用户故事 3 的测试

- [x] T016 [P] [US3] `pavementShift.test.mjs` 增加展示用例：由结果 `start_offset/end_offset` + `shift_regimes` 推导"单班 x 天 + 双班 y 天"拆分文本（依赖 T012）
- [x] T017 [P] [US3] `test_pavement_shift.py` 增加摘要用例：配置班制时 `pavement_summary.resource_assumptions` 含班制说明文案，未配置时不含（依赖 T008）

### 用户故事 3 的实现

- [x] T018 [US3] `04-demo/frontend/src/features/scheduleResults/`（`presenter.ts`/`pavementViewModel.ts`/`PavementPlanTimeline.tsx`）：任务详情接入拆分展示，横道图按班制区间绘制双班底色/标注；历史结果提示依赖既有指纹机制零改动（依赖 T016）
- [x] T019 [US3] `04-demo/backend/app/scheduling/solver/strategies/pavement.py` 的 `result_from_candidate`：配置班制时向 `resource_assumptions` 追加班制说明（依赖 T017）

**检查点**：结果页三个展示面（详情、摘要、横道）口径可见。

## Phase 5：用户故事 4 - 无班制配置时行为完全不变（P2）

**目标**：空配置逐位回归现状，既有测试零修改。

**独立测试**：固定样例无配置求解与现状实现输出一致；全量回归通过。

### 用户故事 4 的测试

- [x] T020 [US4] `test_pavement_shift.py` 增加等价用例：同一固定输入（无班制）经改造后求解的任务偏移、状态、指标与改造前快照输出逐位一致（以现状实现跑出的快照为基准写入用例），前端 `pavementShift.test.mjs` 断言空班制时 `taskDurationForStart === duration_days`（依赖 T010/T011）

**检查点**：兼容底线成立，既有全量测试无需改动即可通过（全量执行归入收尾 T023）。

## Phase 6：收尾与横切事项

- [x] T021 重新捕获架构基线：`04-demo/backend/tests/fixtures/architecture/backend-baseline.json`（`capture_architecture_baseline.py`）与 `04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`（`captureArchitectureBaseline.mjs`），确认 `verify:architecture` 通过（依赖 T002/T003/T008-T019）
- [x] T022 [P] 同步 `04-demo/tools/demo-api-mirror/api.mts` 中 `ScheduleInput`/`PavementSettings` schema 表达（依赖 T002/T003）
- [x] T023 运行 `quickstart.md` 全部验证：后端定向 + 前端全量 + `npm run typecheck`/`build` + `npm test` 全量回归（既有断言零修改）+ `npm.cmd run verify:architecture`；按 quickstart 第 3 节做页面端到端与 19 段 76 任务量级 15 秒预算性能核对（SC-004）（依赖 T020/T021/T022）
- [x] T024 更新权威文档：`03-requirements/specs/README.md` 中 076 行状态与任务计数、`agent.md` 路面能力事实段补一句班制能力；运行文档门禁 `validate_docs.py`（依赖 T023）

---

## 依赖与执行顺序

### 阶段依赖

- **共享基础（Phase 1）**：T001 → T002/T004；T003、T004 与 T001 后的分支可并行；T005 依赖 T001/T002/T004。
- **US1（Phase 2）**：依赖 Phase 1；T008→T009→T010→T011 为求解链路主序；T012 与后端链路并行；T013 依赖 T003/T012。
- **US2（Phase 3）**：依赖 T010/T011（实现由 US1 承载），仅测试任务。
- **US3（Phase 4）**：T016 依赖 T012；T017 依赖 T008；T018/T019 各依赖对应测试。
- **US4（Phase 5）**：依赖 T010/T011，仅等价验证。
- **收尾（Phase 6）**：依赖全部故事完成。

### 并行机会

- Phase 1 内：T001→（T002、T004）与 T003 并行。
- US1 内：T006/T007（测试）先行并行；T012 前端线与 T008-T011 后端线并行。
- T014/T016/T017 分属不同验证面，可并行。
- T022 与 T021 并行。

### 实施策略

1. 完成 Phase 1 与 Phase 2（US1 全部），页面可演示"配置双班 → 工期缩短"。
2. 依次 US2 → US3 → US4，每阶段跑对应定向测试确认。
3. 收尾 T021-T024 全量门禁与文档，`npm.cmd run verify` 通过后按 075 惯例在 spec 状态记录验收结论。

---

## 完成证据（2026-09-29 实施）

- 新增测试：后端 `test_pavement_shift.py` 20 项全绿（SC-001 四场景、配置校验、指纹失效、窝工共存、summary 文案、与 HEAD 无配置快照逐位等价）；前端 `pavementShift.test.mjs` 6 项全绿（与后端同表数值）。
- 全量回归：后端失败集合与 HEAD 完全一致（170 项既有历史失败，零新增）；前端失败集合收敛为 HEAD 既有的 8 项，零新增。`tsc --noEmit` 与 `vite build` 通过。
- 门禁：前后端架构基线 `--check` 通过（后端基线按当前现实整体重捕获，折叠了 071 起 route 72→74 的既有漂移；前端基线 +8 行）；`validate_dependencies`/`validate_docs` OK；`validate_repository` 的 2 项依赖审批错误与治理测试 5 项失败均为 HEAD 既有（package-lock/requirements 未修改，失败清单与 HEAD 逐项一致）。
- HTTP 冒烟：带班制场景经 `/api/solve-scenario` 返回 OPTIMAL 且摘要含班制说明；更换区间独立求解正常。
- 性能（SC-004）：100 任务 15 秒预算，无班制 374 天（初解 382）、双班自 10-01 起 347 天（初解 350），建模 0.16s→0.25s，总时长同量级。
- 偏差说明：为保持拆分口径单源，`pavementResults.test.mjs` 的组件加载器扩展了 `../` 相对导入解析（一行，非断言修改）；后端架构基线采用全量重捕获而非手工补丁（手工方式不可行：每端点内嵌全套 $defs，新属性有 41 处副本）。
- 浏览器页面人工走查（quickstart 第 3 节）留待用户在演示环境执行；组件接线已由 typecheck、build、组件级 Node 测试与 HTTP 冒烟覆盖。
