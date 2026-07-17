# 实施计划：任务结构物参数与工程量拆分

**分支/目录**：`030-task-parameter-quantity-split` | **日期**：2026-07-13 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/030-task-parameter-quantity-split/spec.md` 的功能规格，以及用户确认的柱径术语、平均墩高和全量当前任务覆盖口径。

## 概要

本功能把结构构件及生成任务中混用的结构参数摘要和工程量展示拆开。结构化尺寸、形式、柱径、柱数、支座范围和跨径组合继续作为权威结构数据；新增可空的结构物参数摘要字段用于跨后端、前端和 Netlify Demo 一致展示；现有 `quantity` 继续作为工期计算数值，`quantity_label` 收敛为纯工程量文本。

墩柱工程量从导入链路当前的“统一墩高 × 柱数”改为平均墩高。当前只有统一 `heightM` 时直接使用该值；未来存在逐柱高度列表时对所有大于零有效高度取算术平均。该工程量继续进入现有按米或按标准节工期算法，不修改 CP-SAT 约束、目标函数或资源模型。任务视图增加“结构物参数”列，工效切换时保持参数摘要不变并重算工程量与工期。

## 技术上下文

**语言/版本**：Python 3.14.3；TypeScript 5.7；Node.js 24.14.1

**主要依赖**：FastAPI、Pydantic、React 19、Vite 6、Netlify Functions；OR-Tools 仅消费生成后的任务工期，本功能不修改求解器

**存储**：现有 `ScenarioInput` 项目结构 JSON、本地结构参数文件和计划快照；不新增数据库表、迁移或持久化服务

**测试**：pytest 覆盖桥梁导入、任务生成、工效切换、工期与兼容性；TypeScript 与 Vite 生产构建；本地 FastAPI 页面联调；Netlify Demo 作为未发布参考实现执行字段与生成逻辑的静态契约核对

**目标平台**：本地 FastAPI 服务与 React 页面；未配置发布的 Netlify Demo 参考 API 保持共享任务契约镜像一致

**项目类型**：桥梁施工排程 Web 应用，涉及共享模型、结构参数导入、任务生成、任务视图和演示 API

**性能目标**：在当前样例约 351 个任务规模下不新增网络往返或额外求解；任务视图生成与局部工效切换保持当前用户可感知响应级别

**约束**：不新增依赖；不修改资源约束、工艺逻辑、里程碑、CP-SAT 目标函数和已生成任务类型范围；历史项目和计划无迁移；结构参数摘要不得作为工期计算来源

**规模/范围**：覆盖八类当前下部任务与两类当前上部现浇任务；同步 Python 模型与生成链路、前端类型与任务表、Netlify Demo 镜像、测试和两份现有说明文档

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已通过。*

- **Requirements First：通过。** 用户目标、十类任务范围、平均墩高规则、历史兼容和验收样例已写入 `spec.md`。
- **Explicit Algorithm Specifications：通过。** 墩柱输入、有效高度过滤、算术平均公式、输出工程量、工期联动、无有效高度诊断和可复现 21 天样例均已明确；不改变硬约束、软约束和目标函数。
- **Explicit Frontend-Backend Contracts：通过。** 新字段、接口响应、任务视图列、工效切换、空态、兼容和下游失效已在契约及数据模型中定义。
- **Reuse Existing Docs and Code：通过。** 复用现有结构属性、导入器、任务生成、前端本地工效重算、Netlify 镜像和测试结构，不新增架构或依赖。
- **Phased Delivery：通过。** 先完成字段与下部任务拆分，再完成平均墩高及上部任务覆盖，最后完成兼容、镜像、文档和端到端验证。
- **Spec Kit Gate Before Implementation：通过。** 当前仅生成规划产物，实施须等待 `tasks.md`、`$speckit-analyze` 与用户确认。
- **Completion Report and Verification：通过。** `quickstart.md` 定义可复现输入、期望输出、测试命令和页面验证。
- **语言与安全约束：通过。** 全部产物使用中文简体，不读取或记录密钥。

## 项目结构

### 本功能文档

```text
specs/030-task-parameter-quantity-split/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── task-parameter-quantity-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
backend/
├── app/
│   ├── models.py                  # ComponentModel、UpperStructureComponent、Task 共享字段
│   ├── bridge_import.py           # 下部结构参数摘要与平均墩高导入
│   ├── scenario.py                # 工程量、参数摘要、上部任务和工期生成
│   └── scenario_data.py           # 默认结构构件兼容数据
└── tests/
    ├── test_bridge_import.py
    ├── test_scheduler.py
    └── test_plan_control_repository.py

frontend/src/
├── types/scheduler.ts             # 共享字段类型
└── app/App.tsx                    # 任务表拆列与本地工效重算

netlify/demo-functions/api.mts     # Demo 模型和任务生成镜像

docs/
├── 任务视图页面需求文档_v1.0.md
└── 项目排程系统整体说明_v1.1.md
```

**结构决策**：不新增服务或页面组件。结构摘要生成放在现有导入与任务生成边界，前端只做展示与历史回退；工效切换继续复用 `App.tsx` 中的本地任务重算；Netlify 在现有单文件演示 API 中同步最小契约。

## 设计阶段

### Phase 0：研究与决策

- 明确显示摘要与权威结构数据的边界，避免新增展示字符串成为计算来源。
- 确定平均墩高对当前统一高度、未来逐柱高度和历史总高度数据的兼容顺序。
- 确定十类任务的参数摘要及工程量单位映射。
- 确定 FastAPI、前端本地重算与 Netlify Demo 的一致性策略。

详见 [research.md](./research.md)。

### Phase 1：数据与契约设计

- 在三个共享实体中增加默认可空的 `structure_parameter_label`。
- 保持 `quantity` 数值和 `quantity_label` 文本字段兼容，但把新生成数据的 `quantity_label` 收敛为纯工程量。
- 通过已有 `properties` 保存原始尺寸和兼容派生信息，不增加重复的结构参数对象。
- 为 `/api/generate-schedule-input`、结构参数导入响应及 Netlify 镜像定义增量字段契约。
- 定义平均墩高、历史回退、无效数据和页面列的可运行验证步骤。

详见 [data-model.md](./data-model.md)、[contracts/task-parameter-quantity-contract.md](./contracts/task-parameter-quantity-contract.md) 与 [quickstart.md](./quickstart.md)。

### Phase 2：实施排序

1. 先同步可空共享字段和纯展示 helper，保证旧数据可加载。
2. 再修正下部结构导入和工程量标签，补齐承台、桩基、系梁、墩柱等测试。
3. 然后落实平均墩高工期规则，并验证 `10m → 3节 → 21天`。
4. 再补齐现浇箱梁与连续梁任务的结构参数上下文。
5. 最后调整任务视图、前端局部工效重算、Netlify 镜像、历史兼容与文档，并执行端到端验证。

## 复杂度跟踪

无 Constitution 违反项。本功能只扩展现有共享实体与生成链路，不新增模块、依赖、存储或迁移。
