# 实施计划：普通工程差异化均衡目标

**分支/目录**：`004-normal-work-balance` | **日期**：2026-07-04 | **规格**：[spec.md](./spec.md)

**输入**：来自 `/specs/004-normal-work-balance/spec.md` 的功能规格

## 概要

本变更将普通工程均衡从“全部普通工程仅诊断”调整为“差异化目标”：已配置受限资源的普通工程继续由资源空闲、资源路径连续性和同类资源工作量均衡优化；未配置受限资源、按默认充足处理的普通工程进入低优先级时间均衡目标，避免短时间集中施工。同步更新目标拆解、诊断和精排目标函数算法文档。

## 技术上下文

**语言/版本**：Python、TypeScript

**主要依赖**：FastAPI、React、OR-Tools CP-SAT、Pydantic

**存储**：不涉及数据库或持久化迁移

**测试**：`pytest backend/tests/test_scheduler.py`，前端构建 `npm.cmd --prefix frontend run build`

**目标平台**：本地 FastAPI/React 主链路；Netlify 演示 API 保持兼容但不实现 CP-SAT 精排 parity

**项目类型**：Web 应用 + 后端 CP-SAT 排程服务 + 算法文档

**性能目标**：普通工程均衡目标不得显著扩大求解规模；新增测试场景应在现有 scheduler 测试预算内完成

**约束**：不新增前端可配置目标项 ID；不恢复废弃 `normal_balance` 输入；不降低控制节点、控制缓冲、资源连续施工和总工期目标优先级

**规模/范围**：影响 `backend/app/solver.py`、`backend/app/models.py`（如需目标拆解字段/默认权重调整）、`backend/tests/test_scheduler.py`、`frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx`（如需解析新诊断）、`docs/精排目标函数算法需求文档_v3.8.md`，并视需要同步 `docs/固定资源满足分支详细排程算法文档_v1.5.md`

## Constitution 检查

- 已完成需求评审，或已明确属于小范围变更无需评审。**PASS**：用户直接给出明确算法口径并要求实现；本计划记录来源事实和边界。
- `spec.md` 已引用来源文档、Demo 事实和代码事实。**PASS**
- 排程、资源、工期、CP-SAT、前后端契约影响已明确。**PASS**
- 输入、输出、约束、边界场景和验收标准可测试。**PASS**
- 未经明确批准，不把 Demo 临时限制提升为正式产品目标。**PASS**
- Spec Kit 过程文档和阶段报告使用中文简体。**PASS**

## 项目结构

### 本功能文档

```text
specs/004-normal-work-balance/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── normal-work-balance-contract.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── models.py
│   └── solver.py
└── tests/
    └── test_scheduler.py

frontend/
└── src/
    ├── app/App.tsx
    └── types/scheduler.ts

docs/
├── 精排目标函数算法需求文档_v3.8.md
└── 固定资源满足分支详细排程算法文档_v1.5.md
```

**结构决策**：核心目标函数在 `backend/app/solver.py` 实现；模型字段若仅在 `objective_breakdown` 和 `stats` 中扩展，可保持字典兼容；前端仅在展示已有诊断区域需要解析新字段时调整；算法文档按版本新建，保持文件名和头部版本一致。

## 复杂度跟踪

无 Constitution 违反项。
