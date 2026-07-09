# 实施计划：新增资源压力工期搜索

**分支/目录**：`019-pressure-resource-search` | **日期**：2026-07-08 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/019-pressure-resource-search/spec.md` 的功能规格。

## 概要

当前新增资源分支在当前资源精排未达成业务目标后，直接用原始目标工期求最少资源容量；当容量模型在简化约束下判断当前下限已经可行时，会反复返回同一组当前资源数量，无法产生可解释的新增资源候选。本功能在新增资源分支内增加“内部压力目标”搜索：根据上一轮固定资源精排超期天数逐轮压缩内部目标工期，但不早于工艺关键路径理论最短工期；一旦出现新增资源候选，再回到原始业务目标做完整精排验证，只有验证通过才展示推荐成功。

## 技术上下文

**语言/版本**：Python 3.x、TypeScript、Node.js。

**主要依赖**：FastAPI、React、OR-Tools CP-SAT、pytest、Vite。

**存储**：不新增持久化存储；资源建议诊断随 `ScheduleResult.stats` 和 `objective_breakdown` 返回。

**测试**：后端 `pytest backend/tests/test_scheduler.py`；前端如涉及展示字段，使用 `npm run build` 验证类型和构建。

**目标平台**：本地 FastAPI 后端、React 前端、现有 Netlify 演示镜像按需同步。

**项目类型**：桥梁施工排程 Web 应用，涉及后端排程算法和前端结果展示。

**性能目标**：压力搜索沿用当前新增资源分支最大轮次，避免比现有 5 轮候选验证更长；每轮必须记录停止原因，无法确认时不继续无界搜索。

**约束**：
- 不改变 `ResourcePool.quantity` 作为当前资源下限、`ResourcePool.max_quantity` 作为可增配上限的含义。
- 不改变当前资源已满足目标时 `not_needed` 的成功路径。
- 不把内部压力目标写回用户里程碑，也不作为正式业务验收目标。
- 不改变任务生成、工艺逻辑、命名资源互斥、连续梁约束或现有目标函数权重。

**规模/范围**：
- 后端：`backend/app/scenario.py` 的新增资源分支编排，必要时补充 `backend/app/solver.py` 的最少资源目标输入能力。
- 前端：资源建议摘要和诊断展示，主要在 `frontend/src/app/App.tsx`、`frontend/src/domain/scheduleDerived.ts`、`frontend/src/types/scheduler.ts`。
- 测试：`backend/tests/test_scheduler.py` 增加压力搜索、边界、验证失败和成功推荐回归用例。

## Constitution 检查

- [x] 需求已按 Spec Kit 建立 `spec.md`，并引用当前文档、Demo 和代码事实。
- [x] 算法输入、输出、硬边界、候选验证和失败口径已在规格中定义。
- [x] 前后端共享展示字段范围已限定为资源建议诊断，不引入新的持久化输入字段。
- [x] 方案复用现有新增资源分支、最少资源能力和完整精排验证，不引入新依赖。
- [x] 实施前不进入代码修改，待 `tasks.md` 和 `$speckit-analyze` 经用户确认后再实现。

## 项目结构

### 本功能文档

```text
specs/019-pressure-resource-search/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── resource-recommendation-contract.md
└── tasks.md
```

### 源码结构

```text
backend/
├── app/
│   ├── scenario.py
│   ├── solver.py
│   └── models.py
└── tests/
    └── test_scheduler.py

frontend/
└── src/
    ├── app/App.tsx
    ├── domain/scheduleDerived.ts
    └── types/scheduler.ts
```

**结构决策**：优先在现有固定资源主入口和资源建议分支中实现压力搜索；后端仍返回 `ScheduleResult` 和 `ScenarioAlternativeResult`，前端只解析已有结果对象中的新增诊断字段。

## 复杂度跟踪

| 违反项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|--------------------------|
| 无 | 不适用 | 不适用 |

## Phase 0：研究结论

见 [research.md](./research.md)。关键结论：
- 压力目标应作为内部搜索目标，不替代原始业务目标。
- 压力搜索停止条件必须同时包含关键路径边界、轮次上限、候选产生、求解未确认和上限不可行。
- 输出需要记录每轮压力搜索，避免用户看到黑盒推荐。

## Phase 1：设计产物

- [data-model.md](./data-model.md)：定义压力搜索诊断、轮次、候选资源和目标验证状态。
- [contracts/resource-recommendation-contract.md](./contracts/resource-recommendation-contract.md)：定义资源建议结果中的新增诊断字段。
- [quickstart.md](./quickstart.md)：定义回归验证和本地运行检查路径。

## Phase 1 后 Constitution 复检

- [x] 设计产物仍保持内部压力目标与原始业务目标分离。
- [x] 未新增外部服务、数据库或新依赖。
- [x] 已明确后端测试和前端构建验证。
- [x] 仍需用户确认 `tasks.md` 和 `$speckit-analyze` 后才能实现。
