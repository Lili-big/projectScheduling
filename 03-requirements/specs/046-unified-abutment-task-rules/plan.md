# 实施计划：统一桥台任务生成、工期与资源规则

**分支/目录**：`046-unified-abutment-task-rules` | **日期**：2026-07-17 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `03-requirements/specs/046-unified-abutment-task-rules/spec.md` 的功能规格

**状态**：已纳入任务视图异步映射竞态，等待修订任务清单与一致性分析；未获实现批准

## 概要

本功能把项目主数据、排程构件、工艺库、资源池、求解器和工作台之间的桥台语义统一为一条规范链路：

```text
bridge_abutment 下非桩构件
  -> abutment_body
  -> abutment_body_standard / 桥台施工
  -> fixed_days + count + 15 天/个
  -> 默认配置不新增 abutment_team 资源池
  -> compatible_resource_types=[]
  -> 无具名资源、无资源分配、无资源等待
```

项目主数据历史快照保持不可变；所有生成/求解入口在读取已确认版本时按带版本的规范映射重新投影。新导入或新生成的项目主数据直接写入 `abutment_body`。前端继续作为共享契约消费者，不引入桥台专属显示或计算分支；任务到达但同版本权威名称映射尚未 ready 时使用通用加载态，完整映射原子提交后才渲染可见名称，失败可重试，旧版本晚到响应被忽略。

## 技术上下文

**语言/版本**：Python 3.12；TypeScript；Node.js 22；验证工作包脚本使用 JavaScript/MJS

**主要依赖**：FastAPI、Pydantic、React、OR-Tools CP-SAT、openpyxl；复用现有项目主数据与排程模块

**存储**：项目主数据 SQLite 版本库；历史确认快照保持只读；本功能不新增数据库表

**测试**：pytest 后端单元/集成/契约测试；前端 Node 静态契约与纯状态测试、真实 React 组件/Chromium 或 Edge DOM 运行时验证、当前 Vite 强制重载、TypeScript 构建；固定项目主数据工作簿与确定性投影样例

**目标平台**：本地/容器 FastAPI 服务与 React 工作台；Netlify 仍只发布静态前端

**项目类型**：跨项目主数据、排程生成、资源求解与前端展示的 Web 应用功能

**性能目标**：固定项目主数据样例的重新投影保持确定性；不新增逐任务外部 I/O 或求解分支；现有项目主数据与排程性能门禁不退化

**约束**：不修改 CP-SAT 目标函数；不新增桥台专属模型、资源模式或前端兜底；不直接改写历史确认快照；不改变桥台桩基及桥墩盖梁规则；显示映射只用规范版本与 workpoint ID 集合作为通用请求身份；不引入新依赖

**规模/范围**：D01 主数据定义/生成/投影，D02 工艺/任务/资源语义，D06 共享契约/版本失效/异步行为测试，D05 工作台加载/错误/竞态状态与显示验收；持久化仓储实际 `stale` 消费由 G00 路由 D04 配合。预计影响后端 6～9 个源文件、前端 3～5 个源文件及对应测试/验证样例

## 生命周期归属

- **主要阶段**：`03-requirements`
- **工作包**：`046-unified-abutment-task-rules`
- **资产类型**：Spec Kit 规格、研究、数据模型、契约、验证指南、任务清单与检查表
- **跟踪策略**：`tracked`
- **保留类别**：`formal-output`
- **主归属**：`03-requirements/specs/046-unified-abutment-task-rules/`
- **跨阶段引用**：引用 `04-demo/` 源码与测试、`01-customer-validation/泸古1标/validation-results/_scripts/` 的输入生成脚本；实现和验证资产仍留在各自主阶段，不复制权威原文

## Constitution 检查

*门禁：Phase 0 研究前通过；Phase 1 设计后复核通过。*

- [x] 用户已明确确认产品口径，任务直接进入完整 Spec Kit 门禁。
- [x] `spec.md` 已引用需求文档、规则文档、验证脚本、Demo 与代码事实。
- [x] 任务生成、工期、资源模型、共享契约及前后端影响已明确。
- [x] 输入、输出、硬边界、异常/空态/兼容场景和验收标准可测试。
- [x] 未把 Demo 临时限制提升为正式产品目标；15 天/个由现有权威工艺文档和默认工艺共同支持。
- [x] 全部 Spec Kit 过程文档使用中文简体，保留必要字段名和路径。
- [x] 已声明阶段、工作包、资产类型、跟踪策略、保留类别和唯一主归属。
- [x] 历史数据采用可版本化重新投影；不执行无清单、不可回退的直接改库。
- [x] 用户输入、正式结果与历史快照不会被当作临时文件清理。
- [x] 用户确认 `tasks.md` 与 `$speckit-analyze` 前不进入实现。

## 设计决策

### 1. 规范映射位于项目主数据排程投影边界

- 在项目主数据定义中加入 `abutment_body` 合法构件类型，使新导入/生成数据能直接表达规范语义。
- 在项目主数据生成脚本中依据结构物 `structure_type=bridge_abutment` 输出 `abutment_body`，不得依据“台帽”等名称判断。
- 在 `project_model_from_master` 的下部结构投影中依据父结构物类型规范化：`bridge_abutment` 下 `pile` 保持 `pile`，其余有效构件投影为 `abutment_body`；桥墩 `cap_beam` 继续原样投影。
- 映射保持源构件 ID、数量、单位、启用状态、来源参数和项目主数据引用，不合并或伪造源构件。

### 2. 工艺与工期只来自现有工艺库

- 继续使用现有 `abutment_body_standard`，不建立第二份桥台工艺常量。
- 任务生成通过通用 `component_type → 默认 ProcessTemplate → ProductivityOption → calculate_duration` 链路得到“桥台施工”和 15 天/个。
- 保留 `upgrade_process_library` 对历史 10 天内置默认值升级到当前 15 天的通用迁移行为；不以任务名称或单个项目修补。

### 3. 桥台资源使用资源池缺失的通用默认充足路径

- 默认场景与部署配置不新增 `abutment_team` 资源池；任务初始可由工艺模板保留该资源类型元数据。
- 现有 `_apply_required_resource_types` 在资源池缺失时通过通用路径清空 `compatible_resource_types`。
- `expand_resource_pools` 不会得到桥台资源池，求解器对空兼容资源不建立分配选择，因此无具名资源、资源分配和资源等待。
- 前端资源类型与显示只消费共享字段，不自行把桥台任务转换为受限或无限资源。

### 4. 历史数据使用带版本的重新投影

- 历史 `project_master_versions` 与构件行不直接更新，继续作为已确认来源证据。
- 所有带 `project_data_version_id` 的任务生成和求解入口继续在请求时加载快照并重新投影，新规范自然覆盖历史 `cap_beam`/台帽来源记录。
- 增加稳定的项目主数据排程投影规则版本，并写入投影来源元数据与 `GeneratedScheduleInput.source_summary`。
- 新生成结果必须携带当前投影版本；持久化派生结果的通用读取/复用路径必须实际比较该版本，缺少或不一致时标记为过期或拒绝复用。历史结果可以保留为证据，但不得作为当前结果继续使用。

### 5. 前端保持展示消费者

- `ComponentType` 与共享标签继续保留 `cap_beam` 和 `abutment_body` 两类规范类型。
- 任务视图按后端 `component_type`、`process_name`、`duration_days`、`compatible_resource_types` 展示。
- 不新增 `桥台`、`台帽`、`A0`、`AB`、10、15 等名称/ID/数值分支；空态和错误态复用通用路径。

### 6. 权威名称映射使用通用状态协调器

- 以 `project_data_version_id + sorted(unique(workpoint_ids))` 生成请求身份；缓存、加载、重试和晚到响应均围绕该身份管理。
- 明确 `loading / ready / error` 状态；`ready` 前不调用名称 rows 的可见渲染路径。
- 使用整批成功后原子提交；不再逐请求吞错后提交部分映射。
- 失败显示通用错误/不可用态与重试；快速切换后只允许当前身份提交，旧响应忽略。
- 抽取 taskView 领域内纯状态协调模块，使用现有 TypeScript 工具链执行状态行为断言；另以真实 React 组件/Chromium 或 Edge DOM 验证首次提交、错误重试、身份切换和当前 Vite 强制重载，不以源码正则、纯状态模块或 HTTP 结果代替页面可见性证据。优先使用仓库已有运行环境或 Node 22 内置能力，不给生产代码新增测试依赖。

### 7. 补齐异常与空态回归

- 增加“桥台只有桩基，不补造主体”适配器断言。
- 增加“缺少 `abutment_body_standard` 时通用报错，不回退盖梁工艺”任务生成断言。
- 以资源池缺失作为本期规范输入，并继续覆盖禁用或 `UNLIMITED` 配置的通用兼容语义，不增加桥台条件。

## Phase 0：研究结论

研究已完成，详见 [research.md](./research.md)。所有技术上下文均已解析，无 `NEEDS CLARIFICATION`。

## Phase 1：设计与契约

- 数据模型：[data-model.md](./data-model.md)
- 共享业务契约：[contracts/abutment-task-contract.md](./contracts/abutment-task-contract.md)
- 可复现验证指南：[quickstart.md](./quickstart.md)

### 受影响结构

```text
03-requirements/specs/046-unified-abutment-task-rules/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── abutment-task-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md

04-demo/backend/app/project_master/
├── definitions.py
└── scheduling_adapter.py

04-demo/backend/app/
├── scheduling/application/_scenario.py
└── services/plan_control_repository.py

04-demo/backend/tests/
├── project_master_fixture_helpers.py
├── test_project_master_adapter.py
├── test_scheduler.py
├── test_scheduling_routes.py
└── test_architecture_api_contract.py

04-demo/frontend/src/
├── contracts/scheduler.ts
├── contracts/projectMaster.ts
├── app/workflows/scenarioWorkflow.ts
├── app/Workspace.tsx
├── features/taskView/projectMasterDisplayState.ts
├── features/taskView/presenter.ts
├── features/taskView/TaskViewWorkspace.tsx
└── features/projectMasterData/WorkPointDetail.tsx

04-demo/frontend/tests/
├── taskView.test.mjs
├── taskViewPresenter.test.mjs
└── taskViewProjectMasterDisplay.test.mjs

01-customer-validation/泸古1标/validation-results/_scripts/
└── build_lugu_project_master.mjs
```

**结构决策**：复用当前领域所有权，不新增目录或依赖。项目主数据规范化归 D01；任务/工艺/资源求解归 D02；共享契约、投影版本和测试归 D06；任务视图验收归 D05。验证工作包脚本仅修正其输出映射，不成为运行时权威规则。

## 接口与兼容边界

- 不新增或改名 HTTP 路径；`/api/generate-schedule-input` 与各求解入口继续使用现有请求/响应模型。
- `ComponentType` 保留 `cap_beam` 与 `abutment_body`；默认资源池集合不新增 `abutment_team`，现有通用 `ResourceMode` 契约保持不变。
- `GeneratedScheduleInput.source_summary` 增加投影规则版本等可选键，不破坏旧客户端的开放字典契约。
- 项目主数据派生快照的读取/复用必须检查 `source_summary.scheduling_projection_version`；非项目主数据历史结果不因缺少该字段被误判。
- 历史项目主数据快照不变；新导入模板允许并优先输出 `abutment_body`。
- 桥台桩基和桥墩盖梁是强制回归基线。
- 任务视图显示映射不新增 HTTP 路径；继续使用现有工点读取接口，但请求批次以版本和完整 ID 集合作为当前性边界。
- 映射未 ready、加载失败或身份切换时不得构建可见名称 rows；相同身份的完整 ready 映射可以通用缓存复用。

## 验证策略与角色职责

| 角色 | 验证范围 | 最低证据 |
| --- | --- | --- |
| D01 | 主数据类型定义、导入生成、历史快照投影 | 固定工作簿/快照，桥台非桩为 `abutment_body`，桩基不变 |
| D02 | 工艺、15 天工期、桥台资源池缺失、求解无等待 | 任务字段断言、默认池无桥台资源、资源实例/分配为空、并行样例 |
| D06 | 共享契约、投影版本、旧结果失效、请求身份、行为测试、硬编码扫描 | API/模型测试、持久化结果版本不匹配、可控异步顺序、真实浏览器门禁、静态扫描 |
| D05 | 工作台显示、加载态、原子成功、错误重试、版本竞态 | presenter/状态测试与真实组件/浏览器 DOM 记录，0 次原始 ID 闪现，前端字段逐项等于后端结果 |
| D04（依赖） | 持久化计划/联合快照实际消费投影版本 | 由 G00 路由；仓储旧快照 `stale` 或拒绝复用，D06 复核 |

## Agent 上下文更新

当前仓库不存在 `.specify/scripts/powershell/update-agent-context.ps1`，因此无法执行上游 Skill 描述的自动 Agent 上下文更新脚本。仓库已通过 `AGENTS.md`、`registry.yaml`、`L03.md` 和本规格提供当前上下文；本次不手工修改 `AGENTS.md`。

## 复杂度跟踪

无 Constitution 违反项；新增的是 taskView 领域内最小纯状态协调模块，不新增依赖或数据库迁移。规格索引 README 不在未授权修改范围内，后续只更新本功能 `spec.md` 状态。
