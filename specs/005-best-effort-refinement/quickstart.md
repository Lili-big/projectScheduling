# 快速验证：精排失败最佳努力方案

## 场景 1：当前资源严格精排失败，最佳努力成功

1. 准备一个当前资源容量快排可行、但强制里程碑目标明显早于可完成日期的场景。
2. 运行固定资源求解。
3. 期望结果：
   - `result.stats.schedule_source = "current_resources_best_effort_refinement"`；
   - `result.stats.best_effort_refinement.enabled = true`；
   - `relaxed_constraints` 包含强制里程碑；
   - 里程碑结果仍显示迟延；
   - 资源互斥和同结构同工序绑定不违规。

建议命令：

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q -k "best_effort"
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

## 场景 3：最佳努力仍失败，保留现有回退

1. 准备一个输入错误、资源缺失或模型无效场景。
2. 运行固定资源求解。
3. 期望结果：
   - 不伪造最佳努力精排结果；
   - 保留既有回退或错误诊断；
   - validation 中说明严格精排和最佳努力尝试的失败原因。

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

- 最佳努力来源标签显示为“最佳努力精排”；
- 精排诊断说明严格精排失败原因和放松目标；
- 里程碑迟延仍在里程碑结果表展示；
- 严格精排成功场景不出现最佳努力提示。
