# 实施计划：AI 固定资源排程结果稳定化

**分支/目录**：`038-ai-solve-stability` | **日期**：2026-07-14 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/038-ai-solve-stability/spec.md` 的功能规格

## 概要

在不改变 AI 单方案 15 秒时限、固定资源数量、硬约束和“最大目标延期优先、总工期其次”目标的前提下，解决同一输入重复求解工期大幅退化的问题。实现分为两层：首先只对能力、日历和任务候选集合完全一致的命名资源增加安全的对称性消除；其次让单方案请求可选携带同输入上一版结果，作为求解提示，并在本轮结束后按现有字典序目标选择新旧较优结果。输入指纹不一致时完全忽略旧结果。页面保留求解中的旧结果快照，并展示是否使用旧排程、是否保留旧结果及原因。

## 技术上下文

**语言/版本**：Python 3.11、TypeScript、Node.js（沿用当前仓库）

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React；不新增依赖

**存储**：不新增持久化；上一版结果仅由当前页面会话持有并随请求传递

**测试**：pytest 后端单元/集成测试、真实 Excel 重复求解脚本、前端 TypeScript 与生产构建

**目标平台**：本地 FastAPI 单服务 Demo 与现有 React 页面；Netlify 演示 API 不承载当前 Python CP-SAT 求解，不修改

**项目类型**：Web 应用，涉及后端排程模型、服务编排、共享请求字段和 AI 多方案比选页面

**性能目标**：单方案配置时限保持 15 秒；真实 351 任务平衡方案首次重复样例的最大工期差不超过 30 天；同输入已有结果后的用户可见结果退化次数为 0

**约束**：一次改进请求最多一次 CP-SAT 调用；不恢复第二阶段；不改目标函数、线程数、资源数量、自动增配、里程碑和非 AI 求解入口；旧结果只在指纹一致且自身可行时参与

**规模/范围**：修改 `backend/app/models.py`、`backend/app/solver.py`、`backend/app/scenario.py`、AI 资源助手服务及测试；同步前端类型、API 请求、面板状态和结果说明；更新 AI 验证文档

## Constitution 检查

*门禁：Phase 0 研究前和 Phase 1 设计后均通过。*

- 已以真实 Excel、同输入重复求解和线程对照完成需求发现，不把截图推测直接转为算法修改。
- `spec.md` 已引用来源文档、既有规格、Demo 事实和当前代码事实。
- 输入、输出、硬约束、目标优先级、15 秒边界、接口兼容、失效条件和验收样例均已明确。
- 方案复用现有 `input_fingerprint`、`warm_start_result`、单阶段编排、页面结果状态和测试结构，不新增依赖或持久化模块。
- 本计划只稳定当前业务目标下的限时结果，不把 Demo 的 351 任务规模或 30 天样例阈值提升为所有项目的长期产品上限。
- 所有 Spec Kit 产物使用中文简体，代码标识符和文件路径保留原文。

## Phase 0 研究结论

详见 [research.md](./research.md)。核心结论：单线程可降低部分随机性但会显著恶化 15 秒解质量；仅缓存结果不能改善首次求解；采用“可互换资源对称性消除 + 同输入旧结果 warm start + 新旧结果不退化选择”能同时覆盖首次质量和重复稳定性。

## Phase 1 设计

### 1. 求解输入与复用门禁

- `ResourceAssistantSingleSolveRequest` 增加可选 `previous_plan_result`，历史请求不传该字段时行为不变。
- 前端在清除当前方案结果前先保存同方案旧结果，并随本次请求传递。
- 后端重新计算当前 `_plan_input_fingerprint(scenario, plan)`，只有与 `previous_plan_result.input_fingerprint` 完全一致，且旧 `ScheduleResult.status` 为 `OPTIMAL/FEASIBLE`、任务集合完整时才可复用。
- 指纹不一致、旧结果不可行、任务集合不完整或解析失败时忽略旧结果，并在稳定性诊断中记录原因。

### 2. 可互换资源对称性消除

- 在命名资源分配模型完成后，按资源业务属性、日历/可用性、并行规则和候选任务集合计算可互换签名。
- 仅当同组至少两台资源完全一致时，对其承担任务数建立稳定的非增顺序，消除仅由资源编号置换产生的等价解。
- 不合并资源、不减少数量、不固定具体任务到具体编号；连续梁专用资源或未进入通用 assignment 变量的资源保持原逻辑。
- 返回可互换组数和新增对称约束数用于测试审计。

### 3. 同输入改进求解与结果选择

- 将通过门禁的旧 `ScheduleResult` 传入现有 `warm_start_result`，复用任务开始、结束和命名资源分配提示。
- 仍只执行当前 `primary` 一次求解，时限保持 15 秒、8 线程、固定随机种子和现有目标表达式。
- 对旧结果和本轮候选分别计算比较键：`(max_target_delay_days, objective_days)`；不可行或缺少任务的结果排序在任何可行结果之后。
- 当前候选严格更优或相等时采用当前候选；当前候选更差、无排程或失败时采用旧结果。
- 旧结果为同输入 `OPTIMAL` 时可直接保留并跳过无收益的重复求解；诊断记录 `previous_optimal_reused`，CP-SAT 调用数为 0。
- 最终结果写入 `stability_selection` 诊断，包含旧结果是否有效、warm start 是否使用、本轮候选状态和指标、最终来源、选择原因、求解调用次数、对称性统计和原始最优界。

### 4. 页面状态与解释

- `handleSolvePlan` 不再在发请求前永久丢弃同方案旧结果；请求期间方案卡显示求解中，旧结果仅作为内部候选，不参与新推荐。
- 请求成功后仅用后端最终选择结果替换旧结果；失败时恢复原结果并显示请求失败，避免页面空白或退化。
- 方案详情增加简短稳定性说明：首次求解、使用上次排程继续优化、新结果改善、保留上次较优结果、旧结果因输入变化被忽略。
- 比较、推荐、基准计划和进度反馈只读取最终保留结果，既有门禁不变。

### 5. 兼容与异常

- 新请求字段可选，后端响应模型不新增强类型顶层字段；稳定性事实放入现有 `ScheduleResult.stats`，历史结果缺少该字段时按首次求解展示。
- 批量求解不携带页面旧结果，继续按首次求解处理；后续如需批量改进另行评审。
- 若本轮求解抛出服务级异常，接口沿用失败响应；前端恢复旧结果。若求解器正常返回 `UNKNOWN/INFEASIBLE` 且旧结果有效，接口成功返回旧结果及本轮诊断。

## 项目结构

### 本功能文档

```text
specs/038-ai-solve-stability/
├── discovery.md
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── ai-resource-single-solve.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── models.py
│   ├── scenario.py
│   ├── solver.py
│   └── services/
│       └── ai_resource_scheduling_assistant.py
└── tests/
    ├── test_ai_resource_scheduling_assistant.py
    └── test_scheduler.py

frontend/src/
├── api/schedulerApi.ts
├── domain/resourceAssistant.ts
├── features/resourceAssistant/
│   ├── ResourceAssistantPanel.tsx
│   └── ResourcePlanCard.tsx
└── types/scheduler.ts

docs/
└── AI资源配置与排程优化助手验证说明.md
```

**结构决策**：在现有求解器、AI 严格固定资源编排和页面组件内增量实现；不创建新服务、不引入缓存基础设施、不修改 Netlify 镜像入口。

## 复杂度跟踪

无 Constitution 违反项。

## Phase 1 后 Constitution 复核

- 共享字段仅新增向后兼容的可选请求字段，前后端类型和契约已同步设计。
- 可互换资源规则有严格签名门禁，不改变业务可行域；新旧结果选择复用现有目标优先级。
- 真实 Excel、边界、错误、指纹失效、历史兼容和非 AI 回归均有可执行验证路径。
- 设计未引入新依赖、持久化或额外求解阶段，通过门禁。
