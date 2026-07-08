# 实现计划：精排失败最佳努力方案

**分支**：`005-best-effort-refinement` | **日期**：2026-07-04 | **规格**：`specs/005-best-effort-refinement/spec.md`

**输入**：用户确认当严格精排失败时，放松强制节点和固定工期目标，在当前资源和当前求解时间内返回最合理的精排计划。

## 概述

当前实现已经由后续规格调整：固定资源当前资源链路不再先跑容量快排，也不再在失败后返回 `current_resources_best_effort_refinement`；它直接运行目标函数排程，并用 `current_resources_control_priority_balanced`、`current_resources_target_failed`、`target_unconfirmed`、`physical_infeasible` 表达目标达成状态。005 计划中仍然有效的部分，是最少资源候选复排在目标未达成但有可用结果时返回 `minimum_resources_best_effort_refinement`，并保留目标放松诊断。

## 技术上下文

**语言/版本**：Python 3.x、TypeScript/React

**主要依赖**：FastAPI、OR-Tools CP-SAT、Pydantic、React、Vite

**存储**：无数据库迁移；结果字段通过既有 API payload 返回

**测试**：`pytest` 后端测试；`npm.cmd --prefix frontend run build` 前端构建；必要时通过本地 Vite/后端联调复核

**目标平台**：本地 FastAPI 后端和 React 前端；Docker 后端沿用 Python 主链路

**项目类型**：Web 应用，后端排程算法 + 前端模拟求解页面

**性能约束**：最佳努力分支只在严格精排失败后触发；单次最佳努力尝试使用当前请求的 `time_limit_seconds`，不得无上限重复求解；总响应时间可能包含严格尝试和最佳努力尝试两段耗时，必须输出或记录诊断

**约束**：不得放松施工逻辑、任务持续时间、资源互斥、资源池启用数量、同结构同工序资源绑定和工作面并行上限

**规模/范围**：固定资源当前资源链路已由 `018-unified-target-solve` 接管；本规格当前有效范围覆盖最少资源候选二次复排；不覆盖资源成本优化和 Netlify 演示 API

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
| 当前资源最佳努力分支历史遗留 | 后续统一目标达成口径已经替代该分支 | 继续把旧分支写作当前行为会误导测试和前端解释 |
| 最少资源候选保留最佳努力来源和元数据 | 页面必须区分候选目标达成与目标放松 | 复用既有回退来源会让用户误以为仍是容量参考或严格精排 |
| 最少资源候选作为 P2 | 与固定资源链路共享同类二次精排失败问题 | 首期只做当前资源会解决截图问题，但候选推荐仍可能解释不完整 |

## 阶段策略

1. **历史 P1（已替代）**：固定资源当前资源链路不再返回 `current_resources_best_effort_refinement`，而是按 `018` 的目标达成口径返回当前资源成功、目标未满足、未确认或物理不可行。
2. **当前有效 P2**：最少资源候选二次精排。候选数量不变，严格复排目标未达成但有可用结果时返回 `minimum_resources_best_effort_refinement`。
3. **展示与文档**：前端兼容历史最佳努力来源；当前展示应以“当前资源目标未满足”和“最少资源候选目标未满足”为主口径。
