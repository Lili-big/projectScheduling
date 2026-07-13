# 任务清单：AI 方案状态三态化与最大延期口径优化

**输入**：来自 `specs/029-ai-status-delay-consolidation/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/ai-status-delay-api.md`、`quickstart.md`

**测试要求**：本功能修改前后端共享字段、状态判定、工期摘要和历史计划兼容，必须先补状态矩阵、最大延期、推荐门禁和历史快照测试，再实施对应逻辑。

**组织方式**：任务按用户故事分组；同一文件上的任务保持顺序，标记 `[P]` 的任务位于不同文件且可并行。

## Phase 1：准备（共享基础）

**目标**：确认当前 028 实现、未提交改动和 029 契约边界，不覆盖用户已有修改。

- [x] T001 复核并记录当前工作区已有修改、`specs/028-ai-strict-resource-solve/` 状态契约和 `.local-data/plan-control-store.json` 兼容边界，实施时只修改 `plan.md` 已列出的目标文件
- [x] T002 [P] 对照 `specs/029-ai-status-delay-consolidation/contracts/ai-status-delay-api.md` 检查 `backend/app/models.py` 与 `frontend/src/types/scheduler.ts` 当前字段，确认所有新增字段均为默认可空

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立三态、状态原因和最大延期的共享契约，旧四状态字段保持可解析。

- [x] T003 在 `backend/app/models.py` 增加 `ResourceAssistantScheduleOutcomeStatus`、`ResourceAssistantScheduleOutcomeReason`，并为 `ResourceAssistantPlanResult` 增加默认可空 `schedule_outcome_status`、`schedule_outcome_reason`
- [x] T004 [P] 在 `frontend/src/types/scheduler.ts` 同步三态、原因类型，为 `ResourceAssistantPlanResult` 与 `TargetAchievement` 增加新字段和 `max_target_delay_days`
- [x] T005 在 `backend/app/scenario.py` 增加可复用的三态映射与最大延期聚合辅助函数骨架，保持旧 `_apply_ai_strict_target_achievement()` 的 `plan_status` 与累计字段契约

**检查点**：共享模型可以解析缺少新字段的旧响应和历史计划快照。

---

## Phase 3：用户故事 1 - 用三种业务状态判断方案结果（优先级：P1）

**目标**：方案卡和对比结果只显示三种主状态，同时用状态原因保留证明程度和无排程原因。

**独立测试**：构造满足、最优延期、限时延期、限时无排程、已证明不可行、资源覆盖失败和目标缺失结果，逐项核对三态、原因、排程保留与页面中文说明。

### 用户故事 1 的测试

- [x] T006 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加七类状态映射矩阵测试，覆盖 `duration_target_met`、`duration_target_not_met`、`no_feasible_schedule`、空状态及所有原因
- [x] T007 [P] [US1] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加单方案响应、三方案对比和技术失败契约测试，断言新三态优先且旧 `plan_status` 仍返回

### 用户故事 1 的实现

- [x] T008 [US1] 在 `backend/app/scenario.py` 根据目标存在性、`has_schedule`、`solver_status`、证明状态和延期生成 `schedule_outcome_status`、`schedule_outcome_reason`，并写入目标评估元数据
- [x] T009 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 将新三态和原因写入 `ResourceAssistantPlanResult`，技术失败保持字段为空
- [x] T010 [US1] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 将三方案对比的业务状态行改为优先输出新三态，历史结果缺失时回退旧四状态
- [x] T011 [US1] 在 `frontend/src/domain/resourceAssistant.ts` 增加三态中文名称、色调、状态原因说明和旧四状态回退映射；目标缺失显示配置异常
- [x] T012 [US1] 在 `frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 改用三态与状态原因展示方案主结论，不再把旧四状态作为用户可见主状态
- [x] T013 [US1] 在 `frontend/src/features/resourceAssistant/MetricComparisonTable.tsx` 验证通用表格按新业务状态行显示三种中文主状态，缺失新字段时使用领域层回退结果

**检查点**：页面主状态只有三种，延期排程均保留，`OPTIMAL` 与 `FEASIBLE` 的说明不同，`UNKNOWN` 不被描述为已证明资源不足。

---

## Phase 4：用户故事 2 - 用最大延期判断最严重偏差（优先级：P1）

**目标**：页面主摘要使用所有强制里程碑单项延期和固定总工期超期的最大值，累计值与明细不变。

**独立测试**：输入强制里程碑延期 `[0, 12, 5]` 和固定总工期超期 `8`，断言最大延期 `12`、累计延期 `17`、固定超期 `8`，页面显示“最大延期 12 天”。

### 用户故事 2 的测试

- [x] T014 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加最大延期聚合测试，覆盖混合延期、仅固定工期超期、全零、仅软里程碑和目标缺失
- [x] T015 [P] [US2] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加响应与对比最大延期契约测试，断言累计字段、固定超期和逐里程碑明细未改变

### 用户故事 2 的实现

- [x] T016 [US2] 在 `backend/app/scenario.py` 从强制 `milestone_results[].lateness_days` 与固定总工期超期计算 `max_target_delay_days`，用其零值判定三态但不修改求解目标和旧累计值
- [x] T017 [US2] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 透传最大延期并确保对比数据与单方案结果使用同一后端口径
- [x] T018 [US2] 在 `frontend/src/domain/resourceAssistant.ts` 将延期摘要统一改为“最大延期 X 天”，旧结果缺少新字段时按逐里程碑与固定超期兼容计算

**检查点**：页面摘要不再对多个目标延期求和，状态结论与现有“任一延期即未满足”语义一致。

---

## Phase 5：用户故事 3 - 保持推荐、基准计划和历史版本可用（优先级：P2）

**目标**：新三态参与推荐门禁，旧四状态历史快照继续加载，基准计划和进度反馈资格不变。

**独立测试**：用临时存储加载四种旧状态快照，比较文件前后哈希；生成推荐并创建基准，验证历史不重写、只有目标满足进入推荐、有可行排程仍可设为基准。

### 用户故事 3 的测试

- [x] T019 [P] [US3] 在 `backend/tests/test_ai_resource_scheduling_assistant.py` 增加新三态推荐门禁与旧 `plan_status=met` 回退测试，断言其他新旧状态均不补位
- [x] T020 [P] [US3] 在 `backend/tests/test_plan_control_repository.py` 增加旧 `met/not_met/unconfirmed/infeasible` 快照加载和文件哈希不变测试
- [x] T021 [P] [US3] 在 `backend/tests/test_plan_control_api.py` 增加带新三态及缺少新字段的基准创建/项目摘要测试，保持 `OPTIMAL/FEASIBLE` 资格不变

### 用户故事 3 的实现

- [x] T022 [US3] 在 `backend/app/services/ai_resource_scheduling_assistant.py` 将推荐候选资格改为优先判断 `schedule_outcome_status=duration_target_met`，缺失时回退旧 `plan_status=met`
- [x] T023 [US3] 在 `frontend/src/domain/resourceAssistant.ts` 完成历史四状态到三态和原因的纯展示映射，保证缺少新字段的方案卡、对比和计划快照不报错
- [x] T024 [US3] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 验证资源变化、重新生成和重新求解继续整体删除旧结果，从而同步清除三态、最大延期和推荐

**检查点**：历史版本正常读取且不写回；推荐和基准计划门禁与规格一致；进度反馈页面可继续加载任务。

---

## Phase 6：收尾与横切事项

**目标**：完成文档、全量回归和真实页面验收。

- [x] T025 [P] 更新 `docs/AI资源配置与排程优化助手验证说明.md`，说明三态主状态、状态原因、最大延期、累计值保留和历史兼容
- [x] T026 运行 `backend/tests/test_ai_resource_scheduling_assistant.py`、`backend/tests/test_scheduler.py`、`backend/tests/test_plan_control_api.py`、`backend/tests/test_plan_control_repository.py` 并修复本功能回归
- [x] T027 在仓库根目录运行 `npm.cmd run build` 与 `git diff --check`，确认 `frontend/` TypeScript、生产构建和全仓换行检查通过
- [x] T028 按 `specs/029-ai-status-delay-consolidation/quickstart.md` 完成页面验证：三态、最大延期、推荐门禁、资源变更失效、设为基准和进度反馈读取
- [x] T029 对照 `AGENTS.md` 与 `.specify/memory/constitution.md` 复核门禁，准备 `$speckit-converge` 所需的规格—代码—测试证据

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，只做范围和工作区确认。
- **Phase 2**：依赖 Phase 1，阻塞全部用户故事。
- **US1（Phase 3）**：依赖共享三态类型，是 US2、US3 页面与推荐接入的基础。
- **US2（Phase 4）**：依赖 Phase 2；后端聚合可与 US1 页面任务分开推进，最终接入同一目标评估。
- **US3（Phase 5）**：依赖 US1 的三态契约和 US2 的完整目标评估字段。
- **Phase 6**：依赖所有目标用户故事完成。

### 单个故事内部顺序

- 测试任务先于实现任务，先确认当前缺少新契约或断言失败。
- 后端目标评估先于服务响应和推荐。
- 前端类型先于领域映射，领域映射先于组件显示。
- 历史兼容测试使用临时存储，不修改用户本地计划文件。

### 并行机会

- T003 与 T004 可分别处理后端和前端共享类型。
- T006、T007 可在不同测试文件并行准备。
- T014、T015 可在不同测试文件并行准备。
- T019、T020、T021 可在三个测试文件并行准备。
- T025 可与后端最终回归准备并行。

---

## 并行示例：用户故事 1

```text
Task: "在 backend/tests/test_scheduler.py 增加三态矩阵测试"
Task: "在 backend/tests/test_ai_resource_scheduling_assistant.py 增加响应和对比契约测试"
```

## 并行示例：用户故事 3

```text
Task: "增加推荐门禁兼容测试：backend/tests/test_ai_resource_scheduling_assistant.py"
Task: "增加历史快照哈希测试：backend/tests/test_plan_control_repository.py"
Task: "增加基准 API 兼容测试：backend/tests/test_plan_control_api.py"
```

---

## 实施策略

### MVP 优先

1. 完成 Phase 1、Phase 2。
2. 完成 US1，使页面三态可独立演示。
3. 完成 US2，使最大延期口径可独立验证。
4. 完成 US3，验证历史、推荐和计划执行链路。
5. 完成全量回归与页面验收。

### 兼容发布

1. 新响应同时提供新三态与旧四态字段。
2. 新客户端优先使用三态，旧客户端继续使用旧字段。
3. 历史数据只读映射，不迁移。
4. 后续版本确认无旧客户端依赖后，另行评审旧字段退役，不在本功能范围内删除。

## 备注

- 共 29 项任务；所有任务均包含任务编号和具体文件或验证路径。
- `[P]` 仅用于不同文件且无直接依赖的任务。
- 实施前必须完成 `$speckit-analyze` 并获得用户确认。
