# 实施计划：导航目录与 AI 多方案比选重构

**分支/目录**：`024-navigation-ai-comparison` | **日期**：2026-07-10 | **规格**：[spec.md](spec.md)

**输入**：来自 `specs/024-navigation-ai-comparison/spec.md` 的功能规格

## 概要

在不修改后端和算法的前提下，将前端平铺导航改为两个可展开业务目录，移除 `resultsMvp` 页面及其专属状态，将 `resourceAssistant` 的可见名称统一为“AI多方案比选”。在 AI 页面中为已有求解结果的方案增加页面内下钻，通过同一套完整结果展示组件呈现只读详情，并在返回后保留比选会话状态。

## 技术上下文

**语言/版本**：TypeScript 5.7、Node.js 22

**主要依赖**：React 19、Vite 6、lucide-react

**存储**：不新增持久化；导航展开状态和比选/详情状态保存在当前前端会话内存中

**测试**：`npm.cmd run build`；本地页面手动回归导航、完整模拟求解和 AI 多方案下钻

**目标平台**：本地 Vite 前端及静态前端构建

**项目类型**：前端 Web 页面重构

**性能目标**：返回比选态不发起网络请求；详情直接使用已保存的单方案求解结果；全量任务展示不再固定截断 42 条

**约束**：不修改 CP-SAT、LLM、FastAPI 路由、后端模型或前端 API 请求响应字段；不新增依赖；不修改 `README.md` 和历史需求文档

**规模/范围**：导航、工作区标签类型、主应用页面编排、完整结果展示模式、资源方案卡、AI 多方案比选页面及相关样式

## Constitution 检查

- 已完成需求发现并由用户确认导航层级、完整模拟求解归属、页面内下钻和只读详情范围。
- `spec.md` 已引用现有 AI 资源助手规格、验证说明、MVP 文档及真实前端代码事实。
- 排程算法、资源规则、工期和 CP-SAT 均不变；本次只重构前端页面入口和结果展示复用。
- 前后端契约不变；页面入口、状态、空态、失效、异常和兼容行为已在规格及 UI 契约中明确。
- 复用现有 `ResultsTab` 结果展示、`ResourceAssistantPanel` 状态和 `ResourcePlanCard`，不引入平行结果实现。
- Spec Kit 产物均使用中文简体；代码标识和路径保留原文。

**设计后复核**：通过。没有 Constitution 例外，不新增公共接口或持久化数据，不把 Demo 限制提升为算法规则。

## 设计决策

### 导航分组

- 将页面元数据从单一 `tabs` 数组调整为两个导航组，每组包含编号、名称和有序子项。
- `SideNavigation` 自行维护两个组的展开状态，初始均为展开；整体侧栏折叠不重置该状态。
- `WorkspaceTabStrip` 继续通过同一页面元数据查找标签，不改变 `openTabs` 和 `activeTab` 工作方式。
- 删除 `resultsMvp` 的 `TabKey`，保留 `resourceAssistant` 与 `results` 内部标识。

### MVP 页面清理

- 从 `App` 删除 MVP 工点、日期、生成结果、求解结果和指纹状态，以及两个 MVP 求解函数、MVP 场景构造函数和仅被其使用的类型/样式。
- 从页面渲染和 `ResultsTab` 删除 `mvp` 分支；完整 `results` 页面继续使用交互模式。
- 清理 `App` 中重复且未被调用的 `renderModule` 分支，避免删除页面后遗留第二套分发逻辑。

### 结果详情复用

- 将 `ResultsTab` 明确拆成交互控制区和可复用结果内容区；结果内容区接受统一的只读/交互显示模式。
- 完整模拟求解使用交互模式；AI 方案详情使用只读模式，隐藏参数、求解、保存和历史对比操作，其余结果板块复用同一实现。
- `App` 提供方案详情渲染回调：用基础场景与所选方案的 `resource_pools` 构造方案场景，用 `ResourceAssistantPlanResult` 的 `generated`、`result`、`diagnostics` 和 `metrics` 构造结果上下文。
- 对只有状态和诊断、没有完整排程内容的结果，详情显示诊断空态，不回退到项目或其他方案结果。

### AI 页面下钻

- `ResourceAssistantPanel` 增加 `comparison/detail` 视图状态和 `detailPlanId`。
- `ResourcePlanCard` 仅在存在对应 `plan_result` 时显示“查看方案详情”，并把方案和结果交给页面回调。
- 进入详情时只切换本地视图；返回时只恢复比选视图，不初始化、不求解、不刷新对比、不生成推荐。
- 资源数量调整沿用现有结果失效逻辑，同时清除正在查看的失效详情；场景指纹变化时重置为比选态。
- 删除常驻 `PlanVisualTabs`、仅被它引用的 `ResourceUtilizationView` 与 `ControlPierFocusView`，并清理对应样式和引用。

## 项目结构

### 本功能文档

```text
specs/024-navigation-ai-comparison/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ui-behavior.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构

```text
frontend/src/
├── app/App.tsx
├── types/scheduler.ts
├── features/layout/WorkspaceNavigation.tsx
├── features/resourceAssistant/
│   ├── ResourceAssistantPanel.tsx
│   ├── ResourcePlanCard.tsx
│   ├── PlanVisualTabs.tsx        # 移除
│   ├── ResourceUtilizationView.tsx # 若无其他引用则随简化视图移除
│   └── ControlPierFocusView.tsx  # 若无其他引用则随简化视图移除
└── styles.css
```

**结构决策**：不重命名现有源码目录；通过现有模块内的组件拆分和渲染回调复用结果页面，避免引入新依赖或复制完整结果实现。当前 `ResourceUtilizationView` 和 `ControlPierFocusView` 仅由 `PlanVisualTabs` 引用，因此与常驻简化视图一起删除。

## 复杂度跟踪

无 Constitution 违反项。
