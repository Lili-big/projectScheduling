# 任务清单：普通工程差异化均衡目标

**输入**：来自 `/specs/004-normal-work-balance/` 的设计文档

**前置条件**：`plan.md`、`spec.md`、`research.md`、`data-model.md`、`contracts/normal-work-balance-contract.md`、`quickstart.md`

**测试要求**：本变更涉及排程算法、CP-SAT 目标函数和结果诊断，必须包含后端可复现测试；前端如解析新增字段，需运行构建验证。

## Phase 1：准备（共享基础）

**目标**：确认当前目标函数和普通工程处理边界。

- [x] T001 阅读并确认 `specs/004-normal-work-balance/spec.md`、`plan.md`、`research.md` 的范围和优先级
- [x] T002 检查当前工作区中 `backend/app/solver.py`、`backend/app/models.py`、`frontend/src/app/App.tsx`、`frontend/src/types/scheduler.ts` 和 `docs/` 的既有未提交改动，避免覆盖无关修改
- [x] T003 确认 `docs/精排目标函数算法需求文档_v3.6.md` 当前头部版本与文件名不一致问题，并在文档更新任务中统一升版

---

## Phase 2：基础能力（阻塞前置）

**目标**：建立普通工程资源分类和均衡目标的共享口径。

- [x] T004 在 `backend/app/solver.py` 增加普通工程资源分类 helper，区分已配置受限资源普通工程和未配置受限资源普通工程
- [x] T005 在 `backend/app/solver.py` 增加未配置资源普通工程均衡目标构建逻辑，按周/月统计桶计算工作量偏差
- [x] T006 在 `backend/app/solver.py` 将未配置资源普通工程均衡目标以固定低优先级加入 `solve_control_priority_schedule()` 的加权目标
- [x] T007 在 `backend/app/solver.py` 扩展 `objective_breakdown` 和 `stats.normal_balance_metrics`，输出参与任务数、桶分布、罚分、权重和评分

**检查点**：后端可以区分任务类型并输出新诊断字段。

---

## Phase 3：用户故事 1 - 已配置资源普通工程优先连续施工（优先级：P1）

**目标**：确保配置了受限资源的普通工程不被普通工程均衡目标打散。

**独立测试**：构造启用受限资源的普通工程场景，验证其不进入未配置资源普通工程均衡罚分，仍参与资源空闲和路径连续目标。

### 用户故事 1 的测试

- [x] T008 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加已配置资源普通工程不计入未配置资源均衡的测试
- [x] T009 [P] [US1] 在 `backend/tests/test_scheduler.py` 增加已配置资源普通工程仍可产生资源空闲或路径连续目标贡献的测试

### 用户故事 1 的实现

- [x] T010 [US1] 调整 `backend/app/solver.py` 中未配置资源均衡参与范围，排除存在启用受限资源候选的普通工程
- [x] T011 [US1] 调整 `backend/app/solver.py` 中普通工程分布诊断文案或字段，避免误称全部普通工程均衡

**检查点**：用户故事 1 可独立运行和验证。

---

## Phase 4：用户故事 2 - 未配置资源普通工程避免集中施工（优先级：P1）

**目标**：让资源默认充足的普通工程在不影响关键路径时均匀展开。

**独立测试**：构造无启用受限资源候选的普通工程场景，验证集中施工方案比均匀展开方案产生更高罚分。

### 用户故事 2 的测试

- [x] T012 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加未配置资源普通工程计入均衡罚分和桶诊断的测试
- [x] T013 [P] [US2] 在 `backend/tests/test_scheduler.py` 增加未配置资源普通工程均衡不牺牲控制链或硬约束的测试

### 用户故事 2 的实现

- [x] T014 [US2] 在 `backend/app/solver.py` 完成统计桶实际工作量、理想工作量和偏差汇总计算
- [x] T015 [US2] 在 `backend/app/solver.py` 将新罚分纳入 `weighted_objective` 解释性汇总，并保持低优先级
- [x] T016 [US2] 在 `backend/app/solver.py` 处理少于 2 个参与任务、无统计桶、零工期等边界

**检查点**：用户故事 2 可独立运行和验证。

---

## Phase 5：用户故事 3 - 文档和诊断准确解释新口径（优先级：P2）

**目标**：让目标函数文档、结果拆解和前端诊断与新算法一致。

**独立测试**：阅读文档和运行前端构建，确认不存在旧口径误导，新增字段不会破坏页面。

### 用户故事 3 的实现

- [x] T017 [P] [US3] 更新 `frontend/src/types/scheduler.ts` 中普通工程分布诊断相关类型
- [x] T018 [US3] 按需更新 `frontend/src/app/App.tsx` 中普通工程诊断解析和展示文案，使用“未配置资源普通工程均衡”
- [x] T019 [P] [US3] 新建或更新 `docs/精排目标函数算法需求文档_v3.8.md`，用产品视角说明“有资源看连续、没资源看均衡”的计算步骤和案例
- [x] T020 [P] [US3] 新建或更新 `docs/固定资源满足分支详细排程算法文档_v1.5.md`，同步精排目标函数和输出字段

**检查点**：用户故事 3 可独立运行和验证。

---

## Phase 6：收尾与横切事项

**目标**：完成验证、兼容和交付说明。

- [x] T021 运行 `.\.venv\Scripts\python.exe -m pytest backend\tests\test_scheduler.py -q`
- [x] T022 运行 `npm.cmd --prefix frontend run build`
- [x] T023 检查 `objective_terms_used`、`objective_weights` 不恢复废弃 `normal_balance` 可配置项
- [x] T024 检查 `docs/` 中文档文件名版本、头部版本和最终报告版本一致
- [x] T025 记录实现说明、验证结果和未覆盖风险

---

## 依赖与执行顺序

### 阶段依赖

- **Phase 1**：无依赖。
- **Phase 2**：依赖 Phase 1，阻塞所有用户故事。
- **Phase 3 与 Phase 4**：均依赖 Phase 2；两个 P1 故事可按测试文件冲突情况顺序推进。
- **Phase 5**：依赖后端输出字段稳定。
- **Phase 6**：依赖目标用户故事完成。

### 并行机会

- T008、T009 可并行设计测试。
- T012、T013 可并行设计测试。
- T017、T019、T020 涉及不同文件，可并行。

## 实施策略

### MVP 优先

1. 完成 Phase 1 和 Phase 2。
2. 完成 US1 与 US2 的后端测试和实现。
3. 运行后端 scheduler 测试确认目标函数行为。
4. 再进入文档和前端诊断文案同步。

### 增量交付

1. 先保证已配置资源普通工程不进入新均衡罚分。
2. 再保证未配置资源普通工程产生可解释的均衡罚分。
3. 最后同步前端解析和算法文档。
