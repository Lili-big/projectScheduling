# 任务清单：实际进度日期默认赋值

**输入**：来自 `specs/039-progress-actual-date-defaults/` 的 `spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 和 `quickstart.md`

**前置条件**：已完成需求评审、规格澄清和技术设计；实施必须等待 `$speckit-analyze` 通过及用户确认。

**测试要求**：日期建议是新增业务规则，必须使用 Node 24 内置测试运行器覆盖纯函数，并运行前端生产构建和后端进度链路回归；不新增测试依赖。

## Phase 1：准备（共享基础）

**目标**：建立无新增依赖的规则测试入口，并确认现有生产与测试边界。

- [X] T001 在 `frontend/package.json` 增加仅调用 Node 24 内置运行器的 `test:progress-dates` 脚本，不修改依赖清单
- [X] T002 [P] 复核 `backend/app/services/progress_forecast.py` 的状态日期、实际日期上限、日期顺序和状态必填校验，确认本功能不需要后端生产代码改动

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立所有用户故事共用的计划日期、日期上限和会话建议来源模型。

- [X] T003 在 `frontend/src/features/planControl/progressDateDefaults.ts` 定义 `PlannedTaskDates`、`ActualDateSuggestionState`、ISO 本地日期校验及本地 `YYYY-MM-DD` 生成函数
- [X] T004 在 `frontend/src/features/planControl/progressDateDefaults.ts` 实现计划任务日期映射、`cutoff = min(statusDate, localToday)` 和无效计划日期诊断，不依赖 React 或 DOM

**检查点**：纯日期模块可由 Node 直接导入，API 和存储模型尚未发生变化。

---

## Phase 3：用户故事 1 - 状态切换时获得实际日期建议（优先级：P1）

**目标**：用户切换进行中、暂停、已完成、未开始或取消状态时，获得符合日期上限和计划日期的默认实际日期。

**独立测试**：以固定本地日期和计划日期执行状态矩阵，验证进行中/暂停只建议开始、已完成建议起止、未开始清空、取消不生成，且完成不早于开始。

### 用户故事 1 的测试

- [X] T005 [US1] 在 `frontend/tests/progressDateDefaults.test.mjs` 先增加日期上限、计划日期早晚、五种状态、只补空值和完成不早于开始的失败测试

### 用户故事 1 的实现

- [X] T006 [US1] 在 `frontend/src/features/planControl/progressDateDefaults.ts` 实现逐状态实际日期建议与清理函数，使 T005 全部通过
- [X] T007 [US1] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 用活动计划 `schedule_result_snapshot.tasks` 建立计划日期映射，并以本地日期初始化 `statusDate`
- [X] T008 [US1] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 将状态选择接入日期建议函数，同时保留现有工程量、工效、暂停和完成状态联动

**检查点**：用户故事 1 可通过 `npm.cmd run test:progress-dates` 和页面五状态切换独立验证。

---

## Phase 4：用户故事 2 - 人工事实和历史快照不被覆盖（优先级：P1）

**目标**：系统只重算未人工修改的本次会话建议，历史、人工和保存后的实际日期始终受到保护。

**独立测试**：生成建议后分别修改开始或完成日期，再改变状态日期；验证人工字段不变、未修改建议按新上限重算、历史加载和保存成功后不再自动变化。

### 用户故事 2 的测试

- [X] T009 [US2] 在 `frontend/tests/progressDateDefaults.test.mjs` 增加逐字段人工修改、主动清空、状态日期重算、从已完成切换和历史事实保护测试

### 用户故事 2 的实现

- [X] T010 [US2] 在 `frontend/src/features/planControl/progressDateDefaults.ts` 实现逐字段建议来源更新和仅重算自动建议草稿的纯函数，使 T009 全部通过
- [X] T011 [US2] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 维护按任务区分的会话建议来源，日期输入变更时取消对应自动标记，状态日期变更时仅重算仍为建议的字段
- [X] T012 [US2] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 于历史快照加载、保存成功、刷新和项目切换边界清空建议来源；保存失败时保留当前草稿与标记

**检查点**：用户故事 2 可用固定快照和状态日期独立验证，不依赖新增 API 或持久化字段。

---

## Phase 5：用户故事 3 - 核查默认值来源并安全保存（优先级：P2）

**目标**：用户可看到计划起止日期和“系统建议”来源，并继续依赖现有后端校验安全保存。

**独立测试**：任务行展示活动计划日期，自动字段显示建议标记；计划日期缺失时显示提示且不生成建议；非法人工日期保存被后端拒绝。

### 用户故事 3 的测试

- [X] T013 [P] [US3] 在 `frontend/tests/progressDateDefaults.test.mjs` 增加无效日期格式、计划完成早于开始、空状态日期和本地日期格式测试

### 用户故事 3 的实现

- [X] T014 [US3] 在 `frontend/src/features/planControl/PlanControlPanel.tsx` 于任务名称下展示计划起止日期或不可用提示，并在自动日期输入旁显示“系统建议”且不把来源写入保存请求
- [X] T015 [P] [US3] 在 `frontend/src/styles.css` 增加计划日期、建议标记和日期输入容器样式，保持现有宽表格、分页和小屏布局可用

**检查点**：三个用户故事均可独立演示；API 请求形状、历史快照和后端错误契约保持不变。

---

## Phase 6：收尾与横切验证

**目标**：完成自动化回归、真实页面验收和规格收敛证据。

- [X] T016 [P] 运行 `frontend/tests/progressDateDefaults.test.mjs` 的 `npm.cmd run test:progress-dates` 并记录状态矩阵结果到 `specs/039-progress-actual-date-defaults/quickstart.md`
- [X] T017 [P] 在 `frontend/package.json` 所在目录运行 `npm.cmd run build`，确认 TypeScript 与 Vite 生产构建通过且无新增依赖
- [X] T018 [P] 运行 `backend/tests/test_progress_forecast.py`、`backend/tests/test_plan_control_api.py` 和 `backend/tests/test_plan_control_repository.py`，确认现有日期校验、API 和历史持久化回归通过
- [X] T019 按 `specs/039-progress-actual-date-defaults/quickstart.md` 在本地页面验证状态矩阵、人工保护、状态日期重算、历史加载、保存成功/失败、筛选分页和项目切换
- [X] T020 检查 `specs/039-progress-actual-date-defaults/spec.md`、`plan.md`、`data-model.md`、`contracts/progress-actual-date-defaults-contract.md` 与实现一致，并为 `$speckit-converge` 准备收敛证据

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖，可在用户确认后开始。
- **Phase 2**：依赖 Phase 1，阻塞三个用户故事。
- **US1（Phase 3）**：依赖 Phase 2，是建议生成的 MVP。
- **US2（Phase 4）**：依赖 US1 的建议结果，但其人工保护与重算函数可独立测试。
- **US3（Phase 5）**：依赖 Phase 2；样式 T015 可与 US2 并行，页面展示 T014 在建议来源状态可用后完成。
- **Phase 6**：依赖计划实施范围内的目标故事全部完成。

### 用户故事依赖图

```text
Phase 1 → Phase 2 → US1 → US2 ─┐
                    └────→ US3 ├→ Phase 6
                               ┘
```

### 单个故事内部顺序

- 先写该故事的规则测试，再实现纯函数，再接入 React 页面。
- 页面状态联动完成后再增加来源展示和样式。
- 自动化验证通过后再做真实页面验收。

### 并行机会

- T002 可与 T001 并行。
- T013 和 T015 可在 US2 页面接入期间并行准备，因为分别修改测试和样式文件。
- T016、T017、T018 修改/运行的边界不同，可在代码稳定后并行执行。

## 并行示例

```text
任务 A：在 frontend/tests/progressDateDefaults.test.mjs 增加异常日期测试（T013）
任务 B：在 frontend/src/styles.css 增加计划日期和建议标记样式（T015）

任务 C：运行前端纯规则测试（T016）
任务 D：运行前端生产构建（T017）
任务 E：运行后端进度链路回归（T018）
```

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，交付基于计划日期和日期上限的五状态建议。
3. 运行纯规则测试并做一次页面状态矩阵验证。
4. 再实施 US2 的事实保护和 US3 的可解释展示。

### 增量交付

1. 先建立可测试的纯日期模块，避免业务规则散落在 JSX 事件中。
2. 接入状态切换后验证不破坏现有工程量联动。
3. 增加逐字段建议来源，验证人工和历史事实保护。
4. 增加计划日期与建议标记，最后执行完整回归和真实页面验收。

## 任务统计

- 总任务数：20
- 准备与基础任务：4
- US1：4
- US2：4
- US3：3
- 收尾与横切验证：5
- 明确可并行任务：7

## 备注

- 所有任务均使用严格的 `- [ ] Txxx [P?] [US?] 描述 + 精确路径` 格式。
- 本任务清单不修改后端生产逻辑、共享字段、API、存储或排程算法。
- 未经用户确认，不得开始 T001 及其后的生产代码实施。
