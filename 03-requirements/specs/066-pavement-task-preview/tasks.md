# 实施任务：路面任务自动准备与统一工序链

**状态**：用户已确认实施；10/10完成，验证证据见[quickstart.md](./quickstart.md)。  
**输入**：[spec.md](./spec.md)、[plan.md](./plan.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[页面与API合同](./contracts/task-preview.md)、[quickstart.md](./quickstart.md)。

## 计算与兼容验收

- [x] T001 在 `04-demo/backend/tests/test_pavement_generation.py`、`04-demo/backend/tests/test_pavement_api.py`、`04-demo/backend/tests/test_pavement_solver.py` 建立25段100任务75关系、方法/方案覆盖、1790/800与1790/1000、缺项仍返回已知任务、显式间歇不重复累计、非末层日期保留、无末层条件可求解、旧直接载荷诊断和完成日期边界样例；在 `04-demo/frontend/tests/pavementTaskPreview.test.mjs` 建立投影与可控请求用例，复用 `04-demo/frontend/tests/pavementWorkflow.test.mjs` 覆盖关系优先级。已有正确行为不为制造失败而修改。

## US3：唯一工序链与施工完成口径

- [x] T002 [US3] 修改 `04-demo/backend/app/scheduling/generation/pavement.py` 和 `04-demo/backend/app/scheduling/solver/strategies/pavement.py`：层间按分段>统一>旧条件生效且显式间歇不叠加；保留非末层验收日期及配套/跨段限制。按实际启用层序排除末尾条件，不生成readiness、不要求末层wait_basis；旧直接求解载荷带末层条件时明确提示重新生成。目标取最晚施工任务完成边界，完成日期及末层完成里程碑按finish_date校核，兼容字段与旧结果标识遵循合同，不修改客户存储。
- [x] T003 [US3] 修改 `04-demo/frontend/src/features/logic/LogicTab.tsx`、`04-demo/frontend/src/domain/pavement.ts`、`04-demo/frontend/src/styles/domain-editors.css`：用现有关系行清晰表达唯一工序链，保留统一/分段和四类关系；移除下方施工段养生表、批量等待、末层输入及引导。旧非末层等待在链中回显，编辑只写dependency_rules；已有非末层验收日期在对应分段关系行可选条件内维护，保留旧等待字段。配套与固定跨段顺序留在默认收起的其他配置。

## US1：完整任务分解

- [x] T004 [US1] 在 `04-demo/frontend/src/domain/pavement.ts` 实现按启用层/配套到后端任务的纯展示投影，按段及层序组织，按process_id/productivity_rule_id匹配工效；保留缺项行并核对关系类型/间歇/来源，必要时增补pavementDependencyRows源目标身份。处理未知间歇、缺项中间层、正/零天配套、固定跨段及循环/无效引用，不复制工期算法。

## US2：当前输入自动更新

- [x] T005 [US2] 在 `04-demo/frontend/src/app/workflows/scenarioWorkflow.ts` 实现可注入生成函数的预览控制，复用指纹；同输入复用、请求序号与指纹防旧响应覆盖、离页失效、显式重试。在 `04-demo/frontend/tests/pavementTaskPreview.test.mjs` 用可控Promise验证次序/失败/离页/复用和无自动保存或求解副作用。

## 页面接入

- [x] T006 [US1] 修改 `04-demo/frontend/src/features/taskView/TaskViewWorkspace.tsx` 和 `04-demo/frontend/src/features/taskView/styles.css`：以一张按段折叠的紧凑表替代两张表，默认展开，显示工序、计量工程量、工效方案、实际工效、工期、前置工序和关系；首道独立标示路床条件。未知值显示待完善，保留加载/空态/诊断/重试/保存入口，去除旧“天/套”“专用机组”文案。
- [x] T007 [US2] 在 `04-demo/frontend/src/app/Workspace.tsx` 的PavementWorkspace接入独立preview状态：任务页进入/输入变化合并快速请求、范围固定全项目，隔离求解历史；保存工效复用dirty/error，删除跳往模拟页生成引导及旧手动生成按钮。离页不被请求跳回，失败保留编辑且不无限重试；在 `04-demo/frontend/tests/pavementWorkflow.test.mjs` 验证工效/主数据/关系修改导致预览与历史结果失效。
- [x] T008 [US3] 在 `04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx`、`04-demo/frontend/src/features/scheduleResults/presenter.ts` 以施工完成日期显示本轮结果，隐藏末层可用/交付节点；旧目标或含readiness的结果保留历史并提示重新求解。用 `04-demo/frontend/tests/pavementResults.test.mjs` 验证完成日期不多一天、历史数据不被新语义误读及桥梁展示不变。

## 验证与完成证据

- [x] T009 按 `03-requirements/specs/066-pavement-task-preview/quickstart.md` 运行一次相关pytest、node:test及构建，包含 `04-demo/frontend/tests/contractsCompatibility.test.mjs`；核对生成/求解工期与关系一致、末层排除在各入口一致，桥梁及065共享机组行为保留。相关失败最小修复后只复测受影响项，记录非核心既有问题。
- [x] T010 [US1] 按 `04-demo/runtime/README.md` 更新页面，先检查未保存状态；浏览器验证25组/100任务/75关系、首段3天、折叠与工效修改自动更新，以及唯一工序链、统一/分段编辑、无重复或末尾养生输入。临时编辑恢复原值，不保存测试数据；核对预览前后配置不变。将实际证据与仍缺路床条件的限制记入 `03-requirements/specs/066-pavement-task-preview/quickstart.md`，更新本文件和 `03-requirements/specs/README.md`。

## 依赖与执行顺序

串行T001→T002→T003→T004→T005→T006→T007→T008→T009→T010，不使用子代理。共10项：US1三项、US2两项、US3三项、共享验证两项。先统一计算/逻辑口径，再投影和自动更新，最后统一验证。不新增独立分析/审查阶段，不合并实施064路床三态。

## 一致性检查（2026-09-24，本轮范围修订）

| 需求/验收/决策 | 对应任务与证据 |
| --- | --- |
| FR-001；US1-1；SC-001；D1 | T001、T005、T007、T010 |
| FR-002；US1-2；D3、D6 | T004、T006、T010 |
| FR-003；US1-3、US2-1；SC-002；D4 | T001、T004、T006、T009、T010 |
| FR-004；US1-4、US1-5；SC-003；D5 | T001、T003、T004、T006、T009 |
| FR-005；US1-6、US2-3、US2-4；D7 | T001、T002、T004、T006、T009 |
| FR-006；US2-1、US2-5；D8 | T005、T006、T007、T009、T010 |
| FR-007；US2-2、US2-5；SC-004；D2 | T005、T007、T009、T010 |
| FR-008；SC-004、SC-005；D9 | T001、T002、T005、T007—T010 |
| FR-009；US3-1、US3-2、US3-3；SC-006；D10、D11 | T001—T004、T009、T010 |
| FR-010；US3-4、US3-5；SC-007；D12 | T001、T002、T008—T010 |

结论：10个唯一任务ID，全部10项FR、7项SC、三故事验收及D1—D12均覆盖；无悬空需求、重复全量验证或先用后建依赖。目标路径均在plan内。移除原文“末层条件保持不变”等冲突，未新增API字段、依赖或持久化迁移；仅调整已明确的本轮末尾场景边界。修订清单经用户确认后已实施，实际结果见quickstart。