# 任务：导航目录与 AI 多方案比选重构

**输入**：`specs/024-navigation-ai-comparison/` 下的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/ui-behavior.md`、`quickstart.md`

**测试要求**：用户已明确要求执行前端生产构建和导航、方案下钻、结果失效、完整模拟求解回归，因此任务中包含构建与手动验收。

## Phase 1：准备

**目的**：建立当前前端基线，确认现有代码在改动前可构建。

- [x] T001 在 `frontend/package.json` 现有脚本下运行 `npm.cmd run build` 并记录基线结果，不修改依赖或构建配置

---

## Phase 2：基础能力

**目的**：先形成一套可同时服务完整模拟求解和 AI 方案详情的结果展示能力。

**⚠️ 关键**：本阶段完成后才能实现 US2 的只读方案详情。

- [x] T002 在 `frontend/src/app/App.tsx` 将现有 `ResultsTab` 拆分为交互控制区与可复用结果内容区，并增加 `interactive/readOnly` 显示模式，保证 `readOnly` 隐藏参数、求解、保存和历史对比操作但保留全部结果板块
- [x] T003 在 `frontend/src/app/App.tsx` 为可复用结果内容增加显式诊断空态，允许缺少完整排程内容的方案结果只展示状态与诊断且不回退到其他结果

**检查点**：完整模拟求解继续使用 `interactive` 模式并保持原有功能；结果内容可以由外部方案数据以 `readOnly` 模式渲染。

---

## Phase 3：用户故事 1——按业务阶段浏览功能目录（P1）🎯 MVP

**目标**：将平铺导航调整为两个默认展开的业务目录，保留工作区标签交互。

**独立测试**：启动应用后，仅通过左侧导航展开、收起并依次打开 7 个保留页面，验证分组、顺序、名称和标签一致。

- [x] T004 [US1] 在 `frontend/src/features/layout/WorkspaceNavigation.tsx` 将平铺 `tabs` 元数据重构为两个有序导航组，并统一生成分组子项和工作区标签名称
- [x] T005 [US1] 在 `frontend/src/features/layout/WorkspaceNavigation.tsx` 实现两个目录默认展开、独立折叠、一级标题不打开页面以及整体侧栏折叠不重置目录状态的交互
- [x] T006 [P] [US1] 在 `frontend/src/styles.css` 增加导航分组、层级缩进、折叠按钮、整体侧栏折叠和窄屏适配样式
- [x] T007 [US1] 按 `specs/024-navigation-ai-comparison/contracts/ui-behavior.md` 手动验证 `frontend/src/features/layout/WorkspaceNavigation.tsx` 的 7 个入口顺序、标签名称、目录折叠和侧栏折叠行为

**检查点**：导航结构可独立演示，现有业务页面均可打开且工作区标签可关闭。

---

## Phase 4：用户故事 2——在 AI 多方案比选中查看方案详情（P1）

**目标**：已求解方案可进入页面内只读完整详情并无请求返回比选。

**独立测试**：仅求解一套方案，进入该方案详情并核对资源、任务和诊断；返回后确认所有比选状态保持且没有新增请求。

- [x] T008 [P] [US2] 在 `frontend/src/features/resourceAssistant/ResourcePlanCard.tsx` 增加仅在存在 `plan_result` 时显示的“查看方案详情”操作及回调契约
- [x] T009 [US2] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 增加 `comparison/detail` 状态、当前详情方案、返回入口和方案标题，并在场景变化或结果失效时安全退出详情
- [x] T010 [US2] 在 `frontend/src/app/App.tsx` 向 AI 多方案比选页面提供只读详情渲染回调，使用所选方案的 `resource_pools` 和对应 `ResourceAssistantPlanResult` 构造结果上下文并校验方案标识一致
- [x] T011 [US2] 在 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 将所有用户可见页面名称统一为“AI多方案比选”，进入详情时隐藏方案卡、指标对比和推荐，返回时不触发初始化、求解、对比或推荐请求
- [x] T012 [US2] 删除 `frontend/src/features/resourceAssistant/PlanVisualTabs.tsx`、仅被其引用的 `frontend/src/features/resourceAssistant/ResourceUtilizationView.tsx` 与 `frontend/src/features/resourceAssistant/ControlPierFocusView.tsx`，并清理 `frontend/src/features/resourceAssistant/ResourceAssistantPanel.tsx` 和 `frontend/src/styles.css` 中仅服务常驻简化方案视图的引用和样式
- [x] T013 [US2] 按 `specs/024-navigation-ai-comparison/quickstart.md` 验证已求解、不可行/未知、请求失败、超过 42 个任务、返回状态保持和资源修改失效场景

**检查点**：详情始终对应所点击方案，完整展示全量结果，返回后比选会话状态不变。

---

## Phase 5：用户故事 3——保留完整模拟求解并移除 MVP（P2）

**目标**：移除 `模拟求解-MVP` 全部前端入口和专属状态，完整模拟求解继续可用。

**独立测试**：从“2.2 模拟求解”执行原有三类求解，并确认全局不再产生 MVP 页面或标签。

- [x] T014 [US3] 在 `frontend/src/types/scheduler.ts` 从 `TabKey` 删除 `resultsMvp`，保留 `results`、`resourceAssistant` 和其他现有页面标识
- [x] T015 [US3] 在 `frontend/src/app/App.tsx` 删除 MVP 工点、日期、生成结果、求解结果、指纹状态、两个 MVP 求解函数、MVP 场景构造及仅被其使用的辅助类型和渲染分支
- [x] T016 [US3] 在 `frontend/src/app/App.tsx` 删除 `ResultsTab` 的 `mvp` 变体条件和未使用的重复 `renderModule` 分发逻辑，确认完整 `results` 页面继续使用交互模式
- [x] T017 [P] [US3] 在 `frontend/src/styles.css` 删除仅由 `模拟求解-MVP` 使用的 `.mvp-solve-form` 等样式，并保留完整结果页所需通用样式
- [x] T018 [US3] 按 `specs/024-navigation-ai-comparison/quickstart.md` 回归“2.2 模拟求解”的固定资源最短工期、固定工期最少资源和资源成本优化入口，并确认导航和标签中没有 MVP

**检查点**：`resultsMvp` 不再存在于前端类型和运行路径，完整模拟求解功能无回退。

---

## Phase 6：收尾与跨故事验证

**目的**：完成术语、残留引用、生产构建和核心页面回归。

- [x] T019 [P] 使用 `rg` 检查 `frontend/src/`，确保用户可见“AI资源助手”、`模拟求解-MVP`、`resultsMvp` 和 `PlanVisualTabs` 残留为 0，并仅保留有意不重命名的内部 `resourceAssistant` 标识
- [x] T020 在 `frontend/` 运行 `npm.cmd run build`，修复全部 TypeScript 和 Vite 构建问题
- [x] T021 按 `specs/024-navigation-ai-comparison/quickstart.md` 完成项目基本参数五页、AI多方案比选、完整模拟求解、工作区标签和跨项目状态重置的联合回归

---

## 依赖关系

### 阶段依赖

- Phase 1 无依赖。
- Phase 2 依赖 Phase 1，并阻塞 US2。
- US1 可在 Phase 2 后独立实施和验证。
- US2 依赖 Phase 2；可与 US1 的样式工作错峰进行，但合并前需协调 `styles.css`。
- US3 可在 US1 导航元数据完成后实施，避免同时编辑旧 `resultsMvp` 导航项。
- Phase 6 依赖 US1、US2、US3 全部完成。

### 用户故事依赖图

```text
基础结果复用 ───────> US2 AI方案下钻
US1 导航分组 ───────> US3 移除MVP导航与入口
US1 + US2 + US3 ───> 联合回归
```

### 并行机会

- T006 可在 T004/T005 结构确定后独立处理 `styles.css`。
- T008 可与 T009/T010 的状态和适配设计并行。
- T017 可与 T014-T016 的 TypeScript 清理并行，但需在最终构建前合并。
- T019 可在全部实现任务结束后与回归准备并行。

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2，建立可复用结果展示。
2. 完成 US1，交付可独立演示的新导航目录。
3. 完成 US2，形成 AI 多方案比选到完整详情的核心闭环。
4. 完成 US3，清理重复 MVP 入口并回归完整模拟求解。
5. 执行联合构建和页面回归。

## 格式校验

- 所有任务均使用 `- [ ] T###` 格式。
- 用户故事任务均包含 `[US#]` 标记。
- `[P]` 仅用于不同文件或可独立执行的任务。
- 每个实现或验证任务都包含明确文件路径或规格路径。
