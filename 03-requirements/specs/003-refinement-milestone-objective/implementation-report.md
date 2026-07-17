# 实施记录：精排里程碑与工期目标函数调整

日期：2026-07-04

## 变更范围

- `backend/app/solver.py`
  - 精排 `solve_control_priority_schedule()` 中，已匹配硬里程碑始终加入 `event_var <= target_offset` 硬约束。
  - `control_node_late` 仅统计 `mode = "soft"` 且具备控制属性或关联控制范围的软控制节点。
  - `makespan_and_soft_milestone` 的精排目标贡献改为 `makespan * weight`。
  - `weighted_objective` 的精排工期项改为 `objective_days * objective_weights["makespan_and_soft_milestone"]`。
  - `soft_milestone_penalty` 在精排目标拆解中保留为普通软里程碑诊断字段，不参与目标贡献。
- `backend/tests/test_scheduler.py`
  - 增加硬里程碑不可满足、硬里程碑不进入控制迟延目标、软控制节点最高权重、普通软里程碑仅诊断的回归测试。
  - 将一个用于验证工艺逻辑硬约束的旧用例改为软参考里程碑，避免与硬里程碑新语义冲突。
- `frontend/src/app/App.tsx`
  - `control_node_late` 页面名称改为“软控制节点迟延”。
  - `makespan_and_soft_milestone` 页面名称改为“总工期”。
  - 里程碑结果副标题改为软节点迟延仅作为诊断展示。
- `docs/精排目标函数算法需求文档_v3.2.md`
  - 升级到 v3.2，明确硬里程碑、软控制节点、总工期和普通软里程碑诊断边界。
- `docs/固定资源满足分支详细排程算法文档_v1.2.md`
  - 升级到 v1.2，同步精排目标函数段落和总工期公式。

## 验证结果

- `python -m pytest backend/tests/test_scheduler.py`
  - 结果：107 passed。
- `python -m pytest backend/tests/test_scheduler.py -k "hard_milestone_without_explicit_flag or hard_milestone_is_not_control_lateness_objective or soft_control_lateness_uses_highest_weight or plain_soft_milestone_is_diagnostic_not_makespan_objective"`
  - 结果：4 passed。
- `npm.cmd --prefix frontend run build`
  - 结果：通过。
- 旧文案搜索：
  - 在 `docs/精排目标函数算法需求文档_v3.2.md`、`docs/固定资源满足分支详细排程算法文档_v1.2.md`、`frontend/src/app/App.tsx` 中未检出“强控节点晚点”“总工期及软节点偏差”“总工期和软里程碑”等旧目标项表述。
- `git diff --check`
  - 结果：通过；Git 仅输出现有 CRLF 归一化提示，无尾随空白错误。

## 范围边界与剩余风险

- 固定资源快排、资源建议、资源成本和最少资源分支仍保留既有软里程碑参考/成本口径，未纳入本次精排目标函数变更。
- `makespan_and_soft_milestone` 内部 ID 保留用于兼容既有配置；前端和文档只展示“总工期”业务含义。
- 本次未新增接口字段、数据库迁移或持久化配置。
