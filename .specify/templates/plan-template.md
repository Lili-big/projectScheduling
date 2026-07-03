# 实施计划：[功能]

**分支/目录**：`[###-feature-name]` | **日期**：[DATE] | **规格**：[link]

**输入**：来自 `/specs/[###-feature-name]/spec.md` 的功能规格

**说明**：本模板由 `/speckit-plan` 填写。执行流程以 `.specify/templates/plan-template.md` 和 `.agents/skills/speckit-plan/SKILL.md` 为准。

## 概要

[从功能规格中提取核心需求，并概述技术处理方向]

## 技术上下文

<!--
  请用当前项目真实情况替换本节占位内容。未知项标为“需澄清”，不要凭空补规则。
-->

**语言/版本**：[例如 Python 3.11、TypeScript、Node.js，或“需澄清”]

**主要依赖**：[例如 FastAPI、React、OR-Tools，或“需澄清”]

**存储**：[如适用，例如 PostgreSQL、文件、本地配置，或“不适用”]

**测试**：[例如 pytest、前端构建、接口验证，或“需澄清”]

**目标平台**：[例如本地 FastAPI 服务、Netlify 前端、Docker 后端，或“需澄清”]

**项目类型**：[例如 Web 应用、后端服务、前端页面、文档变更，或“需澄清”]

**性能目标**：[领域相关目标，例如求解耗时、批量处理规模，或“需澄清”]

**约束**：[领域约束，例如不改变 CP-SAT 目标、不持久化原文件，或“需澄清”]

**规模/范围**：[领域范围，例如影响页签、接口、模型、测试数量，或“需澄清”]

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- 已完成需求评审，或已明确属于小范围变更无需评审。
- `spec.md` 已引用来源文档、Demo 事实和代码事实。
- 排程、资源、工期、CP-SAT、前后端契约影响已明确。
- 输入、输出、约束、边界场景和验收标准可测试。
- 未经明确批准，不把 Demo 临时限制提升为正式产品目标。
- Spec Kit 过程文档和阶段报告使用中文简体；代码标识符、文件路径、接口名、任务编号和必要英文缩写可保持原文。

## 项目结构

### 本功能文档

```text
specs/[###-feature]/
├── plan.md              # 本文件（/speckit-plan 输出）
├── research.md          # Phase 0 输出
├── data-model.md        # Phase 1 输出
├── quickstart.md        # Phase 1 输出
├── contracts/           # Phase 1 输出
└── tasks.md             # Phase 2 输出（由 /speckit-tasks 创建）
```

### 源码结构（仓库根目录）

<!--
  用本功能真实涉及的目录替换下方示例；删除未使用路径，不保留“选项”标签。
-->

```text
backend/
├── app/
│   ├── models.py
│   ├── scenario.py
│   ├── solver.py
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── app/
│   ├── api/
│   ├── domain/
│   ├── features/
│   └── components/

netlify/
└── functions/

docs/
└── [需求、PRD、评审和算法文档]
```

**结构决策**：[说明选择的真实结构，并引用上方具体目录]

## 复杂度跟踪

> 仅当 Constitution 检查存在必须解释的违反项时填写。

| 违反项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|--------------------------|
| [例如新增第 4 个模块] | [当前需要] | [为什么现有模块不足] |
