# 实施计划：架梁双幅线路示意图优化

**分支/目录**：`060-girder-line-schematic` | **日期**：2026-07-22 | **规格**：[spec.md](./spec.md)

**输入**：来自当前 `03-requirements/specs/060-girder-line-schematic/spec.md` 的功能规格

## 概要

在现有架梁计划推演的派生线路图上完成两类收敛：后端取消结构累计长度与线路落位长度的 1m 级一致性阻断，并将连续梁三段按本幅结构长度占比投影到本幅全桥示意区间；前端把 ZK/K 节点渲染为两条连续平行主线，把 AK/BK/B1K 等非主线前缀渲染为锚定空间对应组的互通支线层，梁场保持在线路外以部署节点或中心里程标记。实现复用现有线路图节点、空间组、指纹、方案失效和前端组件，不新增持久化字段或 API。

## 技术上下文

**语言/版本**：Python 3.14.3；TypeScript 5.7；Node.js 24.14.1

**主要依赖**：现有 Python 领域模型与确定性线路图构建；React 19；Vite 6；lucide-react 0.468

**存储**：不新增存储；继续只读引用 `.local-data/state/project-master.db` 中已确认项目主数据，方案仍使用现有独立本地状态仓储

**测试**：pytest 后端拓扑/校验测试；Node `node:test` 前端源码契约测试；TypeScript 类型检查；Vite 构建

**目标平台**：本地 FastAPI 后端和 React/Vite Web 页面

**项目类型**：现有 Web 应用内的后端派生拓扑与前端可视化优化

**性能目标**：不增加网络请求；后端投影保持节点线性或排序主导复杂度；现有 500 工点、10 梁场、300 目标性能样例继续满足单次不超过 10 秒

**约束**：不改变梁型、梁片、产能、架梁工效、人工顺序和日期仿真；不修改项目主数据；不恢复已移除的人工连接入口；不引入 GIS、画布库或新依赖；长度差异不生成诊断；其他真实结构与路线错误保持现有行为

**规模/范围**：后端 `girder_plan_simulation/topology.py` 及邻近测试；前端 `girderPlanSimulation/LineGraphView.tsx`、样式和目标测试；无公开接口字段变化

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属必填)
- **实施路径**：`04-demo/backend/app/girder_plan_simulation/`、`04-demo/backend/tests/`、`04-demo/frontend/src/features/girderPlanSimulation/`、`04-demo/frontend/tests/`

## Constitution 检查

*门禁：Phase 0 研究前已通过；Phase 1 设计后再次检查。*

- **可验收需求**：通过。用户已确认示意图业务口径、长度差异行为、双幅关系和项目平面图参考；规格包含可观察验收样例。
- **显式算法规则**：通过。输入为本幅结构顺序、结构类型、正数结构长度和全桥起终里程；输出为三段顺序、结构归属、示意区间和既有待架需求；长度差异不是约束或诊断。
- **显式共享契约**：通过。不新增 API 字段；现有 `LineGraphSnapshot`、`LineGraphNode`、指纹和失效机制保持兼容；UI 派生规则记录于 `contracts/line-graph-schematic-ui.md`。
- **保留行为与最小设计**：通过。复用现有拓扑模块、空间组、React 组件和测试，不新增依赖、持久化模型或第二套线路图。
- **分阶段可验证价值**：通过。后端三段投影和前端双幅/支线展示均可独立测试，组合后以泸古项目页面验收。
- **验证与完成证据**：通过。计划包含当前项目差异样例、反例回归、前端契约、类型检查和构建。
- **资产与数据安全**：通过。不删除或迁移项目主数据、方案和结果；线路图指纹变化沿用现有失效行为。

Phase 1 设计后复核结果不变：没有 Constitution 违反项或未解决澄清项。

## 项目结构

### 本功能文档

```text
03-requirements/specs/060-girder-line-schematic/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── line-graph-schematic-ui.md
└── tasks.md              # 由 speckit-tasks 创建
```

### 生命周期与源码结构（仓库根目录）

```text
04-demo/
├── backend/
│   ├── app/girder_plan_simulation/topology.py
│   └── tests/test_girder_plan_simulation_topology.py
└── frontend/
    ├── src/features/girderPlanSimulation/
    │   ├── LineGraphView.tsx
    │   └── styles.css
    └── tests/girderPlanSimulation.test.mjs
```

**结构决策**：后端继续在唯一线路图构建模块中产生可计算节点；前端只基于既有节点字段派生主线、支线和梁场展示，不创建镜像模型或持久化布局。规格及设计资产唯一归属 `03-requirements/specs/060-girder-line-schematic/`。

## Phase 0：研究结论

详见 [research.md](./research.md)。本功能没有阻塞未知项；关键决策为：

1. 连续梁三段以每幅结构长度占结构总长的比例，投影到该幅全桥起终里程形成示意区间；比例只服务显示和既有路径顺序，不输出工程精确边界。
2. `BRIDGE_SEGMENT_LENGTH_MISMATCH` 被删除，不替换成提示或其他等价诊断；缺失或非法基础数据继续沿用现有诊断。
3. 前端将左幅 ZK、右幅 K 识别为主线；AK/BK/B1K 等其他前缀进入空间组内的互通支线层，不参与 K 主轴宽度计算。
4. 梁场继续通过部署节点和中心里程定位，在线路外显示；路基保持普通细线，桥梁和隧道保持粗线区段。
5. 不修改 API 和持久化模型；线路图节点变化自然更新指纹并使旧方案按既有规则失效。

## Phase 1：设计产物

- [data-model.md](./data-model.md)：定义既有线路节点上的三段示意投影，以及前端主线、互通支线和梁场派生视图。
- [contracts/line-graph-schematic-ui.md](./contracts/line-graph-schematic-ui.md)：定义不新增 API 字段前提下的后端诊断和前端展示契约。
- [quickstart.md](./quickstart.md)：提供后端样例、泸古项目、前端展示和兼容回归验证路径。
- `.specify/scripts/powershell/` 当前没有 agent-context 更新脚本，因此本计划不虚构或手工替代该步骤；根 `AGENTS.md` 和现有 Agent 上下文保持不变。

## 复杂度跟踪

无 Constitution 违反项。
