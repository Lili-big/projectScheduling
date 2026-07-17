# 实施计划：实际进度工程量一致性

**分支/目录**：`031-progress-quantity-consistency` | **日期**：2026-07-13 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/031-progress-quantity-consistency/spec.md` 的功能规格，以及用户确认的总工程量、实际完成比例、实际已完工程量和剩余工程量四列口径。

## 概要

本功能在“实际进度反馈”中增加只读总工程量，并把当前可以独立填写的完成比例、已完工程量和剩余工程量收敛为一个一致的数据闭环。活动执行计划任务中的 `quantity` 和 `quantity_label` 继续作为总工程量及展示口径；页面允许用户编辑实际完成比例或实际已完工程量，立即同步其他数值；后端保存前再次校验并归一，保证滚动预测只使用一致的剩余工程量。

不为 `ProgressEntry` 重复增加总工程量字段，不新增接口、存储版本或迁移。历史快照继续按原值只读加载，缺失值只在页面派生展示；用户主动更正时沿用现有修订和审计机制。未开始、已完成、暂停和取消状态在现有状态规则上补齐工程量归一化，不修改未来排程求解、资源策略或里程碑逻辑。

## 技术上下文

**语言/版本**：Python 3.14.3；TypeScript 5.7；Node.js 24.14.1

**主要依赖**：FastAPI、Pydantic、React 19、Vite 6；滚动预测继续复用现有 OR-Tools 求解链路，本功能不修改求解模型

**存储**：现有本地 `PlanControlStore` JSON、不可变 `PlanVersion` 快照和可修订 `ProgressSnapshot`；不新增数据库、schema 版本或迁移

**测试**：pytest 覆盖进度归一化、状态矩阵、历史兼容、审计和预测失效；TypeScript 与 Vite 生产构建；本地 FastAPI 页面联调

**目标平台**：本地 FastAPI 服务和 React 进度反馈页面；Netlify Demo 当前不实现计划管控接口，不在本次镜像范围

**项目类型**：桥梁施工排程 Web 应用中的计划执行、进度反馈和滚动预测模块改造

**性能目标**：单行编辑在当前页面内即时完成，不新增网络请求；当前约 351 个任务、每页 50 行规模下保存与刷新保持现有用户可感知响应级别

**约束**：不新增依赖；不复制总工程量到进度快照；不解析结构物参数或旧混合工程量文本参与计算；不修改计划任务工程量、工期、资源、里程碑、CP-SAT 目标和调整策略；不重写历史快照

**规模/范围**：影响进度页面一个表格、一个进度保存服务、现有进度模型语义和三组后端测试边界；共享字段形状和 API 路径保持不变

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已通过。*

- **Requirements First：通过。** 用户目标、当前缺口、MVP、状态规则、历史兼容和验收样例已经写入 `spec.md`。
- **Explicit Algorithm Specifications：通过。** 输入总量、比例/数量公式、归一化不变量、剩余工期使用方式、无效总量和可复现 `10m → 40% → 4m/6m → 3天` 样例均已明确；不改变求解硬约束、软约束和目标函数。
- **Explicit Frontend-Backend Contracts：通过。** 页面四列、编辑入口、同步行为、保存校验、422 错误、历史展示、修订和下游失效均在规格和接口契约中定义。
- **Reuse Existing Docs and Code：通过。** 复用 Spec 027 的计划版本、进度快照、保存接口、归一化服务、审计记录、页面组件和测试结构；复用 Spec 030 的纯工程量文本。
- **Phased Delivery：通过。** 先完成后端数据不变量和测试，再完成页面四列及同步，最后完成兼容与端到端验证。
- **Spec Kit Gate Before Implementation：通过。** 本计划只生成设计产物，实施等待 `tasks.md`、`$speckit-analyze` 和用户确认。
- **Completion Report and Verification：通过。** `quickstart.md` 包含状态矩阵、公式样例、历史兼容、接口和页面验证。
- **语言与安全约束：通过。** 产物使用中文简体，不涉及密钥、权限扩展或个人数据新增。

## 项目结构

### 本功能文档

```text
specs/031-progress-quantity-consistency/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── progress-quantity-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── models.py                              # 复核 ProgressEntry 兼容字段，不新增总量
│   └── services/
│       ├── progress_forecast.py               # 保存前归一、状态规则、剩余工期输入
│       └── plan_control_repository.py         # 复用历史快照与修订持久化
└── tests/
    ├── test_progress_forecast.py              # 公式、状态、预测和失效
    ├── test_plan_control_api.py               # 请求响应与错误契约
    └── test_plan_control_repository.py        # 历史兼容和不改写

frontend/src/
├── features/planControl/PlanControlPanel.tsx  # 四列、双入口同步、派生与提示
├── styles.css                                 # 表格宽度、只读值和单位提示
└── types/scheduler.ts                         # 静态复核现有 ProgressEntry 契约

docs/
└── 基建智能计划管控中枢整体产品方案_v1.0.md  # 如实现口径与现有描述冲突时最小同步
```

**结构决策**：不新增服务、页面组件或共享字段。后端权威校验继续放在 `progress_forecast.py` 的进度归一化边界；前端在现有 `PlanControlPanel.tsx` 中维护行级即时联动；历史加载和修订继续复用 `PlanControlRepository`。

## 设计阶段

### Phase 0：研究与决策

- 确定总工程量只引用计划版本任务，不复制到进度填报项。
- 确定比例和已完工程量都是用户入口，剩余工程量只读派生，后端拒绝不一致新请求。
- 确定状态矩阵、无效总量兼容路径、小数精度和滚动预测输入。
- 确定历史快照派生展示、数据质量提示和不改写策略。

详见 [research.md](./research.md)。

### Phase 1：数据与契约设计

- 保持 `ProgressEntry` 字段形状不变，强化 `percent_complete`、`completed_quantity`、`remaining_quantity` 的不变量。
- 将总工程量建模为 `PlanVersion.generated_snapshot.schedule_input.tasks[].quantity` 的只读引用。
- 定义 `/api/plan-control/progress-snapshots` 的归一化响应、冲突错误和历史兼容语义。
- 定义五种任务状态的工程量值、编辑性、剩余工期和预测参与规则。
- 定义页面验证、后端测试、持久化测试与完整回归步骤。

详见 [data-model.md](./data-model.md)、[contracts/progress-quantity-contract.md](./contracts/progress-quantity-contract.md) 与 [quickstart.md](./quickstart.md)。

### Phase 2：实施排序

1. 先补后端公式、状态矩阵和冲突请求测试，建立唯一数据不变量。
2. 再调整后端归一化，保证返回值和预测输入一致。
3. 然后增加页面总工程量、双入口同步、只读剩余量和历史提示。
4. 最后验证历史快照不改写、预测失效、前端构建和真实页面。

## 复杂度跟踪

无 Constitution 违反项。本功能复用现有进度模型和服务，不引入新的总量字段、接口、存储版本、依赖或模块。
