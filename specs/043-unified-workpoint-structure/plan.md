# 实施计划：统一工点与结构物主数据

**分支/目录**：`043-unified-workpoint-structure` | **日期**：2026-07-16 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/043-unified-workpoint-structure/spec.md` 的功能规格

## 概要

建立独立的项目主数据领域，把现有分离的桥梁结构 `ProjectModel.bridges` 与架梁 `GirderWorkPoint[]` 收敛为可版本化的“工点 → 结构物 → 构件参数”模型。统一 Excel 作为完整快照输入，经解析、校验和差异预览后写入本地 SQLite；确认版本成为项目工点与结构物的唯一权威数据。现有桥梁排程不直接读取数据库表，而由适配层将确认版本投影为现有 `ProjectModel / ProjectBridge / WorkSection / StructureModel / UpperStructureComponent / ComponentModel`，继续复用任务生成、工期、逻辑、资源和求解器。

## 技术上下文

**语言/版本**：Python 3.12；TypeScript 5.7；Node.js 22

**主要依赖**：FastAPI、Pydantic、Python 标准库 `sqlite3`、openpyxl、React 19、Vite 6、OR-Tools CP-SAT；不新增 ORM 或数据库运行时依赖

**存储**：新增 `.local-data/project-master.db`，使用 SQLite 关系表、外键、事务、唯一约束和 `PRAGMA user_version` 管理新主数据 schema；`.local-data/plan-control-store.json` 继续承载既有计划管控数据，但新主数据只保存版本引用，不再嵌入工点、结构物和构件快照

**测试**：pytest 后端领域/仓储/导入/API/适配回归；前端 Node 测试、TypeScript 类型检查和 Vite 构建；SQLite 重启恢复、事务失败和并发版本测试；固定桥梁样例任务图等价验证；单服务 HTTP 冒烟

**目标平台**：本地 FastAPI 单服务与 Vite 开发环境；Docker Python 3.12 后端；Netlify 仅发布静态前端并依赖外部 FastAPI，参考 API 镜像不作为本功能正式后端

**项目类型**：FastAPI + React 模块化单体 Web 应用，新增项目主数据领域、Excel 导入流程、关系型持久化、统一维护页面和桥梁排程适配

**性能目标**：参考项目不超过 500 个工点、10,000 个结构物和 50,000 个构件时，导入、校验和差异结果在 30 秒内可见；工点列表采用分页或分段查询，单工点明细无需加载全项目快照

**约束**：不迁移旧 JSON 或旧 Excel 数据；不双写旧存储；旧实现只用于字段和任务规则参考；不修改 CP-SAT 目标、约束、工期和资源规则；非桥梁工点本期不生成任务；已确认版本不可原地修改；导入失败不得改变当前确认版本

**规模/范围**：新增一个后端领域包、一个 API router、共享前后端契约、四工作表 Excel 模板与导入器、SQLite 仓储、一个前端项目主数据 feature；调整场景初始化、项目版本引用、架梁专项引用和任务结果失效；新增相应测试和规格契约

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- **Requirements First：通过。** 用户已确认工点粒度、结构物定义、全类型工点、桥梁排程范围、全量快照、SQLite、本期不迁移和不保留旧交互；`spec.md` 已形成可测试需求。
- **Explicit Algorithm Specifications：通过。** 本功能不改变求解算法；设计明确桥梁确认版本经适配层投影为现有排程输入，并要求固定样例业务不变量等价。
- **Explicit Frontend-Backend Contracts：通过。** 计划生成项目主数据 API、Excel 合同、共享字段、状态码、页面状态和结果失效规则。
- **Reuse Existing Docs and Code：通过。** 复用现有结构模型字段、稳定 ID/指纹、版本状态、openpyxl、FastAPI router、React feature、任务生成和架梁引用语义；不复用旧导入交互和 JSON 存储。
- **Phased Delivery：通过。** 先完成仓储和导入基础，再交付统一查看/确认，最后接入桥梁排程和架梁引用；非桥梁排程留待后续。
- **Spec Kit Gate Before Implementation：通过。** 当前只生成 specify/clarify/plan/tasks/analyze 产物，分析后等待用户确认。
- **Completion Report and Verification：通过。** `quickstart.md` 定义可复现 Excel、持久化、API、前端和任务等价验证。
- **语言与文档治理：通过。** 全部 Spec Kit 产物使用中文简体；不默认修改 `README.md`、`agent.md` 或提交 Git。

### Phase 1 设计后复查

- 新 SQLite 仓储是用户明确确认的本功能核心约束，不属于未经批准的新平台或架构迁移。
- 新项目主数据包与 042 模块边界一致；旧兼容 façade 只用于保护现有导入路径和测试，不成为新流程运行依赖。
- API、Excel、数据模型、状态迁移、错误语义和排程投影均已在 `contracts/`、`data-model.md` 与 `quickstart.md` 中具体化。
- 无未解决 `NEEDS CLARIFICATION`，无 Constitution 违反项。

## 项目结构

### 本功能文档

```text
specs/043-unified-workpoint-structure/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── project-master-api.yaml
│   └── excel-workbook.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── contracts/
│   │   └── project_master.py
│   ├── project_master/
│   │   ├── __init__.py
│   │   ├── repository.py
│   │   ├── schema.py
│   │   ├── workbook.py
│   │   ├── validation.py
│   │   ├── diff.py
│   │   ├── service.py
│   │   └── scheduling_adapter.py
│   ├── api/routers/
│   │   └── project_master.py
│   ├── scheduling/application/
│   ├── girder_planning/
│   └── plan_control/
└── tests/
    ├── fixtures/project_master/
    ├── test_project_master_repository.py
    ├── test_project_master_workbook.py
    ├── test_project_master_api.py
    ├── test_project_master_adapter.py
    └── test_project_master_invalidation.py

frontend/
├── src/
│   ├── contracts/projectMaster.ts
│   ├── api/projectMasterApi.ts
│   ├── domain/projectMaster.ts
│   ├── features/projectMasterData/
│   │   ├── ProjectMasterDataWorkspace.tsx
│   │   ├── WorkPointList.tsx
│   │   ├── WorkPointDetail.tsx
│   │   ├── ImportPreview.tsx
│   │   ├── VersionHistory.tsx
│   │   └── styles.css
│   ├── features/assistant/parameter/
│   │   └── ParameterAssistantPanel.tsx
│   └── app/
└── tests/
    ├── projectMasterData.test.mjs
    └── projectMasterApi.test.mjs
```

**结构决策**：新增 `project_master` 作为项目主数据唯一领域所有者，避免继续向 `plan_control_repository.py`、`bridge_import.py` 或 `girder_planning/import_service.py` 追加职责。API 契约进入域化 contracts，前端使用独立 feature。现有 `ProjectModel` 保留为排程投影，不再作为持久化权威；`project_data_version_id` 继续作为方案和计划稳定引用，减少对 041 已有联算链路的破坏。

## 分阶段实施策略

### 阶段 A：存储与契约基础

1. 建立项目主数据共享契约、SQLite schema、仓储接口和 schema 版本初始化。
2. 实现版本、工点、结构物、构件、参数、导入批次、问题、证据和差异的事务读写。
3. 验证确认版本不可变、单一当前版本、内容指纹幂等和重启恢复。

### 阶段 B：统一 Excel 导入闭环

1. 生成并解析四工作表新模板，不兼容旧模板。
2. 完成字段标准化、父子关系、幅别、类型、工程量、桥梁必需参数和引用删除校验。
3. 生成导入批次、阻断/告警、差异预览；无阻断时创建可确认草稿。

### 阶段 C：统一项目主数据页面

1. 复用现有 `projectFiles` 导航槽位，显示名称改为“项目主数据”，接入独立 feature。
2. 支持模板下载、导入进度、问题、差异、版本列表、确认、工点分页、单工点结构物/构件明细和当前版本导出。
3. 移除新页面对历史桥梁导入和架梁工点导入交互的调用；参数助手迁移为独立导航入口，移除桥梁结构 Excel 导入动作，不承担主数据持久化。

### 阶段 D：桥梁排程与专项引用接入

1. 把确认版本投影为现有 `ProjectModel`，桥梁工点 ID 作为 `ProjectBridge.id`，结构物幅别和工区派生 `WorkSection`。
2. 场景、方案、计划和专项统一沿用现有 `project_data_version_id` 引用 SQLite 中的确认版本，完整排程输入继续使用 `input_fingerprint`；不新增并列的 `project_master_version_id/project_master_fingerprint`，确认新版本后使旧任务、求解、比较、计划和专项引用失效。
3. 架梁路线从统一工点与桥梁幅别派生路线工点视图，不再保存独立主数据副本。
4. 非桥梁工点只显示“暂不参与排程”，不进入任务生成。

### 阶段 E：兼容收口与验证

1. 旧结构导入和旧工点导入从新 UI 移除；旧端点若因现有测试或内部调用必须短期保留，只能作为标记弃用的兼容入口且不得读写新主数据。
2. 计划管控 JSON 不再新增 `project_data_versions` 快照；新方案仅引用 SQLite 中的确认版本。
3. 运行固定桥梁任务图等价、全量后端、前端、架构契约和单服务验证。

## 复杂度跟踪

无 Constitution 违反项。新增领域包和 SQLite 仓储是为建立单一项目主数据所有权、满足用户确认的结构化持久化要求，并防止继续扩大现有计划管控 JSON 和导入模块职责。
