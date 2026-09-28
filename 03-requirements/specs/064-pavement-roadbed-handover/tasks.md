# 实施任务：路床移交状态与开工边界

输入：[规格](./spec.md)、[计划](./plan.md)、[数据模型](./data-model.md)、[接口契约](./contracts/roadbed-handover.md)、[验证指南](./quickstart.md)。

状态：已实施。2026-09-24 用户明确要求“18 个有日期的施工段＋3 个已移交施工段参与排程，另外 4 段显示受阻原因”，按本表既有范围执行。实际验证见 quickstart.md；客户求解已通过输入校验，现有15秒时限内返回UNKNOWN，不宣称已获得可行计划。

## US1：保存并维护三态（3项）

- [x] T001 [US1] 在`04-demo/backend/tests/test_pavement_master.py`、`04-demo/backend/tests/test_pavement_api.py`、`04-demo/frontend/tests/pavementMaster.test.mjs`定义三态保存/回读/Excel往返、旧日期兼容、无状态无日期待定、非法组合、陈旧版本409及草稿保留验收；确认当前实现未满足新行为。（FR-001/002/006/007；US1.1～4、US3.3；SC-001/005/006）
- [x] T002 [US1] 在`04-demo/backend/app/contracts/pavement.py`、`04-demo/backend/app/contracts/project_master.py`、`04-demo/backend/app/contracts/__init__.py`定义路床状态和保存请求；在`04-demo/backend/app/project_master/definitions.py`、`04-demo/backend/app/project_master/workbook.py`增加参数及可选列；在`04-demo/backend/app/project_master/validation.py`实现共用三态解析与组合校验；在`04-demo/backend/app/project_master/service.py`、`04-demo/backend/app/api/routers/project_master.py`复用现有版本机制保存单段移交条件，仅改目标字段。（FR-001/002/006/007；D1/D2）
- [x] T003 [US1] 在`04-demo/frontend/src/contracts/pavement.ts`、`04-demo/frontend/src/contracts/projectMaster.ts`、`04-demo/frontend/src/contracts/index.ts`、`04-demo/frontend/src/api/projectMasterApi.ts`接入类型及保存；在`04-demo/frontend/src/features/projectMasterData/PavementSectionHandover.tsx`、`04-demo/frontend/src/features/projectMasterData/PavementMasterTable.tsx`、`04-demo/frontend/src/features/projectMasterData/styles.css`实现状态/日期/说明编辑和保存失败保留；在`04-demo/frontend/src/domain/pavement.ts`、`04-demo/frontend/src/features/logic/LogicTab.tsx`展示三态并复用版本回调使旧输入失效；用T001前端用例及`04-demo/frontend/tests/pavementWorkflow.test.mjs`验证状态转换。（FR-001/002/006/007；US1.1～4；D5）

## US2：筛选资格并守住开工边界（4项）

- [x] T004 [US2] 在`04-demo/backend/tests/test_pavement_generation.py`、`04-demo/backend/tests/test_pavement_solver.py`、`04-demo/backend/tests/test_pavement_api.py`加入quickstart混合样例、修改计划开始日、所有待定、空主数据、SS/SF和前置配套、固定顺序含待定段、直接求解绕过、同段状态冲突及真实资源/养生缺项场景；验证待定段无任务日期/资源且其他段不被缺路床日期阻断。（FR-003/004/005/009；US2.1～4；SC-002/003/005）
- [x] T005 [US2] 在`04-demo/backend/app/contracts/pavement.py`、`04-demo/backend/app/contracts/_models.py`、`04-demo/backend/app/contracts/__init__.py`定义范围元数据及可选ScheduleInput字段；在`04-demo/backend/app/project_master/scheduling_adapter.py`将段级条件权威投影且区分待定与错误；在`04-demo/backend/app/scheduling/generation/pavement.py`按段筛选核心/配套任务、保留完整引用检查及固定顺序相对次序，对每项纳入任务施加有效路床边界，并输出准确范围。（FR-003/004/005/006/009；D2/D3/D4）
- [x] T006 [US2] 在`04-demo/backend/app/scheduling/solver/strategies/pavement.py`统一校验三态并将路床下限纳入直接求解硬约束，拒绝pending任务和矛盾条件；在`04-demo/backend/app/scheduling/application/pavement.py`、`04-demo/backend/app/api/routers/scheduling.py`短路全待定、保持成功/失败范围元数据、保留其他错误和旧目标。（FR-003/004/005/009；US2.1～4；D3/D4）
- [x] T007 [US2] 在`04-demo/frontend/src/contracts/pavement.ts`、`04-demo/frontend/src/contracts/scheduler.ts`同步范围类型；在`04-demo/frontend/src/features/taskView/TaskViewWorkspace.tsx`、`04-demo/frontend/src/features/scheduleResults/ScheduleResultsWorkspace.tsx`、`04-demo/frontend/src/features/scheduleResults/presenter.ts`显示纳入范围、待定清单、部分范围日期及全待定空态；在`04-demo/frontend/tests/pavementWorkflow.test.mjs`、`04-demo/frontend/tests/pavementResults.test.mjs`验证无虚构日期、无旧历史范围误写及配置恢复。（FR-004/005/006/007；SC-006；D4/D5）

## 共享契约与发布前验证（1项）

- [x] T008 在`04-demo/backend/tests/test_pavement_contracts.py`、`04-demo/frontend/tests/contractsCompatibility.test.mjs`覆盖可选字段、旧输入和桥梁输出兼容；核对`04-demo/tools/demo-api-mirror/api.mts`仍明确拒绝路面；运行`03-requirements/specs/064-pavement-roadbed-handover/quickstart.md`列出的相关后端/前端测试批次和构建一次，按现有架构脚本只更新`04-demo/backend/tests/fixtures/architecture/backend-baseline.json`与`04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json`中本次可解释差异。失败只修本次核心问题，不将无关依赖哈希漂移并入。（FR-006/009；SC-001/005；D1～D5）

## US3：更新当前项目并验证可见效果（2项）

- [x] T009 [US3] 在`.local-data/tmp/pavement-section-update-20260924/`保存实施时的新基线导出及逐段映射，以既有`/api/projects/pavement-project/project-master/imports`和版本确认接口创建新快照；写入用户确认的18 dated/3 handed_over/4 pending，保护`.local-data/state/project-master.db`中历史版本及非移交字段；只同步`.local-data/state/scheduler-config.json`的版本引用，所有工效、资源、关系及计划日期逐项对比保持。发现新基线冲突则重读核对，不绕过版本保护。（FR-007/008；US3.1/2；SC-004；D6）
- [x] T010 [US3] 对T009新版本做HTTP回读/Excel再读及字段比较，确认25段100层、总长37,435m、宽9.2m、21段84层路床资格范围和4段16层未排程；按`04-demo/runtime/README.md`更新服务，在8000页面验证三态、保存失效、任务/结果范围；把实际证据及未补的其他排程条件写入`03-requirements/specs/064-pavement-roadbed-handover/quickstart.md`和本任务表，并更新`03-requirements/specs/README.md`状态。只报告真实通过的范围。（FR-005/007/008/009；US3.1～3；SC-004/006；D6）

## 依赖与执行顺序

T001→T002→T003→T004→T005→T006→T007→T008→T009→T010。当前文件交叉较多，不标[P]，不自动委派代理。

US1可独立验证保存；US2使用独立样例验证三态排程，不依赖客户其他缺参；US3在实现及相关验证通过后才升级真实项目。T008是本批唯一综合测试/构建，T010是不同证据的客户数据与浏览器验收，不重复运行同一完整测试批次。

## 一次跨产物一致性检查

| 规格或决策 | 任务覆盖 |
| --- | --- |
| FR-001/002 | T001～T003 |
| FR-003 | T004～T006 |
| FR-004 | T004～T007 |
| FR-005 | T004～T007、T010 |
| FR-006 | T001～T003、T005、T007、T008 |
| FR-007 | T001～T003、T007、T009、T010 |
| FR-008 | T009、T010 |
| FR-009 | T004～T008、T010 |
| SC-001 | T001、T002、T008 |
| SC-002/003 | T004～T006 |
| SC-004 | T009、T010 |
| SC-005 | T001、T004、T006、T008 |
| SC-006 | T001、T003、T007、T010 |
| US1.1～4 | T001～T003 |
| US2.1～4 | T004～T007 |
| US3.1/2 | T009、T010 |
| US3.3 | T001、T002、T008、T010 |
| D1/D2 | T001、T002、T005、T008 |
| D3 | T004～T006 |
| D4 | T005～T008 |
| D5 | T003、T007 |
| D6 | T009、T010 |

结论：10项，US1为3项、US2为4项、US3为2项、共享验证1项；术语、状态、日期边界、空态/错误码、范围统计及迁移口径一致，未发现需求覆盖缺口、无依据任务、规划外源码路径或重复全套测试任务。该检查形成于实施前，完成证据另见 quickstart.md。

实施范围：上述10项和一致性结果。用户本次明确要求落实既定排程范围，执行speckit-implement，未额外重走需求评审或analyze阶段。
