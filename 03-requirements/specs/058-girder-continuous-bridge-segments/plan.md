# 实施计划：连续结构桥梁分段与线路图清晰展示

**分支/目录**：`058-girder-continuous-bridge-segments` | **日期**：2026-07-21 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `SPECIFY_FEATURE_DIRECTORY/spec.md` 的功能规格

## 概要

在线路图 v2 双幅投影之上增加桥梁“路线分段”派生层：使用项目主数据已存在的分幅上部结构、`span_index`、`span_length_m` 和结构类型识别一个连续的 `continuous_unit` 区块，并在证据完整时把一个桥梁幅别节点派生为小里程引桥、连续结构、大里程引桥三个节点。引桥节点各自汇总预制梁需求并作为人工待架目标，连续结构节点只作为路径和交付控制节点。线路图契约升级到 v3，使旧整桥目标方案失效而不做一对多自动迁移。前端在既有双幅空间组内按节点里程定位名称和粗线段，完整名称使用两条错位标签轨道，桥隧取消圆形轨道图标。

## 技术上下文

**语言/版本**：Python 3.12（Docker/推荐基线），TypeScript 5.7，Node.js 22（部署基线）

**主要依赖**：FastAPI、Pydantic、React 19、Vite 6；不新增依赖

**存储**：项目主数据 SQLite 和架梁计划独立 JSON 状态仓储均不新增表或持久字段；分段为只读派生投影

**测试**：pytest；Node.js `node:test` 前端旅程测试；TypeScript 类型检查；演示 API 镜像和架构契约基线

**目标平台**：本地 FastAPI + React Web Demo；Netlify 静态前端继续调用同一独立 FastAPI 契约

**项目类型**：跨后端线路拓扑、共享契约、前端线路图和演示镜像的 Web 功能变更

**性能目标**：沿用功能 051 的 500 工点 10 秒线路图终态；单个桥梁幅别最多从 1 个节点增加到 3 个节点，前端仍维持固定两条线路

**约束**：不改变 CP-SAT、综合排程、现有架梁专项、梁场生产/架设能力模型或人工排序口径；不修改确认项目主数据；不按名称猜测连续结构；异常数据失败关闭

**规模/范围**：线路图投影 v2→v3；一个后端节点契约增加可选分段类型；拓扑生成与邻接处理、前端类型/线路图、演示镜像及邻近测试同步修改

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：`04-demo/backend/app/contracts/girder_plan_simulation.py`、`04-demo/backend/app/girder_plan_simulation/topology.py`、`04-demo/tools/demo-api-mirror/api.mts`、`04-demo/frontend/src/contracts/girderPlanSimulation.ts`、`04-demo/frontend/src/features/girderPlanSimulation/` 及邻近后端/前端测试和必要架构基线

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- **通过｜可验收需求**：`spec.md` 已记录用户截图、现有页面事实、三个用户故事、异常边界和量化结果。
- **通过｜显式算法规则**：输入结构类型、顺序、长度和分幅落位均明确；输出三个区段、单位（米/片/天）、1 米容差、待架目标和失败关闭规则均有可复现样例。
- **通过｜显式共享契约**：`data-model.md` 和 `contracts/` 定义 v3 节点字段、诊断、加载/阻断状态、旧方案失效及后端/前端/镜像同步边界。
- **通过｜保留行为与最小设计**：复用现有 `ProjectMasterStructure`、`LineGraphNode`、路径展开和 `requires_erection`；不增加项目主数据实体、持久化迁移、算法依赖或第二套路线模型。
- **通过｜分阶段可验证价值**：先交付可测试的后端三段投影，再接入现有路线校验，最后完成页面清晰展示和兼容验证。
- **通过｜验证与完成证据**：任务将覆盖正常三段、左右幅差异、五类阻断、旧方案失效、路径展开、UI 结构断言、类型检查及风险匹配回归。
- **通过｜资产与数据安全**：不改写用户 Excel、确认主数据或既有运行快照；旧成果保留历史记录但不能作为当前结果。

**Phase 1 设计后复核**：通过。研究结论、数据模型、OpenAPI 共享契约和 quickstart 已将三段节点、界面语义、兼容失效和诊断行为闭合，无未解释宪章违反项。

## 项目结构

### 本功能文档

```text
03-requirements/specs/058-girder-continuous-bridge-segments/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── girder-continuous-bridge-segments.openapi.yaml
└── tasks.md
```

### 生命周期与源码结构（仓库根目录）

```text
04-demo/backend/app/
├── contracts/girder_plan_simulation.py
└── girder_plan_simulation/topology.py
04-demo/backend/tests/
04-demo/frontend/src/
├── contracts/girderPlanSimulation.ts
└── features/girderPlanSimulation/
04-demo/frontend/tests/
04-demo/tools/demo-api-mirror/api.mts
```

**结构决策**：分段完全由确认项目主数据派生，继续归属 `girder_plan_simulation/topology.py`；不扩展项目主数据数据库或 Excel。前端复用 `LineGraphView` 的双幅空间组，在一个空间组内部按区段里程比例定位多个节点，而不伪造新的左右幅对应组。

## 技术设计

1. `LineGraphNode` 增加可空 `bridge_segment_kind`，取值为 `approach_small/continuous/approach_large`。未分段节点保持空值和原 ID；分段节点 ID 为 `<workpoint_id>:<side>:<segment_kind>`。
2. 线路图投影升级为 `girder-plan-line-graph/v3`。投影版本、分段字段、区段里程、需求及源结构引用进入现有稳定指纹，v2 运行自然失效。
3. `_node_for_projection` 的单节点投影改为可返回节点列表和诊断。非桥梁、普通桥梁继续返回一个节点；符合条件的连续结构桥梁返回三个节点。构建器把每个节点按真实起点里程放入同一幅别/里程前缀序列，自动生成区段内部和相邻工点之间的边。
4. 分段先过滤同幅上部结构，按 `span_index → sort_order → structure_id` 排序。相邻 `continuous_unit` 合成一个连续区块；其前后结构分别构成两侧引桥。结构长度必须为正，累计总长与线路落位区间差值最多 1 米。
5. 梁型需求聚合函数改为接收区段结构集合：两个引桥段只汇总各自结构的启用预制梁构件/参数；连续区段必须无预制梁需求。每段的 `current_plan_finish_date` 只读取该段结构日期。
6. 无法安全分段时返回旧整桥节点用于页面定位，同时输出 blocking 诊断并阻止方案校验/运行。诊断覆盖缺顺序/长度、多个不相邻连续区块、零长度引桥、总长超差、连续段预制梁冲突。
7. 现有 `girderTargets` 和校验器继续以 `requires_erection` 工作，因此两个引桥目标直接进入人工选择，连续区段由 `resolve_path` 自动补齐。旧整桥目标 ID 无法匹配 v3 节点时沿用 `ROUTE_TARGET_INVALID/LINE_GRAPH_CHANGED` 和指纹失效路径，不增加猜测映射。
8. 前端布局保留空间组列，但每个节点标签与粗线段依据该侧组内起终里程计算相对 `left/width`。完整名称按钮采用绝对定位、`white-space: nowrap`、可见溢出，并由稳定序号交替放入两条标签轨道。
9. 桥梁、隧道的轨道圆形 marker 从 DOM 移除；粗线段本身继续承担类型颜色、风险/选择态和可点击对象语义。路基、连接和梁场的点位表达保持。
10. 演示 API 镜像输出 v3 和分段样例，前端/后端契约及架构基线同步，确保静态预览不会继续伪造 v2 整桥行为。

## 复杂度跟踪

无宪章违反项。新增一个可空分段枚举是表达三段节点语义的最小共享契约；项目主数据已具备全部权威输入，因此无需新增数据库字段或 Excel 表。
