# 任务清单：第二阶段可见墩距路径剪枝

**输入**：`specs/013-stage2-visible-distance-pruning/`  
**测试要求**：本功能涉及排程算法剪枝规则，必须包含后端回归测试。

## Phase 1：准备

- [x] T001 复核当前机械钻路径候选弧判断位置：`backend/app/solver.py`
- [x] T002 复核当前路径剪枝测试位置：`backend/tests/test_scheduler.py`

## Phase 2：用户故事 1 - 机械钻第二阶段按可见墩距剪枝

**目标**：同幅可见墩距 `<= 2`，跨幅可见墩距 `<= 1`，中间没有候选任务时不误剪。

### 测试

- [x] T003 [P] [US1] 更新全量左右幅 1#-6# 的机械钻路径候选弧测试：`backend/tests/test_scheduler.py`
- [x] T004 [P] [US1] 新增只有 1# 和 4# 候选任务仍可建边的测试：`backend/tests/test_scheduler.py`

### 实现

- [x] T005 [US1] 在 `backend/app/solver.py` 增加跨幅窗口诊断常量和元数据
- [x] T006 [US1] 在 `backend/app/solver.py` 将候选距离改为基于可见候选节点集合计算
- [x] T007 [US1] 在 `backend/app/solver.py` 将同幅窗口设为 2、跨幅窗口设为 1，并保留无出入边兜底补边

## Phase 3：收尾验证

- [x] T008 运行聚焦测试：`backend/tests/test_scheduler.py -k "sparse_arcs or visible_support_distance"`
- [x] T009 运行后端排程回归：`backend/tests/test_scheduler.py`
- [x] T010 复核任务清单和剩余风险：`specs/013-stage2-visible-distance-pruning/tasks.md`

## 依赖与执行顺序

- T001-T002 已完成后进入实现。
- T003-T004 可并行准备，但实现前后均需确保断言表达用户规则。
- T005-T007 顺序执行。
- T008-T010 收尾。
