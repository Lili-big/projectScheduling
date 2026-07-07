# 实施计划：第二阶段可见墩距路径剪枝

**目录**：`specs/013-stage2-visible-distance-pruning`  
**日期**：2026-07-07  
**规格**：[spec.md](./spec.md)

## 概要

将第二阶段机械钻路径候选弧从“绝对墩号差统一不超过 2”调整为“同幅可见墩距不超过 2、跨幅可见墩距不超过 1”。可见墩距基于当前资源路径候选节点集合计算，避免中间墩没有任务时误剪边。

## 技术上下文

- **主要文件**：`backend/app/solver.py`、`backend/tests/test_scheduler.py`
- **依赖**：沿用 OR-Tools CP-SAT 与现有测试框架，不新增依赖。
- **约束**：不修改第一阶段资源分配、不修改罚分函数、不修改前端。
- **验证**：运行聚焦的后端测试，再运行 `backend/tests/test_scheduler.py` 全量回归。

## Constitution 检查

- 涉及排程算法剪枝规则，已按 Spec Kit 建立规格、计划、任务和验收。
- 输入对象、输出诊断、硬/软边界和可复现场景已在 `spec.md` 中定义。
- 代码变更范围限定在后端路径候选弧与测试，不扩大需求。

## 项目结构

```text
backend/
├── app/
│   └── solver.py
└── tests/
    └── test_scheduler.py

specs/013-stage2-visible-distance-pruning/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── stage2-visible-distance-pruning-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

## 复杂度跟踪

| 项目 | 结论 |
| --- | --- |
| 新依赖 | 无 |
| 新接口 | 无 |
| 数据迁移 | 无 |
| 风险 | 候选弧数量变化会影响第二阶段求解路径选择，需要回归测试确认 |
