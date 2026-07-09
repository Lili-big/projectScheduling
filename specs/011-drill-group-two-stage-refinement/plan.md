# 实施计划：桩基钻机墩组两阶段精排

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

**分支/目录**：`011-drill-group-two-stage-refinement` | **日期**：2026-07-07 | **规格**：`specs/011-drill-group-two-stage-refinement/spec.md`

**说明**：本计划停留在 Spec Kit 门禁阶段。用户确认 `tasks.md` 和 `$speckit-analyze` 结果后，才进入代码实现。

## 概要

本功能将当前资源路径连续性中直接对候选路径节点建立全量路径排序的方式，调整为机械钻机桩基墩组分阶段精排：第一阶段按当前项目“同结构同工艺同资源组”的口径聚合旋挖钻、冲击钻、回旋钻任务，完成墩组级资源分配、硬里程碑、工艺前后置、资源硬约束和路径连续性偏好；后续 `017-stage1-route-continuity` 已确认第一阶段可行结果直接作为常规自动流程的最终排程，第二阶段仅保留为历史兼容或显式诊断路径。最终仍展开回原任务粒度输出。

MVP 简化后，机械桩基墩组不再依赖 `same_structure_parallel_limit = 1` 触发；除人工挖孔桩外，机械桩基墩组默认由一台对应类型命名资源负责，并由求解模型显式约束。固定资源主链路不再先跑池级最短工期排序，而是直接进入第一阶段精排；若第一阶段不可行或超时，当前资源主结果保持失败语义，并尝试进入资源建议分支。池级排序只作为资源建议测算或明确标记的内部诊断辅助。

核心落点是后端求解器、固定资源编排入口和 scheduler 回归测试。前端任务展示粒度不变，只在需要时消费新增诊断字段；不新增用户可编辑目标项，不改变资源配置页面。

## 技术上下文

**语言/版本**：Python 3.x、TypeScript、React  
**主要依赖**：FastAPI/Pydantic、OR-Tools CP-SAT、React/Vite  
**存储**：不新增持久化存储；内部墩组和两阶段诊断仅随单次求解结果存在  
**测试**：后端 `pytest`，重点覆盖 `backend/tests/test_scheduler.py`；必要时运行前端 Vite 构建做类型兼容验证  
**目标平台**：本地 FastAPI 后端、React 前端、本地 Demo；云端 Docker 后端沿用同一 Python 求解逻辑  
**项目类型**：桥梁施工排程 Web 应用的后端算法改造，附带结果诊断兼容  
**性能目标**：在不少于 30 个机械钻机墩组、3 台同类桩机的验证场景中，第一阶段路径候选弧受窗口约束，不再全量连接所有候选路径节点；资源路径连续性关闭时路径节点和转移弧为 0 或未评价
**约束**：不改变最终 `ScheduleResult.tasks` 粒度；不聚合人工挖孔；不放松工艺前后置、资源互斥、资源数量和硬里程碑；机械桩基组内单资源规则不再依赖 `same_structure_parallel_limit`；常规自动流程不再运行第二阶段 `refined` 排程；不引入新依赖
**规模/范围**：影响固定资源命名资源精排、固定资源主流程编排、最少资源候选精排复用的命名资源精排、最佳努力精排、连续性目标诊断和 scheduler 测试；前端仅做兼容检查或轻量展示补充

## Constitution 检查

- **Requirements First**：已在 `spec.md` 明确业务目标、范围边界、不在范围、假设、用户故事和验收标准，通过。
- **Explicit Algorithm Specifications**：已定义参与输入、最终输出、硬约束、软目标、两阶段优先级、回退路径和验收样例，通过。
- **Explicit Frontend-Backend Contracts**：本计划生成结果契约，说明请求字段不变、最终任务粒度不变、新增诊断字段兼容输出，通过。
- **Reuse Existing Docs and Code**：计划复用 `backend/app/models.py`、`backend/app/scenario.py`、`backend/app/solver.py`、`backend/tests/test_scheduler.py`、`frontend/src/types/scheduler.ts` 和既有目标门控逻辑，通过。
- **Phased Delivery**：P1 先交付可独立验证的“降低路径建模规模且展开回原任务”，P2 再增加跳墩偏好，P3 完善诊断和兼容，通过。
- **Spec Kit Gate Before Implementation**：当前仅生成规格、计划、任务和分析，等待用户确认后实现，通过。

## 项目结构

```text
specs/011-drill-group-two-stage-refinement/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── two-stage-refinement-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

源码影响范围：

```text
backend/app/models.py
backend/app/scenario.py
backend/app/solver.py
backend/tests/test_scheduler.py
frontend/src/types/scheduler.ts
frontend/src/app/App.tsx
```

**结构决策**：不新增外部服务或持久化模块。机械钻机墩组作为求解器内部数据结构优先放在 `solver.py` 附近，必要时使用轻量内部数据类；若诊断字段需要类型化，再同步 `models.py` 和前端类型。`scenario.py` 只负责调用精排和保留结果来源语义，不复制聚合算法。

## Phase 0：研究输出

研究结论写入 `research.md`，覆盖：

- 聚合层只作为求解内部层，不改变任务生成和对外任务粒度
- 聚合 key 沿用当前同结构同工艺资源规则
- 粗排不建全量路径环路，使用资源分配和轻量跳墩偏好
- 第二阶段固定粗排资源分配的方案已保留为历史兼容；当前常规自动流程以第一阶段最终排程为准
- 硬里程碑采用保守组完成口径
- 资源路径连续性目标关闭时跳过路径建模
- 第一阶段可行时返回 `stage1_final`；第二阶段失败回退仅用于历史兼容或显式诊断路径
- MVP 简化：移除 `same_structure_parallel_limit = 1` 聚合门槛，显式约束机械桩基组内同一资源，人工挖孔保持多资源并行
- MVP 简化：固定资源主链路直接进入第一阶段精排；第一阶段失败即返回当前资源失败并尝试资源建议，池级排序只作为资源建议或内部诊断辅助

## Phase 1：设计输出

- `data-model.md`：定义原任务、机械钻机墩组、线路序列、第一阶段结果、历史细排结果、展开结果和诊断字段。
- `contracts/two-stage-refinement-contract.md`：说明请求兼容、结果任务粒度兼容、新增诊断字段和结果来源语义。
- `quickstart.md`：说明后端单元测试、混合桩基场景、路径规模验证、目标关闭验证和前端构建验证。

## Phase 1 复核

- 设计仍限定在现有后端求解和结果诊断范围内，无新依赖。
- 结果契约保持向后兼容，前端不会收到虚拟墩组任务。
- 测试覆盖 P1 降规模、P2 跳墩偏好、P3 展开兼容、`stage1_final` 和历史字段兼容。
- 未发现 Constitution 违反项。
- 本次 MVP 简化属于同一功能的规则收敛，需要补充任务和分析后再进入实现。

## 复杂度跟踪

无需要豁免的复杂度项。当前复杂度来自算法本身的两阶段求解，但它直接服务于降低 `AddCircuit` 建模规模，并复用现有排程模型、资源池配置和测试结构。
