# 任务清单：统一工点与结构物主数据

**输入**：来自 `specs/043-unified-workpoint-structure/` 的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**测试要求**：本功能涉及结构化持久化、Excel 导入、前后端共享字段、排程输入和下游失效，测试任务为必需项。每个用户故事必须完成其独立测试后才能视为交付。

## Phase 1：准备（共享基础）

**目标**：建立独立项目主数据领域的最小目录和配置边界，不触碰旧数据。

- [x] T001 建立项目主数据后端包和公开导出边界：`backend/app/project_master/__init__.py`
- [x] T002 [P] 在 `backend/app/config/environment.py` 增加可覆盖的 `PROJECT_MASTER_DB_PATH`、SQLite busy timeout 和导入文件大小配置，默认数据库为 `.local-data/project-master.db`
- [x] T003 [P] 建立项目主数据测试样例约定并声明禁止使用旧 JSON 作为输入：`backend/tests/fixtures/project_master/fixture-conventions.md`

---

## Phase 2：基础能力（阻塞前置）

**目标**：完成所有用户故事共同依赖的契约、定义目录、SQLite schema、仓储和应用装配；本阶段完成前不得开始用户故事实现。

- [x] T004 [P] 为建表、外键、部分唯一索引、不可变确认版本、事务回滚和重启恢复编写失败测试：`backend/tests/test_project_master_repository.py`
- [x] T005 [P] 定义版本、工点、结构物、构件、参数、批次、问题、差异和来源的 Pydantic 契约：`backend/app/contracts/project_master.py`
- [x] T006 [P] 固化工点类型、结构类型、构件类型、参数类型、幅别规则和 definition version 种子目录：`backend/app/project_master/definitions.py`
- [x] T007 实现 SQLite `PRAGMA user_version` 初始化、关系表、索引、外键、WAL 和 busy timeout：`backend/app/project_master/schema.py`
- [x] T008 实现 `ProjectMasterRepository` 的连接生命周期、事务、版本子树写入和分页读取，并通过 T004：`backend/app/project_master/repository.py`
- [x] T009 [P] 为 `CURRENT_VERSION_CHANGED`、`IMPORT_BLOCKED`、`VERSION_IMMUTABLE`、`REFERENCE_CONFLICT` 和仓储不可用补充稳定 HTTP 错误映射：`backend/app/api/errors.py`
- [x] T010 将默认项目主数据仓储装配到 FastAPI 生命周期且不扫描旧 `.local-data/*.json`：`backend/app/bootstrap.py`

**检查点**：空库可初始化；结构化对象可事务写入和重启读取；一个项目至多一个当前确认版本；旧数据不会被自动读取。

---

## Phase 3：用户故事 1 - 导入统一工点与结构物主数据（优先级：P1）

**目标**：计划工程师使用四工作表新模板上传一份完整快照，系统保存可追溯批次；合法文件形成草稿，非法文件形成阻断问题而不污染主数据版本。

**独立测试**：在空库上传包含 1 座左右幅桥、1 段路基、1 座隧道的合法模板，得到 3 个工点和一个 `ready` 草稿；上传含重复 ID、错误父级和非法幅别的模板，只得到 `blocked` 批次和精确行列问题；重复上传保存新的 `unchanged` 批次但不增加业务版本；取消 `blocked/ready` 批次后保留审计、清理未确认草稿且当前版本不变。

### 用户故事 1 的测试

- [x] T011 [P] [US1] 实现可重复生成合法、阻断、警告和大规模工作簿的测试助手：`backend/tests/project_master_fixture_helpers.py`
- [x] T012 [P] [US1] 为模板生成、四表解析、字段规范化、参数列、稳定 ID、父子关系和桥梁必填参数编写失败测试：`backend/tests/test_project_master_workbook.py`
- [x] T013 [P] [US1] 为模板下载、快照上传、批次查询、批次取消、`unchanged` 引用、`201/202/409/413/422/503` 和错误定位编写 API 测试：`backend/tests/test_project_master_api.py`

### 用户故事 1 的实现

- [x] T014 [P] [US1] 实现“填写说明、工点信息、结构物信息、构件参数”模板生成、导出列定义、解析和规范化指纹：`backend/app/project_master/workbook.py`
- [x] T015 [P] [US1] 实现文件级、字段级、稳定 ID、父子关系、类型/幅别、工程量和桥梁必需参数校验：`backend/app/project_master/validation.py`
- [x] T016 [US1] 实现导入批次状态机、阻断问题持久化、合法快照事务建草稿、重复内容新建 `unchanged` 批次并引用已有版本，以及取消时保留审计并事务清理未确认草稿：`backend/app/project_master/service.py`
- [x] T017 [US1] 实现 `GET /api/project-master/template`、`POST /api/projects/{project_id}/project-master/imports`、`GET /api/project-master/imports/{batch_id}` 和批次取消端点：`backend/app/api/routers/project_master.py`
- [x] T018 [US1] 注册项目主数据 router 并保持现有 endpoint façade 可导入：`backend/app/api/routers/__init__.py`、`backend/app/bootstrap.py`、`backend/app/main.py`

**检查点**：US1 可通过 API 独立完成“下载模板 → 上传 → 查看批次/问题 → 合法文件得到草稿”，无需旧导入器或旧 JSON。

---

## Phase 4：用户故事 2 - 检查差异并确认项目主数据版本（优先级：P1）

**目标**：用户按稳定 ID 查看相对当前版本的新增、修改、删除，确认无阻断草稿；系统以单事务切换唯一当前版本并处理并发冲突。

**独立测试**：以 V1 为基线导入包含新增、修改、删除的 V2，差异分类和字段值完全正确；A 确认后 B 使用旧期望版本确认返回 `409 CURRENT_VERSION_CHANGED`，V2 为唯一当前版本，V1 历史仍可读且不可修改。

### 用户故事 2 的测试

- [x] T019 [P] [US2] 为对象/字段级差异、漏行删除、格式无关幂等和首次空基线编写失败测试：`backend/tests/test_project_master_diff.py`
- [x] T020 [P] [US2] 为告警知悉、确认事务、状态迁移、不可变历史、乐观并发和受引用删除编写失败测试：`backend/tests/test_project_master_confirmation.py`
- [x] T021 [P] [US2] 为版本列表、当前版本、版本详情和确认接口的 `200/404/409/422/503` 编写契约测试：`backend/tests/test_project_master_version_api.py`

### 用户故事 2 的实现

- [x] T022 [US2] 实现以规范化稳定 ID 对齐的对象级和字段级新增、修改、删除差异：`backend/app/project_master/diff.py`
- [x] T023 [US2] 在单 SQLite 事务内实现版本号分配、期望当前版本校验、原版本替代、新版本确认和确认审计：`backend/app/project_master/repository.py`
- [x] T024 [US2] 实现告警知悉、受计划/实绩引用删除检查、期望当前版本冲突处理和版本确认编排：`backend/app/project_master/service.py`
- [x] T025 [US2] 实现版本列表、当前版本、版本详情和 `POST /api/project-master/versions/{version_id}/confirm`：`backend/app/api/routers/project_master.py`

**检查点**：US2 可独立证明全量快照不会静默覆盖数据，确认具有不可变历史、唯一当前版本和并发保护。

---

## Phase 5：用户故事 3 - 统一查看工点和结构物（优先级：P1）

**目标**：用户在“项目主数据”一个入口查看版本、导入问题、差异和“工点 → 结构物 → 构件参数”完整层级，并能导出当前快照；页面不再提供旧桥梁结构和旧架梁工点导入交互。

**独立测试**：页面在无版本、校验中、阻断、可确认和确认成功状态下均有明确反馈；500 工点列表分页加载，单工点仅加载自身子树；抽查对象可追溯到批次/工作表/行号；旧两个导入按钮均不存在。

### 用户故事 3 的测试

- [x] T026 [P] [US3] 为分页工点、单工点子树、来源证据和版本导出的 API 编写失败测试：`backend/tests/test_project_master_query_api.py`
- [x] T027 [P] [US3] 为前端 API 请求、分页参数、二进制模板/导出、批次轮询和错误码映射编写测试：`frontend/tests/projectMasterApi.test.mjs`
- [x] T028 [P] [US3] 为页面空态、导入问题、差异、告警确认、版本历史、工点层级和旧入口消失编写交互测试：`frontend/tests/projectMasterData.test.mjs`

### 用户故事 3 的实现

- [x] T029 [US3] 实现分页工点、单工点完整子树和来源证据查询端点：`backend/app/api/routers/project_master.py`
- [x] T030 [US3] 实现指定版本到统一四工作表 Excel 的无损导出：`backend/app/project_master/workbook.py`
- [x] T031 [US3] 实现 `GET /api/project-master/versions/{version_id}/export` 并设置正确 MIME 与文件名：`backend/app/api/routers/project_master.py`
- [x] T032 [P] [US3] 建立与 OpenAPI 一致的前端版本、批次、差异、工点、结构物、构件和来源类型：`frontend/src/contracts/projectMaster.ts`
- [x] T033 [P] [US3] 实现模板下载、导入、批次轮询、版本、确认、分页工点、明细和导出客户端：`frontend/src/api/projectMasterApi.ts`
- [x] T034 [P] [US3] 实现主数据层级排序、类型/幅别标签、差异分组和错误展示映射：`frontend/src/domain/projectMaster.ts`
- [x] T035 [P] [US3] 实现工点类型筛选、关键字和服务端分页列表：`frontend/src/features/projectMasterData/WorkPointList.tsx`
- [x] T036 [P] [US3] 实现工点基础信息、结构物、构件参数、排程支持状态和来源证据明细：`frontend/src/features/projectMasterData/WorkPointDetail.tsx`
- [x] T037 [P] [US3] 实现上传进度、问题定位、差异预览、告警知悉和确认动作：`frontend/src/features/projectMasterData/ImportPreview.tsx`
- [x] T038 [P] [US3] 实现当前/草稿/已替代版本列表及版本切换查看：`frontend/src/features/projectMasterData/VersionHistory.tsx`
- [x] T039 [US3] 组合空态、模板下载、导入、差异确认、版本、工点列表与明细页面：`frontend/src/features/projectMasterData/ProjectMasterDataWorkspace.tsx`、`frontend/src/features/projectMasterData/styles.css`
- [x] T040 [US3] 将 `projectFiles` 导航显示名改为“项目主数据”并接入新 workspace；新增独立 `parameterAssistant` 导航入口，移除参数助手中的桥梁结构 Excel 导入动作且不接入主数据写入：`frontend/src/contracts/scheduler.ts`、`frontend/src/features/layout/WorkspaceNavigation.tsx`、`frontend/src/app/Workspace.tsx`、`frontend/src/features/assistant/parameter/ParameterAssistantPanel.tsx`

**检查点**：US3 提供唯一主数据维护入口；完整层级、来源和历史无需打开原始 Excel 即可查询，页面不再要求重复导入或手工映射。

---

## Phase 6：用户故事 4 - 使用统一主数据生成桥梁排程输入（优先级：P1）

**目标**：当前确认版本中的桥梁工点和结构物投影为现有排程模型，保持任务业务语义；非桥工点不进入桥梁排程；场景、计划和架梁专项只引用主数据版本和稳定 ID。

**独立测试**：同一桥梁业务数据经旧结构模型和新确认版本分别生成任务，业务键、工点、幅别、工区、结构物、构件、工程量和前后置边 100% 一致；路基/隧道生成桥梁任务数为 0；确认结构变化版本后旧任务、求解、比较、计划和专项状态均标为 `stale`。

### 用户故事 4 的测试

- [x] T041 [P] [US4] 固化包含左右幅、共用结构、墩台、简支跨、现浇联和连续联的业务等价基线：`backend/tests/fixtures/project_master/bridge-projection-baseline.json`
- [x] T042 [P] [US4] 为确认版本到 `ProjectModel` 的字段映射、桥梁任务业务快照等价和非桥过滤编写失败测试：`backend/tests/test_project_master_adapter.py`
- [x] T043 [P] [US4] 为版本指纹变化后的任务图、求解、比较、计划和专项失效编写失败测试：`backend/tests/test_project_master_invalidation.py`
- [x] T044 [P] [US4] 为 `workpoint_id + side` 路线节点派生、稳定引用和旧工点导入不再必需编写失败测试：`backend/tests/test_project_master_girder_projection.py`

### 用户故事 4 的实现

- [x] T045 [US4] 实现桥梁工点到 `ProjectBridge`、`section_code + side` 到 `WorkSection`、上下部结构和构件到现有排程模型的纯适配器：`backend/app/project_master/scheduling_adapter.py`
- [x] T046 [US4] 在规范定义中让场景契约继续使用现有 `project_data_version_id` 引用 SQLite 确认版本并继续以 `input_fingerprint` 表示完整排程输入，禁止新增并列的 `project_master_version_id/project_master_fingerprint`，保留 `ProjectModel` 作为排程投影，并通过领域 façade 导出 `ScenarioInput`：`backend/app/contracts/_models.py`、`backend/app/contracts/scheduling.py`
- [x] T047 [US4] 调整场景生成只从当前确认主数据版本获取桥梁投影，并返回缺参和非桥不支持诊断：`backend/app/scheduling/application/_scenario.py`
- [x] T048 [US4] 将新方案/计划改为保存主数据版本引用而不新增 `project_data_versions` JSON 快照，并实现版本变化失效判定：`backend/app/plan_control/repository.py`、`backend/app/services/plan_control_repository.py`
- [x] T049 [US4] 从统一 `workpoint_id + side` 派生架梁路线工点视图并让路线/梁场/设备/通行条件继续属于专项配置：`backend/app/girder_planning/ownership.py`、`backend/app/girder_planning/application.py`
- [x] T050 [US4] 将架梁专项页面改为选择派生工点，不再上传独立工点 Excel：`frontend/src/features/girderPlanning/GirderPlanningPanel.tsx`、`frontend/src/features/girderPlanning/RouteEditor.tsx`
- [x] T051 [P] [US4] 在规范定义中同步前端 `ScenarioInput` 沿用 `project_data_version_id` 和 `input_fingerprint`，通过领域 façade 导出该类型并更新场景请求装配，不新增 `project_master_*` 字段：`frontend/src/contracts/scheduler.ts`、`frontend/src/contracts/scheduling.ts`、`frontend/src/app/workflows/scenarioWorkflow.ts`
- [x] T052 [US4] 标记旧结构参数和旧工点导入端点为弃用兼容入口并保证其不读写新 SQLite 主数据：`backend/app/api/routers/system.py`、`backend/app/api/routers/project_girder.py`

**检查点**：US4 证明存储重构未改变桥梁排程规则，非桥工点安全隔离，所有下游对象可追溯到唯一确认主数据版本。

---

## Phase 7：收尾与横切事项

**目标**：验证规模、契约、兼容边界和完整回归，交付可复现证据。

- [x] T053 [P] 为 500 工点、10,000 结构物、50,000 构件的 30 秒导入目标和分页查询编写基准测试：`backend/tests/test_project_master_performance.py`
- [x] T054 [P] 校验实现路由和共享字段未偏离 OpenAPI/Excel 契约：`backend/tests/test_contracts_project_master.py`
- [x] T055 [P] 断言新主数据运行路径对 `project-structure-params.json`、旧 `project_data_versions` 快照和旧导入器的依赖为 0：`backend/tests/test_project_master_legacy_boundary.py`
- [x] T056 运行并记录后端项目主数据测试、现有桥梁/架梁/计划回归、前端测试和构建结果：`specs/043-unified-workpoint-structure/quickstart.md`
- [x] T057 按合法、阻断、幂等、取消、删除、并发、重启恢复、排程等价和下游失效场景完成单服务验收，并随机抽查不少于 20 个工点及其结构物从确认版本追溯到批次、工作表和行号的成功率达到 100%：`specs/043-unified-workpoint-structure/quickstart.md`

---

## 依赖与执行顺序

### 阶段依赖

```text
Phase 1 准备
   ↓
Phase 2 基础能力
   ↓
US1 导入完整快照
   ↓
US2 差异与确认
   ├──────────────→ US3 统一查看与维护
   └──────────────→ US4 桥梁排程投影
                         ↓
                   Phase 7 收尾验证
```

- Phase 1 无依赖。
- Phase 2 依赖 Phase 1，并阻塞全部用户故事。
- US1 依赖 Phase 2；它是建立草稿数据的最小 MVP。
- US2 依赖 US1 的批次和草稿版本。
- US3 依赖 US1/US2 的 API 语义；完成后形成完整用户维护闭环。
- US4 依赖 US2 的确认版本；可与 US3 在不同文件范围内并行。
- Phase 7 依赖目标用户故事完成。

### 单个故事内部顺序

- 先编写测试并确认在缺少实现时失败，再实现领域逻辑、API 和页面。
- 模型与仓储先于服务，服务先于路由，路由契约先于前端接入。
- 同一文件的任务按编号串行，标记 `[P]` 的任务仅在文件和依赖不冲突时并行。

## 并行执行示例

### 用户故事 1

```text
并行：T011 测试工作簿助手、T012 解析测试、T013 API 测试
并行：T014 工作簿模块、T015 校验模块
串行：T016 导入服务 → T017 路由 → T018 装配
```

### 用户故事 2

```text
并行：T019 差异测试、T020 确认测试、T021 API 契约测试
串行：T022 差异 → T023 仓储确认事务 → T024 服务 → T025 路由
```

### 用户故事 3

```text
并行：T026 后端查询测试、T027 前端 API 测试、T028 页面测试
并行：T032 前端契约、T033 API 客户端、T034 领域映射
并行：T035 工点列表、T036 工点明细、T037 导入预览、T038 版本历史
串行：T039 页面组合 → T040 Workspace 接入
```

### 用户故事 4

```text
并行：T041 等价基线、T042 适配测试、T043 失效测试、T044 路线投影测试
并行：T049 后端路线派生、T051 前端场景契约
串行：T045 适配器 → T046 后端契约 → T047 场景接入 → T048 下游失效
串行：T049 后端路线派生 → T050 专项页面 → T052 旧入口弃用标记
```

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，独立验证新模板、结构化草稿和阻断问题。
3. 完成 US2，形成可确认、可追溯且不覆盖历史的主数据版本闭环。
4. 在进入 UI 与排程接入前演示上述 API 与持久化结果。

### 增量交付

1. **MVP-A**：US1，统一 Excel → 结构化草稿。
2. **MVP-B**：US2，差异 → 确认版本。
3. **产品闭环**：US3，统一页面 → 查询/维护/导出。
4. **排程闭环**：US4，确认版本 → 桥梁排程与专项稳定引用。
5. 每个增量独立运行相应测试，失败不得带入下一阶段。

## 备注

- `[P]` 仅表示任务可在不同文件且无未完成依赖时并行。
- 本任务清单不包含旧数据迁移、旧 Excel 转换、非桥排程、在线逐行编辑、PostgreSQL 或 ORM 引入。
- 旧模型只用于字段语义和任务回归基线；任何实现不得通过兼容逻辑重新建立双权威数据源。
