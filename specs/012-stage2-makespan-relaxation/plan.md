# 实施计划：放宽第二阶段工期上限

**分支/目录**：`012-stage2-makespan-relaxation` | **日期**：2026-07-07 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/012-stage2-makespan-relaxation/spec.md` 的功能规格

## 概要

本功能将第二阶段路径精排中的“总工期不得超过第一阶段总工期”从硬门槛中移除。第一阶段总工期 `M1` 继续作为诊断基准，第二阶段总工期 `M2` 继续进入现有总工期目标；系统不新增线性的 `M2 - M1` 求解目标，避免总工期被双重计分。硬里程碑、资源互斥、工艺前后置、固定资源分配和未放松的真实固定工期上限保持不变。

## 技术上下文

**语言/版本**：Python 后端、TypeScript 前端；沿用当前仓库运行环境。

**主要依赖**：OR-Tools CP-SAT、FastAPI/本地后端、React/Vite 前端；不新增依赖。

**存储**：不涉及持久化变更；仅调整求解结果诊断 payload。

**测试**：以后端 `backend/tests/test_scheduler.py` 为主；如前端类型字段变更，补充前端构建或类型兼容验证。

**目标平台**：本地桥梁施工排程 Demo 后端和当前前端页面。

**项目类型**：后端排程算法小范围约束调整，附带结果契约兼容。

**性能目标**：不扩大第二阶段路径建模规模；移除 `M2 <= M1` 后不应增加变量规模，只放宽可行域。

**约束**：不得放松硬里程碑；不得新增 `M2 - M1` 求解目标；不得改变第一阶段资源分配；不得改变最终任务粒度。

**规模/范围**：主要影响 `backend/app/solver.py`、`backend/tests/test_scheduler.py`，可选影响 `frontend/src/types/scheduler.ts`。

## Constitution 检查

- 已完成需求评审：用户在连续评审中确认移除第二阶段相对第一阶段总工期的限制。
- `spec.md` 已引用来源文档、当前 Demo/代码事实和不在范围内事项。
- 排程、资源、工期、CP-SAT、前后端契约影响已明确。
- 输入、输出、约束、边界场景和验收标准可测试。
- 未把 Demo 临时限制提升为正式产品目标；本次正是移除该临时门槛。
- Spec Kit 文档使用中文简体，代码标识符和路径保留原文。

## 项目结构

### 本功能文档

```text
specs/012-stage2-makespan-relaxation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── stage2-makespan-relaxation-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   └── solver.py
└── tests/
    └── test_scheduler.py

frontend/
└── src/
    └── types/
        └── scheduler.ts
```

**结构决策**：本功能复用现有两阶段精排入口和诊断结构，不新增模块；若需要前端识别相对工期差值，只在现有可选类型中补充字段。

## 复杂度跟踪

| 违反项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|--------------------------|
| 无 | 不适用 | 不适用 |
