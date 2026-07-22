# 实施计划：架梁双幅线路拓扑

**分支/目录**：`055-girder-dual-carriageway-topology` | **日期**：2026-07-20 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `SPECIFY_FEATURE_DIRECTORY/spec.md` 的功能规格

## 概要

将功能 051 现有“按 `alignment_code` 分线路”的投影升级为“按左/右幅形成两条展示与通行主轴、按里程前缀保留节点局部坐标系”的 v2 投影。项目主数据增加可选、可追溯的线路落位关系，用于保存幅别、原始里程前缀、分幅里程、空间对应组和顺序；既有版本没有显式落位数据时，从结构物 `side`、工点线路编码和稳定排序生成带证据状态的兼容投影。后端按幅别及可比较前缀校验连续性，前端固定渲染两条线路，并让梁场部署、人工连接和待架顺序使用稳定双幅节点。投影变化使旧运行失效，但不修改现有架梁专项联算或人工架梁顺序。

## 技术上下文

**语言/版本**：Python 3.12（Docker/推荐基线），TypeScript 5.7，Node.js 22（部署基线）

**主要依赖**：FastAPI、Pydantic、SQLite、openpyxl、React 19、Vite 6

**存储**：`.local-data/state/project-master.db` 的项目主数据 SQLite；架梁计划推演继续使用其既有独立本地状态仓储

**测试**：pytest；Node.js `node:test` 前端旅程测试；TypeScript 类型检查；Vite 生产构建；架构契约基线

**目标平台**：本地 FastAPI + React Web Demo；Netlify 静态前端继续调用独立 FastAPI

**项目类型**：跨项目主数据、后端拓扑/API、前端线路图的 Web 功能修正

**性能目标**：沿用功能 051 的验收规模，500 个线路工点在 10 秒内返回线路图或明确阻断终态；前端两条线路可水平滚动且不因节点数量新增展示行

**约束**：仅影响独立“架梁计划推演”；不改变 CP-SAT、综合排程、现有架梁专项和用户人工顺序；空间对应关系不得自动形成通行边；确认项目版本不可原地改写

**规模/范围**：新增一个项目主数据线路落位实体和可选 Excel 工作表；升级线路图投影契约至 v2；修改拓扑、梁场定位兼容逻辑、两条前端线路及相关契约/集成测试

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：`04-demo/backend/app/contracts/`、`04-demo/backend/app/project_master/`、`04-demo/backend/app/girder_plan_simulation/`、`04-demo/frontend/src/contracts/`、`04-demo/frontend/src/features/girderPlanSimulation/`、`04-demo/tools/demo-api-mirror/` 及邻近测试/架构基线

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- **通过｜可验收需求**：`spec.md` 已记录用户确认的左右幅、里程前缀、互通连接和 Excel 同行语义，并给出独立故事和量化验收。
- **通过｜显式算法规则**：输入为确认主数据及线路落位，输出为 v2 双幅线路图；幅别投影、里程可比较范围、连续/重叠诊断、兼容推断和阻断边界均已定义。
- **通过｜显式共享契约**：本计划要求同步更新后端模型、SQLite、Excel 模板、前端类型、FastAPI 契约、演示镜像和契约测试，并定义 v1 到 v2 的失效行为。
- **通过｜保留行为与最小设计**：复用现有项目主数据、线路图、节点 ID、人工连接及方案仓储；只增加无法由现有合并工点表达的分幅线路落位实体。
- **通过｜分阶段可验证价值**：先建立线路落位和后端双幅投影，再交付两行页面及梁场/顺序接入，最后验证兼容失效。
- **通过｜验证与完成证据**：设计包含源 Excel 语义样例、同幅真实重叠、跨幅误报、既有版本兼容和端到端页面旅程。
- **通过｜资产与数据安全**：用户 Excel 保持原位且不改写、不复制进 Git；数据库迁移只新增结构，不原地改写已确认版本内容。

**Phase 1 设计后复核**：通过。`data-model.md` 明确实体、校验和兼容状态；`contracts/` 明确 API 字段与投影版本；`quickstart.md` 提供可运行验收，未发现未解释的宪章违反项。

## 项目结构

### 本功能文档

```text
03-requirements/specs/055-girder-dual-carriageway-topology/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── girder-dual-carriageway-topology.openapi.yaml
└── tasks.md
```

### 生命周期与源码结构（仓库根目录）

```text
03-requirements/specs/055-girder-dual-carriageway-topology/
04-demo/backend/app/
├── contracts/
├── project_master/
└── girder_plan_simulation/
04-demo/backend/tests/
04-demo/frontend/src/
├── contracts/
└── features/girderPlanSimulation/
04-demo/frontend/tests/
04-demo/tools/demo-api-mirror/
```

**结构决策**：在线路落位属于项目主数据事实的边界内扩展现有 `project_master`，不建立第二套客户 Excel 仓储；线路图仍由 `girder_plan_simulation/topology.py` 派生，页面继续复用现有 `LineGraphView`、`YardPlanEditor` 和方案流程。用户提供的原 Excel 只作为解析规则与验收证据。

## 技术设计

1. 项目主数据快照新增 `route_placements`。每条记录描述一个工点在一个幅别上的线路落位：稳定 ID、工点、`left/right`、原始里程前缀、分幅起终里程、空间对应组、组内顺序和来源证据。
2. 项目主数据数据库升级到 schema v2，仅新增 `route_placements` 表；已有版本没有记录时仍可加载。统一 Excel 模板新增可选“线路关系”表；新版导出写出该表，解析仍接受旧 1.0 模板并生成兼容提示。
3. 线路图投影升级为 `girder-plan-line-graph/v2`。显式落位优先；缺失时根据结构物 `side` 生成兼容落位：`ZK/K` 按左 `ZK`、右 `K` 拆分，单前缀保留原值，顺序沿用 `sort_order`。兼容落位不伪造原 Excel 行号，且不执行可能误报的严格区间重叠检查。
4. 桥梁和非桥梁都按落位幅别生成节点。桥梁稳定目标 ID 继续使用 `<workpoint_id>:<side>`；非桥梁由旧 `<workpoint_id>:unknown` 升级为 `<workpoint_id>:<side>`。同一空间对应组只控制展示序位，不生成横向边。
5. 自动相邻边只在同一幅别、同一可比较里程前缀或显式连续关系内产生；不同前缀之间必须有人工连接。重叠诊断限定到同幅同前缀且来源为显式落位的数据。
6. `LineGraphNode` 保留 `alignment_code` 作为原始里程前缀兼容字段，新增 `spatial_group_id`、`placement_source` 和 `display_order`；`side` 成为两条展示主轴。投影版本进入指纹。
7. 梁场新增可选稳定 `deployment_node_id`；新编辑操作写入节点 ID，旧方案先按原线路编码/里程兼容匹配，不能唯一匹配时阻断用户重新选择。桥梁目标 ID 不变，既有人工顺序尽量保留；旧路径边或运行快照因 v2 指纹变化失效。
8. 前端固定按 `left/right` 生成两行，共享空间对应组使用统一 CSS 栅格列；节点显示其原始前缀及格式化里程。没有对应节点的一侧保留空列，不伪造节点或连接。

## 复杂度跟踪

无宪章违反项。新增线路落位实体是表达“一个工点可同时拥有左右两套前缀、分幅里程及 Excel 同行关系”的最小数据结构；现有单值 `alignment_code/start/end` 无法无损承载该事实。
