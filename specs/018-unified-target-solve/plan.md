# 实施计划：统一目标函数求解与资源分支重构

**分支/目录**：`018-unified-target-solve` | **日期**：2026-07-08 | **规格**：`specs/018-unified-target-solve/spec.md`

**输入**：来自 `/specs/018-unified-target-solve/spec.md` 的功能规格

**说明**：本计划停留在 Spec Kit 门禁阶段。用户确认 `tasks.md` 与 `$speckit-analyze` 结果后，才能进入实现。

## 概要

本功能把固定资源求工期、固定工期求资源和新增资源候选统一到“完整目标函数求解 + 业务目标达成判定”的口径下，不再把“精排/粗排”作为用户侧主流程标签。CP-SAT 只负责返回物理可行排程和目标函数最优/可行结果；硬里程碑晚点、固定工期超期、最大资源上限不足、限时未确认等结论由业务层基于结果指标判断。

技术处理方向：

- 将硬里程碑晚点从阻断式硬约束改为目标函数项，默认权重为 `10000000000`，并保留可解释的晚点天数和贡献明细。
- 固定资源分支先用当前默认资源运行完整目标函数；若结果未达成硬里程碑或固定工期目标，保留当前资源失败结果，并进入新增资源候选分支。
- 固定工期分支先用最大资源运行硬里程碑和固定工期窗口快速预检；最大资源快速预检不可行时直接提示资源上限不足，最大资源快速预检通过后再搜索候选资源并复排验证。
- 固定资源、固定工期、候选资源复排复用同一套目标函数求解和目标达成判定函数。
- 内部容量模型默认不作为用户侧方案实体；如实现阶段证明完整目标函数资源搜索可替代其性能/正确性作用，则删除或旁路；如仍需保留，必须在实现任务和 analyze 中说明保留证据。
- 单次用户点击求解共享 15 秒总预算，内部多个阶段从同一预算扣减，`UNKNOWN` 或超时不得被解释为无解。

## 技术上下文

**语言/版本**：Python 3.x、TypeScript、React。

**主要依赖**：FastAPI/Pydantic、OR-Tools CP-SAT、pytest、React/Vite。

**存储**：不新增持久化存储；复用现有本地场景配置、请求模型、资源池、里程碑、结果统计和前端状态。

**测试**：后端 `pytest` 覆盖目标函数、分支编排、资源候选和同结构同工艺规则；前端 TypeScript/Vite 构建覆盖结果契约和展示口径。

**目标平台**：本地 FastAPI 调度服务与 React 前端为权威行为；Netlify 演示接口如无法同步完整求解能力，必须明确降级或屏蔽冲突展示。

**项目类型**：Web 应用中的后端排程算法、前后端契约和结果展示重构。

**性能目标**：单次用户求解动作总预算 15 秒；超出预算时返回“限时内无法确认”的可解释状态，而不是无解或资源上限不足。

**约束**：

- 用户确认 `tasks.md` 与 `$speckit-analyze` 前不实施代码。
- 不新增资源池、任务、里程碑或结果解释的持久化业务实体。
- 不引入新求解依赖，不重写与本需求无关的资源、任务和前端架构。
- 同结构同工艺规则只保留当前已确认的桩基机械钻机范围：旋挖钻、冲击钻、回旋钻。
- 不把 15 秒理解为每个内部分支各 15 秒。
- 不修改 `README.md`、不提交 git，除非用户明确要求。

**规模/范围**：

- 后端：`backend/app/models.py`、`backend/app/solver.py`、`backend/app/scenario.py`、`backend/tests/test_scheduler.py`。
- 前端：`frontend/src/types/scheduler.ts`、`frontend/src/app/App.tsx`，必要时同步 API/领域派生工具。
- Netlify：仅检查演示接口是否存在冲突口径；是否修改取决于实现阶段确认的实际入口。
- 文档：实现阶段按需更新目标函数和固定资源/固定工期算法说明文档。

## Constitution 检查

*门禁：Phase 0 研究前必须通过；Phase 1 设计后再次检查。*

- 已完成需求评审并由用户确认关键口径。**PASS**：本需求明确属于排程算法、资源分支和 CP-SAT 目标函数变更，按 `AGENTS.md` 进入 Spec Kit。
- `spec.md` 已引用来源文档、Demo 事实和代码事实。**PASS**：规格中列明 `AGENTS.md`、`agent.md`、`README.md`、目标函数文档、资源配置文档、固定资源文档和当前代码事实。
- 排程、资源、工期、CP-SAT、前后端契约影响已明确。**PASS**：规格覆盖固定资源、固定工期、最大资源预检、候选资源、硬里程碑、15 秒预算和展示状态。
- 输入、输出、约束、边界场景和验收标准可测试。**PASS**：规格包含可独立测试的用户故事、边界场景和成功标准。
- 未把 Demo 临时限制提升为正式产品目标。**PASS**：本计划要求 Netlify 或演示路径必须与权威后端对齐或明确降级。
- Spec Kit 过程文档使用中文简体；代码标识符、文件路径、接口名、任务编号和必要英文缩写保持原文。**PASS**

**Phase 0 结论**：通过。无 Constitution 违反项。

**Phase 1 复核**：通过。设计产物限定在现有模型、求解器、场景编排、前端类型和结果展示内，不要求新增持久化实体或新依赖；容量模型去留被收敛为实现阶段的可验证任务，而不是新增方案实体。

## 项目结构

### 本功能文档

```text
specs/018-unified-target-solve/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── unified-target-solve-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── models.py          # 目标项权重上限、默认目标配置、共享结果模型
│   ├── solver.py          # CP-SAT 完整目标函数、目标贡献、资源候选验证
│   └── scenario.py        # 固定资源/固定工期/新增资源分支编排
└── tests/
    └── test_scheduler.py  # 算法分支、目标判定和兼容测试

frontend/
└── src/
    ├── types/scheduler.ts # 前端共享结果字段和目标达成类型
    └── app/App.tsx        # 求解入口、结果状态、失败/候选资源展示

netlify/
└── functions/             # 演示接口兼容检查，按实现阶段实际情况处理

docs/
└── 目标函数、固定资源、资源配置相关需求文档
```

**结构决策**：保持现有后端为权威求解链路，前端消费统一的目标达成字段和目标函数贡献，不在前端复制目标判定逻辑。固定资源和固定工期内部通过共享求解助手、资源范围构造、目标达成判定和结果包装函数复用，不新增独立业务实体。

## Phase 0：研究

研究结论见 [research.md](research.md)。决策覆盖目标达成判定、硬里程碑目标化、固定工期超期、最大资源硬里程碑快速预检、容量模型去留、15 秒总预算、同结构同工艺规则保留和兼容策略。

## Phase 1：设计与契约

- 数据模型：[data-model.md](data-model.md)
- 接口契约：[contracts/unified-target-solve-contract.md](contracts/unified-target-solve-contract.md)
- 验证指南：[quickstart.md](quickstart.md)

## Constitution 检查 - Post-Design

- 需求和来源事实可通过 `spec.md`、`research.md` 和本计划追溯。**PASS**
- 算法输入、输出、硬约束、目标函数、业务判定、失败态和验收样例已在 `spec.md`、`data-model.md`、契约和 `quickstart.md` 中覆盖。**PASS**
- 前后端契约影响已在 `contracts/unified-target-solve-contract.md` 明确。**PASS**
- 计划保留阶段门禁，未进入实现。**PASS**
- 计划不要求新依赖、新持久化层、README 更新、commit、push 或 deploy。**PASS**

## 复杂度跟踪

无 Constitution 违反项，不需要复杂度豁免。
