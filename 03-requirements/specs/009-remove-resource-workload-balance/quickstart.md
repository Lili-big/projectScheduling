# 快速验证：移除同类资源工作量均衡目标

## 前置条件

- 已完成 009 任务实现。
- 本地依赖已安装。
- 不需要修改 `.specify/feature.json`。

## 验证 1：后端目标项集合

运行：

```powershell
python -m pytest backend/tests/test_scheduler.py -q
```

期望：

- 默认 `ScheduleStrategyConfig.objective_terms` 不包含 `resource_workload_balance`。
- `OBJECTIVE_METRIC_DEFINITIONS` 不包含 `resource_workload_balance`。
- 旧请求带 `resource_workload_balance` 时可被过滤。
- 只启用 `resource_workload_balance` 时无法通过“至少一个目标项启用”校验。

## 验证 2：求解结果贡献

使用包含多台同类命名资源的场景求解。

期望：

- `objective_breakdown.objective_contributions[*].term_id` 不包含 `resource_workload_balance`。
- `objective_breakdown.objective_weights` 不包含 `resource_workload_balance`。
- `objective_breakdown.weighted_objective` 不包含同类资源工作量均衡贡献。
- `stats.resource_organization_analysis.resource_types` 仍可看到工作量统计。

## 验证 3：前端展示

运行：

```powershell
npm.cmd --prefix frontend run build
```

期望：

- 目标函数配置表不显示“同类资源工作量均衡”。
- 目标贡献列表不显示该项。
- 资源诊断仍能展示资源工作量原始统计。

## 验证 4：Excel 导入案例

导入用户当前 Excel 案例并执行“固定资源条件下，推算最短工期”。

期望：

- 求解请求不因旧目标项失败。
- 返回结果不含 `resource_workload_balance` 目标贡献。
- 其他目标项和资源硬约束行为保持不变。

## 本轮执行记录

- 2026-07-06：已运行 `python -m pytest backend/tests/test_scheduler.py -q`，结果为 126 passed。
- 2026-07-06：已运行 `npm.cmd --prefix frontend run build`，TypeScript 和 Vite 构建通过。
- 2026-07-06：由于本轮没有原始 Excel 文件可重新上传，Excel 导入案例未做自动复跑；需要在当前浏览器已导入场景中再次点击“固定资源条件下，推算最短工期”，确认目标贡献中不出现 `resource_workload_balance`。
