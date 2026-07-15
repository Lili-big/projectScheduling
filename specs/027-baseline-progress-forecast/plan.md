# 实施计划：基准计划、进度反馈与滚动预测

**目录**：`027-baseline-progress-forecast` | **日期**：2026-07-12 | **规格**：[spec.md](./spec.md)

## 概要

在 AI 多方案比选之后新增“计划执行与进度”闭环。用户把一个已求解可行方案保存为不可变基准版本，按状态日期提交实际进度快照；后端把已完成历史与状态日期之后的剩余任务网络分离，复用现有 CP-SAT 生成当前趋势预测，并比较不调整、增加瓶颈资源、关键任务优先三类策略。采用策略后创建有父子关系的新执行版本，原基准、历史快照和预测始终保留。

## 技术上下文

**语言/版本**：Python 3.12、TypeScript 5.7、React 19  
**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React、Vite；不新增第三方依赖  
**存储**：复用 `.local-data` 本地 JSON 模式，新增版本化计划管控存储；原子替换与进程内写锁  
**测试**：pytest 后端模型/存储/算法/API 测试，前端 TypeScript/Vite 构建，浏览器端闭环验证  
**目标平台**：单机 FastAPI + React Demo；Docker 后端挂载持久卷时可跨容器重启保存  
**项目类型**：跨前后端计划版本、进度填报、预测算法和页面模块  
**性能目标**：单项目 2,000 个任务、100 个快照以内列表和保存操作在 2 秒内完成；单策略求解沿用现有时间上限，三策略独立执行并返回部分成功  
**约束**：不修改既有三方案生成和求解接口；不接入正式权限审批；实际事实不可被求解器改写；LLM 仅解释  
**规模/范围**：新增计划管控存储与预测服务，扩展共享模型、求解执行约束、API、前端类型/API/页面与测试

## Constitution 检查

- [x] 已完成需求评审并确认四个高影响口径。
- [x] `spec.md` 引用了产品蓝图、发布文档、022/026 规格和当前代码事实。
- [x] 已定义输入、输出、硬约束、软约束、目标顺序、无解和验收样例。
- [x] 已定义共享字段、页面入口、状态、错误、过期和兼容行为。
- [x] MVP 按基准确认、进度快照、滚动预测、调整采用分故事交付。
- [x] 复用现有模型、求解器、资源助手、API 和本地持久化方式，不新增依赖。

**设计后复核**：通过。新增 `ScheduleInput.execution_constraints` 是显式、向后兼容的共享字段；默认空列表，不改变现有求解行为。持久化范围明确为单机 Demo。

## 架构与数据流

```text
AI 三方案求解结果
  → 基准确认服务
  → PlanVersion + BaselineTaskSnapshot（持久化）
  → ProgressSnapshot（状态日期实绩）
  → 剩余任务网络构造
  → CP-SAT 当前趋势预测
  → 基准/实际/预测三态与风险
  → 三类调整策略独立求解
  → 用户采用
  → 新 PlanVersion + PlanChangeRecord
```

### 后端模块职责

- `models.py`：定义计划版本、进度快照、执行约束、预测和调整请求响应。
- `plan_control_repository.py`：负责 schema 版本、读取、原子写入、进程内锁、唯一活动版本和审计记录。
- `progress_forecast.py`：负责进度校验、剩余工期、剩余任务网络、三态合并、风险判断和三策略求解。
- `solver.py`：仅增加可选执行约束：任务最早/固定开始和固定资源；默认无约束时行为不变。
- `main.py`：增加计划管控 API，并将领域错误映射为 404、409、422、503。

### 前端模块职责

- `ResourceAssistantPanel.tsx` / `ResourcePlanCard.tsx`：可行求解结果附近提供“设为基准计划”。
- `PlanControlPanel.tsx`：独立“计划执行与进度”入口，承载版本摘要、状态日期、任务填报、预测风险和调整方案。
- `scheduler.ts` / `schedulerApi.ts`：同步共享契约和 API。
- `App.tsx`：增加导航入口，并在场景变化时清理当前页面临时态、重新加载持久化版本。

## 滚动预测设计

### 1. 剩余工期

- 已完成：剩余工期 0，不进入残余求解。
- 进行中：若 `remaining_quantity` 与 `actual_productivity` 有效，则 `ceil(remaining_quantity / actual_productivity)`；否则使用人工 `estimated_remaining_days`。
- 未开始：沿用基准任务工期。
- 暂停：必须有恢复日期或人工剩余工期；恢复日期转为最早开始约束。
- 取消：不进入残余求解，但对其后续依赖生成阻断诊断；MVP 不自动改写工艺链。

### 2. 残余任务网络

- 残余求解起点为 `status_date`。
- 已完成任务从求解网络移除，其实际日期保留在合并结果中。
- 已完成前置到剩余后续的逻辑转换为状态日期相对释放条件；若已满足则移除该边。
- 进行中任务保留原 ID，工期替换为剩余工期，固定在 offset 0 开始并优先固定原基准资源。
- 剩余任务间原逻辑关系、日历、资源候选和并行约束继续生效。

### 3. 当前趋势 `as_is`

- 保持基准资源池数量。
- 将基准结果中同一 `assigned_resource_id` 的未完成任务顺序转换为残余网络顺序约束。
- 已发生冲突只允许向后顺延，不允许自由重排产生“虚假改善”。
- 强制里程碑在当前趋势中作为比较目标，不作为可行性硬截止；先返回最早可行预测，再计算偏差。

### 4. 调整策略

- `add_bottleneck_resources`：从当前趋势诊断提取瓶颈资源，按用户允许的资源增量上限形成候选，保持其他资源不变并重新求解。
- `prioritize_critical_tasks`：资源数量不变，解除未开始任务的基准资源顺序约束，但保留工艺逻辑；提升关键线路和强制里程碑相关任务优先级。
- 三策略分别求解，任何一个失败不阻塞其他结果。

### 5. 风险与推荐

- `late`：项目或任一强制里程碑预测日期超过目标。
- `at_risk`：未迟延但剩余缓冲低于阈值，或存在高影响数据/资源风险。
- `on_track`：目标均满足且数据可信度达到可判断标准。
- `insufficient_data`：关键任务缺少剩余工期或快照质量不足。
- 推荐先满足强制里程碑，再比较完工日期；收益相近时优先少资源、低成本、低扰动。LLM 不参与结论计算。

## 项目结构

### 本功能文档

```text
specs/027-baseline-progress-forecast/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── plan-control-api.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构

```text
backend/app/
├── models.py
├── solver.py
├── main.py
└── services/
    ├── plan_control_repository.py
    └── progress_forecast.py

backend/tests/
├── test_plan_control_repository.py
├── test_progress_forecast.py
├── test_plan_control_api.py
└── test_scheduler.py

frontend/src/
├── app/App.tsx
├── api/schedulerApi.ts
├── types/scheduler.ts
└── features/
    ├── resourceAssistant/ResourceAssistantPanel.tsx
    ├── resourceAssistant/ResourcePlanCard.tsx
    └── planControl/PlanControlPanel.tsx
```

**结构决策**：新增两个聚焦领域模块是必要边界：存储与预测算法不能继续堆入已较大的资源助手服务。仍复用现有模型、求解器、API 客户端、页面组件和 `.local-data` 约定。

## 复杂度跟踪

| 事项 | 必要性 | 较简单替代方案不足 |
|---|---|---|
| 新增本地计划管控存储模块 | 需要跨刷新、跨重启、版本和审计 | 页面状态或单一配置 JSON 无法安全表达多版本和历史快照 |
| 新增可选执行约束 | 需要冻结进行中任务和原资源事实 | 仅修改工期不能保证任务在状态日期立即继续或保持原资源 |
| 新增独立计划管控页面 | 填报、预测、历史版本是持续业务流程 | 塞入三方案卡片会混淆方案比选与执行管控生命周期 |
