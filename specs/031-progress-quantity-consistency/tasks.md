# 任务清单：实际进度工程量一致性

**输入**：来自 `specs/031-progress-quantity-consistency/` 的规格、研究、数据模型、接口契约和验证指南

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/progress-quantity-contract.md`、`quickstart.md`

**测试要求**：本功能调整进度归一化和滚动预测输入，必须先增加后端公式、状态矩阵、接口错误、历史兼容和预测失效测试；实施后必须运行完整后端回归、前端生产构建和真实页面验证。

**组织方式**：任务按用户故事分组，确保四列展示、同步填报和历史状态兼容均可独立验证。

## Phase 1：准备（共享基础）

**目标**：确认本功能边界和现有工作区状态，保留 Spec 028–030 及用户的其他未提交修改。

- [X] T001 记录当前 `git status`、`.specify/feature.json` 和 `specs/031-progress-quantity-consistency/plan.md` 所列目标文件，实施时不得覆盖 028–030 或其他用户修改
- [X] T002 [P] 对照 `specs/031-progress-quantity-consistency/contracts/progress-quantity-contract.md` 复核 `backend/app/models.py`、`frontend/src/types/scheduler.ts` 和 `frontend/src/api/schedulerApi.ts`，确认不新增总工程量字段或接口路径

---

## Phase 2：基础能力（阻塞前置）

**目标**：先建立所有故事共用的工程量公式、浮点容差和状态归一化基础。

- [X] T003 在 `backend/tests/test_progress_forecast.py` 增加总量/比例/已完/剩余公式、浮点容差、无效总量、空值清除和冲突输入的先行测试
- [X] T004 在 `backend/app/services/progress_forecast.py` 建立只使用计划任务 `quantity` 的进度工程量归一化 helper，并保持 `ProgressEntry` 字段形状不变

**检查点**：后端具备可复用的工程量计算与一致性判定能力，用户故事可以在同一规则上实施。

---

## Phase 3：用户故事 1 - 查看完整工程量进度（优先级：P1）

**目标**：用户能在每个任务行同时核验总工程量、实际完成比例、实际已完工程量和剩余工程量。

**独立测试**：加载一个有活动计划的项目，验证总量 `10m` 的任务行按约定顺序展示四列，总量来自活动计划且数量列不混入结构物参数。

### 用户故事 1 的测试

- [X] T005 [P] [US1] 在 `backend/tests/test_plan_control_api.py` 增加项目汇总响应中活动计划任务总工程量及纯 `quantity_label` 可用于进度展示的契约测试

### 用户故事 1 的实现

- [X] T006 [US1] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 将表头调整为“总工程量、实际完成比例、实际已完工程量、剩余工程量”，并从活动计划任务只读展示总量
- [X] T007 [P] [US1] 在 `frontend/src/styles.css` 调整进度表最小宽度、只读工程量样式、横向滚动和表头固定布局
- [ ] T008 [US1] 按 `specs/031-progress-quantity-consistency/quickstart.md` 验证有计划、无计划、筛选和分页场景下四列展示与任务单位口径

**检查点**：US1 完成后，页面已形成四列核验入口，但双入口同步和状态兼容由后续故事补齐。

---

## Phase 4：用户故事 2 - 一致地填报完成进度（优先级：P1）

**目标**：用户编辑实际完成比例或实际已完工程量时立即得到一致的另外两项数据，保存与滚动预测使用同一剩余量。

**独立测试**：总量 `10m` 输入 `40%` 或 `4m` 均得到 `40% / 4m / 6m`；实际工效 `2m/天` 得到 3 天；冲突请求返回可定位任务的 422。

### 用户故事 2 的测试

- [X] T009 [US2] 在 `backend/tests/test_progress_forecast.py` 增加比例入口、已完量入口、空值清除、`10m → 40% → 4m/6m`、`6m ÷ 2m/天 → 3天` 和服务端归一化响应测试
- [X] T010 [P] [US2] 在 `backend/tests/test_plan_control_api.py` 增加一致请求成功、比例/数量冲突、数量和不等于总量、负数与超总量返回 422 的接口测试，并断言错误可通过 `task_id` 或进度项索引定位

### 用户故事 2 的实现

- [X] T011 [US2] 在 `backend/app/services/progress_forecast.py` 将 `_normalize_progress_entry` 接入共享工程量 helper，拒绝冲突新请求并使用归一剩余量计算剩余工期
- [X] T012 [US2] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 实现实际完成比例与实际已完工程量双入口即时同步，将剩余工程量改为只读派生值
- [X] T013 [US2] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 使用保存响应替换当前行归一值，并保持保存后旧预测、旧调整方案及错误提示的现有失效链路
- [X] T014 [US2] 在 `frontend/src/styles.css` 为可编辑与只读进度值增加一致视觉区分，并保证 50 行页面编辑不产生新增网络请求
- [ ] T015 [US2] 按 `specs/031-progress-quantity-consistency/quickstart.md` 完成双入口切换、空值清除与恢复、保存刷新、计算剩余工期和冲突错误页面验证

**检查点**：US2 完成后，新进度快照和滚动预测使用唯一一致的剩余工程量。

---

## Phase 5：用户故事 3 - 按任务状态与历史快照安全兼容（优先级：P2）

**目标**：五种任务状态均形成明确工程量值；历史缺失或冲突快照可读、可提示、可审计更正且不改写原记录。

**独立测试**：验证未开始、进行中、已完成、暂停、取消状态矩阵，并加载缺失数量或数量冲突的旧快照，确认派生展示、质量提示、修订审计和文件哈希不变。

### 用户故事 3 的测试

- [X] T016 [US3] 在 `backend/tests/test_progress_forecast.py` 增加五状态工程量矩阵、暂停人工剩余工期、取消物理剩余量与 0 天排程工期测试
- [X] T017 [P] [US3] 在 `backend/tests/test_plan_control_repository.py` 增加历史快照缺失工程量字段、数量关系冲突、只读加载哈希不变和新修订保留原快照测试
- [X] T018 [P] [US3] 在 `backend/tests/test_plan_control_api.py` 增加历史项目汇总可加载、同日更正原因/修订号和归一新修订响应测试

### 用户故事 3 的实现

- [X] T019 [US3] 在 `backend/app/services/progress_forecast.py` 补齐未开始、已完成、暂停和取消状态的工程量归一化，并保持现有日期、原因和人工剩余工期校验
- [X] T020 [US3] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 实现状态切换自动值、暂停/取消实绩保留、无效总量兼容路径及字段启停规则
- [X] T021 [US3] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 为历史缺失数量派生只读展示，为历史数量冲突显示质量提示且不自动写回
- [X] T022 [US3] 在 `backend/app/services/plan_control_repository.py` 保持历史 `load` 与项目汇总为纯读取，并确保页面派生值不会写入存储、只有显式更正请求才创建新修订
- [ ] T023 [US3] 按 `specs/031-progress-quantity-consistency/quickstart.md` 完成五状态、历史缺失、历史冲突、更正原因和旧预测失效验证

**检查点**：全部用户故事可独立验证，历史审计和当前滚动预测输入同时成立。

---

## Phase 6：收尾与横切事项

**目标**：同步文档并完成接口、持久化、前端和真实页面全链路验证。

- [X] T024 [P] 对照 `specs/031-progress-quantity-consistency/data-model.md` 静态复核 `backend/app/models.py` 与 `frontend/src/types/scheduler.ts` 的 `ProgressEntry` 可空字段和兼容默认值，确认无需共享字段迁移
- [X] T025 [P] 更新 `docs/基建智能计划管控中枢整体产品方案_v1.0.md` 中实际进度反馈口径，补充四列、同步公式、状态矩阵和历史兼容说明
- [X] T026 运行 `python -m pytest backend/tests/test_progress_forecast.py backend/tests/test_plan_control_api.py backend/tests/test_plan_control_repository.py -q` 并修复本功能回归
- [X] T027 运行 `npm.cmd run build` 与 `git diff --check`，核验 `frontend/src/features/planControl/PlanControlPanel.tsx`、`frontend/src/styles.css` 及全仓格式
- [ ] T028 按 `specs/031-progress-quantity-consistency/quickstart.md` 完成真实页面端到端验证，确认四列、双入口、单位、状态、刷新、分页、错误和预测失效
- [X] T029 运行 `python -m pytest backend/tests -q` 全量回归，并对照 `AGENTS.md`、`.specify/memory/constitution.md` 和本功能产物准备 `$speckit-converge` 证据

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1 准备**：无依赖，可立即开始。
- **Phase 2 基础能力**：依赖 Phase 1，阻塞全部用户故事。
- **US1（Phase 3）**：依赖 Phase 2，先交付四列只读核验。
- **US2（Phase 4）**：依赖 Phase 2；完整页面交付复用 US1 四列布局。
- **US3（Phase 5）**：依赖 Phase 2；历史页面展示复用 US1，状态同步复用 US2。
- **Phase 6 收尾**：依赖三个故事完成。

### 用户故事依赖

- **US1（P1）**：基础能力完成后可独立验证总量来源与四列展示。
- **US2（P1）**：后端公式可独立验证；完整页面交互依赖 US1 的四列结构。
- **US3（P2）**：后端状态与历史兼容可独立测试；页面集成依赖 US1/US2。

### 单个故事内部顺序

- 测试任务先于对应实现任务。
- 后端公式和服务归一化先于前端保存联调。
- 页面即时同步先于历史派生和状态矩阵完善。
- 当前故事完成独立测试后再进入收尾回归。

### 并行机会

- T002 可与 T001 的工作区记录并行。
- T005 与 T007 位于不同边界，可并行。
- T009 与 T010 位于不同测试文件，可在 Phase 4 内并行准备。
- T017 与 T018 位于不同测试文件，可并行准备历史兼容测试。
- T024 与 T025 分别是契约复核和文档更新，可并行。

## 并行示例：用户故事 2

```text
Task: "在 backend/tests/test_progress_forecast.py 增加公式、归一化和剩余工期测试"
Task: "在 backend/tests/test_plan_control_api.py 增加成功与 422 接口契约测试"
```

## 并行示例：用户故事 3

```text
Task: "在 backend/tests/test_plan_control_repository.py 增加历史加载和哈希不变测试"
Task: "在 backend/tests/test_plan_control_api.py 增加历史汇总和修订接口测试"
```

## 实施策略

### MVP 优先

本功能最小可用闭环为 Phase 1、Phase 2、US1 和 US2：用户可以看到总量，并通过比例或已完量得到一致的剩余工程量和剩余工期。US3 历史兼容必须在正式合并前完成，但不阻塞首轮公式和页面演示。

### 增量交付

1. 建立后端公式和冲突校验。
2. 完成 US1 四列展示。
3. 完成 US2 双入口同步与预测输入一致性。
4. 完成 US3 状态矩阵、历史派生和审计兼容。
5. 同步文档并执行完整回归与页面验证。

## 备注

- `[P]` 仅用于不同文件且无未完成依赖冲突的任务。
- 不新增 `total_quantity` 字段、接口、依赖、存储版本或 Netlify 计划管控镜像。
- 历史快照只读加载不形成自动修订；用户保存更正时才创建新快照。
