# 任务：精排失败最佳努力方案

**输入**：`specs/005-best-effort-refinement/` 下的规格、计划、研究、数据模型和契约

**前置条件**：用户确认 `spec.md`、`plan.md`、`tasks.md` 和分析结论后，才能进入实现

**当前实现校正（2026-07-08）**：阶段 3 的当前资源最佳努力分支已被后续 `011` 和 `018` 替代。当前固定资源主链路返回 `current_resources_control_priority_balanced`、`current_resources_target_failed`、`target_unconfirmed` 或 `physical_infeasible`，不再要求实现或验证 `current_resources_best_effort_refinement`。阶段 4 的最少资源候选 `minimum_resources_best_effort_refinement` 仍是当前有效任务口径。

## 阶段 1：准备

- [X] T001 阅读并标注当前严格精排和回退路径：`backend/app/scenario.py`、`backend/app/solver.py`
- [X] T002 阅读当前前端来源标签和精排诊断展示：`frontend/src/app/App.tsx`

## 阶段 2：基础能力

- [X] T003 在 `backend/app/scenario.py` 定义最佳努力来源、performance path 和元数据组装辅助逻辑
- [X] T004 在 `backend/app/solver.py` 为命名资源精排增加“目标放松”求解入口或参数，继续复用既有物理硬约束
- [X] T005 在 `backend/app/solver.py` 输出放松强制里程碑和固定工期的迟延项、目标分值和求解状态

## 阶段 3：用户故事 1 - 固定资源最佳努力精排（历史任务，已替代）

- [X] T006 [US1] 历史任务：曾要求严格精排失败后返回 `current_resources_best_effort_refinement`；当前应由后续测试覆盖 `current_resources_target_failed`
- [X] T007 [US1] 在 `backend/tests/` 增加严格精排成功时不得触发最佳努力分支的回归测试
- [X] T008 [US1] 在 `backend/tests/` 增加最佳努力结果仍遵守资源互斥和同结构同工序绑定的测试
- [X] T009 [US1] 历史任务：当前固定资源链路已改为直接目标函数排程，不再接入当前资源最佳努力精排尝试
- [X] T010 [US1] 历史任务：当前固定资源目标失败不再保留容量快排作为主展示回退
- [X] T011 [US1] 运行后端聚焦测试，确认固定资源最佳努力和既有回归通过

## 阶段 4：用户故事 2 - 最少资源候选最佳努力精排（P2）

- [X] T012 [US2] 在 `backend/tests/` 增加最少资源候选严格精排失败后返回 `minimum_resources_best_effort_refinement` 的测试
- [X] T013 [US2] 在 `backend/tests/` 增加候选严格精排成功时继续返回 `minimum_resources_control_priority_balanced` 的回归测试
- [X] T014 [US2] 在 `backend/app/scenario.py` 的最少资源候选二次精排中接入最佳努力尝试
- [X] T015 [US2] 在 `backend/app/scenario.py` 保留最佳努力失败时的已验证候选回退，并补充诊断
- [X] T016 [US2] 运行最少资源相关后端聚焦测试

## 阶段 5：用户故事 3 - 前端展示与接口口径（P2）

- [X] T017 [US3] 在 `frontend/src/app/App.tsx` 新增最佳努力来源标签和候选方案标题
- [X] T018 [US3] 在 `frontend/src/app/App.tsx` 扩展精排诊断摘要，显示严格精排状态、放松目标和目标迟延
- [X] T019 [US3] 如前端类型需要，更新 `frontend/src/types/` 中的结果元数据类型
- [X] T020 [US3] 构建前端并手工复核最佳努力标签、里程碑迟延和严格成功场景

## 阶段 6：文档与收尾

- [X] T021 历史任务：固定资源当前资源最佳努力分支说明已被后续统一目标达成文档替代
- [X] T022 更新精排目标函数算法文档，说明最少资源候选最佳努力分支中的目标放松诊断口径
- [X] T023 运行后端完整相关测试和前端构建，记录验证命令与结果
- [X] T024 执行 `$speckit-converge`，确认规格、实现、测试和文档一致
