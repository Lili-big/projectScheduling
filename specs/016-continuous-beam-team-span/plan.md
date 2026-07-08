# 实施计划：现浇连续梁联级班组占用

**分支/目录**：`016-continuous-beam-team-span` | **日期**：2026-07-08 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/016-continuous-beam-team-span/spec.md` 的功能规格。

## 概要

本功能将现浇连续梁班组从“任务级互斥资源”调整为“联级占用资源”。连续梁任务仍保持原有任务粒度和工艺约束；系统按 `bridge_id + work_section_id + group_index` 识别连续梁联，给每个联建立班组归属和占用窗口，用连续梁班组数量控制跨联并行能力。结果侧需要能解释每个连续梁任务所属联、联级占用起止和班组归属。

## 技术上下文

**语言/版本**：Python 3.11、TypeScript、Node.js。

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React、Vite、pytest。

**存储**：不新增持久化存储；继续使用现有 `ScenarioInput`、本地配置和前端状态。

**测试**：`python -m pytest backend/tests/test_scheduler.py`；必要时补充 `npm.cmd run build` 验证前端类型和展示兼容。

**目标平台**：本地 Python 后端、React 前端；Netlify 演示 API 是否同步在实现阶段按实际逻辑覆盖判断。

**项目类型**：桥梁施工排程 Web 应用，涉及后端求解器、共享模型、前端类型和结果展示。

**性能目标**：新增联级占用约束不得使典型连续梁场景求解不可接受地退化；同类测试场景应在现有测试时限内完成。

**约束**：
- 不改变连续梁任务拆分粒度。
- 不放松工艺前后置、下部结构、左右悬臂同步、合龙完成间隔、里程碑等既有约束。
- 不改变非连续梁任务的命名资源互斥和桩基墩组两阶段精排规则。
- 不新增外部依赖。
- 未经用户确认 `tasks.md` 与 `$speckit-analyze` 结果前不进入实现。

**规模/范围**：
- 后端：`backend/app/models.py`、`backend/app/scenario.py`、`backend/app/solver.py`、`backend/tests/test_scheduler.py`。
- 前端：`frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx` 中与资源分配、任务详情或诊断展示相关的兼容逻辑。
- 文档与验证：本规格目录下的设计产物和 quickstart。

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- [x] 已明确属于用户确认的算法与资源规则调整，进入 Spec Kit。
- [x] `spec.md` 已引用来源文档、Demo 事实和代码事实。
- [x] 排程、资源、CP-SAT、前后端契约影响已明确。
- [x] 输入、输出、约束、边界场景和验收标准可测试。
- [x] 未把 Demo 临时限制提升为额外产品目标。
- [x] Spec Kit 过程文档使用中文简体；代码标识符和文件路径保留原文。

## 项目结构

### 本功能文档

```text
specs/016-continuous-beam-team-span/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── continuous-beam-team-span-contract.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── models.py
│   ├── scenario.py
│   └── solver.py
└── tests/
    └── test_scheduler.py

frontend/
└── src/
    ├── app/
    │   └── App.tsx
    └── types/
        └── scheduler.ts

netlify/
└── functions/
    └── api.mts
```

**结构决策**：优先在现有模型和求解器中增加连续梁联级资源语义，不新建独立服务或新依赖。若 Netlify 演示 API 存在同类连续梁求解逻辑，任务阶段单独列出检查项。

## 复杂度跟踪

| 违反项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|--------------------------|
| 新增联级资源占用层 | 当前任务级资源互斥无法表达“联内不互斥、跨联互斥” | 仅调整资源数量或 `same_structure_resource_binding` 会继续限制联内任务并行 |

## Phase 0：研究结论

见 [research.md](./research.md)。

## Phase 1：设计产物

- [data-model.md](./data-model.md)
- [contracts/continuous-beam-team-span-contract.md](./contracts/continuous-beam-team-span-contract.md)
- [quickstart.md](./quickstart.md)

## Phase 1 后 Constitution 复核

- [x] 算法输入、输出、硬约束、边界和验收样例已在设计产物中展开。
- [x] 前后端共享字段和兼容要求已在契约中说明。
- [x] 任务粒度、联级占用、跨联互斥、联内不互斥的边界没有冲突。
- [x] 未引入无关重构或新依赖。
