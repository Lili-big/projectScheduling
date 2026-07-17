# 任务清单：新增资源压力工期搜索

**输入**：来自 `specs/019-pressure-resource-search/` 的设计文档。

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/resource-recommendation-contract.md`、`quickstart.md`。

**测试要求**：本功能涉及排程算法、资源模型和前后端共享诊断字段，必须包含可复现测试任务。

**组织方式**：任务按用户故事分组，确保每个故事都可独立实现和验证。

## Phase 1：准备（共享基础）

**目标**：确认当前工作区和受影响文件，避免覆盖无关改动。

- [x] T001 检查并记录当前未提交改动范围，重点确认 `backend/app/scenario.py`、`backend/tests/test_scheduler.py`、`frontend/src/app/App.tsx`、`frontend/src/domain/scheduleDerived.ts` 的既有改动不被覆盖
- [x] T002 阅读当前资源建议实现路径并标注待改位置：`backend/app/scenario.py`、`backend/app/solver.py`
- [x] T003 [P] 阅读当前前端资源建议展示和类型路径：`frontend/src/app/App.tsx`、`frontend/src/domain/scheduleDerived.ts`、`frontend/src/types/scheduler.ts`

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立压力搜索所需的共享计算和诊断结构，供所有用户故事复用。

- [x] T004 在 `backend/tests/test_scheduler.py` 添加压力搜索公共测试夹具，覆盖“当前资源精排超期、资源上限内存在更大候选”的最小场景
- [x] T005 在 `backend/app/scenario.py` 增加目标超期天数提取逻辑，支持硬里程碑最大迟延和固定工期超出两类来源
- [x] T006 在 `backend/app/scenario.py` 增加内部压力目标计算逻辑，按“原始目标工期 - 超期天数 × 轮次”生成压力目标，并支持关键路径理论最短工期边界
- [x] T007 在 `backend/app/scenario.py` 增加压力搜索轮次诊断构造逻辑，字段对齐 `contracts/resource-recommendation-contract.md`
- [x] T008 在 `backend/app/scenario.py` 增加判断候选是否真正新增资源的逻辑，要求至少一个资源池数量高于当前下限

**检查点**：基础 helper 可被单元测试覆盖，但尚未改变主流程行为。

---

## Phase 3：用户故事 1 - 超期后得到可验证的新增资源建议（优先级：P1）

**目标**：当前资源精排可用但目标未满足时，资源建议能通过压力搜索产生新增资源候选，并用原始目标验证成功后展示推荐。

**独立测试**：运行压力搜索成功场景，验证多轮压力目标中至少一轮产生 `added_quantity > 0`，候选完整精排满足原始目标，并返回 `recommended_resources_verified`。

### 用户故事 1 的测试

- [x] T009 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加“第一轮返回当前下限后继续压缩，后续轮次产生新增候选”的回归测试
- [x] T010 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加“新增资源候选通过原始目标完整精排后才推荐成功”的回归测试

### 用户故事 1 的实现

- [x] T011 [US1] 在 `backend/app/scenario.py` 将压力目标接入 `_fixed_resource_recommendation()` 的资源建议循环
- [x] T012 [US1] 在 `backend/app/scenario.py` 调整每轮 `solve_min_resources_schedule()` 输入，使其使用本轮内部压力目标而不是始终使用原始目标
- [x] T013 [US1] 在 `backend/app/scenario.py` 当容量模型返回当前下限时跳过完整精排验证并进入下一轮压力搜索
- [x] T014 [US1] 在 `backend/app/scenario.py` 当产生新增资源候选时，使用原始目标执行完整精排验证并保留现有推荐成功口径
- [x] T015 [US1] 在 `backend/app/scenario.py` 把 `pressure_search_status`、`pressure_search_stop_reason`、`pressure_search_attempts` 写入资源建议元数据

**检查点**：用户故事 1 可独立运行，解决“多轮都返回当前数量”的核心问题。

---

## Phase 4：用户故事 2 - 防止压力目标压过理论关键路径（优先级：P1）

**目标**：内部压力目标达到工艺关键路径理论最短工期后停止继续压缩，不输出误导性成功推荐。

**独立测试**：构造关键路径边界场景，验证压力目标被截断，停止原因可解释，且不产生虚假的成功推荐。

### 用户故事 2 的测试

- [x] T016 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加“压力目标不得早于关键路径理论最短工期”的回归测试
- [x] T017 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加“达到关键路径边界仍无候选时不推荐成功”的回归测试

### 用户故事 2 的实现

- [x] T018 [US2] 在 `backend/app/scenario.py` 将 `_critical_path_schedule()` 的理论最短工期结果接入压力目标下界判断
- [x] T019 [US2] 在 `backend/app/scenario.py` 增加关键路径边界停止原因和诊断字段
- [x] T020 [US2] 在 `backend/app/scenario.py` 确保关键路径不可行、未知或资源上限不可行时沿用现有失败状态且补充压力搜索未运行或停止诊断

**检查点**：用户故事 2 可独立证明系统不会把资源无法解决的问题包装成新增资源建议。

---

## Phase 5：用户故事 3 - 保留原始目标作为最终验收口径（优先级：P2）

**目标**：页面和结果摘要清楚区分内部压力目标与原始业务目标，成功推荐只依据原始目标。

**独立测试**：候选满足内部容量模型但完整精排不满足原始目标时，不显示成功推荐；前端能展示压力轮次诊断。

### 用户故事 3 的测试

- [x] T021 [P] [US3] 在 `backend/tests/test_scheduler.py` 增加“候选满足容量模型但完整精排不满足原始目标时不推荐成功”的回归测试
- [x] T022 [P] [US3] 在 `frontend/src/types/scheduler.ts` 补充压力搜索诊断类型后运行前端类型构建验证

### 用户故事 3 的实现

- [x] T023 [US3] 在 `frontend/src/types/scheduler.ts` 增加压力搜索诊断字段类型，兼容字段缺失的旧结果
- [ ] T024 [US3] 在 `frontend/src/domain/scheduleDerived.ts` 增加压力搜索诊断解析 helper，保持旧结果兼容
- [x] T025 [US3] 在 `frontend/src/app/App.tsx` 的资源建议诊断区域展示压力搜索轮次、内部压力目标和原始目标验证状态
- [x] T026 [US3] 在 `frontend/src/app/App.tsx` 确保内部压力目标不替代用户配置的里程碑目标文案

**检查点**：用户故事 3 可独立验证前端展示口径正确，且不会误导用户。

---

## Phase 6：收尾与横切事项

**目标**：完成回归验证、文档同步和门禁检查。

- [ ] T027 [P] 按需更新 `docs/排程算法当前实现交底文档_v1.0.md` 中资源建议流程说明，补充压力搜索口径
- [x] T028 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q -k "fixed_resource or min_resources or pressure_resource"` 并记录结果
- [x] T029 运行 `.\.venv\Scripts\python.exe -m py_compile backend\app\scenario.py backend\app\solver.py backend\tests\test_scheduler.py` 并记录结果
- [x] T030 如修改前端，运行 `cd frontend; npm run build` 并记录结果
- [x] T031 检查 `specs/019-pressure-resource-search/quickstart.md` 中所有验证场景是否已覆盖
- [x] T032 检查 `AGENTS.md` 和 `.specify/memory/constitution.md` 门禁是否仍满足本功能要求

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1 准备**：无依赖。
- **Phase 2 基础能力**：依赖 Phase 1。
- **US1**：依赖 Phase 2，是 MVP。
- **US2**：依赖 Phase 2，可与 US1 部分并行，但建议在 US1 主流程后合入。
- **US3**：依赖 US1 的后端诊断字段，前端类型和展示可在后端字段契约确定后进行。
- **收尾**：依赖目标用户故事完成。

### 用户故事依赖

- **US1**：核心搜索能力，必须先完成。
- **US2**：关键路径边界，可在 US1 helper 基础上实现。
- **US3**：展示和最终验收口径，依赖 US1/US2 输出字段稳定。

### 并行机会

- T002 与 T003 可并行。
- T009 与 T010 可并行。
- T016 与 T017 可并行。
- T023 与 T024 可在后端契约确定后并行。
- T027 可与最终测试前的代码清理并行，但不得提前写入未验证行为。

## 并行示例：用户故事 1

```text
Task: "T009 在 backend/tests/test_scheduler.py 增加返回当前下限后继续压缩的回归测试"
Task: "T010 在 backend/tests/test_scheduler.py 增加候选通过原始目标验证才推荐成功的回归测试"
```

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1，证明压力搜索能产生新增候选并通过原始目标验证。
3. 运行 US1 相关后端测试。
4. 再补 US2 的关键路径边界和 US3 的展示口径。

### 增量交付

1. 后端先实现压力搜索诊断字段，不破坏旧字段。
2. 前端在字段可缺失的前提下增量展示。
3. 每个用户故事完成后运行对应测试，再进入下一故事。

## 备注

- 不得在用户确认 `$speckit-analyze` 前开始执行这些实现任务。
- 任务实施时必须保护当前工作区已有未提交改动，不得重置或覆盖无关文件。

