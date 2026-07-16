# 任务清单：项目架构治理与模块化升级

**输入**：来自 `specs/042-repo-architecture-modernization/` 的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**前置条件**：用户确认本任务清单与 `$speckit-analyze` 结果后，才能执行 `$speckit-implement`。

**测试要求**：本功能涉及排程核心模块、共享契约、前后端入口和仓库迁移。测试、契约快照、行为不变量、构建、性能、单服务健康和文档引用门禁均为必需项。

**组织方式**：任务按用户故事分组；每个迁移批次必须保持兼容 façade，可独立验证和回退。

## Phase 1：准备（迁移清单与当前基线）

**目标**：冻结实施范围、工作树事实和可比较基线，不改变生产代码。

- [X] T001 记录当前分支、Git 状态、受影响路径、禁止覆盖的无关改动，并建立每个 Batch 的前置条件/验证/回退/阻断/审批证据模板：`specs/042-repo-architecture-modernization/migration-inventory.md`
- [X] T002 [P] 建立后端路由、Pydantic schema、Python 导入、`requirements.txt` 运行时依赖和固定场景基线采集脚本：`backend/scripts/capture_architecture_baseline.py`
- [X] T003 [P] 建立前端导出、API 函数、模块规模、构建体积及根/前端/辅助工具 npm 依赖树基线采集脚本：`frontend/scripts/captureArchitectureBaseline.mjs`
- [X] T004 [P] 建立仓库资产分类、跟踪状态、引用和二进制哈希清单脚本：`tools/repo-governance/inventory_repository.py`
- [X] T005 生成并审核重构前架构基线夹具：`backend/tests/fixtures/architecture/`、`frontend/tests/fixtures/architecture/`
- [X] T006 记录 `041` 已完成、部分完成、未完成任务和当前实现文件映射：`specs/042-repo-architecture-modernization/041-status-baseline.md`
- [X] T007 记录重构前后端 328/1、前端 21/21、构建体积和性能结果：`specs/042-repo-architecture-modernization/quickstart.md`

---

## Phase 2：基础能力（阻塞所有迁移批次）

**目标**：先建立兼容和治理门禁；本阶段完成前不得移动生产模块或仓库资产。

- [X] T008 [P] 增加 45 个 `/api` 路由、方法、schema、状态码和错误 `detail` 的 OpenAPI 契约测试：`backend/tests/test_architecture_api_contract.py`
- [X] T009 [P] 增加 `app.models`、`app.scenario`、`app.solver` 旧导入及 Pydantic schema/dump 兼容测试：`backend/tests/test_architecture_import_contract.py`
- [X] T010 [P] 增加固定排程、最少资源、资源成本、架梁联算和计划管控业务不变量测试：`backend/tests/test_architecture_behavior_baseline.py`
- [X] T011 [P] 增加 `.local-data` 路径、schema、合并顺序、稳定 ID/指纹和版本冲突兼容测试：`backend/tests/test_architecture_storage_contract.py`
- [X] T012 [P] 增加 `types/scheduler.ts`、`schedulerApi.ts`、根 `App.tsx` 导出和场景失效规则兼容测试：`frontend/tests/architectureCompatibility.test.mjs`
- [X] T013 [P] 增加前后端依赖方向、禁止跨 feature 内部引用和兼容 façade 唯一实现检查：`tools/repo-governance/validate_dependencies.py`
- [X] T014 [P] 增加根目录白名单、跟踪生成物、临时锁文件、密钥/日志/缓存、正式交付物清单及未经批准的 Python/npm 依赖变化检查：`tools/repo-governance/validate_repository.py`
- [X] T015 [P] 增加 Markdown 内部链接、文件路径和入口命令静态检查：`tools/repo-governance/validate_docs.py`
- [X] T016 仅将架构基线、依赖方向、仓库和文档检查接入 `verify:architecture` 入口，不新增或改写全量 `typecheck`/`test`/`verify` 命令：`package.json`、`tools/repo-governance/README.md`

**检查点**：兼容契约和行为基线可重复运行，生产代码迁移开始前能检测真实回归。

---

## Phase 3：用户故事 1 - 快速理解项目与定位修改入口（优先级：P1）

**目标**：让维护者在 10 分钟内从入口文档定位主应用、模块、共享契约和验证方式，并明确当前实现与 `041` 未完成目标。

**独立测试**：选择综合排程、架梁专项、计划管控和 AI 参数助手四条能力，只使用入口文档完成路径定位；运行文档事实与链接检查全部通过。

### 用户故事 1 的测试

- [X] T017 [P] [US1] 为 README/agent 中 API、脚本、环境变量、模块路径和部署事实增加断言：`backend/tests/test_documented_project_facts.py`
- [X] T018 [P] [US1] 建立不少于 10 项近期能力/API 的 10 分钟定位验收表，其中必须包含综合排程、架梁专项、计划管控和 AI 参数助手：`specs/042-repo-architecture-modernization/checklists/maintainer-navigation.md`
- [X] T019 [P] [US1] 扫描并分类 `docs/` 与 `specs/` 当前失效引用，区分历史缺失、规划目标和真实错误：`specs/042-repo-architecture-modernization/broken-reference-baseline.md`

### 用户故事 1 的实现

- [X] T020 [P] [US1] 创建文档总索引，记录分类、状态、权威范围、替代关系和维护触发条件：`docs/README.md`
- [X] T021 [P] [US1] 创建规格总索引，保留重复编号和历史路径并标注 active/completed/superseded：`specs/README.md`
- [X] T022 [P] [US1] 编写当前系统上下文、用户角色、主链路和外部边界：`docs/architecture/system-context.md`
- [X] T023 [P] [US1] 编写后端、前端、工具、数据、部署的模块所有权地图：`docs/architecture/module-map.md`
- [X] T024 [P] [US1] 编写后端与前端依赖方向、公开入口和禁止依赖规则：`docs/architecture/dependency-rules.md`
- [X] T025 [P] [US1] 编写本地、单服务、Docker、Netlify 静态前端和参考 API 的运行部署边界：`docs/architecture/runtime-and-deployment.md`
- [X] T026 [US1] 创建行为保持型模块化重构 ADR，记录兼容门面和被拒绝替代方案：`docs/architecture/decisions/0001-behavior-preserving-modular-monolith.md`
- [X] T027 [US1] 第一轮重写 README，准确说明当前能力、快速启动、验证、部署、目录地图和详细入口：`README.md`
- [X] T028 [US1] 第一轮重写 Agent 手册，补齐架梁专项、综合排程、计划管控、进度预测、AI 资源助手、真实 API 和修改矩阵：`agent.md`
- [X] T029 [US1] 修正 Netlify 参考 API、当前模块和 `docs/` 跟踪策略的错误引用：`README.md`、`agent.md`、`docs/README.md`
- [X] T030 [US1] 运行维护者定位验收、事实检查和链接检查并记录结果：`specs/042-repo-architecture-modernization/quickstart.md`

**检查点**：不移动代码也能获得准确项目地图；入口文档不把 `041` 未完成内容写成现状。

---

## Phase 4：用户故事 2 - 在清晰边界内安全修改代码（优先级：P1）

**目标**：通过兼容门面分批拆分后端和前端全局热点，固定模块所有权与依赖方向，保持业务行为等价。

**独立测试**：完成一个后端接口、一个排程诊断和一个前端面板的维护样例；修改局限在对应模块，旧入口、全量测试、固定行为基线、构建和主要用户旅程全部通过。

### 用户故事 2A：后端启动与 HTTP 边界测试

- [X] T031 [P] [US2] 为 `create_app`、CORS、静态资源、SPA 回退和健康检查增加真实 HTTP 测试：`backend/tests/test_app_bootstrap.py`
- [X] T032 [P] [US2] 为场景/求解 router 的成功与 4xx/5xx 映射增加测试：`backend/tests/test_scheduling_routes.py`
- [X] T033 [P] [US2] 为 AI 参数/资源助手 router 的状态码和错误 `detail` 增加测试：`backend/tests/test_assistant_routes.py`
- [X] T034 [P] [US2] 为项目数据/架梁/综合排程 router 的契约增加测试：`backend/tests/test_project_girder_routes.py`
- [X] T035 [P] [US2] 为计划管控 router 的版本冲突、未找到和校验错误增加测试：`backend/tests/test_plan_control_routes.py`

### 用户故事 2A：后端启动与 HTTP 边界实现

- [X] T036 [P] [US2] 提取统一 HTTP 异常映射且保持现有状态码和 `detail`：`backend/app/api/errors.py`
- [X] T037 [P] [US2] 按系统健康、兼容接口和静态行为拆 router：`backend/app/api/routers/system.py`
- [X] T038 [P] [US2] 按场景生成、三类求解和方案比较拆 router：`backend/app/api/routers/scheduling.py`
- [X] T039 [P] [US2] 按 AI 参数助手与 AI 资源助手拆 router：`backend/app/api/routers/assistants.py`
- [X] T040 [P] [US2] 按项目数据导入、版本、架梁专项和综合排程拆 router：`backend/app/api/routers/project_girder.py`
- [X] T041 [P] [US2] 按基线、实绩、预测、调整与采纳拆 router：`backend/app/api/routers/plan_control.py`
- [X] T042 [US2] 创建 app factory，装配环境、CORS、routers、静态资源和 SPA 回退：`backend/app/bootstrap.py`
- [X] T043 [US2] 将 `app.main:app` 收敛为兼容入口并保留现有 endpoint 转发：`backend/app/main.py`
- [X] T044 [US2] 比较 OpenAPI manifest、真实 HTTP、静态托管和旧直接调用入口并记录结果：`specs/042-repo-architecture-modernization/quickstart.md`

### 用户故事 2B：后端共享契约测试

- [X] T045 [P] [US2] 为 common/project/scheduling 契约的 schema、默认值、JSON 和导出增加测试：`backend/tests/test_contracts_scheduling.py`
- [X] T046 [P] [US2] 为 assistants 契约的 schema、状态枚举和导出增加测试：`backend/tests/test_contracts_assistants.py`
- [X] T047 [P] [US2] 为 girder/plan_control 契约的 schema、版本状态和导出增加测试：`backend/tests/test_contracts_girder_plan_control.py`

### 用户故事 2B：后端共享契约实现

- [X] T048 [P] [US2] 拆分通用验证消息、来源、稳定枚举和基础契约：`backend/app/contracts/common.py`
- [X] T049 [P] [US2] 拆分项目结构、工艺、逻辑、资源、里程碑和场景输入契约：`backend/app/contracts/project.py`
- [X] T050 [P] [US2] 拆分任务、求解输入、结果、方案比较和诊断契约：`backend/app/contracts/scheduling.py`
- [X] T051 [P] [US2] 拆分 AI 参数助手与 AI 资源助手契约：`backend/app/contracts/assistants.py`
- [X] T052 [P] [US2] 拆分架梁专项、项目版本和综合计算契约：`backend/app/contracts/girder.py`
- [X] T053 [P] [US2] 拆分计划版本、实绩、预测、调整和仓储契约：`backend/app/contracts/plan_control.py`
- [X] T054 [US2] 通过 contracts 包聚合公开名称并解决前向引用：`backend/app/contracts/__init__.py`
- [X] T055 [US2] 将 `app.models` 改为完整兼容重导出、迁移内部消费者到新契约，并即时回填本批验证与回退记录：`backend/app/models.py`、`backend/app/`、`specs/042-repo-architecture-modernization/migration-inventory.md`

### 用户故事 2C：后端业务所有权收拢

- [X] T056 [P] [US2] 为旧 `services` 导入与新业务 façade 等价增加测试：`backend/tests/test_service_compatibility_facades.py`
- [X] T057 [P] [US2] 将桥梁导入服务与配置收拢到 importing 包并保留旧入口：`backend/app/importing/bridge.py`、`backend/app/services/bridge_import_service.py`
- [X] T058 [P] [US2] 将参数助手、材料、存储和模型客户端收拢到 assistants/parameter 并保留旧入口：`backend/app/assistants/parameter/`、`backend/app/services/ai_parameter_*.py`
- [X] T059 [P] [US2] 将资源助手编排与解释器收拢到 assistants/resource 并保留后端确定性推荐边界：`backend/app/assistants/resource/`、`backend/app/services/ai_resource_*.py`
- [X] T060 [P] [US2] 将架梁适配和联合计算收拢到 girder_planning application façade：`backend/app/girder_planning/application.py`、`backend/app/girder_planning/schedule_adapter.py`
- [X] T061 [P] [US2] 将计划仓储、预测和调整收拢到 plan_control 包并保留存储路径：`backend/app/plan_control/`、`backend/app/services/plan_control_repository.py`、`backend/app/services/progress_forecast.py`
- [X] T062 [US2] 将环境加载、本地场景配置、工艺配置仓储和发布默认配置访问收拢到 `config/`，清理 `services/` 跨域穿透、保留旧导入转发并即时回填本批验证与回退记录：`backend/app/config/`、`backend/app/local_config.py`、`backend/app/local_scenario_config.py`、`backend/app/process_repository.py`、`backend/app/services/`、`specs/042-repo-architecture-modernization/migration-inventory.md`

### 用户故事 2D：场景编排拆分测试

- [X] T063 [P] [US2] 将任务生成、资源展开和上下部结构派生回归从大测试文件拆出：`backend/tests/scheduling/test_generation.py`
- [X] T064 [P] [US2] 将固定资源、目标达成和 best-effort 回归拆出：`backend/tests/scheduling/test_fixed_resource_application.py`
- [X] T065 [P] [US2] 将资源压力搜索、最少资源和成本求解回归拆出：`backend/tests/scheduling/test_resource_search_application.py`
- [X] T066 [P] [US2] 将方案比较、输出状态和来源标签回归拆出：`backend/tests/scheduling/test_comparison_application.py`

### 用户故事 2D：场景编排实现

- [X] T067 [P] [US2] 迁移任务图、工期、资源候选和上下部结构派生：`backend/app/scheduling/generation/task_graph.py`、`backend/app/scheduling/generation/structures.py`
- [X] T068 [P] [US2] 迁移固定资源、目标达成和 best-effort 场景编排：`backend/app/scheduling/application/fixed_resource.py`
- [X] T069 [P] [US2] 迁移资源压力、最少资源和成本搜索编排：`backend/app/scheduling/application/resource_search.py`
- [X] T070 [P] [US2] 迁移方案比较、替代方案和输出元数据编排：`backend/app/scheduling/application/comparison.py`
- [X] T071 [US2] 建立 scheduling application façade、将 `app.scenario` 收敛为兼容转发，并即时回填本批验证与回退记录：`backend/app/scheduling/application/__init__.py`、`backend/app/scenario.py`、`specs/042-repo-architecture-modernization/migration-inventory.md`

### 用户故事 2E：求解器拆分测试

- [X] T072 [P] [US2] 拆出结果转换、里程碑、关键路径和诊断回归：`backend/tests/scheduling/test_solver_results_diagnostics.py`
- [X] T073 [P] [US2] 拆出前后置、资源、工作面、日历和连续性硬约束回归：`backend/tests/scheduling/test_solver_constraints.py`
- [X] T074 [P] [US2] 拆出控制节点、工期、空闲、连续性和成本目标回归：`backend/tests/scheduling/test_solver_objectives.py`
- [X] T075 [P] [US2] 拆出 shortest/control/min-resource/resource-cost 策略与阶段路由回归：`backend/tests/scheduling/test_solver_strategies.py`
- [X] T076 [P] [US2] 增加固定输入重构前后等价和性能回归：`backend/tests/scheduling/test_solver_refactor_equivalence.py`

### 用户故事 2E：求解器实现

- [X] T077 [P] [US2] 迁移结果构造、资源分配、目标分解和公共数据转换：`backend/app/scheduling/solver/results.py`
- [X] T078 [P] [US2] 迁移里程碑匹配、评价和关键路径计算：`backend/app/scheduling/solver/milestones.py`
- [X] T079 [P] [US2] 迁移连续性、资源路径、利用率和解释诊断：`backend/app/scheduling/solver/diagnostics.py`
- [X] T080 [P] [US2] 迁移前后置、资源互斥/容量、工作面和日历约束：`backend/app/scheduling/solver/constraints/`
- [X] T081 [P] [US2] 迁移控制节点、工期、资源空闲、连续性和成本目标：`backend/app/scheduling/solver/objectives/`
- [X] T082 [P] [US2] 迁移最短工期与控制优先求解策略：`backend/app/scheduling/solver/strategies/shortest.py`、`backend/app/scheduling/solver/strategies/control_priority.py`
- [X] T083 [P] [US2] 迁移最少资源与资源成本求解策略：`backend/app/scheduling/solver/strategies/min_resources.py`、`backend/app/scheduling/solver/strategies/resource_cost.py`
- [X] T084 [US2] 建立统一 solver engine，保持 seed、worker、时间预算、warm start 和阶段路由：`backend/app/scheduling/solver/engine.py`
- [X] T085 [US2] 将 `app.solver` 收敛为唯一实现的兼容转发，通过等价/性能门禁并即时回填本批验证与回退记录：`backend/app/solver.py`、`specs/042-repo-architecture-modernization/migration-inventory.md`

### 用户故事 2F：前端兼容端口测试与实现

- [X] T086 [P] [US2] 为按域 contracts 与旧 `types/scheduler.ts` 重导出增加编译/运行测试：`frontend/tests/contractsCompatibility.test.mjs`
- [X] T087 [P] [US2] 为按域 API 与旧 `schedulerApi.ts` 40 个函数重导出增加测试：`frontend/tests/apiCompatibility.test.mjs`
- [X] T088 [P] [US2] 拆分 core/project/scenario/schedule 前端契约：`frontend/src/contracts/core.ts`、`frontend/src/contracts/project.ts`、`frontend/src/contracts/scheduling.ts`
- [X] T089 [P] [US2] 拆分 assistant/resourceAssistant/planControl/girder 前端契约：`frontend/src/contracts/assistants.ts`、`frontend/src/contracts/planControl.ts`、`frontend/src/contracts/girder.ts`
- [X] T090 [US2] 将 `types/scheduler.ts` 收敛为完整兼容重导出并迁移内部消费者：`frontend/src/types/scheduler.ts`、`frontend/src/`
- [X] T091 [P] [US2] 拆分 scenario/scheduling/assistant API：`frontend/src/api/scenarioApi.ts`、`frontend/src/api/schedulingApi.ts`、`frontend/src/api/assistantApi.ts`
- [X] T092 [P] [US2] 拆分 resourceAssistant/planControl/girder API：`frontend/src/api/resourceAssistantApi.ts`、`frontend/src/api/planControlApi.ts`、`frontend/src/api/girderPlanningApi.ts`
- [X] T093 [US2] 将 `schedulerApi.ts` 收敛为 40 个公开函数的兼容重导出，并即时回填前端契约批次验证与回退记录：`frontend/src/api/schedulerApi.ts`、`specs/042-repo-architecture-modernization/migration-inventory.md`

### 用户故事 2G：前端工作台与功能边界测试

- [X] T094 [P] [US2] 为任务视图纯函数、过滤、分组和前置解释增加测试：`frontend/tests/taskView.test.mjs`
- [X] T095 [P] [US2] 为结果 presenter、状态标签、目标分解和诊断摘要增加测试：`frontend/tests/scheduleResults.test.mjs`
- [X] T096 [P] [US2] 为 workspace controller 加载、求解、错误和场景指纹失效增加测试：`frontend/tests/workspaceController.test.mjs`
- [X] T097 [P] [US2] 为计划管控与架梁专项公开边界和跨功能组合增加测试：`frontend/tests/featureBoundaries.test.mjs`

### 用户故事 2G：前端工作台与功能边界实现

- [X] T098 [P] [US2] 迁移日期选择与通用弹层到公共组件：`frontend/src/components/common/DateRangePicker.tsx`、`frontend/src/components/common/Modal.tsx`
- [X] T099 [P] [US2] 将任务视图组件、过滤和 presenter 迁入独立 feature：`frontend/src/features/taskView/`
- [X] T100 [P] [US2] 将结果列表、甘特、目标分解和诊断 presenter 迁入独立 feature：`frontend/src/features/scheduleResults/`
- [X] T101 [P] [US2] 提取场景加载、任务生成和三类求解 workflow：`frontend/src/app/workflows/scenarioWorkflow.ts`、`frontend/src/app/workflows/solveWorkflow.ts`
- [X] T102 [US2] 建立 workspace controller，集中跨 feature 结果失效、busy/error 和当前快照协调：`frontend/src/app/useWorkspaceController.ts`
- [X] T103 [US2] 将 `app/App.tsx` 收敛为导航、工作台装配和跨功能协调：`frontend/src/app/App.tsx`
- [X] T104 [P] [US2] 拆分计划管控请求控制、进度编辑、预测展示和调整展示：`frontend/src/features/planControl/`
- [X] T105 [US2] 消除 feature 对其他 feature 内部文件的直接引用，通过公开 `index.ts` 或 app adapter 组合：`frontend/src/features/planControl/index.ts`、`frontend/src/features/girderPlanning/index.ts`
- [X] T106 [P] [US2] 建立 tokens、base、工作台 layout 样式入口：`frontend/src/styles/tokens.css`、`frontend/src/styles/base.css`、`frontend/src/styles/layout.css`
- [X] T107 [P] [US2] 将任务、结果、计划管控、架梁和助手样式迁入对应 feature 并保留选择器顺序：`frontend/src/features/`
- [X] T108 [US2] 将 `styles.css` 收敛为稳定聚合入口，完成关键页面视觉对比并即时回填前端工作台批次验证与回退记录：`frontend/src/styles.css`、`specs/042-repo-architecture-modernization/visual-regression.md`、`specs/042-repo-architecture-modernization/migration-inventory.md`
- [X] T109 [US2] 运行后端/前端全量、行为等价、依赖方向和模块规模门禁并记录 US2 结果：`specs/042-repo-architecture-modernization/quickstart.md`

**检查点**：旧公开入口全部保留；全局热点成为短兼容门面或装配层；修改单一能力不再进入无关全局实现。

---

## Phase 5：用户故事 3 - 稳定运行、测试与部署（优先级：P1）

**目标**：保证每个迁移批次可运行、可回退，原启动/构建/部署入口和性能基线保持稳定。

**独立测试**：在干净依赖环境执行文档命令，完成后端全量、前端测试/构建、Docker 构建、Netlify 静态构建、单服务健康和性能门禁。

### 用户故事 3 的测试

- [X] T110 [P] [US3] 增加单服务启动、健康检查、静态资源和 SPA 回退的冒烟脚本：`backend/scripts/smoke_single_service.ps1`
- [X] T111 [P] [US3] 增加 Docker 默认样例、启动命令和健康接口验证：`backend/tests/test_docker_runtime_contract.py`
- [X] T112 [P] [US3] 增加前端构建体积 5% 阈值和输出目录检查：`frontend/scripts/checkBuildBudget.mjs`
- [X] T113 [P] [US3] 增加 800 综合任务/300 架梁分跨和典型排程 10% 退化门禁：`backend/tests/test_architecture_performance.py`

### 用户故事 3 的实现

- [X] T114 [US3] 在 T016 的 `verify:architecture` 基础上增加全量 `typecheck`、`test`、`verify` 编排并保留原 npm 命令：`package.json`、`frontend/package.json`
- [X] T115 [US3] 在样例数据迁移前增加新旧路径兼容搜索和 Docker 复制：`backend/app/importing/bridge.py`、`Dockerfile`
- [X] T116 [US3] 验证并更新 Vite `/api` 代理、`VITE_API_BASE_URL`、Netlify 发布目录和 Node 版本说明：`frontend/vite.config.ts`、`netlify.toml`、`README.md`
- [X] T117 [US3] 运行单服务、Docker、Netlify 静态前端和性能验证并记录证据：`specs/042-repo-architecture-modernization/quickstart.md`
- [X] T118 [US3] 审计各 Batch 是否已在执行时即时记录前置条件、验证证据和回退结果，禁止事后补写缺失门禁：`specs/042-repo-architecture-modernization/migration-inventory.md`

**检查点**：原命令、接口和部署入口可用，纯重构不造成未解释性能或包体退化。

---

## Phase 6：用户故事 4 - 持续维护文档与仓库卫生（优先级：P2）

**目标**：完成资产分区、正式交付物保留、生成物治理和文档维护规则，使结构不会再次失控。

**独立测试**：模拟新增业务模块、PRD、正式交付物和本地产物，维护者均能一次选择正确位置；仓库、链接、事实、哈希和根目录白名单检查全部通过。

### 用户故事 4 的测试

- [X] T119 [P] [US4] 为根目录白名单、资产分类、allowlist 和临时锁文件增加回归夹具：`tools/repo-governance/tests/test_repository_layout.py`
- [X] T120 [P] [US4] 为 Markdown 链接、迁移映射、文档状态和规格索引增加回归夹具：`tools/repo-governance/tests/test_document_index.py`
- [X] T121 [P] [US4] 为正式二进制交付物清单和迁移前后哈希增加验证：`tools/repo-governance/tests/test_deliverable_manifest.py`

### 用户故事 4 的实现

- [X] T122 [US4] 提交逐文件资产迁移清单并等待用户二次明确确认；未确认前不得执行 T123～T129 的 `git mv`、取消跟踪或正式交付物分区：`specs/042-repo-architecture-modernization/migration-inventory.md`
- [X] T123 [US4] 仅按 T122 已确认清单，将根目录方案、当前 PRD、算法交底、验证和调研资料迁入对应分区并保留历史迁移表：`docs/product/`、`docs/engineering/`、`docs/validation/`、`docs/research/`、`docs/archive/path-migration.md`
- [X] T124 [P] [US4] 将结果查看器和精简样例迁入 examples，并将大结果/预览中间件从文档分区移出：`examples/result-viewer/`、`artifacts/`
- [X] T125 [P] [US4] 按 T122 清单迁移 PPT 辅助工具，修正旧工作区说明，并增加/运行本地 `verify` 类型与布局检查：`tools/ai-ppt-system/package.json`、`tools/ai-ppt-system/tsconfig.json`、`tools/ai-ppt-system/README.md`
- [X] T126 [P] [US4] 按 T122 清单迁移 Netlify 参考 API，明确非正式后端，并增加/运行无部署语法与类型检查：`tools/demo-api-mirror/api.mts`、`tools/demo-api-mirror/verify.mjs`、`tools/demo-api-mirror/README.md`
- [X] T127 [P] [US4] 按 T122 清单迁移交付物构建/校验脚本和最终文件，并使用固定夹具完成一次构建与复核：`tools/delivery-builders/`、`deliverables/`、`tools/repo-governance/tests/test_deliverable_manifest.py`
- [X] T128 [US4] 仅按 T122 已确认清单，对 `outputs/`、PPT output、`~$*`、检查 NDJSON、预览、已忽略仍跟踪文件和根目录本地 `*.log` 迁移或取消跟踪；日志只移入 `.local-data/logs/legacy/`，不删除用户本地文件：`specs/042-repo-architecture-modernization/migration-inventory.md`、`.gitignore`
- [X] T129 [US4] 仅在 T122 明确确认且兼容读取、Docker 和测试通过后迁移根样例 Excel并保留旧路径回退说明：`examples/bridge-import/`、`backend/app/importing/bridge.py`、`Dockerfile`
- [X] T130 [US4] 更新全部当前代码、配置、文档和测试引用；历史失效引用按分类清单保留解释：`docs/archive/path-migration.md`、`specs/042-repo-architecture-modernization/broken-reference-baseline.md`
- [X] T131 [US4] 编写文档、规格、工具、交付物和本地产物维护规则：`docs/architecture/repository-governance.md`
- [X] T132 [US4] 完成 README 最终目录、能力、命令、部署和文档导航收敛：`README.md`
- [X] T133 [US4] 完成 agent.md 最终模块所有权、调用链、兼容边界、修改路线和验证矩阵收敛：`agent.md`
- [X] T134 [US4] 运行新增资产放置演练、根目录、文档链接、事实和交付物哈希门禁并记录结果：`specs/042-repo-architecture-modernization/quickstart.md`

**检查点**：每类资产有唯一位置和版本控制规则，入口文档与详细知识分层，历史和正式交付物可追溯。

---

## Phase 7：收尾与横切事项

**目标**：完成全量回归、人工旅程、视觉/性能、规格状态和实现收敛审计。

- [ ] T135 [P] 运行后端全量 pytest、架构契约、存储兼容和固定行为基线：`specs/042-repo-architecture-modernization/quickstart.md`
- [ ] T136 [P] 运行前端 Node 测试、类型检查、构建、包体和依赖方向检查：`specs/042-repo-architecture-modernization/quickstart.md`
- [ ] T137 [P] 运行 800/300 性能夹具、典型排程 10% 阈值和结果等价比较：`specs/042-repo-architecture-modernization/quickstart.md`
- [ ] T138 [P] 完成默认场景、三类求解、AI 助手、架梁专项和计划管控浏览器旅程：`specs/042-repo-architecture-modernization/manual-smoke.md`
- [ ] T139 [P] 完成关键页签多视口视觉对比并确认 CSS 级联、弹层和响应式无回归：`specs/042-repo-architecture-modernization/visual-regression.md`
- [ ] T140 [P] 运行根目录、Git 跟踪、密钥、日志、缓存、临时锁、生成物和二进制哈希检查：`specs/042-repo-architecture-modernization/quickstart.md`
- [ ] T141 复核 `041` 任务状态、兼容 façade 和历史规格路径未被错误改变：`specs/042-repo-architecture-modernization/041-status-baseline.md`
- [ ] T142 运行 `git diff --check` 并记录修改文件、验证结果、未覆盖风险和回退边界：`specs/042-repo-architecture-modernization/implementation-report.md`
- [ ] T143 对照 `spec.md`、`plan.md`、`tasks.md`、contracts 和 Constitution 执行 `$speckit-converge`：`specs/042-repo-architecture-modernization/tasks.md`

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1 准备**：无依赖。
- **Phase 2 基础能力**：依赖 Phase 1；阻塞所有迁移。
- **US1（Phase 3）**：依赖 Phase 2，先交付准确入口和架构地图。
- **US2（Phase 4）**：依赖 Phase 2；为减少路径反复，建议在 US1 的目标边界文档完成后实施。
- **US3（Phase 5）**：基础测试可在 US2 期间并行准备，最终运行/部署验证依赖 US2。
- **US4（Phase 6）**：索引和清单可在 US1 后开始；物理资产迁移依赖 US2 路径稳定、US3 兼容门禁就绪。
- **Phase 7 收尾**：依赖目标用户故事全部完成；T143 最后执行。

### 用户故事依赖图

```text
Phase 1 -> Phase 2 -> US1 -> US2 -> US3 -> US4 -> Phase 7
                    \              /
                     +-- indexes --+
```

### 单个迁移批次顺序

1. 先写兼容/行为测试并确认能保护旧行为。
2. 新建目标模块和兼容 façade。
3. 迁移内部消费者，不复制业务规则。
4. 运行目标测试、全量回归、契约和性能门禁。
5. 更新迁移清单和当前文档。
6. 验证可回退后再进入下一批。

### 并行机会

- Phase 1 的后端、前端和仓库基线采集可并行。
- Phase 2 的 API、模型、行为、前端和仓库检查使用不同文件，可并行。
- US1 的文档索引、系统上下文、模块地图、依赖规则和运行部署说明可并行起草。
- US2 中不同 router、contract 域、业务包、场景测试、求解测试和前端测试可在共享接口稳定后并行。
- US3 的单服务、Docker、包体和性能测试可并行准备。
- US4 的文档、工具、查看器和交付物迁移可在资产清单批准后按独立路径并行。

## 并行示例

### US1

```text
T020 docs/README.md
T021 specs/README.md
T022 system-context.md
T023 module-map.md
T024 dependency-rules.md
T025 runtime-and-deployment.md
```

### US2 后端契约

```text
T048 common.py
T049 project.py
T050 scheduling.py
T051 assistants.py
T052 girder.py
T053 plan_control.py
```

### US2 前端功能

```text
T099 taskView/
T100 scheduleResults/
T101 app/workflows/
T104 features/planControl/
T106 src/styles/
```

## 实施策略

### 建议第一增量：可理解、可验证的架构基线

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，修正入口事实并建立架构/文档/规格索引。
3. 停下运行定位验收、链接和事实检查。

该增量能立即解决文档落后和项目难定位问题，但不宣称代码架构已完成。

### 核心重构增量

1. 按 US2A～US2G 顺序迁移，每个小节单独通过回归后再继续。
2. 优先交付 HTTP/契约兼容边界，再处理高风险 scenario/solver，最后拆前端工作台与样式。
3. US3 在各批次持续验证运行、部署、性能和包体。
4. US4 最后执行物理资产迁移和文档最终收敛。

### 实施门禁

- 用户确认本 `tasks.md` 和 `$speckit-analyze` 结果前，不运行 `$speckit-implement`。
- 发现业务规则、公开 API、共享字段、状态码、部署或新依赖变化时，停止并回到规格澄清。
- 不提交、不推送、不部署，除非用户另行明确要求。

## 备注

- `[P]` 只用于不同文件或可独立准备的任务；同一兼容 façade 的修改按顺序执行。
- 旧入口在本功能内保留，删除兼容层不属于完成条件。
- 物理文件迁移必须先有资产清单、引用映射和正式二进制哈希。
- 所有任务都必须把实际结果回填到 `quickstart.md` 或对应验证记录，不能只勾选状态。
