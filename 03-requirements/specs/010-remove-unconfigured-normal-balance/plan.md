# 实施计划：移除未配置资源普通工程均衡目标

**分支/目录**：`010-remove-unconfigured-normal-balance` | **日期**：2026-07-06 | **规格**：`specs/010-remove-unconfigured-normal-balance/spec.md`

**输入**：来自 `specs/010-remove-unconfigured-normal-balance/spec.md` 的功能规格。

## 概要

本变更从目标函数体系中移除 `unconfigured_normal_balance`，使“未配置资源普通工程均衡”不再作为可配置指标、默认权重、CP-SAT 目标项或结果贡献展示。`normal_balance_metrics` 继续保留为普通工程分布诊断。

## 技术上下文

**语言/版本**：Python、TypeScript、React。

**主要依赖**：FastAPI/Pydantic 数据模型、OR-Tools CP-SAT 求解器、React 前端。

**存储**：不涉及持久化迁移；影响内存模型、本地场景配置解析和 API 结果。

**测试**：`pytest` 后端测试、前端 TypeScript/构建验证。

**目标平台**：本地 FastAPI 后端和 Vite/React 前端。

**项目类型**：桥梁施工排程 Web Demo，涉及后端求解和前端配置展示。

**性能目标**：移除一个目标项后不得增加模型规模；未配置普通工程诊断应基于结果统计，不额外增加 CP-SAT 决策变量。

**约束**：
- 不恢复 009 已废弃的 `resource_workload_balance`。
- 不改变硬约束、普通工程时间窗口和工作面并行约束。
- 不删除 `normal_balance_metrics` 诊断。
- 不修改 `README.md`。
- 实现前必须等待用户确认 `tasks.md` 和分析结论。

**规模/范围**：影响 `backend/app/models.py`、`backend/app/solver.py`、`backend/tests/test_scheduler.py`、`frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx`，可选更新目标函数算法文档。

## Constitution 检查

- 已完成需求定位：用户明确要移除“未配置资源普通工程均衡”目标项。
- `spec.md` 已引用来源文档、Demo 行为和代码事实。
- 排程、资源、CP-SAT、前后端契约影响已明确。
- 输入、输出、边界场景和验收标准可测试。
- 未把 Demo 临时限制提升为正式产品目标。
- Spec Kit 文档使用中文简体，代码标识符保留原文。

## 项目结构

### 本功能文档

```text
specs/010-remove-unconfigured-normal-balance/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── objective-term-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构

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
└── 精排目标函数算法需求文档_v4.0.md
```

**结构决策**：复用现有模型、求解器和前端目标项定义，不新增目录、依赖或服务层。

## 复杂度跟踪

| 违反项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|--------------------------|
| 无 | 不适用 | 不适用 |
