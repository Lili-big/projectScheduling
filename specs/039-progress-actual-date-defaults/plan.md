# 实施计划：实际进度日期默认赋值

**分支/目录**：`039-progress-actual-date-defaults` | **日期**：2026-07-14 | **规格**：[spec.md](./spec.md)

**输入**：来自 `specs/039-progress-actual-date-defaults/spec.md` 的功能规格，以及用户确认的日期上限、状态映射和人工事实保护口径。

## 概要

本功能在“进度反馈与预测”页面为实际日期提供保存前建议值。页面以活动计划版本的 `schedule_result_snapshot.tasks[].start_date/finish_date` 为计划日期来源，以 `min(状态日期, 系统当前本地日期)` 为日期上限；进行中和暂停只建议实际开始，已完成同时建议实际开始和实际完成，未开始清空实际日期，取消不新增建议。

实现采用前端纯日期规则函数和会话级建议来源标记。只对空字段赋值，用户修改后立即取消对应字段的“自动建议”资格；状态日期变化时只重算仍未人工修改的建议草稿。加载历史快照、保存成功或切换项目时清空建议来源标记，使后端返回值始终按已确认事实处理。页面在任务名称下展示计划起止日期，并在自动建议日期旁显示“系统建议”。

不修改 `ProgressEntry`、保存接口、持久化格式、后端归一化、滚动预测或 CP-SAT。后端现有状态日期、实际日期上限、日期顺序和状态必填校验继续作为权威边界。

## 技术上下文

**语言/版本**：Python 3.14.3；TypeScript 5.7；Node.js 24.14.1

**主要依赖**：React 19、Vite 6、FastAPI、Pydantic；本功能不修改 OR-Tools 求解链路

**存储**：现有本地 `PlanControlStore` JSON、不可变 `PlanVersion` 和可修订 `ProgressSnapshot`；自动建议来源只存在于页面会话内，不持久化

**测试**：Node 24 内置 `node:test` 验证纯日期规则；前端 TypeScript 与 Vite 生产构建；pytest 回归现有进度保存、API 与持久化校验；本地页面联调

**目标平台**：本地 FastAPI 服务承载的 React 进度反馈页面；Netlify Demo 不包含计划管控接口，不在本次范围

**项目类型**：桥梁施工排程 Web 应用中的计划执行与进度反馈交互优化

**性能目标**：单行状态切换和状态日期重算均在浏览器内完成，不新增网络请求；约 351 个任务、每页 50 行时保持即时反馈

**约束**：不新增依赖；不新增或修改共享接口字段；不覆盖人工或历史实际日期；使用本地业务日期而非 UTC 截断日期；不修改工程量联动、预测、排程、资源、里程碑和 CP-SAT

**规模/范围**：新增一个前端纯日期辅助模块及无依赖测试，调整一个页面组件和局部样式；后端仅运行回归测试，不改生产代码

## Constitution 检查

*门禁：Phase 0 研究前与 Phase 1 设计后均已通过。*

- **Requirements First：通过。** 业务目标、用户、状态矩阵、日期公式、人工事实保护、历史兼容和验收标准已经写入 `spec.md`。
- **Explicit Algorithm Specifications：通过。** 输入、输出、日期上限、逐状态行为、空值规则、重算边界和异常日期均已明确；本功能不修改排程目标函数、硬约束或软约束。
- **Explicit Frontend-Backend Contracts：通过。** 计划日期来源、页面建议标记、保存请求不变、后端 422 校验和历史快照行为已在契约中定义。
- **Reuse Existing Docs and Code：通过。** 复用 Spec 027 的计划版本/快照、Spec 031 的进度页面与保存链路、现有 `PlanControlPanel`、`ScheduledTask` 日期和后端校验。
- **Phased Delivery：通过。** 先建立纯日期规则与测试，再接入页面草稿状态，最后完成样式、回归和真实页面验证。
- **Spec Kit Gate Before Implementation：通过。** 当前只生成设计产物；实施等待 `tasks.md`、`$speckit-analyze` 和用户确认。
- **Completion Report and Verification：通过。** `quickstart.md` 包含状态矩阵、边界日期、人工保护、历史加载、接口错误和页面验证。
- **语言与安全约束：通过。** 全部 Spec Kit 产物使用中文简体，不涉及密钥、个人数据新增或权限扩展。

## 项目结构

### 本功能文档

```text
specs/039-progress-actual-date-defaults/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── progress-actual-date-defaults-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### 源码结构（仓库根目录）

```text
frontend/
├── src/
│   ├── features/planControl/
│   │   ├── PlanControlPanel.tsx              # 状态切换、草稿来源、计划日期展示
│   │   └── progressDateDefaults.ts           # 纯日期规则、状态转换和重算
│   └── styles.css                            # 计划日期与建议标记样式
└── tests/
    └── progressDateDefaults.test.mjs         # Node 24 无依赖规则测试

backend/
├── app/services/progress_forecast.py         # 复核既有权威校验，不修改
└── tests/
    ├── test_progress_forecast.py             # 状态与日期校验回归
    ├── test_plan_control_api.py               # 请求响应与错误契约回归
    └── test_plan_control_repository.py        # 历史快照与修订回归
```

**结构决策**：纯业务日期计算从页面组件抽到同目录辅助模块，便于无 React 环境测试；页面只维护 `ProgressEntry` 与会话级 `ActualDateSuggestionState`。不新增后端模块、共享模型、API、存储字段或依赖。

## 设计阶段

### Phase 0：研究与决策

- 明确自动值是保存前建议，不是后端自动事实。
- 明确计划日期从活动计划的已求解快照读取，不能从任务工期重新推算。
- 明确日期上限使用状态日期和系统当前本地日期的较早值。
- 明确用会话级逐字段来源标记保护人工与历史日期，并在保存/加载边界清空标记。
- 明确不引入测试框架，使用 Node 24 内置运行器覆盖纯规则。

详见 [research.md](./research.md)。

### Phase 1：数据与契约设计

- `ProgressEntry`、`ProgressSnapshot`、`PlanVersion` 和保存请求字段保持不变。
- 新增仅前端内存使用的 `PlannedTaskDates` 与 `ActualDateSuggestionState`。
- 定义五种状态转换、状态日期重算、人工修改、历史加载和保存成功后的状态机。
- 定义任务行计划日期展示、建议标记、计划日期缺失提示和既有后端错误行为。

详见 [data-model.md](./data-model.md)、[contracts/progress-actual-date-defaults-contract.md](./contracts/progress-actual-date-defaults-contract.md) 与 [quickstart.md](./quickstart.md)。

### Phase 2：实施排序

1. 先实现并测试本地日期、日期上限和逐状态建议纯函数。
2. 再把计划日期映射和会话级建议来源接入 `PlanControlPanel`，处理状态切换、日期修改、状态日期重算、加载与保存边界。
3. 然后增加计划起止日期和“系统建议”提示样式。
4. 最后运行规则测试、前端生产构建、后端回归和真实页面场景验证。

## 复杂度跟踪

无 Constitution 违反项。本功能没有共享契约、持久化或求解算法改动；新增辅助模块仅用于隔离可测试的日期规则，优于继续扩大现有页面组件中的条件分支。
