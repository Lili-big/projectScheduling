# 实现计划：精排失败最佳努力方案

**分支**：`005-best-effort-refinement` | **日期**：2026-07-04 | **规格**：`specs/005-best-effort-refinement/spec.md`

**输入**：用户确认当严格精排失败时，放松强制节点和固定工期目标，在当前资源和当前求解时间内返回最合理的精排计划。

## 概述

在现有固定资源和最少资源候选链路中保留“严格精排优先”。当严格命名资源精排没有可用结果时，新增一次目标放松的命名资源精排尝试：只把强制里程碑和固定工期从硬约束转为高优先级软目标，继续遵守工序、资源、同结构同工序、工作面等硬约束。若放松后得到 `OPTIMAL` 或 `FEASIBLE`，返回最佳努力精排来源和完整目标迟延诊断；若仍无可用结果，保留现有回退。

## 技术上下文

**语言/版本**：Python 3.x、TypeScript/React

**主要依赖**：FastAPI、OR-Tools CP-SAT、Pydantic、React、Vite

**存储**：无数据库迁移；结果字段通过既有 API payload 返回

**测试**：`pytest` 后端测试；`npm.cmd --prefix frontend run build` 前端构建；必要时通过本地 Vite/后端联调复核

**目标平台**：本地 FastAPI 后端和 React 前端；Docker 后端沿用 Python 主链路

**项目类型**：Web 应用，后端排程算法 + 前端模拟求解页面

**性能约束**：最佳努力分支只在严格精排失败后触发；单次最佳努力尝试使用当前请求的 `time_limit_seconds`，不得无上限重复求解；总响应时间可能包含严格尝试和最佳努力尝试两段耗时，必须输出或记录诊断

**约束**：不得放松施工逻辑、任务持续时间、资源互斥、资源池启用数量、同结构同工序资源绑定和工作面并行上限

**规模/范围**：P1 覆盖固定资源当前资源链路；P2 覆盖最少资源候选二次精排；首期不覆盖资源成本优化和 Netlify 演示 API

## 宪法检查

- **Requirements First**：已在 `spec.md` 明确业务目标、用户、范围、假设和验收标准，通过。
- **Explicit Algorithm Specifications**：已明确输入、输出、硬约束、软目标、优先级和异常处理，通过。
- **Explicit Frontend-Backend Contracts**：已规划 `stats`/`objective_breakdown` 元数据和前端来源标签，通过。
- **Reuse Existing Docs and Code**：复用 `solve_control_priority_schedule()`、固定资源链路、候选精排链路和现有结果来源模式，通过。
- **Phased Delivery**：P1 当前资源链路，P2 最少资源候选，P3/后续不纳入首期，通过。
- **Spec Kit Gate Before Implementation**：当前仅生成规格、计划、任务和分析，等待用户确认后再实现，通过。
- **Completion Report and Verification**：任务中要求后端测试、前端构建和验证说明，通过。

## 项目结构

### 文档

```text
specs/005-best-effort-refinement/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── schedule-result-best-effort.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 预计实现触点

```text
backend/app/scenario.py
backend/app/solver.py
backend/app/models.py
backend/tests/
frontend/src/app/App.tsx
frontend/src/types/
docs/固定资源满足分支详细排程算法文档_v*.md
docs/精排目标函数算法需求文档_v*.md
```

## 复杂度跟踪

| 风险 | 为什么需要 | 更简单方案为什么不足 |
| --- | --- | --- |
| 严格失败后增加第二次 CP-SAT 尝试 | 用户需要当前资源下最合理的命名资源精排版本 | 只返回容量快排会丢失命名资源精排目标和同结构同工序控制 |
| 新增最佳努力来源和元数据 | 页面必须区分严格满足与目标放松 | 复用既有回退来源会让用户误以为仍是容量参考或严格精排 |
| 最少资源候选作为 P2 | 与固定资源链路共享同类二次精排失败问题 | 首期只做当前资源会解决截图问题，但候选推荐仍可能解释不完整 |

## 阶段策略

1. **P1**：固定资源当前资源链路。严格精排失败后运行最佳努力精排，返回 `current_resources_best_effort_refinement`。
2. **P2**：最少资源候选二次精排。候选数量不变，严格失败后返回 `minimum_resources_best_effort_refinement`。
3. **展示与文档**：前端新增最佳努力标签和诊断；算法文档同步说明目标放松分支和验收口径。
