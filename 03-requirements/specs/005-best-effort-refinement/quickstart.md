# 快速验证：精排失败最佳努力方案

## 场景 1：当前资源目标未满足（当前口径）

1. 准备一个当前资源可排程、但强制里程碑目标明显早于可完成日期的场景。
2. 运行固定资源求解。
3. 期望结果：
   - `result.stats.schedule_source = "current_resources_target_failed"`；
   - `result.stats.target_achievement.business_success = false`；
   - 不依赖 `current_resources_best_effort_refinement` 或 `current_resources_capacity_shortest_fallback` 作为主结果来源；
   - 里程碑结果仍显示迟延；
   - 资源互斥和同结构同工序绑定不违规。

建议命令：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q -k "target_failed"
```

## 场景 2：严格精排成功，行为不变

1. 准备一个强制里程碑可满足的固定资源场景。
2. 运行固定资源求解。
3. 期望结果：
   - `result.stats.schedule_source = "current_resources_control_priority_balanced"`；
   - 不出现 `best_effort_refinement.enabled = true`；
   - 所有强制里程碑 `lateness_days = 0`。

建议命令：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q -k "control_priority"
```

## 场景 3：当前资源物理不可行或限时未确认

1. 准备一个输入错误、资源缺失或模型无效场景。
2. 运行固定资源求解。
3. 期望结果：
   - 不伪造最佳努力精排结果；
   - 物理不可行时返回 `physical_infeasible` 或模型错误诊断；
   - 限时未确认时返回 `target_unconfirmed`，不得提示确定无解。

## 场景 4：最少资源候选最佳努力

1. 先运行固定资源最短工期，或配置可匹配强制里程碑。
2. 运行固定工期最少资源求解，使用一个候选精排严格失败但放松固定工期可排程的场景。
3. 期望结果：
   - `result.stats.schedule_source = "minimum_resources_best_effort_refinement"`；
   - 保留推荐资源数量；
   - `fixed_duration_overrun_days` 或 `target_lateness_days` 大于 0。

## 前端验证

构建前端：

```powershell
npm.cmd --prefix frontend run build
```

手工复核：

- 当前资源目标未满足显示为“当前资源目标未满足”；
- 最少资源候选最佳努力显示目标未满足、放松目标和迟延信息；
- 里程碑迟延仍在里程碑结果表展示；
- 当前资源目标达成场景不出现最佳努力提示。
