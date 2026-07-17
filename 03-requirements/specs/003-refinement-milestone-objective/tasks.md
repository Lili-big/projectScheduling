# 任务清单：精排里程碑与工期目标函数调整

**输入**：来自 `/specs/003-refinement-milestone-objective/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/refinement-objective-contract.md`、`quickstart.md`

**测试要求**：本功能涉及 CP-SAT 精排约束、目标函数、前端目标配置和算法文档，必须包含后端测试、前端构建和文档静态检查。

## Phase 1：准备（共享基础）

**目标**：确认当前目标函数、里程碑处理和文案位置，避免覆盖无关改动。

- [X] T001 检查当前工作区状态并记录本功能只允许触碰的文件范围：`backend/app/solver.py`、`backend/tests/test_scheduler.py`、`frontend/src/app/App.tsx`、`docs/精排目标函数算法需求文档_v3.1.md -> docs/精排目标函数算法需求文档_v3.2.md`、`docs/固定资源满足分支详细排程算法文档_v1.1.md -> docs/固定资源满足分支详细排程算法文档_v1.2.md`
- [X] T002 [P] 复核精排目标函数组装、里程碑变量和目标拆解字段位置：`backend/app/solver.py`
- [X] T003 [P] 复核前端目标项定义和里程碑结果副标题位置：`frontend/src/app/App.tsx`
- [X] T004 [P] 复核当前两份算法文档中的旧口径位置：`docs/精排目标函数算法需求文档_v3.1.md`、`docs/固定资源满足分支详细排程算法文档_v1.1.md`，并确认目标版本路径 `docs/精排目标函数算法需求文档_v3.2.md`、`docs/固定资源满足分支详细排程算法文档_v1.2.md`

---

## Phase 2：基础测试（阻塞前置）

**目标**：先用可复现测试锁定新业务口径；本阶段完成前不得改目标函数实现。

- [X] T005 [P] 增加精排硬里程碑不可满足时不得返回硬节点迟延精排主方案的测试：`backend/tests/test_scheduler.py`
- [X] T006 [P] 增加精排硬里程碑可满足时 `lateness_days = 0` 且不计入控制迟延目标的测试：`backend/tests/test_scheduler.py`
- [X] T007 [P] 增加软控制节点迟延进入 `control_node_late` 和 `weighted_objective` 的测试：`backend/tests/test_scheduler.py`
- [X] T008 [P] 增加普通软里程碑迟延只保留诊断且不进入总工期目标贡献的测试：`backend/tests/test_scheduler.py`

**检查点**：测试能表达新需求，且在实现前应失败或缺失对应断言。

---

## Phase 3：用户故事 1 - 精排必须守住硬里程碑（优先级：P1）

**目标**：精排成功结果不得迟延已匹配硬里程碑。

**独立测试**：运行硬里程碑相关后端测试，确认可满足硬节点被满足，不可满足硬节点不会返回迟延精排主方案。

- [X] T009 [US1] 在精排里程碑建模中始终对已匹配硬里程碑添加必须满足约束：`backend/app/solver.py`
- [X] T010 [US1] 调整精排硬里程碑结果构建，确保硬里程碑不生成软迟延目标变量：`backend/app/solver.py`
- [X] T011 [US1] 确认固定资源快排和资源建议分支仍保留事后评价与参考排程口径：`backend/app/solver.py`
- [X] T012 [US1] 运行硬里程碑测试并修复断言或诊断口径不一致：`backend/tests/test_scheduler.py`

**检查点**：用户故事 1 可独立运行和验证。

---

## Phase 4：用户故事 2 - 软控制节点迟延由最高权重压低（优先级：P2）

**目标**：软控制节点进入最高权重迟延目标，硬里程碑和普通软里程碑不混入该目标。

**独立测试**：运行软控制节点相关测试，确认控制迟延目标只覆盖软控制节点。

- [X] T013 [US2] 增加或调整软控制节点判定逻辑，限定为 `mode="soft"` 且具备控制属性或关联控制范围的里程碑：`backend/app/solver.py`
- [X] T014 [US2] 调整 `control_lateness_terms`、`control_lateness_days` 和 `soft_control_lateness_penalty` 的计算对象：`backend/app/solver.py`
- [X] T015 [US2] 确认控制链缓冲和风险等待仍可使用控制目标任务，但不把硬里程碑迟延作为软目标：`backend/app/solver.py`
- [X] T016 [US2] 运行软控制节点测试并修复目标拆解断言：`backend/tests/test_scheduler.py`

**检查点**：用户故事 2 可独立运行和验证。

---

## Phase 5：用户故事 3 - 工期目标只表达总工期（优先级：P3）

**目标**：总工期目标只按项目完工跨度计算，前端和文档同步新口径。

**独立测试**：运行目标函数测试和前端构建，确认旧目标项文案不再作为当前口径出现。

- [X] T017 [US3] 将精排目标函数中的工期项从 `(makespan + sum(soft_penalty_terms)) * weight` 改为 `makespan * weight`：`backend/app/solver.py`
- [X] T018 [US3] 调整 `weighted_objective`，确保普通软里程碑迟延不进入工期目标贡献：`backend/app/solver.py`
- [X] T019 [US3] 保留 `soft_milestone_penalty` 作为结果诊断字段并更新相关断言：`backend/tests/test_scheduler.py`
- [X] T020 [US3] 将前端目标项 `control_node_late` 文案改为“软控制节点迟延”：`frontend/src/app/App.tsx`
- [X] T021 [US3] 将前端目标项 `makespan_and_soft_milestone` 文案改为“总工期”，并调整里程碑结果副标题：`frontend/src/app/App.tsx`
- [X] T022 [US3] 将精排目标函数算法文档从 `docs/精排目标函数算法需求文档_v3.1.md` 升级为 `docs/精排目标函数算法需求文档_v3.2.md` 并写清新口径
- [X] T023 [US3] 将固定资源满足分支详细排程算法文档从 `docs/固定资源满足分支详细排程算法文档_v1.1.md` 升级为 `docs/固定资源满足分支详细排程算法文档_v1.2.md` 并同步精排目标函数段落

**检查点**：用户故事 3 可独立运行和验证。

---

## Phase 6：收尾与横切事项

**目标**：完成全链路验证、格式检查和 Spec Kit 收敛准备。

- [X] T024 运行后端排程测试：`backend/tests/test_scheduler.py`
- [X] T025 运行前端构建验证：`frontend/src/app/App.tsx`
- [X] T026 运行文档和前端旧文案搜索，确认不再把旧名称作为当前目标项：`docs/`、`frontend/src/app/App.tsx`
- [X] T027 运行 `git diff --check` 并修复尾随空白或格式问题：`.`
- [X] T028 记录实现后的变更文件、核心逻辑、验证命令和剩余风险，供 `$speckit-converge` 使用：`specs/003-refinement-milestone-objective/`

---

## 依赖与执行顺序

### 阶段依赖

- **准备（Phase 1）**：无依赖，可立即开始。
- **基础测试（Phase 2）**：依赖准备阶段完成，阻塞所有实现故事。
- **US1**：依赖基础测试完成，是 MVP。
- **US2**：依赖基础测试完成，可在 US1 后实现。
- **US3**：依赖基础测试完成，可在 US1/US2 后实现。
- **收尾阶段**：依赖目标用户故事完成。

### 用户故事依赖

- **用户故事 1（P1）**：必须优先完成，确保精排硬节点语义正确。
- **用户故事 2（P2）**：可在 US1 后完成，避免硬节点和软控制节点混淆。
- **用户故事 3（P3）**：可在 US2 后完成，确保公式、前端和文档统一。

### 并行机会

- T002、T003、T004 可并行。
- T005、T006、T007、T008 可并行编写，但都在同一测试文件中，合并时需避免冲突。
- 文档升级 T022、T023 可在算法测试通过后并行执行。

---

## 并行示例：基础测试阶段

```text
Task: "增加精排硬里程碑不可满足测试：backend/tests/test_scheduler.py"
Task: "增加软控制节点迟延测试：backend/tests/test_scheduler.py"
Task: "增加普通软里程碑不进入总工期目标测试：backend/tests/test_scheduler.py"
```

---

## 实施策略

### MVP 优先（用户故事 1）

1. 完成准备和基础测试。
2. 实现精排硬里程碑硬约束。
3. 验证可满足和不可满足硬里程碑场景。
4. 确认固定资源快排行为未改变。

### 增量交付

1. 完成 US1，确保硬节点不可权重折中。
2. 完成 US2，收口软控制节点迟延。
3. 完成 US3，同步总工期目标、前端文案和算法文档。
4. 运行全量指定验证并准备 converge。
