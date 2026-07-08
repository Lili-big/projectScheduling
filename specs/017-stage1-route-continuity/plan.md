# 实施计划：第一阶段钻机组路径连续性优化

**分支/目录**：`017-stage1-route-continuity` | **日期**：2026-07-08 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/017-stage1-route-continuity/spec.md` 的功能规格。

## 概要

本功能将机械钻机组第一阶段粗排从“轻量相邻换机/洞洞跳墩惩罚”升级为“粗粒度空间路径选择”。在 `resource_path_continuity` 开启时，第一阶段为每台机械钻资源在钻机组节点之间构建受限候选路径：同幅按可施工序列距离 `<= 2`，跨幅按真实墩号差 `<= 1`。相邻可施工节点不罚分，跳过一个可施工节点罚 1，允许跨幅切换罚 1；超出窗口的远距离转移不生成兜底弧。

## 技术上下文

**语言/版本**：Python 3.11、TypeScript、Node.js。

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React、Vite、pytest。

**存储**：不新增持久化存储；继续使用现有 `ScenarioInput`、`ScheduleInput`、`ScheduleResult` 和前端状态。

**测试**：`python -m pytest backend/tests/test_scheduler.py`；如前端诊断字段展示或类型变更，补充 `npm.cmd run build`。

**目标平台**：本地 Python 后端与 React 前端；Netlify 演示 API 如存在同类求解逻辑需在任务中检查。

**项目类型**：桥梁施工排程 Web 应用，涉及后端 CP-SAT 求解器、结果诊断、测试和可能的前端诊断展示。

**性能目标**：第一阶段路径候选弧数量应低于全候选路径连接；新增样例和现有 scheduler 回归应在项目既有测试时限内完成。

**约束**：
- 不新增前端目标项；沿用 `resource_path_continuity`。
- 不改变桩基任务粒度、工期、工艺前后置、资源兼容和硬里程碑定义。
- 不允许远距离候选弧作为硬里程碑兜底。
- 不引入新依赖和大范围重构。
- 未经用户确认 `tasks.md` 与 `$speckit-analyze` 结果前不进入实现。

**规模/范围**：
- 后端：`backend/app/solver.py`、`backend/app/models.py`（仅当诊断契约需要扩展）、`backend/app/scenario.py`（仅确认主流程复用口径）。
- 测试：`backend/tests/test_scheduler.py`。
- 前端：`frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx`（仅当需要展示新增诊断）。
- 文档与验证：本规格目录下的 `research.md`、`data-model.md`、`contracts/`、`quickstart.md`、`tasks.md`。

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- [x] 已完成需求评审，用户确认继续执行。
- [x] `spec.md` 已引用来源文档、Demo 事实和代码事实。
- [x] 排程、资源、CP-SAT、目标函数、诊断和失败语义影响已明确。
- [x] 输入、输出、硬约束、软目标、边界场景和验收标准可测试。
- [x] 未把 Demo 临时限制提升为额外产品目标。
- [x] Spec Kit 过程文档使用中文简体；代码标识符和文件路径保留原文。

## 项目结构

### 本功能文档

```text
specs/017-stage1-route-continuity/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── stage1-route-continuity-contract.md
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

**结构决策**：优先在现有求解器的钻机组两阶段精排内部调整第一阶段候选路径与诊断，不新建服务、不新增依赖、不改变外部 API 入口。前端只消费可选诊断字段，保持旧结果兼容。

## 复杂度跟踪

| 违反项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|--------------------------|
| 第一阶段新增路径候选层 | 现有粗排只做换机/洞洞跳墩惩罚，不能表达用户确认的同幅和跨幅窗口规则 | 只调整罚分不限制候选弧，仍可能为满足里程碑返回远距离跳转 |

## Phase 0：研究结论

见 [research.md](./research.md)。

## Phase 1：设计产物

- [data-model.md](./data-model.md)
- [contracts/stage1-route-continuity-contract.md](./contracts/stage1-route-continuity-contract.md)
- [quickstart.md](./quickstart.md)

## Phase 1 后 Constitution 复核

- [x] 算法输入、输出、硬约束、软目标、边界和验收样例已在设计产物中展开。
- [x] 诊断契约和兼容要求已在契约中说明。
- [x] 第一阶段窗口规则、惩罚公式和不可行处理没有冲突。
- [x] 未引入无关重构或新依赖。
## 2026-07-08 补充决策：取消常规第二阶段排程

资源连续性开启且第一阶段可行时，第一阶段 CP-SAT 已同时处理钻机组路径、里程碑、总工期、资源空闲和任务时间落位，因此自动流程直接采用第一阶段结果作为最终排程。第二阶段 `refined` 不再作为常规路径运行，仅保留既有函数和历史字段兼容。
