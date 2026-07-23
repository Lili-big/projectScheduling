# 任务清单：任务视图权威主数据快速加载

**输入**：`03-requirements/specs/062-task-view-master-loading/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/task-view-display-map-api.md` 和 `quickstart.md`

**前置条件**：用户确认本任务清单和一致性结果后，才能执行 `$speckit-implement`。

## Phase 1：用户故事 1 - 快速进入完整任务清单（P1）

**目标**：把任务视图从 13 次重型详情读取改为一次最小批量投影，并在现有基线下 5 秒内原子展示完整任务。

**独立测试**：使用 13 工点、1586 任务基线连续硬刷新 3 次；每次最多 1 个显示映射业务请求、5 秒内 ready、响应不超过 442 KB、任务 DOM 只提交一次。

### 测试先行

- [x] T001 [P] [US1] 在 `04-demo/backend/tests/test_project_master_version_api.py` 增加批量端点测试，覆盖乱序/重复工点归一化、最小字段、稳定顺序、空集合、缺失版本/工点、500 项边界与 501 项校验，并保留现有单工点详情字段断言。
- [x] T002 [P] [US1] 在 `04-demo/backend/tests/test_contracts_project_master.py` 固定 POST 路径、请求/响应 Pydantic schema、500 上限及既有项目主数据路径兼容性。
- [x] T003 [P] [US1] 在 `04-demo/frontend/tests/taskViewProjectMasterDisplay.test.mjs` 把协调器测试改为每个请求身份只调用一次批量 loader，并固定去空/去重/排序、完整成功原子提交、相同身份缓存和空集合零请求行为。
- [x] T004 [P] [US1] 在 `04-demo/frontend/tests/taskView.test.mjs` 与 `04-demo/frontend/tests/contractsCompatibility.test.mjs` 固定任务视图使用批量 API、共享最小投影类型且不再调用逐工点详情接口。
- [x] T005 [P] [US1] 在 `04-demo/frontend/tests/taskViewRuntime.test.mjs` 把成功场景网络证据改为批量端点，并记录连续 3 次硬刷新各自的业务请求数、加载到 ready 耗时、响应字节、DOM 提交次数和原始 ID 命中数。

### 实现

- [x] T006 [P] [US1] 在 `04-demo/backend/app/contracts/project_master.py` 增加批量请求、工点显示投影、工区显示投影和批量响应模型，落实 0～500 项和字段约束。
- [x] T007 [US1] 在 `04-demo/backend/app/project_master/repository.py` 实现按版本与工点集合精确查询的最小任务视图投影，整体拒绝缺失工点，并让 `get_workpoint()` 使用精确单工点完整查询而非 `load_snapshot()`。
- [x] T008 [US1] 在 `04-demo/backend/app/api/routers/project_master.py` 接入 `POST /api/project-master/versions/{version_id}/task-view-display-map`，复用项目主数据稳定错误结构，并同步 `04-demo/backend/app/main.py` 的公开导出（如当前入口需要）。
- [x] T009 [US1] 在 `04-demo/frontend/src/contracts/projectMaster.ts`、`04-demo/frontend/src/api/projectMasterApi.ts`、`04-demo/frontend/src/features/taskView/projectMasterDisplayState.ts`、`04-demo/frontend/src/features/taskView/presenter.ts` 和 `04-demo/frontend/src/app/Workspace.tsx` 接入单次批量 loader、最小投影 Map 和完整成功原子提交，删除任务视图逐工点请求路径。

**检查点**：批量接口和任务视图成功路径可独立运行；当前基线一次请求完成完整名称展示。

---

## Phase 2：用户故事 2 - 加速后仍保持权威与隔离（P2）

**目标**：批量化后继续保持加载/错误/重试、响应完整性、缓存身份和旧请求隔离，原始 ID 零泄漏。

**独立测试**：暂停、失败、重试、缺失/额外工点响应、版本切换、工点集合切换和旧响应晚到时，页面只提交当前身份的完整权威映射。

### 测试先行

- [x] T010 [P] [US2] 在 `04-demo/frontend/tests/taskViewProjectMasterDisplay.test.mjs` 增加版本不匹配、工点缺失/重复/额外、失败后重试、版本/集合快速切换和旧批量响应晚到测试，断言部分映射与旧身份提交次数为 0。
- [x] T011 [P] [US2] 在 `04-demo/frontend/tests/taskViewRuntime.test.mjs` 将失败拦截、重试和身份切换场景迁移到批量端点，继续断言加载态/错误态/最终 DOM、原始 ID 零命中及旧响应零覆盖。

### 实现

- [x] T012 [US2] 在 `04-demo/frontend/src/features/taskView/projectMasterDisplayState.ts` 增加批量响应版本/集合完整性校验，并保留 generation/token、成功缓存和 retry 语义；在 `04-demo/frontend/src/features/taskView/TaskViewWorkspace.tsx` 保持既有加载与错误/重试可见行为。
- [x] T013 [US2] 在 `04-demo/frontend/src/app/Workspace.tsx` 完成版本或规范化工点集合变化时的批量身份接线，确保旧映射不参与 `buildTaskViewRows()` 且无版本时沿用既有非权威路径。

**检查点**：成功、失败、重试和竞态场景均只显示当前身份的完整权威名称。

---

## Phase 3：跨故事验收

- [x] T014 按 `03-requirements/specs/062-task-view-master-loading/quickstart.md` 运行一次风险匹配验证批次：后端项目主数据接口/契约测试、前端任务视图定向测试、前端 build、真实浏览器连续 3 次性能与竞态测试、文档校验及 `git diff --check`；只修复本功能相关失败并记录无关剩余风险。

## 依赖与执行顺序

1. T001～T005 可并行编写失败测试；完成后确认现状不满足批量/性能契约。
2. T006 完成后执行 T007；T007 完成后执行 T008。
3. T006 可与 T003～T005 并行；T009 依赖 T006～T008 以及 T003/T004 的测试契约。
4. US1 检查点通过后执行 T010～T013；T010/T011 可并行，T012/T013 按状态机后接线顺序执行。
5. T014 依赖 T001～T013 全部完成，是实施完成门禁。

## 并行机会

- 后端测试 T001/T002、前端协调器测试 T003、静态契约测试 T004 和运行测试 T005 修改不同文件，可并行。
- 后端模型 T006 与前端测试准备 T003～T005 可并行。
- US2 的协调器测试 T010 与浏览器运行测试 T011 位于不同测试层，但都修改既有文件；若由同一工作树执行，应串行落盘以避免文件冲突。

## 需求与任务覆盖

| 来源 | 覆盖任务 |
|---|---|
| US1 验收 1～3；FR-001、FR-002、FR-003、FR-004、FR-005、FR-009、FR-010、FR-011、FR-012；SC-001、SC-002、SC-005 | T001～T009、T014 |
| US2 验收 1～4；FR-004、FR-005、FR-006、FR-007、FR-008、FR-011、FR-012、FR-013；SC-003、SC-004、SC-005 | T010～T014 |
| 最小载荷、单详情兼容、空态与 500 项边界 | T001、T002、T006～T009、T014 |
| 性能、请求数、响应体、原子 DOM 与原始 ID 零泄漏 | T005、T009、T011～T014 |

## 实施边界

- 不新增依赖、持久化迁移、兼容层或全局状态管理。
- 不修改任务生成、排程算法、资源/工期模型、项目主数据导入/确认和任务视图布局。
- 不触碰当前工作树中的 feature 061、架梁模拟或客户验证资产改动。
