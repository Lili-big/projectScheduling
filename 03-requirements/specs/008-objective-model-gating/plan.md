# 实施计划：目标指标建模门控

> 当前实现校正（2026-07-09）：`resource_path_continuity` 已从当前目标项体系中移除；旧输入字段仅作为废弃兼容字段被忽略。当前目标项为 `control_node_late`、`makespan_and_soft_milestone`、`resource_idle`。第一阶段路径连续性、无窗口候选路径和资源路径罚分均为历史设计，不再建路径 circuit 或产生路径罚分；机械钻组聚合、组内升序和同组同资源保留为基础规则。

**分支/目录**：`008-objective-model-gating` | **日期**：2026-07-06 | **规格**：`specs/008-objective-model-gating/spec.md`

**说明**：本计划停留在 Spec Kit 门禁阶段。用户确认 `tasks.md` 和分析结果后，才进入代码实现。

## 概要

本功能让目标函数配置真正控制 CP-SAT 精排建模范围：目标项未启用时，不再构建该目标专属的优化变量、约束、罚分项和已评价诊断；目标项启用时保持原有优化效果。硬约束不受影响，默认目标配置保持兼容。

核心落点是后端精排求解器。前端目标配置控件不新增目标项，只需要在结果展示中区分未启用、未评价和已评价状态。Netlify 演示 API 保持字段兼容，不要求实现 Python CP-SAT 建模等价。

## 技术上下文

**语言/版本**：Python 3.x、TypeScript、React  
**主要依赖**：FastAPI/Pydantic、OR-Tools CP-SAT、React/Vite  
**存储**：不新增持久化存储  
**测试**：后端 `pytest`、前端 Vite 构建；新增 scheduler 回归测试覆盖建模门控  
**目标平台**：本地 FastAPI 后端、React 前端、本地 Demo  
**性能目标**：关闭目标项后，对应建模规模下降；只启用 `control_node_late` 时不再构建资源路径连续性节点和转移弧  
**约束**：不改变施工硬约束、资源降级算法、目标项 ID、资源成本求解主目标，不引入新依赖

## Constitution 检查

- **Requirements First**：已在 `spec.md` 明确用户目标、范围、不在范围、假设和验收标准，通过。
- **Explicit Algorithm Specifications**：已明确输入、输出、硬约束、软目标、门控规则、共享支持数据和最佳努力例外，通过。
- **Explicit Frontend-Backend Contracts**：计划生成结果契约，覆盖 `objective_terms_used`、目标状态和诊断字段，通过。
- **Reuse Existing Docs and Code**：复用 `backend/app/models.py`、`backend/app/solver.py`、`frontend/src/app/App.tsx` 和现有测试结构，通过。
- **Spec Kit Gate Before Implementation**：当前仅生成规格、计划、任务和分析，等待用户确认后实现，通过。

## 项目结构

```text
specs/008-objective-model-gating/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── objective-model-gating-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

源码影响范围：

```text
backend/app/models.py
backend/app/solver.py
backend/app/scenario.py
backend/tests/test_scheduler.py
frontend/src/types/scheduler.ts
frontend/src/app/App.tsx
```

**结构决策**：不新增独立模块。目标门控由后端归一化后的有效权重驱动，精排建模在 `solver.py` 内按目标项拆分。前端只消费后端结果，不复制求解目标逻辑。

## Phase 0：研究输出

研究结论写入 `research.md`，覆盖：

- 以有效权重作为唯一门控来源
- 将资源组织类目标拆成独立建模分支
- 被关闭指标使用未启用或未评价状态
- 共享支持数据只服务于启用目标
- 最佳努力目标放松作为独立例外

## Phase 1：设计输出

- `data-model.md`：定义目标建模门控、目标支持数据、目标评价状态、目标拆解结果和最佳努力放松诊断。
- `contracts/objective-model-gating-contract.md`：说明请求字段不变、结果诊断字段和前端展示兼容。
- `quickstart.md`：说明导入 Excel 案例、目标项开关验证、后端测试和前端构建验证。

## Phase 1 复核

- 设计仍限定在现有后端求解器、结果字典和前端展示范围内，无新依赖。
- 契约保持向后兼容，默认配置不改变既有行为。
- 测试覆盖只启用 `control_node_late`、默认配置、单个资源目标关闭和全部资源目标关闭。
- 未发现 Constitution 违反项。

## 复杂度跟踪

无需要豁免的复杂度项。当前复杂度来自现有 CP-SAT 模型拆分，本计划通过门控降低关闭项建模规模，不引入新架构。
