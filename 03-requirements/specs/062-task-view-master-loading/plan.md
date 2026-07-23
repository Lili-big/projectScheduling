# 实施计划：任务视图权威主数据快速加载

**分支/目录**：`062-task-view-master-loading` | **日期**：2026-07-22 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `03-requirements/specs/062-task-view-master-loading/spec.md` 的功能规格

## 概要

以任务视图专用批量显示投影替换前端逐工点详情请求。后端按照 `project_data_version_id + 规范化 workpoint_ids` 一次查询目标工点及其工区/幅别显示字段，不加载构件、参数或来源证据；前端协调器改为一次请求、完整性校验、原子提交，并继续保留成功缓存、失败重试和旧响应隔离。现有单工点详情、项目主数据导入/确认、任务生成和排程规则不变。

## 技术上下文

**语言/版本**：Python 3.12、TypeScript 5.7、Node.js 24

**主要依赖**：FastAPI、Pydantic、SQLite、React 19、Vite 6；不新增依赖

**存储**：现有项目主数据 SQLite；不新增表、字段或迁移

**测试**：pytest 接口/仓储/契约测试，Node `node:test` 前端协调器和静态契约测试，真实 Chrome/CDP 任务视图运行测试，TypeScript 构建

**目标平台**：本地 FastAPI 服务与 React/Vite Demo

**项目类型**：跨前后端 Web 应用共享读取契约与性能优化

**性能目标**：13 工点、1586 任务基线连续 3 次硬刷新均在 5 秒内完成；一次业务请求；响应体不超过既有 2.21 MB 合计的 20%

**约束**：权威名称必须全量就绪后原子展示；不得显示原始 ID、部分映射或旧版本结果；单工点详情语义、持久化、任务/资源/工期/求解规则不变

**规模/范围**：一个后端最小投影模型与仓储查询、一个 API 路由、前端共享类型/API/协调器/展示投影适配，以及对应接口、协调器和真实浏览器测试

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：`04-demo/backend/app/contracts/project_master.py`、`04-demo/backend/app/project_master/repository.py`、`04-demo/backend/app/api/routers/project_master.py`、`04-demo/backend/tests/`、`04-demo/frontend/src/contracts/projectMaster.ts`、`04-demo/frontend/src/api/projectMasterApi.ts`、`04-demo/frontend/src/features/taskView/`、`04-demo/frontend/src/app/Workspace.tsx`、`04-demo/frontend/tests/`

## Constitution 检查

*Phase 0 前检查：通过；Phase 1 设计后复核：通过。*

- 用户已确认针对已定位性能缺陷进入 Spec Kit；规格包含当前代码和运行证据，无阻断澄清项。
- 本功能不改变排程、资源、工期、CP-SAT 约束或目标；只改变任务视图权威显示数据的读取契约。
- 输入、输出、最大集合、错误码、加载/失败/重试/空态、缓存身份、竞态隔离和性能验收均已明确。
- 后端 Pydantic、前端 TypeScript、API 路由、OpenAPI/接口测试和浏览器行为测试将同步更新共享契约。
- 复用现有仓储、路由、API 客户端、协调器、展示映射和运行测试，不引入新依赖、持久化结构或兼容层。
- 保留既有单工点详情公开行为和任务视图原子展示，不把 Demo 性能基线提升为排程业务规则。
- 规格与设计资产只有 `03-requirements/specs/062-task-view-master-loading/` 一个主归属；不迁移或清理本地状态、用户输入及其他工作树改动。

## 项目结构

### 本功能文档

```text
03-requirements/specs/062-task-view-master-loading/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── task-view-display-map-api.md
└── tasks.md
```

### 生命周期与源码结构（仓库根目录）

```text
04-demo/backend/
├── app/contracts/project_master.py          # 批量请求与最小显示投影模型
├── app/project_master/repository.py         # 按版本和工点集合精确查询
├── app/api/routers/project_master.py         # 任务视图批量读取端点
└── tests/                                    # 仓储、接口和 OpenAPI 契约验证

04-demo/frontend/
├── src/contracts/projectMaster.ts            # 对齐的批量映射类型
├── src/api/projectMasterApi.ts               # 单次批量请求
├── src/features/taskView/
│   ├── projectMasterDisplayState.ts          # 单请求协调、校验、缓存和竞态隔离
│   └── presenter.ts                          # 最小投影转任务视图 Map
├── src/app/Workspace.tsx                     # 接入批量 loader
└── tests/                                    # 协调器、静态契约和真实浏览器性能验证
```

**结构决策**：批量端点放入现有项目主数据路由，查询放入现有仓储，避免新服务层。返回任务视图直接需要的最小显示投影，不复用重型 `ProjectMasterWorkpoint`，从类型层阻止构件、参数和来源证据进入响应。前端保留现有协调器状态机，只把 loader 从“每个工点一次”收敛为“当前身份一次”。

## Phase 0：研究结论

- 主要耗时来自 13 个并发单工点详情请求各自调用 `load_snapshot()`，重复读取并组装同一版本的全部工点、结构物、构件、参数和证据；缩短前端超时或增加并发不能消除根因。
- 任务视图实际只消费工点名称/顺序，以及由 `section_code + side` 得到的工区身份、名称、顺序和幅别；无需完整构件、参数和来源证据。
- 采用 POST 批量读取可稳定承载最多 500 个去重工点 ID，避免 GET 查询串长度限制；该端点是只读语义，不改变持久化。
- 完整性由后端拒绝版本或工点缺失、前端再次核对版本和工点集合共同保证；既有原子提交、成功缓存和 generation/token 隔离继续使用。
- 单工点详情仍可能被资源配置等页面使用，本期保留其响应语义，并将内部实现改为精确查询以消除独立的全快照读取风险。

详见 [research.md](./research.md)。

## Phase 1：数据与接口契约

- [data-model.md](./data-model.md) 定义请求身份、批量请求、最小工点/工区投影和加载状态，不新增持久化实体。
- [task-view-display-map-api.md](./contracts/task-view-display-map-api.md) 定义 POST 路径、字段、限制、成功响应、稳定错误码和前端状态转换。
- [quickstart.md](./quickstart.md) 给出接口、协调器和真实浏览器性能/原子性验收步骤。
- 仓库当前没有计划 Skill 所述的 agent context 更新脚本，因此本功能不生成或修改第二套 Agent 上下文。

## 计划实现顺序

1. 先以仓储和 API 测试固定批量投影字段、缺失工点、空集合、500 上限及单工点详情兼容行为。
2. 在后端新增最小 Pydantic 契约、集合精确查询和批量路由，并让单工点详情复用精确查询而非完整快照。
3. 以前端协调器测试固定一次 loader 调用、响应完整性、原子提交、缓存、重试与旧响应隔离，再更新共享类型、API 和 Workspace 接线。
4. 更新真实浏览器运行测试，记录请求数、响应体、连续 3 次硬刷新耗时、任务 DOM 提交次数和原始 ID 泄漏计数。
5. 运行一次风险匹配验证批次；只修复本功能相关失败并记录无关风险。

## 复杂度跟踪

无 Constitution 违反项。
