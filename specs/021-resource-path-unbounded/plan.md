# 实施计划：resource_path_continuity 候选路径无窗口化

**分支/目录**：`021-resource-path-unbounded` | **日期**：2026-07-09 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/021-resource-path-unbounded/spec.md` 的功能规格。

## 概要

本功能对机械钻机组和 `resource_path_continuity` 做定向优化：保留机械桩基按同结构物聚合为“钻机组节点”的能力，组内按默认升序、组间按空间位置和墩号稳定排序；移除同幅 `<= 2`、跨幅 `<= 1` 的候选路径窗口硬过滤，并移除资源顺序罚分机制。远距离同幅或跨幅转移不再被拒绝，也不再进入加权目标，只保留必要的空间合法性过滤和可解释诊断。

## 技术上下文

**语言/版本**：Python 3.11/3.12 兼容环境、TypeScript、Node.js。

**主要依赖**：FastAPI、Pydantic、OR-Tools CP-SAT、React、Vite、pytest。

**存储**：不新增持久化存储；继续使用现有 `ScenarioInput`、`ScheduleInput`、`ScheduleResult` 和结果诊断结构。

**测试**：`python -m pytest backend/tests/test_scheduler.py -k "stage1_route or mechanical_drill"`；完整回归为 `python -m pytest backend/tests/test_scheduler.py`；若前端类型或展示变更，再运行 `npm.cmd run build --prefix frontend`。

**目标平台**：本地 Python 后端主求解链路；前端仅消费兼容诊断字段时涉及。

**项目类型**：桥梁施工排程 Web 应用，核心影响后端 CP-SAT 求解器、结果诊断和测试。

**性能目标**：新增无窗口候选弧后，相关后端测试应在既有测试时间限制内完成；若 Excel 固定资源案例运行，开启 `resource_path_continuity` 后不应因窗口硬过滤返回明显劣化或窗口不可行语义。

**约束**：
- 不新增前端目标项；沿用 `resource_path_continuity`。
- 不改变机械桩基聚合规则、任务粒度、工期、工艺前后置和命名资源互斥。
- 不通过固定距离窗口、远距离兜底开关或隐藏剪枝重新限制候选弧。
- 不引入新依赖和大范围重构。
- 用户确认 `tasks.md` 与 `$speckit-analyze` 结果前不进入实现。

**规模/范围**：
- 后端：`backend/app/solver.py`。
- 测试：`backend/tests/test_scheduler.py`。
- 前端：`frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx` 仅在新增可选诊断字段需要展示或类型对齐时涉及。
- 文档与验证：本规格目录下的 `research.md`、`data-model.md`、`contracts/`、`quickstart.md`、`tasks.md`。

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- [x] 本变更为用户明确提出的算法目标项优化，已进入 Spec Kit。
- [x] `spec.md` 已引用来源文档、Demo/代码事实和旧规格。
- [x] 排程、资源、CP-SAT、目标函数、诊断和失败语义影响已明确。
- [x] 输入、输出、硬过滤、无顺序罚分目标、边界场景和验收标准可测试。
- [x] 未把 Demo 临时限制提升为额外产品目标。
- [x] Spec Kit 过程文档使用中文简体；代码标识符和文件路径保留原文。

## 项目结构

### 本功能文档

```text
specs/021-resource-path-unbounded/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── resource-path-unbounded-contract.md
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
    ├── app/
    │   └── App.tsx
    └── types/
        └── scheduler.ts
```

**结构决策**：优先在现有 `backend/app/solver.py` 的机械钻机组第一阶段路径逻辑中调整候选生成、组排序和顺序罚分归零。除非诊断字段需要前端类型或展示补齐，否则不触碰前端。旧 `017-stage1-route-continuity` 作为历史规格来源，本次新规格覆盖其“窗口外不生成候选弧”“窗口不可行”和“资源顺序罚分”语义。

## 复杂度跟踪

| 违反项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|--------------------------|
| 第一阶段候选弧从窗口内扩展为同范围全有序对 | 用户明确要求移除候选路径窗口约束，且当前固定资源结果受窗口硬过滤影响 | 仅调低目标权重或放宽窗口仍会把部分可行路径排除在模型外，不能满足“移除约束” |
| 移除资源顺序罚分 | 用户明确要求 `resource_path_continuity` 不再对资源顺序罚分 | 保留低权重罚分仍会影响目标函数，不能满足“移除罚分机制” |

## Phase 0：研究结论

见 [research.md](./research.md)。

## Phase 1：设计产物

- [data-model.md](./data-model.md)
- [contracts/resource-path-unbounded-contract.md](./contracts/resource-path-unbounded-contract.md)
- [quickstart.md](./quickstart.md)

## Phase 1 后 Constitution 复核

- [x] 算法输入、输出、硬过滤保留范围、顺序罚分归零、边界和验收样例已在设计产物中展开。
- [x] 诊断契约和兼容要求已在契约中说明。
- [x] 不再存在“窗口外候选弧不可进入模型”和“窗口不可行”的目标语义。
- [x] 未引入无关重构或新依赖。
