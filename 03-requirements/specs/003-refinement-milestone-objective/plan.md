# 实施计划：精排里程碑与工期目标函数调整

**分支/目录**：`003-refinement-milestone-objective` | **日期**：2026-07-04 | **规格**：[spec.md](spec.md)

**输入**：来自 `/specs/003-refinement-milestone-objective/spec.md` 的功能规格

## 概要

本功能调整精排阶段的里程碑和工期目标口径：硬里程碑在精排中作为硬约束，软控制节点迟延继续以最高权重压低，普通软里程碑迟延保留为诊断展示，总工期目标项只优化项目完工跨度。实现上复用现有排程模型、目标项 ID、结果字段和前端配置入口，不新增接口字段或持久化结构。

## 技术上下文

**语言/版本**：Python 3.x、TypeScript、React

**主要依赖**：OR-Tools CP-SAT、Pydantic、FastAPI、React、Vite

**存储**：不涉及数据库或持久化迁移

**测试**：`python -m pytest backend/tests/test_scheduler.py`、`npm --prefix frontend run build`、文档与字段静态搜索

**目标平台**：本地 FastAPI + React 主链路；Netlify 演示 API 不新增精排 CP-SAT 行为

**项目类型**：桥梁施工排程 Web 应用的后端算法、前端配置文案和算法文档变更

**性能目标**：不引入新的大规模变量维度；精排求解时间不应因本变更显著增加，测试场景应在现有测试预算内完成

**约束**：保留 `control_node_late` 与 `makespan_and_soft_milestone` 内部 ID；不新增接口字段；不改变固定资源快排的硬里程碑事后评价流程；实现前必须通过 Spec Kit analyze 并等待用户确认

**规模/范围**：影响 `backend/app/solver.py`、`backend/tests/test_scheduler.py`、`frontend/src/app/App.tsx`、`docs/精排目标函数算法需求文档_v3.1.md -> docs/精排目标函数算法需求文档_v3.2.md`、`docs/固定资源满足分支详细排程算法文档_v1.1.md -> docs/固定资源满足分支详细排程算法文档_v1.2.md`

## Constitution 检查

- 已完成需求评审，或已明确属于小范围变更无需评审。**PASS**：用户已明确给出实施计划并要求进入 Spec Kit。
- `spec.md` 已引用来源文档、Demo 事实和代码事实。**PASS**：规格列出目标函数文档、固定资源文档、项目手册和当前代码事实。
- 排程、资源、工期、CP-SAT、前后端契约影响已明确。**PASS**：本变更仅调整精排里程碑硬约束、控制迟延目标、总工期目标和前端文案。
- 输入、输出、约束、边界场景和验收标准可测试。**PASS**：规格包含硬里程碑可行/不可行、软控制节点、普通软里程碑和前端展示场景。
- 未经明确批准，不把 Demo 临时限制提升为正式产品目标。**PASS**：固定资源快排仍保留既有参考排程和事后评价口径。
- Spec Kit 过程文档和阶段报告使用中文简体；代码标识符、文件路径、接口名、任务编号和必要英文缩写可保持原文。**PASS**

## 项目结构

### 本功能文档

```text
specs/003-refinement-milestone-objective/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── refinement-objective-contract.md
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
    └── app/
        └── App.tsx

docs/
├── 精排目标函数算法需求文档_v3.1.md -> 精排目标函数算法需求文档_v3.2.md
└── 固定资源满足分支详细排程算法文档_v1.1.md -> 固定资源满足分支详细排程算法文档_v1.2.md
```

**结构决策**：复用现有求解器、测试文件、前端目标配置数组和算法文档，不新增服务层、路由、类型文件或数据迁移。

## 复杂度跟踪

无 Constitution 违反项。
