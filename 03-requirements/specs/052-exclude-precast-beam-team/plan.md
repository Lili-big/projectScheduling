# 实施计划：工点资源排除预制梁班组

**分支/目录**：`052-exclude-precast-beam-team` | **日期**：2026-07-20 | **规格**：[spec.md](./spec.md)

## 概要

在 050 已建立的统一资源目录排除集合中加入 `precast_beam_team`。由于目录投影和工点结构匹配已共同使用该集合，一处规则即可同时移除自动建议和补充目录；保留预制梁工艺、类型映射和中文兼容名称，避免改变任务生成、求解器及历史显式输入读取。

## 技术上下文

**语言/版本**：TypeScript 5.7、Node.js

**主要依赖**：现有 React 19、Vite 6；无新增依赖

**存储**：不适用；不删除或迁移历史资源数据

**测试**：Node `node:test` 定向领域测试、TypeScript 类型检查、Vite 生产构建、`validate_docs.py`

**目标平台**：现有 React/Vite Demo

**项目类型**：前端资源目录规则小范围变更

**性能目标**：不增加请求、遍历或持久化开销

**约束**：只排除 `precast_beam_team`；保留 `beam_erection_team` 和其他资源；不改梁场、任务和求解器

**规模/范围**：1 个领域常量文件、1 个邻近测试文件和本规格资产

## 生命周期归属

- **规格归属引用**：[`spec.md#生命周期归属`](./spec.md#生命周期归属)
- **实施路径**：`04-demo/frontend/src/domain/constants.ts`、`04-demo/frontend/tests/resourceWorkpointScope.test.mjs`

## Constitution 检查

*Phase 0 前检查：通过；Phase 1 设计后复核：通过。*

- 用户已明确业务边界，规格包含来源、范围和可观察验收。
- 资源影响只限 UI 目录投影；任务、工期、候选和求解器保持不变。
- 输入为统一排除集合，输出为自动建议及补充目录不含该类型，规则可用纯领域测试复现。
- 不引入 Demo 临时业务规则，不删除用户数据，不新增资产迁移。
- 规格具有唯一生命周期归属，本计划只引用 050 和梁场业务边界。

## 项目结构

```text
03-requirements/specs/052-exclude-precast-beam-team/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── resource-exclusion-ui-contract.md
└── tasks.md

04-demo/frontend/
├── src/domain/constants.ts
└── tests/resourceWorkpointScope.test.mjs
```

**结构决策**：复用 050 的 `excludedResourceCatalogTypes`，不在页面增加第二层过滤，不修改 `ResourcesTab.tsx`、API、后端或求解器。

## 设计阶段

- [research.md](./research.md)：确认统一排除集合是自动建议和完整目录的共同权威入口。
- [data-model.md](./data-model.md)：记录排除集合新增值及兼容边界，无持久化模型变化。
- [resource-exclusion-ui-contract.md](./contracts/resource-exclusion-ui-contract.md)：定义可见性、不回退和保留行为。
- [quickstart.md](./quickstart.md)：提供预制梁与其他结构资源的定向验证。

## 复杂度跟踪

无 Constitution 违反项。
